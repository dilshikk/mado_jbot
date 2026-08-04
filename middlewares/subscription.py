import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import database as db
from config import REQUIRED_CHANNEL
from messages import LOCALIZATION

logger = logging.getLogger(__name__)

SUBSCRIBED_STATUSES = {
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.CREATOR,
}

_FREE_COMMANDS  = {"/start", "/help"}
_FREE_TEXTS     = {"🇷🇺 Русский", "🇺🇿 O'zbekcha", "🌐 Сменить язык", "🌐 Tilni o'zgartirish"}
_FREE_CALLBACKS = {"check_subscription"}


def _build_subscribe_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=LOCALIZATION[lang]["btn_subscribe_channel"],
                url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}",
            )],
            [InlineKeyboardButton(
                text=LOCALIZATION[lang]["btn_check_subscription"],
                callback_data="check_subscription",
            )],
        ]
    )


async def _is_subscribed(bot, user_id: int) -> bool:
    if not REQUIRED_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        return member.status in SUBSCRIBED_STATUSES
    except TelegramAPIError:
        logger.warning(
            "Не удалось проверить подписку на канал %s. "
            "Убедитесь, что бот добавлен в канал как администратор.",
            REQUIRED_CHANNEL,
        )
        return True


class SubscriptionMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable[..., Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        # Callback: пропускаем whitelist
        if isinstance(event, CallbackQuery):
            if event.data in _FREE_CALLBACKS:
                return await handler(event, data)
            if event.message and event.message.chat.type != "private":
                return await handler(event, data)

        # Message: только приватные + whitelist
        if isinstance(event, Message):
            if event.chat.type != "private":
                return await handler(event, data)
            text = (event.text or "").strip()
            if text in _FREE_TEXTS or any(text.startswith(c) for c in _FREE_COMMANDS):
                return await handler(event, data)

        # Проверка подписки
        user_id = event.from_user.id
        lang    = db.get_user_lang(user_id) or "ru"
        bot     = data["bot"]

        if await _is_subscribed(bot, user_id):
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer(
                LOCALIZATION[lang]["subscription_not_subscribed"],
                reply_markup=_build_subscribe_keyboard(lang),
                parse_mode="HTML",
            )
        elif isinstance(event, CallbackQuery):
            await event.answer(
                LOCALIZATION[lang]["subscription_not_done"],
                show_alert=True,
            )
        return
