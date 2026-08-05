# bot/ai/interview.py
"""Recruiter AI — диалоговое интервью с кандидатом."""

import ast
import json
import logging
import re

from bot.ai.client import cf_chat
from bot.ai.models import INTERVIEW_MODEL
from bot.ai.prompts import INTERVIEW_SYSTEM

logger = logging.getLogger(__name__)

MAX_QUESTIONS = 10


def _extract_text(result: dict) -> str:
    """Извлекает текст ответа из структуры CF API."""
    inner = (result.get("result") or {}).get("response") or ""
    if isinstance(inner, dict):
        inner = inner.get("content") or inner.get("text") or str(inner)
    return str(inner).strip()


def _parse_step(raw: str) -> dict | None:
    """Пробует распарсить JSON или Python-dict из строки ответа модели.

    Модель может вернуть:
      - валидный JSON:      {"done": false, "question": "..."}
      - Python-литерал:     {'done': False, 'question': '...'}
      - просто текст вопроса
    """
    # 1. Ищем фигурные скобки в любом месте строки
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None

    candidate = match.group()

    # 2. Пробуем JSON (стандарт)
    try:
        parsed = json.loads(candidate)
        if "done" in parsed:
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # 3. Пробуем Python-literal_eval (одинарные кавычки, True/False)
    try:
        # json.loads не понимает одинарные кавычки и Python-булы
        parsed = ast.literal_eval(candidate)
        if isinstance(parsed, dict) and "done" in parsed:
            return parsed
    except (ValueError, SyntaxError):
        pass

    return None


def _build_messages(form_data: dict, qa_log: list[dict], lang: str) -> list[dict]:
    lang_hint = "Общайся на русском языке." if lang == "ru" else "O'zbek tilida gaplash."
    context = (
        f"Язык кандидата: {lang_hint}\n"
        f"Вакансия: {form_data.get('position', '—')}\n"
        f"Опыт: {form_data.get('experience', '—')}\n"
        f"Гражданство: {form_data.get('citizenship', '—')}\n"
        f"Вопросов задано: {len(qa_log)} из {MAX_QUESTIONS}\n"
    )
    messages: list[dict] = [
        {"role": "system", "content": f"{INTERVIEW_SYSTEM}\n\n{context}"},
    ]
    for entry in qa_log:
        messages.append({"role": "assistant", "content": entry["q"]})
        messages.append({"role": "user",      "content": entry["a"]})
    return messages


async def get_next_step(
    form_data: dict,
    qa_log: list[dict],
    lang: str,
) -> dict:
    """Возвращает следующий шаг интервью."""
    if len(qa_log) >= MAX_QUESTIONS:
        return {"done": True, "reason": f"Достигнут лимит {MAX_QUESTIONS} вопросов"}

    messages = _build_messages(form_data, qa_log, lang)
    result = await cf_chat(model=INTERVIEW_MODEL, messages=messages, max_tokens=300)

    if result is None:
        logger.warning("cf_chat вернул None — интервью завершается")
        return {"done": True, "reason": "AI недоступен"}

    raw = _extract_text(result)
    logger.debug("CF raw ответ (интервью): %r", raw[:300] if raw else "<пусто>")

    if not raw:
        return {"done": True, "reason": "Пустой ответ AI"}

    # Пробуем распарсить структурированный ответ
    parsed = _parse_step(raw)
    if parsed is not None:
        done = parsed.get("done", False)
        if done:
            return {"done": True, "reason": parsed.get("reason", "AI завершил интервью")}
        question = parsed.get("question", "").strip()
        if question:
            return {"done": False, "question": question}

    # Модель вернула просто текст — это и есть вопрос
    return {"done": False, "question": raw}
