# bot/handlers/errors.py

import logging
from contextlib import suppress
from typing import Any

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ErrorEvent

from bot.core.config import ADMIN_CHAT_ID

router = Router()
logger = logging.getLogger(__name__)


@router.error()
async def error_handler(event: ErrorEvent, data: dict[str, Any]) -> None:
    """Глобальный обработчик необработанных ошибок."""
    logger.exception(
        "Необработанная ошибка при обработке update_id=%s: %s",
        event.update.update_id, event.exception,
        exc_info=event.exception,
    )
    bot = data.get("bot")
    if not bot:
        return
    with suppress(TelegramAPIError):
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"🔴 <b>Ошибка в боте</b>\n\n"
                f"<code>{type(event.exception).__name__}: {event.exception}</code>\n\n"
                f"update_id: <code>{event.update.update_id}</code>"
            ),
            parse_mode="HTML",
        )
