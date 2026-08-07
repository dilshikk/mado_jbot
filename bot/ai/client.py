# bot/ai/client.py
"""OpenAI Responses API — низкоуровневый async-клиент.

Перешёл с POST /v1/chat/completions на POST /v1/responses:
- лучшая поддержка GPT-5 / GPT-5-mini;
- structured outputs через text.format.json_schema (strict=True);
- логирование времени запроса и потребления токенов.

Технические детали:
- Один модульный aiohttp.ClientSession с TCPConnector (limit=20) —
  создаётся при первом запросе и переиспользуется для всех последующих запросов.
- retry с экспоненциальным бэкоффом для 408/429/5xx.
- max_output_tokens включает reasoning_tokens + content_tokens
  (обязательно для reasoning-моделей GPT-5/GPT-5-mini).
"""

import asyncio
import logging
import random
import time

import aiohttp

from bot.core.config import settings

logger = logging.getLogger(__name__)

_API_URL = "https://api.openai.com/v1/responses"
_TIMEOUT = aiohttp.ClientTimeout(total=90)

_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_BACKOFF_BASE = 1.0

# Модульный пул соединений — создаётся один раз, закрывается при shutdown.
_connector: aiohttp.TCPConnector | None = None
_session: aiohttp.ClientSession | None = None


def _get_session() -> aiohttp.ClientSession:
    global _connector, _session
    if _session is None or _session.closed:
        _connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
        _session = aiohttp.ClientSession(connector=_connector, timeout=_TIMEOUT)
    return _session


async def close_session() -> None:
    """Gracefully closes the shared session on bot shutdown."""
    global _session, _connector
    if _session and not _session.closed:
        await _session.close()
        _session = None
    if _connector and not _connector.closed:
        await _connector.close()
        _connector = None


async def cf_chat(
    model: str,
    messages: list[dict],
    max_tokens: int = 2000,
    text_format: dict | None = None,
) -> dict | None:
    """Отправляет chat-запрос через OpenAI Responses API.

    Args:
        model:       название модели (gpt-5, gpt-5-mini и др.)
        messages:    список сообщений в формате [{"role": ..., "content": ...}]
        max_tokens:  max_output_tokens (reasoning + content)
        text_format: словарь text.format, например:
                       {"type": "json_object"}
                       {"type": "json_schema", "name": "...", "strict": True, "schema": {...}}

    Returns:
        {"result": {"response": "<text>"}} или None при ошибке.
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
        "input": messages,
        "max_output_tokens": max_tokens,
    }
    if text_format:
        payload["text"] = {"format": text_format}

    http = _get_session()

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        t0 = time.monotonic()
        try:
            async with http.post(_API_URL, json=payload, headers=headers) as resp:
                elapsed = time.monotonic() - t0

                if resp.status == 200:
                    data = await resp.json()

                    # Извлекаем текст из output[].content[].text
                    # (output может содержать элементы type="reasoning" — пропускаем их)
                    text = ""
                    for item in data.get("output") or []:
                        if item.get("type") == "message":
                            for block in item.get("content") or []:
                                if block.get("type") == "output_text":
                                    text = block.get("text") or ""
                                    break
                        if text:
                            break

                    status = data.get("status", "")

                    # Логируем использование токенов (полезно для отладки)
                    usage = data.get("usage") or {}
                    in_tok = usage.get("input_tokens", 0)
                    out_tok = usage.get("output_tokens", 0)
                    reasoning_tok = (
                        (usage.get("output_tokens_details") or {})
                        .get("reasoning_tokens", 0)
                    )

                    logger.debug(
                        "OpenAI OK | model=%s status=%s len=%d "
                        "| tokens: in=%d out=%d (reasoning=%d) | %.2fs",
                        model, status, len(text),
                        in_tok, out_tok, reasoning_tok, elapsed,
                    )

                    if not text:
                        logger.warning(
                            "OpenAI вернул пустой text "
                            "| status=%s in=%d out=%d reasoning=%d "
                            "| raw_output=%s",
                            status, in_tok, out_tok, reasoning_tok,
                            str(data.get("output"))[:400],
                        )

                    return {"result": {"response": text}}

                body = await resp.text()
                elapsed = time.monotonic() - t0
                logger.warning(
                    "OpenAI HTTP %d (попытка %d/%d, %.2fs): %s",
                    resp.status, attempt, _MAX_ATTEMPTS, elapsed, body[:400],
                )
                if resp.status not in _RETRYABLE_STATUSES:
                    return None

        except Exception as e:
            elapsed = time.monotonic() - t0
            logger.warning(
                "Ошибка OpenAI API (попытка %d/%d, %.2fs): %s",
                attempt, _MAX_ATTEMPTS, elapsed, e,
            )
            if attempt == _MAX_ATTEMPTS:
                logger.error("OpenAI API: все попытки исчерпаны", exc_info=True)
                return None

        if attempt < _MAX_ATTEMPTS:
            delay = _BACKOFF_BASE * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            await asyncio.sleep(delay)

    return None
