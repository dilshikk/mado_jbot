# bot/handlers/errors.py
"""Глобальный обработчик необработанных исключений."""

import logging

from aiogram import Router
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.types import ErrorEvent

router = Router()
logger = logging.getLogger(__name__)

# Сетевые ошибки — временные, логируем только как WARNING без traceback
_NETWORK_ERRORS = (
    "Connection reset by peer",
    "ClientOSError",
    "ServerDisconnectedError",
    "TimeoutError",
    "ClientConnectorError",
)


@router.errors()
async def handle_errors(event: ErrorEvent) -> None:
    exc = event.exception

    # Flood control — aiogram сам обрабатывает, просто логируем
    if isinstance(exc, TelegramRetryAfter):
        logger.warning("Flood control: повтор через %d сек.", exc.retry_after)
        return

    # Сетевые разрывы — временно, не нужен traceback
    if isinstance(exc, TelegramNetworkError):
        msg = str(exc)
        if any(e in msg for e in _NETWORK_ERRORS):
            logger.warning(
                "Сетевая ошибка (временная) при update_id=%s: %s",
                getattr(event.update, "update_id", "?"),
                msg,
            )
            return

    # Всё остальное — полный traceback
    logger.error(
        "Необработанная ошибка при обработке update_id=%s: %s",
        getattr(event.update, "update_id", "?"),
        exc,
        exc_info=exc,
    )
