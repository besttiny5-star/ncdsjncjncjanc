from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiohttp import web

from payment_qa_bot.config import load_config
from payment_qa_bot.models.db import OrdersRepository
from payment_qa_bot.routers.admin import get_admin_router
from payment_qa_bot.routers.public import get_public_router
from payment_qa_bot.services.security import CredentialEncryptor
from payment_qa_bot.web.server import create_web_app

logging.basicConfig(level=logging.INFO)


def build_dispatcher(repo: OrdersRepository, encryptor, config, bot_username: str):
    dp = Dispatcher()
    dp.include_router(get_public_router(config, repo, encryptor, bot_username))
    dp.include_router(get_admin_router(config, repo))
    return dp


async def main() -> None:
    config = load_config()
    repo = OrdersRepository(config.db_path)
    await repo.init()
    encryptor = CredentialEncryptor(config.encryption_key)
    bot = Bot(token=config.bot_token, parse_mode="HTML")
    me = await bot.get_me()
    dp = build_dispatcher(repo, encryptor, config, bot_username=me.username or "")
    web_app = create_web_app(config, repo, encryptor, bot_username=me.username or "")
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, host=config.api_host, port=config.api_port)
    await site.start()
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
