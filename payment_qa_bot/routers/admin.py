from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from payment_qa_bot.config import Config
from payment_qa_bot.models.db import OrdersRepository
from payment_qa_bot.services.geo import format_country
from payment_qa_bot.texts.catalog import TEXTS


def get_admin_router(config: Config, repo: OrdersRepository) -> Router:
    router = Router()

    def is_admin(user_id: int) -> bool:
        return user_id in config.admin_ids

    def render_order_line(order) -> str:
        geo = format_country(order.geo or "") if order.geo else "—"
        return (
            f"#{order.order_id} | {order.status} | €{order.price_eur or 0}\n"
            f"GEO: {geo}\n"
            f"Method: {order.method_user_text or '—'}\n"
            f"User: @{order.username or '—'} ({order.user_id})"
        )

    @router.message(Command("admin"))
    async def stats(message: Message) -> None:
        if not is_admin(message.from_user.id):
            await message.answer("Access denied")
            return
        counts = await repo.get_stats()
        lines = [TEXTS.get("admin.stats.header", "en"), ""]
        for status, count in sorted(counts.items()):
            lines.append(TEXTS.get("admin.stats.line", "en", status=status, count=count))
        await message.answer("\n".join(lines))

    @router.message(Command("pending"))
    async def pending(message: Message) -> None:
        if not is_admin(message.from_user.id):
            await message.answer("Access denied")
            return
        orders = await repo.list_by_status("awaiting_payment")
        if not orders:
            await message.answer(TEXTS.get("admin.no.orders", "en"))
            return
        await message.answer("\n\n".join(render_order_line(order) for order in orders))

    @router.message(Command("proofs"))
    async def proofs(message: Message) -> None:
        if not is_admin(message.from_user.id):
            await message.answer("Access denied")
            return
        orders = await repo.list_by_status("proof_received")
        if not orders:
            await message.answer(TEXTS.get("admin.no.orders", "en"))
            return
        await message.answer("\n\n".join(render_order_line(order) for order in orders))

    @router.message(Command("paid"))
    async def paid(message: Message) -> None:
        if not is_admin(message.from_user.id):
            await message.answer("Access denied")
            return
        orders = await repo.list_by_status("paid")
        if not orders:
            await message.answer(TEXTS.get("admin.no.orders", "en"))
            return
        await message.answer("\n\n".join(render_order_line(order) for order in orders))

    return router
