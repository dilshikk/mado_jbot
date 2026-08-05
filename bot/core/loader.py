# bot/core/loader.py

import asyncio
from contextlib import suppress

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramAPIError
from aiogram_sqlite_storage.sqlitestore import SQLStorage

from bot.core.config import settings
from bot.lexicon import LOCALIZATION
from bot.middlewares.auth import SubscriptionMiddleware
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.localization import LangMiddleware
from bot.handlers import errors
from bot.handlers.admin import broadcast as admin_broadcast
from bot.handlers.admin import vacancies as admin_vacancies
from bot.handlers.hr import actions as hr
from bot.handlers.hr import dashboard as hr_dashboard
from bot.handlers.user import common as user
from bot.handlers.user import form
from bot.handlers.user import form_extra
from bot.handlers.user import interview as user_interview
from bot.handlers.user import subscription


async def handle_group_messages(message) -> None:
    """Отвечает на /start в группах — редирект в личку."""
    if not (message.text and message.text.startswith("/start")):
        return
    bot_info = await message.bot.get_me()
    await message.answer(
        f"Для заполнения анкеты перейдите в личку: @{bot_info.username}"
    )


def create_dispatcher() -> Dispatcher:
    storage = SQLStorage(db_path=settings.sqlite_path)
    dp = Dispatcher(storage=storage)

    # Middlewares
    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())
    dp.message.middleware(LangMiddleware())
    dp.callback_query.middleware(LangMiddleware())

    # Routers — порядок важен!
    dp.include_router(errors.router)
    dp.include_router(subscription.router)
    dp.include_router(hr.router)
    dp.include_router(hr_dashboard.router)
    dp.include_router(admin_broadcast.router)
    dp.include_router(admin_vacancies.router)
    dp.include_router(user.router)
    dp.include_router(form.router)
    # Новые шаги анкеты — после form, но до interview
    dp.include_router(form_extra.router)
    # AI-интервью — должен быть после form, чтобы его FSM не перехватывал анкету
    dp.include_router(user_interview.router)

    return dp


async def send_startup_notification(bot: Bot) -> None:
    with suppress(TelegramAPIError):
        from bot.core.config import ADMIN_IDS
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, "✅ Бот запущен")


async def send_shutdown_notification(bot: Bot) -> None:
    with suppress(TelegramAPIError):
        from bot.core.config import ADMIN_IDS
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, "⛔ Бот остановлен")
