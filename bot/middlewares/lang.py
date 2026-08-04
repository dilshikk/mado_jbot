# bot/middlewares/lang.py

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.db import database as db


class LangMiddleware(BaseMiddleware):
    """
    Определяет язык пользователя и прокидывает его в хендлеры через data['lang'].
    Приоритет: 1) БД, 2) FSM state, 3) Fallback 'ru'
    """

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        data["lang"] = await self._resolve_lang(event, data)
        return await handler(event, data)

    @staticmethod
    async def _resolve_lang(event: Message, data: dict[str, Any]) -> str:
        user_id = event.from_user.id if event.from_user else None
        if user_id:
            db_lang = db.get_user_lang(user_id)
            if db_lang in ("ru", "uz"):
                return db_lang
        state = data.get("state")
        if state:
            state_data = await state.get_data() or {}
            state_lang = state_data.get("lang")
            if state_lang in ("ru", "uz"):
                return state_lang
        return "ru"
