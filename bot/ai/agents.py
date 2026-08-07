# bot/ai/agents.py
"""5-уровневый AI-пайплайн оценки кандидата.

Уровень 1 — Interview AI (уже отработал до вызова агентов)
Уровень 2 — Resume Extractor AI (1 запрос, json_object)
Уровень 3 — Communication AI (параллельно, json_schema strict)
             Integrity AI     (параллельно, json_object)
Уровень 4 — Job Match AI (json_schema strict)
Уровень 5 — Hiring Decision AI (json_schema strict)

Итого: 5 запросов вместо 9. Итоговый балл считается в Python.
Typical reasoning overhead: 500–1500 токенов на запрос.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from bot.ai.client import cf_chat
from bot.ai.models import (
    COMMUNICATION_MODEL,
    HIRING_DECISION_MODEL,
    INTEGRITY_MODEL,
    JOB_MATCH_MODEL,
    RESUME_MODEL,
)
from bot.ai.parser import extract_json, extract_text
from bot.ai.prompts import (
    COMMUNICATION_SYSTEM,
    HIRING_DECISION_SYSTEM,
    INTEGRITY_SYSTEM,
    JOB_MATCH_SYSTEM,
    RESUME_SYSTEM,
)
from bot.ai.schemas import (
    COMMUNICATION_FORMAT,
    HIRING_DECISION_FORMAT,
    JOB_MATCH_FORMAT,
    JSON_OBJECT_FORMAT,
)

logger = logging.getLogger(__name__)

# Должности, для которых грамотность письменной речи — важный критерий
_LANGUAGE_SENSITIVE_POSITIONS = {
    "администратор", "hr", "менеджер", "оператор",
    "administrator", "manager", "operator",
}

# Веса для итогового балла
_WEIGHTS = {
    "motivation":    0.30,
    "experience":    0.30,
    "communication": 0.20,
    "integrity":     0.20,
}

# ---------------------------------------------------------------------------
# Внутренние хелперы
# ---------------------------------------------------------------------------

def _base_context(form_data: dict, qa_log: list[dict]) -> str:
    lines = ["=== АНКЕТА КАНДИДАТА ==="]
    for key, value in form_data.items():
        lines.append(f"{key}: {value}")

    lines.append("\n=== ОТВЕТЫ НА ИНТЕРВЬЮ ===")
    for entry in qa_log:
        q = entry.get("q") or entry.get("question", "")
        a = entry.get("a") or entry.get("answer", "")
        lines.append(f"В: {q}\nО: {a}")

    return "\n".join(lines)


async def _run_json_agent(
    system_prompt: str,
    user_content: str,
    max_tokens: int = 2000,
    model: str = RESUME_MODEL,
    text_format: dict | None = None,
) -> dict[str, Any]:
    """Запрашивает агента, всегда возвращает dict (никогда не кидает исключений).

    Args:
        text_format: если None — используется json_object;
                     иначе — передаётся напрямую в cf_chat.
    """
    fmt = text_format or JSON_OBJECT_FORMAT
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    try:
        result = await cf_chat(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            text_format=fmt,
        )
        if not result:
            return {"error": "no_response"}

        text = extract_text(result)
        if not text:
            logger.warning("_run_json_agent: пустой ответ, result=%r", result)
            return {"error": "no_text"}

        # Если Structured Outputs вернул dict напрямую
        inner = (result.get("result") or {}).get("response")
        if isinstance(inner, dict):
            return inner

        parsed = extract_json(text)
        if "error" not in parsed:
            return parsed

        logger.warning(
            "_run_json_agent: не удалось распарсить JSON | text=%s | ошибка=%s",
            text[:200], parsed.get("error"),
        )
        return parsed

    except Exception as exc:
        logger.error("_run_json_agent упал: %s", exc, exc_info=True)
        return {"error": "exception", "detail": str(exc)}


def _safe_score(raw: object) -> float:
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(10.0, value))


# ---------------------------------------------------------------------------
# Основная точка входа
# ---------------------------------------------------------------------------

async def run_all_agents(form_data: dict, qa_log: list[dict]) -> dict[str, Any]:
    """5-уровневый пайплайн оценки кандидата."""
    context = _base_context(form_data, qa_log)

    # ── Уровень 2: Resume Extractor ────────────────────────────────────────────────
    # json_object: динамические ключи в jobs[] не позволяют strict schema
    resume_data = await _run_json_agent(
        RESUME_SYSTEM, context,
        max_tokens=3000, model=RESUME_MODEL,
        text_format=JSON_OBJECT_FORMAT,
    )

    # ── Уровень 3: Communication (строгая schema) + Integrity (json_object) ───────
    comm_result, integrity_result = await asyncio.gather(
        _run_json_agent(
            COMMUNICATION_SYSTEM, context,
            max_tokens=2500, model=COMMUNICATION_MODEL,
            text_format=COMMUNICATION_FORMAT,      # json_schema strict
        ),
        _run_json_agent(
            INTEGRITY_SYSTEM, context,
            max_tokens=2500, model=INTEGRITY_MODEL,
            text_format=JSON_OBJECT_FORMAT,        # динам. массивы contradictions/flags
        ),
        return_exceptions=True,
    )

    def _safe_dict(val: object) -> dict[str, Any]:
        if isinstance(val, Exception):
            logger.error("Агент упал: %s", val)
            return {"error": "exception", "detail": str(val)}
        return val  # type: ignore[return-value]

    comm_data = _safe_dict(comm_result)
    integrity_data = _safe_dict(integrity_result)

    # ── Уровень 4: Job Match (строгая schema) ─────────────────────────────────────
    level3_context = (
        context
        + "\n\n=== RESUME EXTRACTOR ===\n"
        + json.dumps(resume_data, ensure_ascii=False)
        + "\n\n=== COMMUNICATION AI ===\n"
        + json.dumps(comm_data, ensure_ascii=False)
        + "\n\n=== INTEGRITY AI ===\n"
        + json.dumps(integrity_data, ensure_ascii=False)
    )
    job_match_data = await _run_json_agent(
        JOB_MATCH_SYSTEM, level3_context,
        max_tokens=2500, model=JOB_MATCH_MODEL,
        text_format=JOB_MATCH_FORMAT,              # json_schema strict
    )

    # ── Уровень 5: Hiring Decision (строгая schema) ───────────────────────────
    level4_context = (
        level3_context
        + "\n\n=== JOB MATCH AI ===\n"
        + json.dumps(job_match_data, ensure_ascii=False)
    )
    decision_data = await _run_json_agent(
        HIRING_DECISION_SYSTEM, level4_context,
        max_tokens=3000, model=HIRING_DECISION_MODEL,
        text_format=HIRING_DECISION_FORMAT,        # json_schema strict
    )

    # Итоговый балл — веса считает Python
    scores = decision_data.get("scores", {})
    total = 0.0
    for key, weight in _WEIGHTS.items():
        criterion = scores.get(key, {}) if isinstance(scores, dict) else {}
        score = criterion.get("score", 0) if isinstance(criterion, dict) else 0
        total += _safe_score(score) * weight
    total = round(total, 2)
    decision_data["total_score"] = total

    summary = _build_summary_text(resume_data, decision_data, job_match_data, integrity_data)

    return {
        "resume":        resume_data,
        "communication": comm_data,
        "integrity":     integrity_data,
        "job_match":     job_match_data,
        "decision":      decision_data,
        "total_score":   total,
        "summary":       summary,
    }


# ---------------------------------------------------------------------------
# Форматирование текстового отчёта (Python, без AI)
# ---------------------------------------------------------------------------

_DECISION_LABELS = {
    "invite": "✅ Пригласить на собеседование",
    "review": "⚠️ Рассмотреть",
    "reject": "❌ Отклонить",
}
_PRIORITY_LABELS = {
    "high":   "🔴 Высокий",
    "medium": "🟡 Средний",
    "low":    "🟢 Низкий",
}
_RISK_LABELS = {
    "low":    "🟢 Низкий",
    "medium": "🟡 Средний",
    "high":   "🔴 Высокий",
}


def _build_summary_text(
    resume: dict,
    decision: dict,
    job_match: dict,
    integrity: dict,
) -> str:
    lines: list[str] = []

    cand = resume.get("candidate", {})
    name = cand.get("name", "—")
    age = cand.get("age", "—")
    position = cand.get("position_applied") or cand.get("position", "—")
    lines.append(f"👤 {name}, {age} лет — {position}")

    total = decision.get("total_score", 0)
    decision_key = decision.get("decision", "")
    decision_label = _DECISION_LABELS.get(decision_key, decision_key)
    lines.append(f"📊 Балл: {total}/10 | {decision_label}")

    priority_key = decision.get("priority", "")
    if priority_key:
        lines.append(f"🎯 Приоритет: {_PRIORITY_LABELS.get(priority_key, priority_key)}")

    match_pct = job_match.get("match_percent")
    if match_pct is not None:
        lines.append(f"💼 Соответствие: {match_pct}%")

    risk = integrity.get("risk_level", "")
    if risk:
        lines.append(f"🛡 Риски: {_RISK_LABELS.get(risk, risk)}")

    reasons = decision.get("reasons") or []
    if reasons:
        lines.append("\n Ключевые факты: ")
        for r in reasons[:4]:
            lines.append(f" • {r}")

    questions = decision.get("questions_for_hr") or []
    if questions:
        lines.append("\n Уточнить на очном интервью: ")
        for q in questions[:3]:
            lines.append(f" ❓ {q}")

    skills = resume.get("skills") or []
    if isinstance(skills, dict):
        hard = skills.get("hard", [])
        soft = skills.get("soft", [])
        skills = hard + soft
    if skills:
        lines.append(f"\n Навыки: {', '.join(skills[:6])}")

    return "\n".join(lines)
