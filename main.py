# main.py — точка входа

import asyncio
import logging
import signal
from contextlib import suppress
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram_sqlite_storage.sqlitestore import SQLStorage

from config import BOT_TOKEN, ADMIN_CHAT_ID, LOG_PATH, LOG_LEVEL
from bot.messages import LOCALIZATION
from bot.middlewares.lang import LangMiddleware
from bot.middlewares.rate_limit import RateLimitMiddleware
from bot.middlewares.subscription import SubscriptionMiddleware
from bot.services.scheduler import auto_unblock_users, notify_stale_applications, send_interview_reminders
from bot.db import database as db

# Handlers
from bot.handlers.admin import broadcast as admin_broadcast
from bot.handlers.admin import vacancies as admin_vacancies
from bot.handlers.hr import actions as hr
from bot.handlers.hr import dashboard as hr_dashboard
from bot.handlers.user import common as user
from bot.handlers.user import form
from bot.handlers.user import subscription

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH),
    ],
)

if LOG_LEVEL > logging.DEBUG:
    for lib in ("aiogram", "apscheduler", "gspread", "urllib3", "httpcore", "httpx"):
        logging.getLogger(lib).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.info("Логирование: уровень=%s, файл=%s", logging.getLevelName(LOG_LEVEL), LOG_PATH)

BASE_DIR         = Path(__file__).parent
FSM_STORAGE_PATH = str(BASE_DIR / "fsm_storage.db")


async def _delete_after(message: Message, delay: int) -> None:
    await asyncio.sleep(delay)
    with suppress(TelegramAPIError):
        await message.delete()


async def handle_group_messages(message: Message) -> None:
    if not (message.text and message.text.startswith("/start")):
        return
    with suppress(TelegramAPIError):
        bot_info = await message.bot.get_me()
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=LOCALIZATION["ru"]["btn_redirect_pm"],
                url=f"https://t.me/{bot_info.username}?start=true",
            )
        ]])
        sent = await message.reply(LOCALIZATION["ru"]["group_protection_text"], reply_markup=kb, parse_mode="HTML")
        asyncio.create_task(_delete_after(sent, delay=15))
        asyncio.create_task(_delete_after(message, delay=15))


def create_dispatcher(storage: SQLStorage) -> Dispatcher:
    dp = Dispatcher(storage=storage)

    # Rate limiting — первым
    dp.message.outer_middleware(RateLimitMiddleware())
    dp.callback_query.outer_middleware(RateLimitMiddleware())

    dp.message.middleware(LangMiddleware())
    dp.message.outer_middleware(SubscriptionMiddleware())
    dp.callback_query.outer_middleware(SubscriptionMiddleware())

    dp.include_router(subscription.router)
    dp.include_router(hr.router)
    dp.include_router(hr_dashboard.router)
    dp.include_router(admin_broadcast.router)
    dp.include_router(admin_vacancies.router)
    dp.include_router(user.router)
    dp.include_router(form.router)

    dp.message.register(
        handle_group_messages,
        F.chat.type.in_({"group", "supergroup"}),
        StateFilter(None),
    )
    return dp


async def on_startup(bot: Bot) -> None:
    db.init_db()
    db.migrate_db()
    logger.info("БД инициализирована.")
    with suppress(TelegramAPIError):
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text="🟢 <b>Бот MADO запущен</b> и готов к работе.", parse_mode="HTML")
    bot_info = await bot.get_me()
    logger.info("Бот запущен: @%s (id=%d)", bot_info.username, bot_info.id)


async def on_shutdown(bot: Bot) -> None:
    logger.warning("Бот останавливается...")
    with suppress(TelegramAPIError):
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text="🔴 <b>Бот MADO остановлен.</b>", parse_mode="HTML")


async def main() -> None:
    bot     = Bot(token=BOT_TOKEN)
    storage = SQLStorage(FSM_STORAGE_PATH)
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
        scheduler.shutdown(wait=False)
        with suppress(Exception):
            await storage.close()
        with suppress(Exception):
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
