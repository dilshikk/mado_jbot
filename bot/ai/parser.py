# bot/ai/parser.py
"""Утилиты для разбора ответов Cloudflare Workers AI."""

import logging

logger = logging.getLogger(__name__)


def extract_text(result: dict | None) -> str | None:
    """Извлекает текст ответа из структуры CF API.

    CF может вернуть разные форматы:
      {"result": {"response": "текст"}}
      {"result": {"response": {"content": "текст"}}}
      {"result": {"response": [{"content": "текст"}]}}   # некоторые модели
    """
    if not result:
        return None

    inner = (result.get("result") or {}).get("response")

    if inner is None:
        logger.debug("CF ответ не содержит response: %r", result)
        return None

    # Строка — самый частый случай
    if isinstance(inner, str):
        text = inner.strip()
        return text if text else None

    # Dict — некоторые модели оборачивают в объект
    if isinstance(inner, dict):
        text = (
            inner.get("content")
            or inner.get("text")
            or inner.get("message")
            or str(inner)
        )
        return str(text).strip() or None

    # List — chat-completion формат
    if isinstance(inner, list) and inner:
        first = inner[0]
        if isinstance(first, dict):
            text = (
                first.get("content")
                or first.get("text")
                or ""
            )
            return str(text).strip() or None

    logger.warning("Неизвестный формат CF response: %r", type(inner))
    return str(inner).strip() or None
