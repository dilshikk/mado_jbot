# bot/middlewares/throttling.py

import logging
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

logger = logging.getLogger(__name__)

_MESSAGE_LIMIT    = 5
_CALLBACK_LIMIT   = 10
_WINDOW_SECONDS   = 5
_COOLDOWN_SECONDS = 15


class RateLimitMiddleware(BaseMiddleware):
    """Защита от спама: не более N событий за окно времени."""

    def __init__(self) -> None:
        self._msg_history: dict[int, list[float]] = defaultdict(list)
        self._cb_history:  dict[int, list[float]] = defaultdict(list)
        self._warned_at:   dict[int, float]        = {}

    async def __call__(
        self,
        handler: Callable[..., Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        user = event.from_user
        if not user:
            return await handler(event, data)
        user_id = user.id
        now     = time.monotonic()

        if isinstance(event, Message):
            limited = self._is_limited(self._msg_history, user_id, now, _MESSAGE_LIMIT)
        else:
            limited = self._is_limited(self._cb_history, user_id, now, _CALLBACK_LIMIT)

        if not limited:
            return await handler(event, data)

        last_warn = self._warned_at.get(user_id, 0)
        if now - last_warn >= _COOLDOWN_SECONDS:
            self._warned_at[user_id] = now
            logger.warning("Rate limit: user_id=%d", user_id)
            if isinstance(event, Message):
                await event.answer(f"⚠️ Слишком быстро. Подождите {_COOLDOWN_SECONDS} секунд.")
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    f"⚠️ Слишком много нажатий. Подождите {_COOLDOWN_SECONDS} сек.",
                    show_alert=True,
                )
        return None

    @staticmethod
    def _is_limited(history: dict[int, list[float]], user_id: int, now: float, limit: int) -> bool:
        window_start     = now - _WINDOW_SECONDS
        history[user_id] = [t for t in history[user_id] if t > window_start]
        history[user_id].append(now)
        return len(history[user_id]) > limit
