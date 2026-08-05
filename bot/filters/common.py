# bot/filters/common.py

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

_CANCEL_TEXTS: frozenset[str] = frozenset({
    "❌ Отменить заполнение",
    "❌ Bekor qilish",
})

class IsCancelMessage(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.text in _CANCEL_TEXTS

class IsPrivateChat(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        if isinstance(event, CallbackQuery):
            return event.message.chat.type == "private" if event.message else True
        return event.chat.type == "private"
