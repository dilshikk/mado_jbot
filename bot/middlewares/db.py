# bot/middlewares/db.py

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.db.base import session_pool


class DbSessionMiddleware(BaseMiddleware):
    """Создаёт AsyncSession на каждый update и прокидывает в хендлеры как data['session']."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with session_pool() as session:
            data["session"] = session
            return await handler(event, data)
