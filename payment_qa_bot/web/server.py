from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path
from typing import Any, Dict, List, Optional

from aiohttp import web

from payment_qa_bot.config import Config
from payment_qa_bot.models.db import OrderRecord, OrdersRepository
from payment_qa_bot.services.geo import COUNTRY_NAMES, format_country
from payment_qa_bot.services.payment_methods import PAYMENT_METHODS
from payment_qa_bot.services.pricing import BASE_PRICE_PER_TEST
from payment_qa_bot.services.security import CredentialEncryptor
from payment_qa_bot.texts.catalog import TEXTS


ROOT_DIR = Path(__file__).resolve().parents[2]
SITE_FILE = ROOT_DIR / "index.html"
ADMIN_DIR = ROOT_DIR / "admin"


def _package_from_tests(tests: int) -> str:
    if tests >= 10:
        return "retainer"
    if tests >= 5:
        return "mini"
    return "single"


def _build_countries() -> Dict[str, Dict[str, str]]:
    mapping: Dict[str, Dict[str, str]] = {}
    for code, name in COUNTRY_NAMES.items():
        mapping[code] = {"name": name, "flag": format_country(code).split(" ", 1)[0]}
    return mapping


def _payment_proof(record: OrderRecord) -> Optional[Dict[str, Any]]:
    if not record.payment_proof_file_id and not record.payment_txid:
        return None
    payload: Dict[str, Any] = {
        "fileId": record.payment_proof_file_id,
        "txid": record.payment_txid,
        "uploadedAt": record.updated_at,
    }
    return payload


def _serialize_order(record: OrderRecord, encryptor: CredentialEncryptor) -> Dict[str, Any]:
    login = encryptor.decrypt(record.login)
    password = encryptor.decrypt(record.password_enc)
    paid_at = record.updated_at if record.status in {"paid", "in_progress", "completed"} else None
    started_at = record.updated_at if record.status in {"in_progress", "completed"} else None
    completed_at = record.updated_at if record.status == "completed" else None
    proof = _payment_proof(record)
    return {
        "id": record.order_id,
        "orderNumber": f"QA-{record.order_id:06d}",
        "createdAt": record.created_at,
        "paidAt": paid_at,
        "startedAt": started_at,
        "completedAt": completed_at,
        "client": {
            "username": record.username,
            "telegramId": record.user_id,
            "source": record.source,
        },
        "packageType": _package_from_tests(record.tests_count or 1),
        "geo": record.geo,
        "priceEur": record.price_eur or 0,
        "status": record.status,
        "testerId": None,
        "paymentMethod": record.method_user_text,
        "websiteUrl": record.site_url,
        "credentials": {"login": login, "password": password},
        "comments": record.comments,
        "reportUrl": None,
        "attachments": [],
        "paymentProof": proof,
        "notes": record.admin_notes,
        "siteReady": bool(record.site_url),
        "testsCount": record.tests_count,
        "withdrawRequired": record.withdraw_required,
        "kycRequired": record.kyc_required,
        "paymentWallet": record.payment_wallet,
        "paymentNetwork": record.payment_network,
        "source": record.source,
    }


def _build_activity(orders: List[OrderRecord]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    base_id = 3000
    for index, order in enumerate(sorted(orders, key=lambda item: item.created_at)):
        events.append(
            {
                "id": base_id + index * 10,
                "eventType": "order_created",
                "orderId": order.order_id,
                "description": f"Новый заказ QA-{order.order_id:06d} от @{order.username or order.user_id}",
                "createdAt": order.created_at,
                "metadata": {"status": order.status, "source": order.source},
            }
        )
        if order.payment_proof_file_id or order.payment_txid:
            events.append(
                {
                    "id": base_id + index * 10 + 1,
                    "eventType": "payment_proof_received",
                    "orderId": order.order_id,
                    "description": f"Получен чек по QA-{order.order_id:06d}",
                    "createdAt": order.updated_at,
                    "metadata": {"fileId": order.payment_proof_file_id, "txid": order.payment_txid},
                }
            )
        if order.status in {"paid", "in_progress", "completed"}:
            events.append(
                {
                    "id": base_id + index * 10 + 2,
                    "eventType": "order_paid",
                    "orderId": order.order_id,
                    "description": f"Оплата по QA-{order.order_id:06d} подтверждена",
                    "createdAt": order.updated_at,
                    "metadata": {"status": order.status},
                }
            )
        if order.status == "completed":
            events.append(
                {
                    "id": base_id + index * 10 + 3,
                    "eventType": "order_completed",
                    "orderId": order.order_id,
                    "description": f"Заказ QA-{order.order_id:06d} завершён",
                    "createdAt": order.updated_at,
                }
            )
    return sorted(events, key=lambda item: item["createdAt"], reverse=True)


async def handle_dashboard(request: web.Request) -> web.Response:
    repo: OrdersRepository = request.app["repo"]
    encryptor: CredentialEncryptor = request.app["encryptor"]
    orders = await repo.list_orders()
    serialized = [_serialize_order(order, encryptor) for order in orders]
    payload = {
        "orders": serialized,
        "testers": [],
        "activity": _build_activity(orders),
        "countries": _build_countries(),
    }
    return web.json_response(payload)


async def handle_orders(request: web.Request) -> web.Response:
    repo: OrdersRepository = request.app["repo"]
    encryptor: CredentialEncryptor = request.app["encryptor"]
    orders = await repo.list_orders()
    return web.json_response([_serialize_order(order, encryptor) for order in orders])


async def handle_order(request: web.Request) -> web.Response:
    repo: OrdersRepository = request.app["repo"]
    encryptor: CredentialEncryptor = request.app["encryptor"]
    order_id = int(request.match_info["order_id"])
    order = await repo.get_order(order_id)
    if order is None:
        raise web.HTTPNotFound()
    return web.json_response(_serialize_order(order, encryptor))


async def handle_status_update(request: web.Request) -> web.Response:
    repo: OrdersRepository = request.app["repo"]
    encryptor: CredentialEncryptor = request.app["encryptor"]
    order_id = int(request.match_info["order_id"])
    payload = await request.json()
    status = payload.get("status")
    if status not in {"awaiting_payment", "proof_received", "paid", "in_progress", "completed", "cancelled"}:
        raise web.HTTPBadRequest(text="Unsupported status")
    fields: Dict[str, Any] = {"status": status}
    if "payment_txid" in payload:
        fields["payment_txid"] = payload.get("payment_txid")
    if "payment_proof_file_id" in payload:
        fields["payment_proof_file_id"] = payload.get("payment_proof_file_id")
    await repo.update_order(order_id, **fields)
    order = await repo.get_order(order_id)
    if order is None:
        raise web.HTTPNotFound()
    return web.json_response(_serialize_order(order, encryptor))


async def handle_catalog(request: web.Request) -> web.Response:
    config: Config = request.app["config"]
    payout_options = []
    for key in ("payout.option.none", "payout.option.withdraw", "payout.option.kyc"):
        surcharge = 0
        withdraw = False
        kyc = False
        if key.endswith("withdraw"):
            surcharge = 10
            withdraw = True
        if key.endswith("kyc"):
            surcharge = 25
            withdraw = True
            kyc = True
        payout_options.append(
            {
                "key": key,
                "surcharge": surcharge,
                "withdraw": withdraw,
                "kyc": kyc,
                "labels": {
                    "en": TEXTS.button(key, "en"),
                    "ru": TEXTS.button(key, "ru"),
                },
            }
        )
    payload = {
        "geo": [{"code": code, "label": format_country(code)} for code in config.geo_whitelist],
        "paymentMethods": PAYMENT_METHODS,
        "payoutOptions": payout_options,
        "basePricePerTest": BASE_PRICE_PER_TEST,
    }
    return web.json_response(payload)


async def handle_index(_: web.Request) -> web.Response:
    if SITE_FILE.exists():
        return web.FileResponse(SITE_FILE)
    raise web.HTTPNotFound()


async def handle_admin_root(_: web.Request) -> web.Response:
    raise web.HTTPFound("/admin/index.html")


def build_app(config: Config, repo: OrdersRepository, encryptor: CredentialEncryptor) -> web.Application:
    app = web.Application()
    app["repo"] = repo
    app["encryptor"] = encryptor
    app["config"] = config

    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    app.router.add_get("/admin", handle_admin_root)
    if ADMIN_DIR.exists():
        app.router.add_static("/admin", ADMIN_DIR, show_index=False)

    app.router.add_get("/api/dashboard", handle_dashboard)
    app.router.add_get("/api/orders", handle_orders)
    app.router.add_get("/api/orders/{order_id:int}", handle_order)
    app.router.add_post("/api/orders/{order_id:int}/status", handle_status_update)
    app.router.add_get("/api/catalog", handle_catalog)

    async def cors_middleware(app, handler):
        async def middleware_handler(request):
            response = await handler(request)
            response.headers.setdefault("Access-Control-Allow-Origin", "*")
            return response

        return middleware_handler

    app.middlewares.append(cors_middleware)
    return app


async def run_web_app(config: Config, repo: OrdersRepository, encryptor: CredentialEncryptor) -> None:
    app = build_app(config, repo, encryptor)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.web_host, config.web_port)
    await site.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        with suppress(Exception):
            await runner.cleanup()
