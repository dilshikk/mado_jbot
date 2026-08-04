import asyncio
import logging
import signal
from contextlib import suppress

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot.core.config import ADMIN_CHAT_ID, settings
from bot.core.loader import create_bot, create_dispatcher, create_storage
from bot.db.base import engine, init_db
from bot.services.scheduler import (
    auto_unblock_users,
    notify_stale_applications,
    send_interview_reminders,
)
from bot.utils.logger import setup_logging

logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    await init_db()
    logger.info("БД инициализирована.")
    with suppress(TelegramAPIError):
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text="🟢 <b>Бот MADO запущен</b> и готов к работе.",
            parse_mode="HTML",
        )
    bot_info = await bot.get_me()
    logger.info("Бот запущен: @%s (id=%d)", bot_info.username, bot_info.id)


async def on_shutdown(bot: Bot) -> None:
    logger.warning("Бот останавливается...")
    with suppress(TelegramAPIError):
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text="🔴 <b>Бот MADO остановлен.</b>",
            parse_mode="HTML",
        )


async def main() -> None:
    setup_logging(settings.log_path, settings.log_level_int)

    bot     = create_bot()
    storage = create_storage()
    dp      = create_dispatcher(storage)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(dp.stop_polling()))

    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    scheduler.add_job(send_interview_reminders,  "interval", minutes=30, args=[bot])
    scheduler.add_job(notify_stale_applications, "interval", hours=12,   args=[bot])
    scheduler.add_job(auto_unblock_users,        "interval", hours=24,   args=[bot])
    scheduler.start()

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Graceful shutdown: новые задачи не запускаются,
        # выполняющиеся дожидаются завершения
        with suppress(Exception):
            scheduler.pause()
        with suppress(Exception):
            scheduler.shutdown(wait=True)
        with suppress(Exception):
            await storage.close()
        with suppress(Exception):
            await engine.dispose()
        with suppress(Exception):
            await bot.session.close()
        logger.info("Бот корректно остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
