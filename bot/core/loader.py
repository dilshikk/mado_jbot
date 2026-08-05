# bot/core/loader.py

import asyncio
from contextlib import suppress

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram_sqlite_storage.sqlitestore import SQLStorage

from bot.core.config import settings
from bot.lexicon import LOCALIZATION
from bot.middlewares.auth import SubscriptionMiddleware
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.localization import LangMiddleware
from bot.handlers import errors
from bot.handlers.admin import broadcast as admin_broadcast
from bot.handlers.admin import vacancies as admin_vacancies
from bot.handlers.admin import metro_stations as admin_metro
from bot.handlers.hr import actions as hr
from bot.handlers.hr import dashboard as hr_dashboard
from bot.handlers.user import common as user
from bot.handlers.user import form
from bot.handlers.user import form_extra
from bot.handlers.user import interview as user_interview
from bot.handlers.user import metro as user_metro
from bot.handlers.user import subscription

# Роутер для групповых и супергрупповых чатов
group_router = Router()

@group_router.message(CommandStart(), F.chat.type.in_({"group", "supergroup"}))
async def handle_group_start(message: Message) -> None:
    """Отвечает на /start в группах — редирект в личку."""
    bot_info = await message.bot.get_me()
    await message.answer(
        f"Для заполнения анкеты перейдите в личку: @{bot_info.username}"
    )


def create_bot() -> Bot:
    """Создаёт клиент Telegram Bot."""
    return Bot(token=settings.bot_token)


def create_storage() -> SQLStorage:
    """Создаёт хранилище состояний FSM."""
    return SQLStorage(db_path=settings.fsm_storage_path)


def create_dispatcher(storage: SQLStorage | None = None) -> Dispatcher:
    """Создаёт диспетчер и регистрирует middleware и роутеры."""
    if storage is None:
        storage = create_storage()
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
    dp.include_router(group_router)
    dp.include_router(subscription.router)
    dp.include_router(hr.router)
    dp.include_router(hr_dashboard.router)
    dp.include_router(admin_broadcast.router)
    dp.include_router(admin_vacancies.router)
    dp.include_router(admin_metro.router)
    dp.include_router(user.router)
    dp.include_router(form.router)
    # Новые шаги анкеты — после form, но до interview
    dp.include_router(form_extra.router)
    # Inline-выбор метро — callback_query хендлеры для состояния Form.waiting_metro
    dp.include_router(user_metro.router)
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
