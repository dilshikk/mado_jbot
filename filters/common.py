# filters/common.py

from aiogram.filters import BaseFilter
from aiogram.types import Message

_CANCEL_TEXTS: frozenset[str] = frozenset({
    "❌ Отменить заполнение",
    "❌ Bekor qilish",
})


class IsCancelMessage(BaseFilter):
    """True если пользователь нажал кнопку отмены."""

    async def __call__(self, message: Message) -> bool:
        return message.text in _CANCEL_TEXTS


class IsPrivateChat(BaseFilter):
    """True если сообщение отправлено в личном чате."""

    async def __call__(self, message: Message) -> bool:
        return message.chat.type == "private"
