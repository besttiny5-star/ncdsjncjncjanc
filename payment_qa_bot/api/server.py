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
        "createdAt": order.created_at,
        "updatedAt": order.updated_at,
    }


def create_api_app(repo: OrdersRepository, encryptor: CredentialEncryptor, config: Config) -> web.Application:
    app = web.Application()

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

    async def create_site_order(request: web.Request) -> web.Response:
        try:
            body: Dict[str, Any] = await request.json()
        except Exception as exc:  # noqa: BLE001
            raise web.HTTPBadRequest(text="invalid_json") from exc

        email = (body.get("email") or "").strip()
        if not EMAIL_PATTERN.fullmatch(email):
            raise web.HTTPBadRequest(text="invalid_email")

        geo = (body.get("geo") or "").strip().upper()
        if len(geo) != 2 or not geo.isalpha():
            raise web.HTTPBadRequest(text="invalid_geo")

        try:
            tests = int(body.get("tests"))
        except (TypeError, ValueError) as exc:
            raise web.HTTPBadRequest(text="invalid_tests") from exc
        if tests < 1 or tests > MAX_CALC_TESTS:
            raise web.HTTPBadRequest(text="invalid_tests")

        payout_code = (body.get("payoutCode") or "").strip().upper() or "N"
        payout_info = PAYOUT_CODE_MAP.get(payout_code)
        if payout_info is None:
            raise web.HTTPBadRequest(text="invalid_payout")

        method = (body.get("paymentMethod") or "").strip()
        site_url_raw = body.get("siteUrl")
        site_url = (
            site_url_raw.strip() if isinstance(site_url_raw, str) and site_url_raw.strip() else None
        )
        login_raw = body.get("login")
        login = login_raw.strip() if isinstance(login_raw, str) and login_raw.strip() else None
        password_raw = body.get("password")
        password = (
            password_raw.strip() if isinstance(password_raw, str) and password_raw.strip() else None
        )
        comments_raw = body.get("comments")
        comments = comments_raw.strip() if isinstance(comments_raw, str) and comments_raw.strip() else None

        payout_surcharge = int(payout_info["surcharge"])
        try:
            price = calculate_price(tests, payout_surcharge)
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc

        provided_total = body.get("total")
        if provided_total is not None:
            try:
                provided_total_int = int(provided_total)
            except (TypeError, ValueError) as exc:
                raise web.HTTPBadRequest(text="invalid_total") from exc
            if provided_total_int != price.total:
                # Use trusted total from server-side calculation
                pass

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

        order = OrderCreate(
            user_id=_derive_user_id(email),
            username=email,
            source="site",
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
            status="awaiting_payment",
            payment_network="USDT TRC-20",
            payment_wallet=config.wallet_trc20,
            payload_hash=payload_hash,
        )
        order_id = await repo.create_order(order)
        message = f"Спасибо! Заказ #{order_id} принят. Мы свяжемся с вами по email."
        return web.json_response({"orderId": order_id, "message": message}, status=201)

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
    app.router.add_post("/api/site-orders", create_site_order)
    app.router.add_options("/api/orders/{order_id}", lambda _: web.Response(status=204))
    app.router.add_options("/api/payloads", lambda _: web.Response(status=204))
    app.router.add_options("/api/site-orders", lambda _: web.Response(status=204))
    app.router.add_get("/api/stats", stats)
    app.router.add_options("/api/orders", lambda _: web.Response(status=204))
    app.router.add_options("/api/stats", lambda _: web.Response(status=204))
    return app
