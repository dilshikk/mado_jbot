# bot/ai/client.py
"""OpenAI API — низкоуровневый async-клиент."""

import asyncio
import logging
import random

import aiohttp

from bot.core.config import settings

logger = logging.getLogger(__name__)

_API_URL = "https://api.openai.com/v1/chat/completions"
_TIMEOUT = aiohttp.ClientTimeout(total=60)

_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_BACKOFF_BASE = 1.0


async def cf_chat(
    model: str,
    messages: list[dict],
    max_tokens: int = 300,
) -> dict | None:
    """Отправляет chat-запрос в OpenAI API с ретраями.

    До _MAX_ATTEMPTS попыток с экспоненциальным backoff между ними.
    Возвращает распарсенный JSON-ответ в формате, совместимом с ранее
    используемым Cloudflare Workers AI (result.result.response), или None.
    Никогда не бросает исключений.
    """
    if not settings.ai_available:
        return None

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    # gpt-5 / gpt-5-mini: не поддерживают max_tokens и temperature != 1
    payload = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": max_tokens,
    }

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
                async with http.post(_API_URL, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Оборачиваем в формат, совместимый с Cloudflare:
                        # parser.py ожидает data["result"]["response"]
                        text = (
                            data.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "")
                        )
                        return {"result": {"response": text}}

                    body = await resp.text()
                    logger.warning(
                        "OpenAI HTTP %d (попытка %d/%d): %s",
                        resp.status, attempt, _MAX_ATTEMPTS, body[:300],
                    )
                    if resp.status not in _RETRYABLE_STATUSES:
                        return None
        except Exception as e:
            logger.warning(
                "Ошибка OpenAI API (попытка %d/%d): %s",
                attempt, _MAX_ATTEMPTS, e,
            )
            if attempt == _MAX_ATTEMPTS:
                logger.error("OpenAI API: все попытки исчерпаны", exc_info=True)

        if attempt < _MAX_ATTEMPTS:
            delay = _BACKOFF_BASE * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            await asyncio.sleep(delay)

    return None
