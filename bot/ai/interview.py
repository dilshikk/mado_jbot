# bot/ai/interview.py
"""Recruiter AI — диалоговое интервью с кандидатом."""

import json
import logging

from bot.ai.client import cf_chat
from bot.ai.models import INTERVIEW_MODEL
from bot.ai.prompts import INTERVIEW_SYSTEM

logger = logging.getLogger(__name__)

MAX_QUESTIONS = 10


def _build_messages(form_data: dict, qa_log: list[dict], lang: str) -> list[dict]:
    """Формирует историю диалога для модели."""
    lang_hint = "Общайся на русском языке." if lang == "ru" else "O'zbek tilida gaplash."

    # Системный промпт + контекст анкеты
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
    # История Q&A
    for entry in qa_log:
        messages.append({"role": "assistant", "content": entry["q"]})
        messages.append({"role": "user",      "content": entry["a"]})
    return messages


async def get_next_step(
    form_data: dict,
    qa_log: list[dict],
    lang: str,
) -> dict:
    """Возвращает следующий шаг интервью.

    Returns:
        {"done": False, "question": str} — задать следующий вопрос
        {"done": True,  "reason": str}   — интервью завершено
    """
    # Принудительное завершение при достижении лимита
    if len(qa_log) >= MAX_QUESTIONS:
        return {"done": True, "reason": f"Достигнут лимит {MAX_QUESTIONS} вопросов"}

    messages = _build_messages(form_data, qa_log, lang)
    result = await cf_chat(model=INTERVIEW_MODEL, messages=messages, max_tokens=200)
    if result is None:
        return {"done": True, "reason": "AI недоступен"}

    raw = ((result.get("result") or {}).get("response") or "").strip()

    # Пробуем распарсить JSON из ответа
    try:
        # Модель может завернуть JSON в ```json ... ```
        import re
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            if "done" in parsed:
                return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Если модель вернула просто текст — считаем это вопросом
    if raw:
        return {"done": False, "question": raw}

    return {"done": True, "reason": "Пустой ответ AI"}
