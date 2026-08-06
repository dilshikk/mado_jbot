# bot/ai/interview.py
"""Recruiter AI — диалоговое интервью с кандидатом.

Вопросы генерируются моделью динамически на основе компетенций вакансии
и истории диалога. Нет фиксированного списка вопросов и нет MAX_QUESTIONS.
"""

import ast
import json
import logging
import re

from bot.ai.client import cf_chat
from bot.ai.models import INTERVIEW_MODEL
from bot.ai.parser import extract_text
from bot.ai.prompts import INTERVIEW_SYSTEM

logger = logging.getLogger(__name__)

MIN_QUESTIONS = 5
# Абсолютный лимит — защита от бесконечного интервью.
# Модель сама завершает интервью по компетенциям, но не более этого.
HARD_MAX_QUESTIONS = 25


def _parse_step(raw: str) -> dict | None:
    """Пробует распарсить JSON или Python-dict из строки ответа модели."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    candidate = match.group()
    try:
        parsed = json.loads(candidate)
        if "done" in parsed:
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        parsed = ast.literal_eval(candidate)
        if isinstance(parsed, dict) and "done" in parsed:
            return parsed
    except (ValueError, SyntaxError):
        pass
    return None


def _build_messages(form_data: dict, qa_log: list[dict], lang: str) -> list[dict]:
    lang_hint = "Общайся на русском языке." if lang == "ru" else "O'zbek tilida gaplash."
    position  = form_data.get("position", "—")

    # ── Данные анкеты (AI не должен спрашивать их повторно) ──────────────────
    field_map = [
        ("name",           "ФИО"),
        ("birthday",       "Дата рождения"),
        ("gender",         "Пол"),
        ("phone",          "Телефон"),
        ("metro",          "Метро"),
        ("languages",      "Языки"),
        ("readiness",      "Готовность к работе"),
        ("experience",     "Опыт"),
        ("exp_company",    "Место работы"),
        ("exp_position",   "Должность в прошлом"),
        ("exp_duration",   "Стаж"),
        ("salary",         "Зарплатные ожидания"),
        ("schedule",       "График"),
        ("evening_shifts", "Вечерние смены"),
        ("weekends",       "Выходные и праздники"),
        ("smoking",        "Курение"),
        ("med_book",       "Медкнижка"),
    ]
    known_fields = []
    for key, label in field_map:
        val = form_data.get(key)
        if val and val != "—":
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            known_fields.append(f"  {label}: {val}")

    known_section = "\n".join(known_fields) if known_fields else "  (нет данных)"

    # ── История Q&A — раскрытые темы ─────────────────────────────────────────
    covered_topics: list[str] = []
    for entry in qa_log:
        topic = entry.get("topic", "")
        if topic and topic not in covered_topics:
            covered_topics.append(topic)
    covered_str = (
        "Уже раскрытые темы: " + ", ".join(covered_topics)
        if covered_topics else
        "Темы ещё не раскрывались."
    )

    context = (
        f"Язык кандидата: {lang_hint}\n"
        f"Вакансия: {position}\n"
        f"\n--- ДАННЫЕ ИЗ АНКЕТЫ (эти вопросы не задавай) ---\n"
        f"{known_section}\n"
        f"---\n"
        f"\n--- СТАТУС ИНТЕРВЬЮ ---\n"
        f"Вопросов задано: {len(qa_log)}.\n"
        f"{covered_str}\n"
        f"Абсолютный лимит: {HARD_MAX_QUESTIONS} вопросов.\n"
        f"---\n"
        f"\nПроанализируй историю диалога, определи первую нераскрытую обязательную\n"
        f"компетенцию для вакансии «{position}» и сформулируй следующий вопрос.\n"
        f"Если все обязательные компетенции раскрыты — верни {{\"done\": true}}.\n"
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
    """Возвращает следующий шаг интервью.

    Модель сама решает когда завершать — по раскрытым компетенциям.
    Абсолютный лимит HARD_MAX_QUESTIONS защищает от бесконечного интервью.
    """
    if len(qa_log) >= HARD_MAX_QUESTIONS:
        return {
            "done": True,
            "reason": f"Достигнут абсолютный лимит {HARD_MAX_QUESTIONS} вопросов",
        }

    messages = _build_messages(form_data, qa_log, lang)
    result = await cf_chat(model=INTERVIEW_MODEL, messages=messages, max_tokens=400)

    if result is None:
        logger.warning("cf_chat вернул None — интервью завершается")
        return {"done": True, "reason": "AI недоступен"}

    raw = extract_text(result) or ""
    logger.debug("CF raw ответ (интервью): %r", raw[:400] if raw else "<пусто>")

    if not raw:
        return {"done": True, "reason": "Пустой ответ AI"}

    parsed = _parse_step(raw)
    if parsed is not None:
        if parsed.get("done"):
            return {
                "done": True,
                "reason": parsed.get("reason", "AI завершил интервью"),
            }
        question = parsed.get("question", "").strip()
        if question:
            return {
                "done": False,
                "question": question,
                "topic": parsed.get("topic", ""),
                "reason": parsed.get("reason", ""),
            }

    # Если модель ответила текстом без JSON — используем как вопрос
    return {"done": False, "question": raw, "topic": "", "reason": ""}
