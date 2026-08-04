# middlewares/rate_limit.py

import time
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

logger = logging.getLogger(__name__)

# Лимиты: сколько запросов разрешено за окно времени
_MESSAGE_LIMIT  = 5    # сообщений
_CALLBACK_LIMIT = 10   # callback-нажатий
_WINDOW_SECONDS = 5    # за 5 секунд

# Cooldown при превышении лимита (секунды)
_COOLDOWN_SECONDS = 15


class RateLimitMiddleware(BaseMiddleware):
    """
    Защита от спама: ограничивает частоту запросов от одного пользователя.

    - Сообщения: не более _MESSAGE_LIMIT за _WINDOW_SECONDS секунд
    - Callback-кнопки: не более _CALLBACK_LIMIT за _WINDOW_SECONDS секунд
    - При превышении: запрос игнорируется, пользователь получает предупреждение
      (но не чаще одного раза в _COOLDOWN_SECONDS секунд)
    """

    def __init__(self) -> None:
        # {user_id: [timestamp, ...]} — скользящее окно запросов
        self._msg_history:  dict[int, list[float]] = defaultdict(list)
        self._cb_history:   dict[int, list[float]] = defaultdict(list)
        # {user_id: timestamp} — когда последний раз предупреждали
        self._warned_at:    dict[int, float]        = {}

    # ── Общий вход ────────────────────────────────────────────────────────────

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

        # Предупреждаем не чаще раза в _COOLDOWN_SECONDS
        last_warn = self._warned_at.get(user_id, 0)
        if now - last_warn >= _COOLDOWN_SECONDS:
            self._warned_at[user_id] = now
            logger.warning("Rate limit: user_id=%d превысил лимит запросов", user_id)

            if isinstance(event, Message):
                await event.answer(
                    f"⚠️ Вы отправляете сообщения слишком быстро.\n"
                    f"Подождите {_COOLDOWN_SECONDS} секунд."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    f"⚠️ Слишком много нажатий. Подождите {_COOLDOWN_SECONDS} сек.",
                    show_alert=True,
                )

        # Запрос блокируется — handler не вызывается
        return None

    # ── Скользящее окно ───────────────────────────────────────────────────────

    @staticmethod
    def _is_limited(
        history: dict[int, list[float]],
        user_id: int,
        now: float,
        limit: int,
    ) -> bool:
        """
        Удаляет устаревшие записи и проверяет, превышен ли лимит.
        Возвращает True если лимит превышен.
        """
        window_start = now - _WINDOW_SECONDS
        timestamps   = history[user_id]

        # Убираем записи старше окна
        history[user_id] = [t for t in timestamps if t > window_start]
        history[user_id].append(now)

        return len(history[user_id]) > limit
