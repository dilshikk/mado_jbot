# bot/handlers/user/subscription.py

from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from bot.db import database as db
from bot.messages import LOCALIZATION
from bot.middlewares.subscription import _build_subscribe_keyboard, _is_subscribed

router = Router()


@router.callback_query(lambda c: c.data == "check_subscription")
async def handle_check_subscription(callback: CallbackQuery, lang: str = None) -> None:
    if not lang:
        lang = db.get_user_lang(callback.from_user.id) or "ru"
    user_id = callback.from_user.id
    if await _is_subscribed(callback.bot, user_id):
        try:
            await callback.message.edit_text(LOCALIZATION[lang]["subscription_confirmed"], parse_mode="HTML")
        except TelegramBadRequest:
            pass
        await callback.answer(LOCALIZATION[lang]["subscription_confirmed_alert"])
    else:
        await callback.answer(LOCALIZATION[lang]["subscription_not_done"], show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=_build_subscribe_keyboard(lang))
        except TelegramBadRequest:
            pass
