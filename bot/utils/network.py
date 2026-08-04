# bot/utils/network.py

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from aiogram.exceptions import TelegramNetworkError

logger = logging.getLogger(__name__)
T = TypeVar("T")


async def safe_call(
    factory: Callable[[], Coroutine[Any, Any, T]],
    retries: int = 3,
    delay: float = 1.5,
) -> T | None:
    """
    Retry-обёртка для Telegram API вызовов при сетевых сбоях.
    Принимает callable (лямбду), а не корутину — корутина одноразовая.
    """
    for attempt in range(retries):
        try:
            return await factory()
        except TelegramNetworkError as e:
            logger.warning("Сетевой сбой (попытка %d/%d): %s", attempt + 1, retries, e)
            if attempt < retries - 1:
                await asyncio.sleep(delay * (attempt + 1))
    logger.error("safe_call: все %d попытки исчерпаны.", retries)
    return None
