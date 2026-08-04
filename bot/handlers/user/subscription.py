# bot/handlers/user/subscription.py

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import requests as db
from bot.lexicon import LOCALIZATION
from bot.middlewares.auth import build_subscribe_keyboard, is_subscribed

router = Router()


@router.callback_query(lambda c: c.data == "check_subscription")
async def handle_check_subscription(
    callback: CallbackQuery,
    session: AsyncSession,
    lang: str | None = None,
) -> None:
    if not lang:
        lang = await db.get_user_lang(session, callback.from_user.id) or "ru"

    if await is_subscribed(callback.bot, callback.from_user.id):
        try:
            await callback.message.edit_text(LOCALIZATION[lang]["subscription_confirmed"], parse_mode="HTML")
        except TelegramBadRequest:
            pass
        await callback.answer(LOCALIZATION[lang]["subscription_confirmed_alert"])
    else:
        await callback.answer(LOCALIZATION[lang]["subscription_not_done"], show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=build_subscribe_keyboard(lang))
        except TelegramBadRequest:
            pass
