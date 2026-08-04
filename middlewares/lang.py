# middlewares/lang.py

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

import database as db


class LangMiddleware(BaseMiddleware):
    """
    Определяет язык пользователя и прокидывает его в хендлеры через data['lang'].

    Приоритет источников:
      1. БД — основной source of truth (пользователь уже зарегистрирован)
      2. FSM state — используется только при первом выборе языка (/start)
      3. Fallback — "ru"

    Это избавляет от повторного `state.get_data().get('lang', 'ru')` в каждом хендлере.
    """

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        lang = await self._resolve_lang(event, data)
        data["lang"] = lang
        return await handler(event, data)

    @staticmethod
    async def _resolve_lang(event: Message, data: dict[str, Any]) -> str:
        user_id = event.from_user.id if event.from_user else None

        # 1. БД — приоритет, пользователь уже зарегистрирован
        if user_id:
            db_lang = db.get_user_lang(user_id)
            if db_lang in ("ru", "uz"):
                return db_lang

        # 2. FSM state — только при первичном выборе языка
        state = data.get("state")
        if state:
            state_data = await state.get_data() or {}
            state_lang = state_data.get("lang")
            if state_lang in ("ru", "uz"):
                return state_lang

        # 3. Fallback
        return "ru"
