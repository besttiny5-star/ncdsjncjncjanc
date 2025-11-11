from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from payment_qa_bot.config import load_config
from payment_qa_bot.models.db import OrdersRepository
from payment_qa_bot.routers.admin import get_admin_router
from payment_qa_bot.routers.public import get_public_router
from payment_qa_bot.services.security import CredentialEncryptor

logging.basicConfig(level=logging.INFO)


def build_dispatcher(repo: OrdersRepository, encryptor, config):
    dp = Dispatcher()
    dp.include_router(get_public_router(config, repo, encryptor))
    dp.include_router(get_admin_router(config, repo))
    return dp


async def main() -> None:
    config = load_config()
    repo = OrdersRepository(config.db_path)
    await repo.init()
    encryptor = CredentialEncryptor(config.encryption_key)
    bot = Bot(token=config.bot_token, parse_mode="HTML")
    dp = build_dispatcher(repo, encryptor, config)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
