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

# ── Локализованные метки полей анкеты ────────────────────────────────────────
_FIELD_LABELS_RU = [
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

_FIELD_LABELS_UZ = [
    ("name",           "F.I.Sh."),
    ("birthday",       "Tug'ilgan sana"),
    ("gender",         "Jinsi"),
    ("phone",          "Telefon"),
    ("metro",          "Metro"),
    ("languages",      "Tillar"),
    ("readiness",      "Ishga tayyorlik"),
    ("experience",     "Tajriba"),
    ("exp_company",    "Ish joyi"),
    ("exp_position",   "Oldingi lavozim"),
    ("exp_duration",   "Ish staji"),
    ("salary",         "Ish haqi kutilmalari"),
    ("schedule",       "Grafik"),
    ("evening_shifts", "Kechki smenalar"),
    ("weekends",       "Dam olish kunlari"),
    ("smoking",        "Chekish"),
    ("med_book",       "Tibbiy daftar"),
]

# ── Локализованные тексты контекста ──────────────────────────────────────────
_CTX = {
    "ru": {
        "lang_hint":        "Общайся ТОЛЬКО на русском языке. Не переходи на узбекский.",
        "vacancy":          "Вакансия",
        "known_header":     "ДАННЫЕ ИЗ АНКЕТЫ (эти вопросы не задавай)",
        "no_data":          "(нет данных)",
        "status_header":    "СТАТУС ИНТЕРВЬЮ",
        "asked":            "Вопросов задано",
        "covered_prefix":   "Уже раскрытые темы",
        "not_covered":      "Темы ещё не раскрывались.",
        "hard_limit":       "Абсолютный лимит",
        "questions":        "вопросов",
        "instruction":      (
            "Проанализируй историю диалога, определи первую нераскрытую обязательную\n"
            "компетенцию для вакансии «{position}» и сформулируй следующий вопрос.\n"
            "Если все обязательные компетенции раскрыты — верни {{\"done\": true}}."
        ),
    },
    "uz": {
        "lang_hint":        "FAQAT o'zbek tilida gaplash. Rus tiliga o'tma.",
        "vacancy":          "Vakansiya",
        "known_header":     "ANKETA MA'LUMOTLARI (bu savollarni qayta so'rama)",
        "no_data":          "(ma'lumot yo'q)",
        "status_header":    "INTERVYU HOLATI",
        "asked":            "Berilgan savollar soni",
        "covered_prefix":   "Allaqachon ochilgan mavzular",
        "not_covered":      "Mavzular hali ochilmagan.",
        "hard_limit":       "Mutlaq chegara",
        "questions":        "savol",
        "instruction":      (
            "Muloqot tarixini tahlil qil, «{position}» vakansiyasi uchun birinchi ochilmagan\n"
            "majburiy kompetensiyani aniqlang va keyingi savolni tuzib ber.\n"
            "Agar barcha majburiy kompetensiyalar ochilgan bo'lsa — {{\"done\": true}} qaytara."
        ),
    },
}


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
    t = _CTX.get(lang, _CTX["ru"])
    field_map = _FIELD_LABELS_UZ if lang == "uz" else _FIELD_LABELS_RU
    position = form_data.get("position", "—")

    # ── Данные анкеты ────────────────────────────────────────────────────────
    known_fields = []
    for key, label in field_map:
        val = form_data.get(key)
        if val and val != "—":
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            known_fields.append(f"  {label}: {val}")

    known_section = "\n".join(known_fields) if known_fields else f"  {t['no_data']}"

    # ── Раскрытые темы ───────────────────────────────────────────────────────
    covered_topics: list[str] = []
    for entry in qa_log:
        topic = entry.get("topic", "")
        if topic and topic not in covered_topics:
            covered_topics.append(topic)
    covered_str = (
        t["covered_prefix"] + ": " + ", ".join(covered_topics)
        if covered_topics else
        t["not_covered"]
    )

    instruction = t["instruction"].format(position=position)

    context = (
        f"lang={lang}\n"
        f"{t['lang_hint']}\n"
        f"{t['vacancy']}: {position}\n"
        f"\n--- {t['known_header']} ---\n"
        f"{known_section}\n"
        f"---\n"
        f"\n--- {t['status_header']} ---\n"
        f"{t['asked']}: {len(qa_log)}.\n"
        f"{covered_str}\n"
        f"{t['hard_limit']}: {HARD_MAX_QUESTIONS} {t['questions']}.\n"
        f"---\n"
        f"\n{instruction}\n"
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
