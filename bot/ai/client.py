# bot/ai/client.py
"""OpenAI API — низкоуровневый async-клиент."""

import asyncio
import logging
import random

import aiohttp

from bot.core.config import settings

logger = logging.getLogger(__name__)

_API_URL = "https://api.openai.com/v1/chat/completions"
_TIMEOUT = aiohttp.ClientTimeout(total=90)

_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_BACKOFF_BASE = 1.0


async def cf_chat(
    model: str,
    messages: list[dict],
    max_tokens: int = 300,
    response_format: dict | None = None,
) -> dict | None:
    """Отправляет chat-запрос в OpenAI API с ретраями.

    Возвращает структуру совместимую с ранее используемым Cloudflare API:
        {"result": {"response": "<text>"}}
    или None при ошибке.

    Никогда не бросает исключений.
    """
    if not settings.ai_available:
        return None

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "model": model,
        "messages": messages,
        # gpt-5 / gpt-5-mini: используют max_completion_tokens; temperature не поддерживается
        "max_completion_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
                async with http.post(_API_URL, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        choice = (data.get("choices") or [{}])[0]
                        finish = choice.get("finish_reason", "")
                        text = choice.get("message", {}).get("content") or ""

                        # Если модель завершила по причине рассуждения — контент
                        # может быть в reasoning поле (o-series compatible)
                        if not text:
                            text = choice.get("message", {}).get("reasoning") or ""

                        logger.debug(
                            "OpenAI OK | model=%s finish=%s len=%d",
                            model, finish, len(text),
                        )
                        if not text:
                            logger.warning(
                                "OpenAI вернул пустой content | finish=%s | raw=%s",
                                finish,
                                str(data)[:500],
                            )
                        return {"result": {"response": text}}

                    body = await resp.text()
                    logger.warning(
                        "OpenAI HTTP %d (попытка %d/%d): %s",
                        resp.status, attempt, _MAX_ATTEMPTS, body[:400],
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
                return None

        if attempt < _MAX_ATTEMPTS:
            delay = _BACKOFF_BASE * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            await asyncio.sleep(delay)

    return None
