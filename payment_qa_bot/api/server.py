from __future__ import annotations

import secrets
from typing import Any, Dict

from aiohttp import web

from payment_qa_bot.models.db import OrderRecord, OrdersRepository
from payment_qa_bot.services.security import CredentialEncryptor

PAYLOAD_MAX_LENGTH = 4096
PAYLOAD_CLEANUP_HOURS = 72


def _generate_payload_token() -> str:
    return secrets.token_urlsafe(9)


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


def create_api_app(repo: OrdersRepository, encryptor: CredentialEncryptor) -> web.Application:
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
    app.router.add_options("/api/orders/{order_id}", lambda _: web.Response(status=204))
    app.router.add_options("/api/payloads", lambda _: web.Response(status=204))
    app.router.add_get("/api/stats", stats)
    app.router.add_options("/api/orders", lambda _: web.Response(status=204))
    app.router.add_options("/api/stats", lambda _: web.Response(status=204))
    return app
