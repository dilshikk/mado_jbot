# bot/ai/agents.py
"""Трёхуровневый AI-пайплайн оценки кандидата.

Уровень 1 — Interview AI (уже отработал до вызова агентов).
Уровень 2 — два независимых агента запускаются параллельно:
    • Analysis AI  — навыки, личность, соответствие, скрининг (fraud + red flags + language)
    • Resume AI    — краткое структурированное резюме
Уровень 3 — HR Summary AI получает оба отчёта и выдаёт финальное заключение.

Итого: 3 запроса к Workers AI вместо 9.
"""

from __future__ import annotations

import asyncio
import logging

from bot.ai.client import cf_chat
from bot.ai.parser import extract_text
from bot.ai.prompts import (
    HR_SUMMARY_SYSTEM,
    JOB_MATCH_SYSTEM,
    PERSONALITY_SYSTEM,
    RESUME_SYSTEM,
    SKILL_SYSTEM,
)

logger = logging.getLogger(__name__)

# Модель по умолчанию — Llama 3 8B на Workers AI
_DEFAULT_MODEL = "@cf/meta/llama-3-8b-instruct"


# ---------------------------------------------------------------------------
# Внутренний хелпер
# ---------------------------------------------------------------------------


async def _run_agent(system_prompt: str, user_content: str, max_tokens: int = 400) -> str | None:
    """Отправляет один chat-запрос к Workers AI и возвращает текст ответа."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    result = await cf_chat(_DEFAULT_MODEL, messages, max_tokens=max_tokens)
    return extract_text(result) if result else None


def _base_context(form_data: dict, qa_log: list[dict]) -> str:
    """Формирует единый текстовый контекст для всех агентов."""
    lines = ["=== АНКЕТА КАНДИДАТА ==="]
    for key, value in form_data.items():
        lines.append(f"{key}: {value}")

    lines.append("\n=== ОТВЕТЫ НА ИНТЕРВЬЮ ===")
    for entry in qa_log:
        q = entry.get("question", "")
        a = entry.get("answer", "")
        lines.append(f"В: {q}\nО: {a}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Промпты для агентов уровня 2
# ---------------------------------------------------------------------------

_ANALYSIS_SYSTEM = f"""\
Ты — Analysis AI. Проанализируй кандидата по трём направлениям и выдай
единый структурированный отчёт.

───────────────────────────────────────────────────────
1. НАВЫКИ И ОПЫТ
───────────────────────────────────────────────────────
{SKILL_SYSTEM}

───────────────────────────────────────────────────────
2. ЛИЧНОСТЬ И СТИЛЬ
───────────────────────────────────────────────────────
{PERSONALITY_SYSTEM}

───────────────────────────────────────────────────────
3. СООТВЕТСТВИЕ ВАКАНСИИ
───────────────────────────────────────────────────────
{JOB_MATCH_SYSTEM}

───────────────────────────────────────────────────────
4. СКРИНИНГ (Fraud · Language · Red Flags)
───────────────────────────────────────────────────────
Кратко (1-2 строки на каждый пункт):
🚨 ПРОТИВОРЕЧИЯ: (или «не выявлено»)
✍️ ГРАМОТНОСТЬ: общая оценка /10 и 1 фраза
⚠️ РИСКИ: список (или «не выявлено»)
"""

_SUMMARY_WITH_ANALYSIS_SYSTEM = f"""\
{HR_SUMMARY_SYSTEM}

Дополнительно используй отчёты Analysis AI и Resume AI,
приложенные ниже, для обоснованного вывода.
"""


# ---------------------------------------------------------------------------
# Основная точка входа
# ---------------------------------------------------------------------------


async def run_all_agents(form_data: dict, qa_log: list[dict]) -> dict:
    """Запускает трёхуровневый пайплайн.

    Уровень 1 — контекст (готов до вызова).
    Уровень 2 — Analysis AI + Resume AI (параллельно, 2 запроса).
    Уровень 3 — HR Summary AI с учётом результатов уровня 2 (1 запрос).

    Returns:
        {
            "resume":    str | None,   # краткое резюме кандидата
            "analysis":  str | None,   # навыки + личность + соответствие + скрининг
            "summary":   str | None,   # итоговое HR-заключение
        }
    """
    context = _base_context(form_data, qa_log)

    # ── Уровень 2: два агента параллельно ─────────────────────────────────
    analysis_result, resume_result = await asyncio.gather(
        _run_agent(_ANALYSIS_SYSTEM, context, max_tokens=700),
        _run_agent(RESUME_SYSTEM, context, max_tokens=300),
        return_exceptions=True,
    )

    def _safe(val: object) -> str | None:
        if isinstance(val, Exception):
            logger.error("Агент упал: %s", val)
            return None
        return val  # type: ignore[return-value]

    analysis_text = _safe(analysis_result)
    resume_text = _safe(resume_result)

    # ── Уровень 3: Summary с учётом обоих отчётов ─────────────────────────
    summary_context = context
    if analysis_text or resume_text:
        parts = ["=== ОТЧЁТЫ ПРЕДЫДУЩИХ АГЕНТОВ ==="]
        if resume_text:
            parts.append(f"--- Resume AI ---\n{resume_text}")
        if analysis_text:
            parts.append(f"--- Analysis AI ---\n{analysis_text}")
        summary_context = context + "\n\n" + "\n\n".join(parts)

    summary_text = await _run_agent(
        _SUMMARY_WITH_ANALYSIS_SYSTEM, summary_context, max_tokens=500
    )

    return {
        "resume":   resume_text,
        "analysis": analysis_text,
        "summary":  summary_text,
        # Обратная совместимость: поля, которые могли читаться снаружи
        "skills":      None,
        "personality": None,
        "job_match":   None,
    }
