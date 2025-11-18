from __future__ import annotations

import hashlib
import json
import re
import secrets
from typing import Any, Dict, Optional

from aiohttp import web

from payment_qa_bot.config import Config
from payment_qa_bot.models.db import OrderCreate, OrderRecord, OrdersRepository
from payment_qa_bot.services.pricing import calculate_price
from payment_qa_bot.services.security import CredentialEncryptor

PAYLOAD_MAX_LENGTH = 4096
PAYLOAD_CLEANUP_HOURS = 72
MAX_CALC_TESTS = 25
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ACTIVE_STATES = ("draft", "in_progress")

PAYOUT_CODE_MAP = {
    "N": {"surcharge": 0, "withdraw_required": False, "kyc_required": False, "text_key": "payout.option.none"},
    "W": {"surcharge": 10, "withdraw_required": True, "kyc_required": False, "text_key": "payout.option.withdraw"},
    "K": {"surcharge": 25, "withdraw_required": True, "kyc_required": True, "text_key": "payout.option.kyc"},
}


def _generate_payload_token() -> str:
    return secrets.token_urlsafe(9)


def _derive_user_id(email: str) -> int:
    digest = hashlib.sha256(email.lower().encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _compute_payload_hash(payload: Optional[str], fallback_parts: Dict[str, Any]) -> str:
    if payload:
        base = payload.strip()
    else:
        base = json.dumps(fallback_parts, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _payout_label(order: OrderRecord) -> str:
    if order.kyc_required:
        return "kyc"
    if order.withdraw_required:
        return "withdraw"
    return "none"


def serialize_order(order: OrderRecord, encryptor: CredentialEncryptor) -> Dict[str, Any]:
    return {
        "id": order.order_id,
        "userId": order.user_id,
        "username": order.username,
        "source": order.source,
        "state": order.state,
        "startToken": order.start_token,
        "geo": order.geo,
        "paymentMethod": order.method_user_text,
        "testsCount": order.tests_count,
        "withdrawRequired": order.withdraw_required,
        "kycRequired": order.kyc_required,
        "payoutOption": _payout_label(order),
        "comments": order.comments,
        "siteUrl": order.site_url,
        "login": encryptor.decrypt(order.login),
        "password": encryptor.decrypt(order.password_enc),
        "priceEur": order.price_eur,
        "payoutSurcharge": order.payout_surcharge,
        "status": order.status,
        "paymentNetwork": order.payment_network,
        "paymentWallet": order.payment_wallet,
        "paymentTxid": order.payment_txid,
        "payloadHash": order.payload_hash,
        "tgUserId": order.tg_user_id,
        "email": order.email,
        "createdAt": order.created_at,
        "updatedAt": order.updated_at,
    }


def create_api_app(repo: OrdersRepository, encryptor: CredentialEncryptor, config: Config) -> web.Application:
    app = web.Application()

    def _clean_optional_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        return cleaned or None

    def _parse_tests(raw: Any) -> int:
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:  # noqa: BLE001
            raise web.HTTPBadRequest(text="invalid_tests") from exc
        if value < 1 or value > MAX_CALC_TESTS:
            raise web.HTTPBadRequest(text="invalid_tests")
        return value

    def _map_payout(code: str) -> Dict[str, Any]:
        payout_info = PAYOUT_CODE_MAP.get(code)
        if payout_info is None:
            raise web.HTTPBadRequest(text="invalid_payout")
        return payout_info

    async def list_orders(request: web.Request) -> web.Response:
        limit = request.query.get("limit")
        try:
            limit_value = int(limit) if limit else 200
        except ValueError:
            limit_value = 200
        orders = await repo.list_recent(limit=limit_value)
        payload = [serialize_order(order, encryptor) for order in orders]
        return web.json_response({"orders": payload})

    async def get_order(request: web.Request) -> web.Response:
        order_id = int(request.match_info["order_id"])
        record = await repo.get_order(order_id)
        if record is None:
            raise web.HTTPNotFound()
        return web.json_response(serialize_order(record, encryptor))

    async def update_order(request: web.Request) -> web.Response:
        order_id = int(request.match_info["order_id"])
        body: Dict[str, Any]
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            raise web.HTTPBadRequest(text=str(exc))
        updates: Dict[str, Any] = {}
        status = body.get("status")
        if status:
            updates["status"] = status
            updates["state"] = status
        payment_txid = body.get("paymentTxid")
        if payment_txid is not None:
            updates["payment_txid"] = payment_txid
        if not updates:
            return web.json_response({"updated": False})
        await repo.update_order(order_id, **updates)
        record = await repo.get_order(order_id)
        if record is None:
            raise web.HTTPNotFound()
        return web.json_response(serialize_order(record, encryptor))

    async def stats(_: web.Request) -> web.Response:
        counts = await repo.get_stats()
        return web.json_response({"stats": counts})

    async def create_payload(request: web.Request) -> web.Response:
        try:
            body: Dict[str, Any] = await request.json()
        except Exception as exc:  # noqa: BLE001
            raise web.HTTPBadRequest(text=str(exc))

        payload = (body.get("payload") or "").strip()
        if not payload:
            raise web.HTTPBadRequest(text="payload_required")
        if len(payload) > PAYLOAD_MAX_LENGTH:
            raise web.HTTPBadRequest(text="payload_too_large")

        token = (body.get("token") or "").strip()
        if not token:
            token = _generate_payload_token()
        if len(token) > 128:
            raise web.HTTPBadRequest(text="token_too_long")

        await repo.save_payload_reference(token, payload)
        await repo.cleanup_payload_references(PAYLOAD_CLEANUP_HOURS)
        return web.json_response({"token": token})

    async def create_draft_order(request: web.Request) -> web.Response:
        try:
            body: Dict[str, Any] = await request.json()
        except Exception as exc:  # noqa: BLE001
            raise web.HTTPBadRequest(text="invalid_json") from exc

        email = (body.get("email") or "").strip().lower()
        if not EMAIL_PATTERN.fullmatch(email):
            raise web.HTTPBadRequest(text="invalid_email")

        geo = (body.get("geo") or "").strip().upper()
        if len(geo) != 2 or not geo.isalpha():
            raise web.HTTPBadRequest(text="invalid_geo")

        tests = _parse_tests(body.get("tests"))
        payout_code = (body.get("payoutCode") or "").strip().upper() or "N"
        payout_info = _map_payout(payout_code)

        method = (body.get("paymentMethod") or "").strip()
        site_url = _clean_optional_text(body.get("siteUrl"))
        login = _clean_optional_text(body.get("login"))
        password = _clean_optional_text(body.get("password"))
        comments = _clean_optional_text(body.get("comments"))

        payout_surcharge = int(payout_info["surcharge"])
        try:
            price = calculate_price(tests, payout_surcharge)
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc

        payload_raw = (body.get("payload") or "").strip()
        payload_hash = _compute_payload_hash(
            payload_raw,
            {
                "email": email,
                "geo": geo,
                "tests": tests,
                "payout": payout_code,
                "method": method,
                "site": site_url or "",
                "login": login or "",
                "password": password or "",
                "comments": comments or "",
            },
        )

        encrypted_login = encryptor.encrypt(login) if login else None
        encrypted_password = encryptor.encrypt(password) if password else None
        start_token = (body.get("startToken") or "").strip() or repo.generate_start_token()

        order = OrderCreate(
            source="web",
            state="draft",
            start_token=start_token,
            user_id=_derive_user_id(email),
            username=email,
            geo=geo,
            method_user_text=method,
            tests_count=tests,
            withdraw_required=payout_info["withdraw_required"],
            custom_test_required=False,
            custom_test_text=None,
            kyc_required=payout_info["kyc_required"],
            comments=comments,
            site_url=site_url,
            login=encrypted_login,
            password_enc=encrypted_password,
            payout_surcharge=payout_surcharge,
            price_eur=price.total,
            status="draft",
            payment_network=None,
            payment_wallet=None,
            payload_hash=payload_hash,
            tg_user_id=None,
            email=email,
        )
        record = await repo.upsert_draft_order(
            order,
            match_email=email,
            match_tg_user_id=None,
        )
        return web.json_response({"order_id": record.order_id, "start_token": record.start_token})

    async def get_by_token(request: web.Request) -> web.Response:
        token = request.match_info["token"]
        record = await repo.get_by_start_token(token)
        if record is None or record.state == "cancelled":
            raise web.HTTPNotFound()
        return web.json_response(serialize_order(record, encryptor))

    async def update_from_telegram(request: web.Request) -> web.Response:
        order_id = int(request.match_info["order_id"])
        try:
            body: Dict[str, Any] = await request.json()
        except Exception as exc:  # noqa: BLE001
            raise web.HTTPBadRequest(text="invalid_json") from exc

        updates: Dict[str, Any] = {}
        if "geo" in body:
            updates["geo"] = (body.get("geo") or "").strip().upper() or None
        if "method" in body or "paymentMethod" in body:
            updates["method_user_text"] = _clean_optional_text(body.get("method") or body.get("paymentMethod"))
        if "tests" in body or "testsCount" in body:
            updates["tests_count"] = _parse_tests(body.get("tests") or body.get("testsCount"))
        payout_code_raw = body.get("payoutCode") or body.get("payout")
        if payout_code_raw is not None:
            payout_code = (payout_code_raw or "").strip().upper() or "N"
            payout_info = _map_payout(payout_code)
            updates.update(
                {
                    "withdraw_required": payout_info["withdraw_required"],
                    "kyc_required": payout_info["kyc_required"],
                    "payout_surcharge": payout_info["surcharge"],
                }
            )
        if "comments" in body:
            updates["comments"] = _clean_optional_text(body.get("comments"))
        if "siteUrl" in body or "site_url" in body:
            updates["site_url"] = _clean_optional_text(body.get("siteUrl") or body.get("site_url"))
        if "login" in body:
            login_value = _clean_optional_text(body.get("login"))
            updates["login"] = encryptor.encrypt(login_value) if login_value else None
        if "password" in body:
            password_value = _clean_optional_text(body.get("password"))
            updates["password_enc"] = encryptor.encrypt(password_value) if password_value else None

        record = await repo.update_from_telegram(
            order_id,
            tg_user_id=body.get("tg_user_id") or body.get("tgUserId"),
            **updates,
        )
        if record is None:
            raise web.HTTPNotFound()
        return web.json_response(serialize_order(record, encryptor))

    async def submit_order(request: web.Request) -> web.Response:
        order_id = int(request.match_info["order_id"])
        try:
            body: Dict[str, Any] = await request.json()
        except Exception:
            body = {}
        price_eur = body.get("price_eur") or body.get("priceEur")
        if price_eur is not None:
            try:
                price_eur = int(price_eur)
            except (TypeError, ValueError):  # noqa: BLE001
                raise web.HTTPBadRequest(text="invalid_price")
        record = await repo.submit_order(order_id, price_eur=price_eur)
        if record is None:
            raise web.HTTPNotFound()
        return web.json_response(serialize_order(record, encryptor))

    async def active_for_user(request: web.Request) -> web.Response:
        email = (request.query.get("email") or "").strip().lower()
        tg_user_raw = request.query.get("tg_user_id") or request.query.get("tgUserId")
        tg_user_id = None
        if tg_user_raw:
            try:
                tg_user_id = int(tg_user_raw)
            except ValueError:
                raise web.HTTPBadRequest(text="invalid_tg_user_id")
        record: Optional[OrderRecord] = None
        if email:
            record = await repo.find_active_for_email(email, ACTIVE_STATES + ("submitted",))
        if record is None and tg_user_id is not None:
            record = await repo.find_active_for_tg(tg_user_id, ACTIVE_STATES + ("submitted",))
        if record is None:
            return web.json_response({"order": None})
        return web.json_response({"order": serialize_order(record, encryptor)})

    async def cors_middleware(app: web.Application, handler):  # type: ignore[override]
        async def middleware_handler(request: web.Request) -> web.Response:
            if request.method == "OPTIONS":
                response = web.Response(status=204)
            else:
                response = await handler(request)
            response.headers.update(
                {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PATCH, OPTIONS",
                }
            )
            return response

        return middleware_handler

    app.middlewares.append(cors_middleware)  # type: ignore[arg-type]
    app.router.add_get("/api/orders", list_orders)
    app.router.add_get("/api/orders/{order_id}", get_order)
    app.router.add_patch("/api/orders/{order_id}", update_order)
    app.router.add_post("/api/payloads", create_payload)
    app.router.add_get("/api/stats", stats)
    app.router.add_post("/orders/draft", create_draft_order)
    app.router.add_post("/api/orders/draft", create_draft_order)
    app.router.add_get("/orders/by_token/{token}", get_by_token)
    app.router.add_get("/api/orders/by_token/{token}", get_by_token)
    app.router.add_post(
        "/orders/{order_id}/update_from_telegram", update_from_telegram
    )
    app.router.add_post(
        "/api/orders/{order_id}/update_from_telegram", update_from_telegram
    )
    app.router.add_post("/orders/{order_id}/submit", submit_order)
    app.router.add_post("/api/orders/{order_id}/submit", submit_order)
    app.router.add_get("/orders/active_for_user", active_for_user)
    app.router.add_get("/api/orders/active_for_user", active_for_user)
    app.router.add_options("/api/orders/{order_id}", lambda _: web.Response(status=204))
    app.router.add_options("/api/payloads", lambda _: web.Response(status=204))
    app.router.add_options("/orders/draft", lambda _: web.Response(status=204))
    app.router.add_options("/api/orders/draft", lambda _: web.Response(status=204))
    app.router.add_options("/orders/by_token/{token}", lambda _: web.Response(status=204))
    app.router.add_options("/api/orders/by_token/{token}", lambda _: web.Response(status=204))
    app.router.add_options(
        "/orders/{order_id}/update_from_telegram", lambda _: web.Response(status=204)
    )
    app.router.add_options(
        "/api/orders/{order_id}/update_from_telegram", lambda _: web.Response(status=204)
    )
    app.router.add_options("/orders/{order_id}/submit", lambda _: web.Response(status=204))
    app.router.add_options("/api/orders/{order_id}/submit", lambda _: web.Response(status=204))
    app.router.add_options("/orders/active_for_user", lambda _: web.Response(status=204))
    app.router.add_options("/api/orders/active_for_user", lambda _: web.Response(status=204))
    app.router.add_options("/api/orders", lambda _: web.Response(status=204))
    app.router.add_options("/api/stats", lambda _: web.Response(status=204))
    return app
