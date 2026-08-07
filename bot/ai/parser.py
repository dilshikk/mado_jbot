# bot/ai/parser.py
"""Утилиты для разбора ответов OpenAI API.

Единая точка правды для:
  - извлечения текста из структуры ответа (extract_text)
  - извлечения JSON/Python-dict из текста модели (extract_json)

Не дублируйте эту логику в других модулях — баг-фиксы должны
долетать до всех потребителей автоматически.
"""

import ast
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def extract_text(result: dict | None) -> str | None:
    """Извлекает текст ответа из структуры API.

    Поддерживаемые форматы:
      {"result": {"response": "текст"}}           — наш wrapper для OpenAI
      {"result": {"response": {"content": "..."}}}
      {"result": {"response": [{"content": "..."}]}}
    """
    if not result:
        return None

    inner = (result.get("result") or {}).get("response")

    if inner is None:
        logger.debug("Ответ не содержит response: %r", result)
        return None

    # Строка — стандартный случай (наш OpenAI wrapper всегда возвращает str)
    if isinstance(inner, str):
        text = inner.strip()
        return text if text else None

    # Dict
    if isinstance(inner, dict):
        text = (
            inner.get("content")
            or inner.get("text")
            or inner.get("message")
            or str(inner)
        )
        return str(text).strip() or None

    # List
    if isinstance(inner, list) and inner:
        first = inner[0]
        if isinstance(first, dict):
            text = (
                first.get("content")
                or first.get("text")
                or ""
            )
            return str(text).strip() or None

    logger.warning("Неизвестный формат response: %r", type(inner))
    return str(inner).strip() or None


def extract_json(text: str) -> dict[str, Any]:
    """Извлекает JSON-объект из текста модели с тремя уровнями fallback:
    1. json.loads на вырезанный блок { ... }
    2. regex-чистка одиночных кавычек
    3. ast.literal_eval

    При полной неудаче возвращает {"error": ..., "raw": ...} — всегда dict,
    никогда не бросает исключений.
    """
    # Ищем самый внешний блок { ... }
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end <= start:
        return {"error": "no_json", "raw": text[:500]}

    chunk = text[start:end]

    # Попытка 1: стандартный json.loads
    try:
        parsed = json.loads(chunk)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Попытка 2: одиночные кавычки → двойные
    try:
        fixed = re.sub(r"(?<![\\\"])\'", '"', chunk)
        parsed = json.loads(fixed)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Попытка 3: ast.literal_eval (Python-dict)
    try:
        result = ast.literal_eval(chunk)
        if isinstance(result, dict):
            return result
    except Exception:
        pass

    logger.warning("extract_json: все попытки не удались, raw=%s", chunk[:200])
    return {"error": "invalid_json", "raw": chunk[:500]}
