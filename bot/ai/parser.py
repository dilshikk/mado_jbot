# bot/ai/parser.py
"""JSON-парсер ответов Cloudflare Workers AI."""

import json
import logging
import re

logger = logging.getLogger(__name__)


def extract_text(result: dict) -> str | None:
    """Извлекает текстовый ответ из стандартного ответа CF Workers AI."""
    text = (result.get("result") or {}).get("response")
    if not text:
        logger.warning("Workers AI вернул пустой ответ: %s", str(result)[:300])
        return None
    return text.strip()


def extract_json(result: dict) -> dict | None:
    """Извлекает и парсит JSON из текстового ответа модели.

    Модель может обернуть JSON в markdown-блок ```json ... ```,
    эта функция аккуратно его вырезает.
    """
    text = extract_text(result)
    if not text:
        return None

    # Пробуем найти JSON-блок внутри ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = match.group(1) if match else text

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Не удалось распарсить JSON из ответа AI: %s | текст: %s", e, text[:300])
        return None
