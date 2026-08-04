# bot/ai/client.py
"""Cloudflare Workers AI — низкоуровневый HTTP-клиент."""

import logging

import aiohttp

from bot.core.config import settings

logger = logging.getLogger(__name__)

_API_URL = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
_TIMEOUT = aiohttp.ClientTimeout(total=25)


async def cf_chat(
    model: str,
    messages: list[dict],
    max_tokens: int = 300,
) -> dict | None:
    """Отправляет chat-запрос в Cloudflare Workers AI.

    Возвращает распарсенный JSON-ответ или None при ошибке.
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

    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
            async with http.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("Workers AI HTTP %d: %s", resp.status, body[:300])
                    return None
                return await resp.json()
    except Exception as e:
        logger.error("Ошибка Workers AI: %s", e, exc_info=True)
        return None
