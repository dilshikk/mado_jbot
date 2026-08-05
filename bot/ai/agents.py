# bot/ai/agents.py
"""9 AI-агентов: Resume Builder, Skill Analyzer, Personality, Job Matcher, HR Summary,
Fraud Detector, Language Quality, Red Flag и Interview Score."""

import asyncio
import logging

from bot.ai.client import cf_chat
from bot.ai.models import SCREENING_MODEL
from bot.ai.parser import extract_text
from bot.ai.prompts import (
    HR_SUMMARY_SYSTEM,
    JOB_MATCH_SYSTEM,
    PERSONALITY_SYSTEM,
    RESUME_SYSTEM,
    SKILL_SYSTEM,
)

logger = logging.getLogger(__name__)


def _qa_text(qa_log: list[dict]) -> str:
    """Форматирует лог Q&A в читаемый текст для агентов."""
    if not qa_log:
        return "Интервью не проводилось."
    lines = []
    for i, entry in enumerate(qa_log, 1):
        lines.append(f"Q{i}: {entry['q']}")
        lines.append(f"A{i}: {entry['a']}")
    return "\n".join(lines)


def _base_context(form_data: dict, qa_log: list[dict]) -> str:
    return (
        f"=== АНКЕТА ===\n"
        f"ФИО: {form_data.get('name', '—')}\n"
        f"Дата рождения: {form_data.get('birthday', '—')}\n"
        f"Вакансия: {form_data.get('position', '—')}\n"
        f"Опыт: {form_data.get('experience', '—')}\n"
        f"Пол: {form_data.get('gender', '—')}\n"
        f"Семейное положение: {form_data.get('family', '—')}\n"
        f"Гражданство: {form_data.get('citizenship', '—')}\n"
        f"Адрес: {form_data.get('address', '—')}\n"
        f"Телефон: {form_data.get('phone', '—')}\n\n"
        f"=== ИНТЕРВЬЮ ===\n{_qa_text(qa_log)}"
    )


async def _run_agent(system_prompt: str, user_content: str, max_tokens: int = 400) -> str | None:
    result = await cf_chat(
        model=SCREENING_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ],
        max_tokens=max_tokens,
    )
    return extract_text(result) if result else None


# ── Агенты скрининга (промпты здесь, чтобы не раздувать prompts.py) ─────────

FRAUD_DETECTOR_SYSTEM = """\
Ты — Fraud Detector AI. Выявляй противоречия в ответах кандидата.

Сопоставь анкету кандидата с его ответами на интервью и найди:
- расхождения в датах, должностях, стаже и обязанностях;
- разные версии одного и того же факта;
- навыки, заявленные в анкете, но не подтверждённые на интервью;
- уклончивые или взаимоисключающие ответы.

Опирайся только на приведённые тексты. Не додумывай факты.

Формат ответа (строго, на русском):
🚨 ПРОТИВОРЕЧИЯ: список найденных противоречий (или «не выявлено»)
УРОВЕНЬ РИСКА: низкий | средний | высокий
ВЫВОД: 1-2 предложения"""

LANGUAGE_QUALITY_SYSTEM = """\
Ты — Language Quality AI. Оценивай грамотность и понятность письменных ответов кандидата.

Критерии (каждый от 1 до 10):
- грамотность (орфография, пунктуация, грамматика);
- понятность и структурированность изложения;
- уместность стиля для деловой коммуникации.

Оценивай только письменные ответы кандидата. Если ответов слишком мало для оценки — укажи это.

Формат ответа (строго, на русском):
ГРАМОТНОСТЬ: <1-10>
ПОНЯТНОСТЬ: <1-10>
СТИЛЬ: <1-10>
ОБЩАЯ ОЦЕНКА: <среднее 1-10>
КОММЕНТАРИЙ: краткий разбор с примерами ошибок, если есть"""

RED_FLAG_SYSTEM = """\
Ты — Red Flag AI. Отмечай потенциальные кадровые риски.

Ищи только по фактам из анкеты и интервью:
- частая смена мест работы без объяснимых причин;
- длительные перерывы в стаже;
- явные несоответствия опыта требованиям вакансии;
- противоречивые или расплывчатые ответы на ключевые вопросы.

Правила: только факты, каждый флаг — с конкретным доказательством из текста.
Не делай предположений о личности, возрасте, семье и т.п.

Формат ответа (строго, на русском):
⚠️ ФЛАГИ: список рисков с доказательствами (или «не выявлено»)
УРОВЕНЬ РИСКА: низкий | средний | высокий
ВЫВОД: 1-2 предложения"""

INTERVIEW_SCORE_SYSTEM = """\
Ты — Interview Score AI. Формируешь итоговую оценку кандидата.

Оцени по четырём критериям (каждый от 1 до 10):
- мотивация — заинтересованность в вакансии;
- опыт — релевантный опыт и подтверждённые навыки;
- коммуникация — качество общения в интервью;
- соответствие вакансии — насколько кандидат подходит под требования.

Если приложены отчёты других агентов (противоречия, риски, качество речи) — учитывай их.

Формат ответа (строго, на русском):
МОТИВАЦИЯ: <1-10> — обоснование
ОПЫТ: <1-10> — обоснование
КОММУНИКАЦИЯ: <1-10> — обоснование
СООТВЕТСТВИЕ ВАКАНСИИ: <1-10> — обоснование
ОБЩИЙ БАЛЛ: <среднее 1-10>
РЕКОМЕНДАЦИЯ: настоятельно рекомендую | рекомендую | под вопросом | не рекомендую
ИТОГ: 2-3 предложения"""

_SCREENING_SECTIONS = (
    ("🚨 Fraud Detector",    "fraud"),
    ("✍️ Language Quality",  "language_quality"),
    ("⚠️ Red Flags",         "red_flags"),
    ("📊 Interview Score",   "interview_score"),
)


def _merge_summary(base_summary: str | None, screening: dict) -> str | None:
    """Склеивает HR Summary с отчётами агентов скрининга.

    В БД и в сообщение HR попадает только поле summary — поэтому новые
    отчёты добавляем разделами в него, не меняя схему сохранения.
    """
    parts = [base_summary] if base_summary else []
    for title, key in _SCREENING_SECTIONS:
        text = screening.get(key)
        if text:
            parts.append(f"{title}\n{'—' * 30}\n{text}")
    return "\n\n".join(parts) if parts else None


async def run_all_agents(form_data: dict, qa_log: list[dict]) -> dict:
    """Запускает всех агентов параллельно.

    Returns:
        {
            "resume": str | None,
            "skills": str | None,
            "personality": str | None,
            "job_match": str | None,
            "summary": str | None,  # HR Summary + разделы скрининга
        }
    """
    context = _base_context(form_data, qa_log)

    results = await asyncio.gather(
        _run_agent(RESUME_SYSTEM,       context, max_tokens=500),
        _run_agent(SKILL_SYSTEM,        context, max_tokens=300),
        _run_agent(PERSONALITY_SYSTEM,  context, max_tokens=300),
        _run_agent(JOB_MATCH_SYSTEM,    context, max_tokens=300),
        _run_agent(HR_SUMMARY_SYSTEM,   context, max_tokens=400),
        _run_agent(FRAUD_DETECTOR_SYSTEM,   context, max_tokens=400),
        _run_agent(LANGUAGE_QUALITY_SYSTEM, context, max_tokens=400),
        _run_agent(RED_FLAG_SYSTEM,         context, max_tokens=400),
        return_exceptions=True,
    )

    keys = (
        "resume", "skills", "personality", "job_match", "summary",
        "fraud", "language_quality", "red_flags",
    )
    output: dict = {}
    for key, val in zip(keys, results):
        if isinstance(val, Exception):
            logger.error("Агент %s упал с ошибкой: %s", key, val)
            output[key] = None
        else:
            output[key] = val

    # Финальный агент оценивает кандидата с учётом отчётов скрининга
    score_sections = []
    for title, key in _SCREENING_SECTIONS[:3]:
        text = output.get(key)
        if text:
            score_sections.append(f"--- {title} ---\n{text}")
    score_context = context
    if score_sections:
        score_context += "\n\n=== ОТЧЁТЫ ДРУГИХ АГЕНТОВ ===\n" + "\n\n".join(score_sections)

    try:
        output["interview_score"] = await _run_agent(
            INTERVIEW_SCORE_SYSTEM, score_context, max_tokens=500,
        )
    except Exception as exc:
        logger.error("Агент interview_score упал с ошибкой: %s", exc)
        output["interview_score"] = None

    output["summary"] = _merge_summary(output.get("summary"), output)
    return output
