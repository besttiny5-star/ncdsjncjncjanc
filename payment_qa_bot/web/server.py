from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from aiohttp import web

from payment_qa_bot.config import Config
from payment_qa_bot.models.db import OrderRecord, OrdersRepository
from payment_qa_bot.services.geo import COUNTRY_NAMES, flag
from payment_qa_bot.services.payment_methods import PAYMENT_METHODS
from payment_qa_bot.services.payouts import iter_payout_options
from payment_qa_bot.services.pricing import BASE_PRICE_PER_TEST
from payment_qa_bot.services.security import CredentialEncryptor


def _parse_iso(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    try:
        return datetime.fromisoformat(dt)
    except ValueError:
        return None


def _order_number(order: OrderRecord) -> str:
    created = _parse_iso(order.created_at) or datetime.utcnow()
    return f"QA-{created:%y%m}{order.order_id:04d}"


def _package_type(order: OrderRecord) -> str:
    tests = order.tests_count or 1
    if tests >= 10:
        return "retainer"
    if tests >= 5:
        return "mini"
    if tests == 1:
        return "single"
    return "custom"


def _serialize_order(order: OrderRecord, encryptor: CredentialEncryptor) -> Dict[str, Any]:
    decrypted_login = encryptor.decrypt(order.login) if encryptor else order.login
    decrypted_password = encryptor.decrypt(order.password_enc) if encryptor else order.password_enc
    paid_at = None
    started_at = None
    completed_at = None
    if order.status in {"paid", "in_progress", "completed"}:
        paid_at = order.updated_at
    if order.status in {"in_progress", "completed"}:
        started_at = order.updated_at
    if order.status == "completed":
        completed_at = order.updated_at
    return {
        "id": order.order_id,
        "orderNumber": _order_number(order),
        "createdAt": order.created_at,
        "updatedAt": order.updated_at,
        "paidAt": paid_at,
        "startedAt": started_at,
        "completedAt": completed_at,
        "client": {
            "username": order.username,
            "telegramId": order.user_id,
            "email": None,
            "phone": None,
        },
        "packageType": _package_type(order),
        "geo": order.geo,
        "priceEur": order.price_eur,
        "status": order.status,
        "testerId": None,
        "paymentMethod": order.method_user_text,
        "websiteUrl": order.site_url,
        "credentials": {
            "login": decrypted_login,
            "password": decrypted_password,
        },
        "comments": order.comments,
        "reportUrl": None,
        "attachments": [],
        "paymentProof": {"fileId": order.payment_proof_file_id} if order.payment_proof_file_id else None,
        "notes": order.admin_notes,
        "siteReady": bool(order.site_url),
        "testsCount": order.tests_count or 1,
        "withdrawRequired": bool(order.withdraw_required),
        "kycRequired": bool(order.kyc_required),
        "source": order.source,
        "payoutOption": order.kyc_required and "payout.option.kyc"
        or (order.withdraw_required and "payout.option.withdraw")
        or "payout.option.none",
        "payloadHash": order.payload_hash,
        "paymentNetwork": order.payment_network,
        "paymentWallet": order.payment_wallet,
        "paymentTxid": order.payment_txid,
    }


def _build_activity(order: OrderRecord) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    events.append(
        {
            "id": f"{order.order_id}-created",
            "type": "order_created",
            "createdAt": order.created_at,
            "title": f"Order #{order.order_id} created",
            "description": f"Source: {order.source}. Status: {order.status}.",
        }
    )
    if order.payment_proof_file_id:
        events.append(
            {
                "id": f"{order.order_id}-proof",
                "type": "payment_proof_received",
                "createdAt": order.updated_at,
                "title": f"Payment proof for order #{order.order_id}",
                "description": "User uploaded confirmation of payment.",
            }
        )
    if order.status in {"paid", "in_progress", "completed"}:
        events.append(
            {
                "id": f"{order.order_id}-paid",
                "type": "order_paid",
                "createdAt": order.updated_at,
                "title": f"Order #{order.order_id} marked as paid",
                "description": "Awaiting execution by operations team.",
            }
        )
    if order.status == "completed":
        events.append(
            {
                "id": f"{order.order_id}-completed",
                "type": "order_completed",
                "createdAt": order.updated_at,
                "title": f"Order #{order.order_id} completed",
                "description": "Results delivered to the client.",
            }
        )
    return events


async def handle_meta(request: web.Request) -> web.Response:
    config: Config = request.app["config"]
    bot_username: str = request.app["bot_username"]
    geos = []
    for code in config.geo_whitelist:
        geos.append({
            "code": code,
            "name": COUNTRY_NAMES.get(code.upper(), code.upper()),
            "flag": flag(code),
        })
    payout_options = [asdict(option) for option in iter_payout_options()]
    return web.json_response(
        {
            "geos": geos,
            "paymentMethods": {code: PAYMENT_METHODS.get(code, []) for code in config.geo_whitelist},
            "payoutOptions": payout_options,
            "pricing": {"base": BASE_PRICE_PER_TEST},
            "bot": {"username": bot_username},
        }
    )


async def handle_dashboard(request: web.Request) -> web.Response:
    repo: OrdersRepository = request.app["repo"]
    encryptor: CredentialEncryptor = request.app["encryptor"]
    bot_username: str = request.app["bot_username"]
    orders = await repo.list_orders()
    serialized = [_serialize_order(order, encryptor) for order in orders]
    activity: List[Dict[str, Any]] = []
    for order in orders:
        activity.extend(_build_activity(order))
    activity.sort(key=lambda item: item["createdAt"], reverse=True)
    stats: Dict[str, int] = {}
    for order in orders:
        stats[order.status] = stats.get(order.status, 0) + 1
    countries = {
        code: {"name": COUNTRY_NAMES.get(code, code), "flag": flag(code)}
        for code in COUNTRY_NAMES.keys()
    }
    return web.json_response(
        {
            "orders": serialized,
            "stats": stats,
            "activity": activity,
            "testers": [],
            "countries": countries,
            "bot": {"username": bot_username},
        }
    )


async def handle_orders(request: web.Request) -> web.Response:
    repo: OrdersRepository = request.app["repo"]
    encryptor: CredentialEncryptor = request.app["encryptor"]
    orders = await repo.list_orders()
    return web.json_response([_serialize_order(order, encryptor) for order in orders])


async def handle_order_detail(request: web.Request) -> web.Response:
    repo: OrdersRepository = request.app["repo"]
    encryptor: CredentialEncryptor = request.app["encryptor"]
    order_id = int(request.match_info["order_id"])
    order = await repo.get_order(order_id)
    if not order:
        raise web.HTTPNotFound()
    return web.json_response(_serialize_order(order, encryptor))


async def handle_order_update(request: web.Request) -> web.Response:
    repo: OrdersRepository = request.app["repo"]
    encryptor: CredentialEncryptor = request.app["encryptor"]
    order_id = int(request.match_info["order_id"])
    payload = await request.json()
    allowed_statuses = {"awaiting_payment", "proof_received", "paid", "in_progress", "completed", "cancelled"}
    fields: Dict[str, Any] = {}
    status = payload.get("status")
    if status:
        if status not in allowed_statuses:
            raise web.HTTPBadRequest(text="Unsupported status")
        fields["status"] = status
    note = payload.get("adminNotes")
    if note is not None:
        fields["admin_notes"] = note
    if txid := payload.get("paymentTxid"):
        fields["payment_txid"] = txid
    if fields:
        await repo.update_order(order_id, **fields)
    order = await repo.get_order(order_id)
    if not order:
        raise web.HTTPNotFound()
    return web.json_response(_serialize_order(order, encryptor))


async def handle_index(request: web.Request) -> web.StreamResponse:
    base_dir: Path = request.app["base_dir"]
    index_path = base_dir / "index.html"
    if not index_path.exists():
        raise web.HTTPNotFound()
    return web.FileResponse(index_path)


def create_web_app(
    config: Config,
    repo: OrdersRepository,
    encryptor: CredentialEncryptor,
    bot_username: str,
) -> web.Application:
    app = web.Application()
    app["config"] = config
    app["repo"] = repo
    app["encryptor"] = encryptor
    app["bot_username"] = bot_username
    app["base_dir"] = Path(__file__).resolve().parent.parent.parent

    app.add_routes(
        [
            web.get("/", handle_index),
            web.get("/index.html", handle_index),
            web.get("/api/meta", handle_meta),
            web.get("/api/dashboard", handle_dashboard),
            web.get("/api/orders", handle_orders),
            web.get("/api/orders/{order_id:\d+}", handle_order_detail),
            web.patch("/api/orders/{order_id:\d+}", handle_order_update),
        ]
    )

    base_dir: Path = app["base_dir"]
    admin_dir = base_dir / "admin"
    if admin_dir.exists():
        app.router.add_static("/admin", admin_dir, show_index=False)

    return app
