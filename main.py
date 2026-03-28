import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import MANAGER_BOT_TOKEN
import db
from handlers import status, add_bot, bot_card, logs, scan, common

logging.basicConfig(level=logging.INFO)


async def main():
    await db.init_db()

    bot = Bot(
        token=MANAGER_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # common подключается последним — иначе catch-all перехватит всё
    dp.include_routers(status.router, add_bot.router, bot_card.router, logs.router, scan.router, common.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
