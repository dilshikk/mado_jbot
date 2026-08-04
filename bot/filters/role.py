# bot/filters/role.py

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from bot.core.config import ADMIN_IDS


class IsAdmin(BaseFilter):
    """True если отправитель — администратор бота (ID в ADMIN_IDS)."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return bool(user and user.id in ADMIN_IDS)
