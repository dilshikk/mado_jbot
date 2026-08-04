# bot/ai/agents.py
"""5 AI-агентов: Resume Builder, Skill Analyzer, Personality, Job Matcher, HR Summary."""

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


async def run_all_agents(form_data: dict, qa_log: list[dict]) -> dict:
    """Запускает всех 5 агентов параллельно.

    Returns:
        {
            "resume": str | None,
            "skills": str | None,
            "personality": str | None,
            "job_match": str | None,
            "summary": str | None,
        }
    """
    context = _base_context(form_data, qa_log)

    results = await asyncio.gather(
        _run_agent(RESUME_SYSTEM,       context, max_tokens=500),
        _run_agent(SKILL_SYSTEM,        context, max_tokens=300),
        _run_agent(PERSONALITY_SYSTEM,  context, max_tokens=300),
        _run_agent(JOB_MATCH_SYSTEM,    context, max_tokens=300),
        _run_agent(HR_SUMMARY_SYSTEM,   context, max_tokens=400),
        return_exceptions=True,
    )

    keys = ("resume", "skills", "personality", "job_match", "summary")
    output: dict = {}
    for key, val in zip(keys, results):
        if isinstance(val, Exception):
            logger.error("Агент %s упал с ошибкой: %s", key, val)
            output[key] = None
        else:
            output[key] = val
    return output
