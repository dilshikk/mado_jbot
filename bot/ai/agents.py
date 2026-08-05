# bot/ai/agents.py
"""5-уровневый AI-пайплайн оценки кандидата.

Уровень 1 — Interview AI (уже отработал до вызова агентов)
Уровень 2 — Resume Extractor AI (1 запрос, JSON-структура)
Уровень 3 — Communication AI (параллельно)
             Integrity AI (параллельно)
Уровень 4 — Job Match AI (1 запрос, видит уровни 2+3)
Уровень 5 — Hiring Decision AI (1 запрос, видит всё)

Итого: 5 запросов вместо 9. Все ответы — строгий JSON.
Итоговый балл считается в Python (мотивация 30%, опыт 30%, коммуникация 20%, риски 20%).
Language AI включается только для должностей, требующих грамотного общения.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from bot.ai.client import cf_chat
from bot.ai.models import (
    LLAMA_70B,
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
    CommunicationResult,
    DecisionResult,
    IntegrityResult,
    JobMatchResult,
    ResumeResult,
    parse_agent_result,
)

logger = logging.getLogger(__name__)

# Должности, для которых грамотность письменной речи — важный критерий
_LANGUAGE_SENSITIVE_POSITIONS = {
    "администратор", "hr", "менеджер", "оператор",
    "administrator", "manager", "operator",
}

# Веса для итогового балла (должны давать 1.0 в сумме)
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
    """Формирует единый текстовый контекст для всех агентов."""
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
    max_tokens: int = 500,
    model: str = LLAMA_70B,
) -> dict[str, Any]:
    """Запрашивает агента, всегда возвращает dict (никогда не кидает исключений)."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_content},
    ]
    try:
        result = await cf_chat(model, messages, max_tokens=max_tokens)
        if not result:
            return {"error": "no_response"}

        text = extract_text(result) or ""
        return extract_json(text)

    except Exception as exc:
        logger.error("Агент упал: %s", exc, exc_info=True)
        return {"error": "exception", "detail": str(exc)}


def _safe_score(raw: object, lo: float = 0.0, hi: float = 10.0) -> float:
    """Приводит score от LLM к числу в диапазоне [lo, hi].

    Модель иногда возвращает строки, None или значения вне шкалы (15 вместо 0–10).
    Невалидное значение трактуем как 0, валидное — клэмпим в диапазон.
    """
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, value))


def _compute_total_score(dec: DecisionResult) -> float:
    """Считает итоговый балл из критериев по весам. Делается в Python, не в AI."""
    total = 0.0
    for key, weight in _WEIGHTS.items():
        criterion = getattr(dec.scores, key, None)
        raw = criterion.score if criterion is not None else 0
        total += _safe_score(raw) * weight
    return round(total, 2)


def _is_language_sensitive(form_data: dict) -> bool:
    """Нужна ли оценка грамотности для данной позиции."""
    position = str(form_data.get("position") or form_data.get("должность", "")).lower()
    return any(p in position for p in _LANGUAGE_SENSITIVE_POSITIONS)


# ---------------------------------------------------------------------------
# Основная точка входа
# ---------------------------------------------------------------------------

async def run_all_agents(form_data: dict, qa_log: list[dict]) -> dict[str, Any]:
    """Запускает 5-уровневый пайплайн оценки кандидата.

    Returns:
        {
            "resume":        ResumeResult (сериализованный dict),
            "communication": CommunicationResult,
            "integrity":     IntegrityResult,
            "job_match":     JobMatchResult,
            "decision":      DecisionResult  (total_score проставлен Python),
            "total_score":   float | None,
            "status":        "completed" | "partial" | "needs_manual_review",
            "failed_agents": list[str],
            "summary":       str,
        }
    """
    context = _base_context(form_data, qa_log)

    # ── Уровень 2: Resume Extractor ───────────────────────────────────────
    raw_resume = await _run_json_agent(
        RESUME_SYSTEM, context, max_tokens=400, model=RESUME_MODEL,
    )
    if "error" in raw_resume:
        # Resume критичен для уровней 4–5: даём второй шанс
        logger.warning(
            "Resume Extractor упал (%s), повторный запрос", raw_resume.get("error"),
        )
        raw_resume = await _run_json_agent(
            RESUME_SYSTEM, context, max_tokens=400, model=RESUME_MODEL,
        )
    resume = parse_agent_result(ResumeResult, raw_resume, "resume")

    # ── Уровень 3: Communication + Integrity параллельно ─────────────────
    raw_comm_res, raw_integrity_res = await asyncio.gather(
        _run_json_agent(COMMUNICATION_SYSTEM, context, max_tokens=400, model=COMMUNICATION_MODEL),
        _run_json_agent(INTEGRITY_SYSTEM,     context, max_tokens=500, model=INTEGRITY_MODEL),
        return_exceptions=True,
    )

    def _safe_raw(val: object, name: str) -> dict[str, Any]:
        if isinstance(val, Exception):
            logger.error("Агент %s упал: %s", name, val)
            return {"error": "exception", "detail": str(val)}
        return val  # type: ignore[return-value]

    comm      = parse_agent_result(CommunicationResult, _safe_raw(raw_comm_res,      "communication"), "communication")
    integrity = parse_agent_result(IntegrityResult,     _safe_raw(raw_integrity_res, "integrity"),     "integrity")

    # ── Уровень 4: Job Match — получает Resume + Communication + Integrity ─
    level3_context = (
        context
        + "\n\n=== RESUME EXTRACTOR ===\n"
        + json.dumps(resume.model_dump(), ensure_ascii=False)
        + "\n\n=== COMMUNICATION AI ===\n"
        + json.dumps(comm.model_dump(), ensure_ascii=False)
        + "\n\n=== INTEGRITY AI ===\n"
        + json.dumps(integrity.model_dump(), ensure_ascii=False)
    )
    raw_job_match = await _run_json_agent(
        JOB_MATCH_SYSTEM, level3_context, max_tokens=400, model=JOB_MATCH_MODEL,
    )
    job_match = parse_agent_result(JobMatchResult, raw_job_match, "job_match")

    # ── Уровень 5: Hiring Decision — получает ВСЁ ─────────────────────────
    level4_context = (
        level3_context
        + "\n\n=== JOB MATCH AI ===\n"
        + json.dumps(job_match.model_dump(), ensure_ascii=False)
    )
    raw_decision = await _run_json_agent(
        HIRING_DECISION_SYSTEM, level4_context, max_tokens=600, model=HIRING_DECISION_MODEL,
    )
    decision = parse_agent_result(DecisionResult, raw_decision, "decision")

    # Собираем упавших агентов
    failed_agents: list[str] = [
        name for name, obj in (
            ("resume",        resume),
            ("communication", comm),
            ("integrity",     integrity),
            ("job_match",     job_match),
            ("decision",      decision),
        )
        if obj.error is not None
    ]

    # Итоговый балл считается в Python по весам.
    if "decision" in failed_agents:
        total: float | None = None
        decision.decision    = "needs_manual_review"
        decision.total_score = 0.0
    else:
        total                = _compute_total_score(decision)
        decision.total_score = total

    # Статус пайплайна
    if "decision" in failed_agents:
        status = "needs_manual_review"
    elif failed_agents:
        status = "partial"
    else:
        status = "completed"

    # Краткий текст для HR-чата (без AI, только Python)
    summary = _build_summary_text(resume, decision, job_match, integrity)

    if failed_agents:
        summary = (
            "⚠️ AI-оценка не завершена, требуется ручная проверка "
            f"(ошибки: {', '.join(failed_agents)})\n\n"
            + summary
        )

    return {
        "resume":        resume.model_dump(),
        "communication": comm.model_dump(),
        "integrity":     integrity.model_dump(),
        "job_match":     job_match.model_dump(),
        "decision":      decision.model_dump(),
        "total_score":   total,
        "status":        status,
        "failed_agents": failed_agents,
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
    resume:    ResumeResult,
    decision:  DecisionResult,
    job_match: JobMatchResult,
    integrity: IntegrityResult,
) -> str:
    """Строит читаемый текст отчёта для HR из типизированных объектов."""
    lines: list[str] = []

    # Кандидат
    c = resume.candidate
    lines.append(f"👤 {c.name or '—'}, {c.age or '—'} лет — {c.position_applied or '—'}")

    # Итоговый балл
    if decision.total_score == 0.0 and decision.error:
        lines.append("📊 Балл: — | ⚠️ Требуется ручная проверка")
    else:
        decision_label = _DECISION_LABELS.get(decision.decision, decision.decision)
        lines.append(f"📊 Балл: {decision.total_score}/10 | {decision_label}")

    # Приоритет
    if decision.priority:
        lines.append(f"🎯 Приоритет: {_PRIORITY_LABELS.get(decision.priority, decision.priority)}")

    # Соответствие вакансии
    if job_match.match_percent:
        lines.append(f"💼 Соответствие: {job_match.match_percent}%")

    # Риски
    if integrity.risk_level:
        lines.append(f"🛡 Риски: {_RISK_LABELS.get(integrity.risk_level, integrity.risk_level)}")

    # Причины решения
    if decision.reasons:
        lines.append("\n Ключевые факты: ")
        for r in decision.reasons[:4]:
            lines.append(f"  • {r}")

    # Вопросы для HR
    if decision.questions_for_hr:
        lines.append("\n Уточнить на очном интервью: ")
        for q in decision.questions_for_hr[:3]:
            lines.append(f"  ❓ {q}")

    # Навыки
    all_skills = resume.skills.hard + resume.skills.soft
    if all_skills:
        lines.append(f"\n Навыки: {', '.join(all_skills[:6])}")

    return "\n".join(lines)
