# bot/ai/client.py
"""Cloudflare Workers AI — низкоуровневый HTTP-клиент."""

import asyncio
import logging
import random

import aiohttp

from bot.core.config import settings

logger = logging.getLogger(__name__)

_API_URL = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
_TIMEOUT = aiohttp.ClientTimeout(total=25)

# Ретраи: один сбойный HTTP-запрос не должен убивать всю ветку оценки.
# Статусы, которые есть смысл повторять (временные сбои CF / rate limit).
_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3        # 1 основной + 2 ретрая
_BACKOFF_BASE = 1.0      # секунды: 1s, 2s (+ джиттер до 0.5s)


async def cf_chat(
    model: str,
    messages: list[dict],
    max_tokens: int = 300,
) -> dict | None:
    """Отправляет chat-запрос в Cloudflare Workers AI с ретраями.

    До _MAX_ATTEMPTS попыток с экспоненциальным backoff между ними.
    Возвращает распарсенный JSON-ответ или None, если все попытки исчерпаны.
    Никогда не бросает исключений.
    """
    if not settings.ai_available:
        return None

    url = _API_URL.format(
        account_id=settings.cloudflare_account_id,
        model=model,
    )
    payload = {"messages": messages, "max_tokens": max_tokens}
    headers = {"Authorization": f"Bearer {settings.cloudflare_api_token}"}

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
                async with http.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        return await resp.json()

                    body = await resp.text()
                    logger.warning(
                        "Workers AI HTTP %d (попытка %d/%d): %s",
                        resp.status, attempt, _MAX_ATTEMPTS, body[:300],
                    )
                    # 4xx (кроме 408/429) — ошибка запроса, ретрай бессмысленен
                    if resp.status not in _RETRYABLE_STATUSES:
                        return None
        except Exception as e:
            logger.warning(
                "Ошибка Workers AI (попытка %d/%d): %s",
                attempt, _MAX_ATTEMPTS, e,
            )
            if attempt == _MAX_ATTEMPTS:
                logger.error("Workers AI: все попытки исчерпаны", exc_info=True)

        # Backoff перед следующей попыткой
        if attempt < _MAX_ATTEMPTS:
            delay = _BACKOFF_BASE * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            await asyncio.sleep(delay)

    return None
