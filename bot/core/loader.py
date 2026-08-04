# bot/core/loader.py

import asyncio
from contextlib import suppress

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram_sqlite_storage.sqlitestore import SQLStorage

from bot.core.config import settings
from bot.lexicon import LOCALIZATION
from bot.middlewares.auth import SubscriptionMiddleware
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.localization import LangMiddleware
from bot.middlewares.throttling import RateLimitMiddleware
from bot.handlers import errors
from bot.handlers.admin import broadcast as admin_broadcast
from bot.handlers.admin import vacancies as admin_vacancies
from bot.handlers.hr import actions as hr
from bot.handlers.hr import dashboard as hr_dashboard
from bot.handlers.user import common as user
from bot.handlers.user import form
from bot.handlers.user import subscription


def create_bot() -> Bot:
    return Bot(token=settings.bot_token)


def create_storage() -> SQLStorage:
    return SQLStorage(settings.fsm_storage_path)


def create_dispatcher(storage: SQLStorage) -> Dispatcher:
    dp = Dispatcher(storage=storage)

    # Сессия БД — первой, чтобы быть доступной всем ниже
    dp.update.outer_middleware(DbSessionMiddleware())

    # Rate limiting — отсекать спам до остальной логики
    dp.message.outer_middleware(RateLimitMiddleware())
    dp.callback_query.outer_middleware(RateLimitMiddleware())

    dp.message.middleware(LangMiddleware())
    dp.message.outer_middleware(SubscriptionMiddleware())
    dp.callback_query.outer_middleware(SubscriptionMiddleware())

    dp.include_router(errors.router)
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


async def handle_group_messages(message: Message) -> None:
    """Отвечает на /start в группах — редирект в личку."""
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
        sent = await message.reply(
            LOCALIZATION["ru"]["group_protection_text"],
            reply_markup=kb,
            parse_mode="HTML",
        )
        asyncio.create_task(_delete_after(sent, delay=15))
        asyncio.create_task(_delete_after(message, delay=15))


async def _delete_after(message: Message, delay: int) -> None:
    await asyncio.sleep(delay)
    with suppress(TelegramAPIError):
        await message.delete()
