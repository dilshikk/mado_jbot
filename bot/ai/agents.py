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

import ast
import asyncio
import json
import logging
import re
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
from bot.ai.prompts import (
    COMMUNICATION_SYSTEM,
    HIRING_DECISION_SYSTEM,
    INTEGRITY_SYSTEM,
    JOB_MATCH_SYSTEM,
    RESUME_SYSTEM,
)

logger = logging.getLogger(__name__)

# Должности, для которых грамотность письменной речи — важный критерий
_LANGUAGE_SENSITIVE_POSITIONS = {
    "администратор", "hr", "менеджер", "оператор",
    "administrator", "manager", "operator",
}

# Веса для итогового балла (должны давать 1.0 в сумме)
_WEIGHTS = {
    "motivation": 0.30,
    "experience": 0.30,
    "communication": 0.20,
    "integrity": 0.20,
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


def _extract_json(text: str) -> dict[str, Any]:
    """Извлекает JSON из текста с тремя уровнями fallback:
    1. json.loads на вырезанный блок {}
    2. regex-чистка одиночных кавычек
    3. ast.literal_eval (для Python-dict от CF Workers AI)
    """
    # Вырезаем первый блок { ... }
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end <= start:
        return {"error": "no_json", "raw": text[:500]}

    chunk = text[start:end]

    # Попытка 1: стандартный json.loads
    try:
        return json.loads(chunk)
    except json.JSONDecodeError:
        pass

    # Попытка 2: заменяем одиночные кавычки → двойные (CF Workers AI иногда возвращает Python-dict)
    try:
        fixed = re.sub(r"(?<![\\])'", '"', chunk)
        return json.loads(fixed)
    except (json.JSONDecodeError, Exception):
        pass

    # Попытка 3: ast.literal_eval
    try:
        result = ast.literal_eval(chunk)
        if isinstance(result, dict):
            return result
    except Exception:
        pass

    logger.warning("_extract_json: все попытки не удались, raw=%s", chunk[:200])
    return {"error": "invalid_json", "raw": chunk[:500]}


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

        # Workers AI возвращает {"result": {"response": "..."}}
        text: str = ""
        if isinstance(result, dict):
            inner = result.get("result", result)
            text = inner.get("response", "") if isinstance(inner, dict) else str(inner)
        else:
            text = str(result)

        return _extract_json(text)

    except Exception as exc:
        logger.error("Агент упал: %s", exc, exc_info=True)
        return {"error": "exception", "detail": str(exc)}


def _compute_total_score(scores: dict[str, Any]) -> float:
    """Считает итоговый балл из критериев по весам. Делается в Python, не в AI."""
    total = 0.0
    for key, weight in _WEIGHTS.items():
        criterion = scores.get(key, {})
        score = criterion.get("score", 0) if isinstance(criterion, dict) else 0
        total += float(score) * weight
    return round(total, 2)


def _is_language_sensitive(form_data: dict) -> bool:
    """Нужна ли оценка грамотности для данной позиции."""
    position = str(form_data.get("position") or form_data.get("должность", "")).lower()
    return any(p in position for p in _LANGUAGE_SENSITIVE_POSITIONS)


def _to_str_list(value: object) -> list[str]:
    """Безопасно приводит любое значение к списку строк для join/slice."""
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, (set, frozenset, tuple)):
        return [str(v) for v in value]
    if isinstance(value, dict):
        return [str(k) for k in value]
    if isinstance(value, str) and value:
        return [value]
    return []


# ---------------------------------------------------------------------------
# Основная точка входа
# ---------------------------------------------------------------------------

async def run_all_agents(form_data: dict, qa_log: list[dict]) -> dict[str, Any]:
    """Запускает 5-уровневый пайплайн оценки кандидата.

    Returns:
        {
            "resume": dict,        # Resume Extractor JSON
            "communication": dict, # Communication AI JSON
            "integrity": dict,     # Integrity AI JSON (Fraud + RedFlags)
            "job_match": dict,     # Job Match AI JSON
            "decision": dict,      # Hiring Decision AI JSON
            "total_score": float | None,  # рассчитан в Python; None, если Decision AI упал
            "status": str,         # completed | partial | needs_manual_review
            "failed_agents": list[str],  # имена агентов, вернувших ошибку
            "summary": str,        # краткий текст для HR-чата
        }
    """
    context = _base_context(form_data, qa_log)

    # ── Уровень 2: Resume Extractor ───────────────────────────────────────
    resume_data = await _run_json_agent(
        RESUME_SYSTEM, context, max_tokens=400, model=RESUME_MODEL,
    )
    if "error" in resume_data:
        # Resume критичен для уровней 4–5: даём второй шанс
        logger.warning(
            "Resume Extractor упал (%s), повторный запрос", resume_data.get("error"),
        )
        resume_data = await _run_json_agent(
            RESUME_SYSTEM, context, max_tokens=400, model=RESUME_MODEL,
        )

    # ── Уровень 3: Communication + Integrity параллельно ─────────────────
    comm_result, integrity_result = await asyncio.gather(
        _run_json_agent(COMMUNICATION_SYSTEM, context, max_tokens=400, model=COMMUNICATION_MODEL),
        _run_json_agent(INTEGRITY_SYSTEM, context, max_tokens=500, model=INTEGRITY_MODEL),
        return_exceptions=True,
    )

    def _safe_dict(val: object) -> dict[str, Any]:
        if isinstance(val, Exception):
            logger.error("Агент упал: %s", val)
            return {"error": "exception", "detail": str(val)}
        return val  # type: ignore[return-value]

    comm_data      = _safe_dict(comm_result)
    integrity_data = _safe_dict(integrity_result)

    # ── Уровень 4: Job Match — получает Resume + Communication + Integrity ─
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
        JOB_MATCH_SYSTEM, level3_context, max_tokens=400, model=JOB_MATCH_MODEL,
    )

    # ── Уровень 5: Hiring Decision — получает ВСЁ ─────────────────────────
    level4_context = (
        level3_context
        + "\n\n=== JOB MATCH AI ===\n"
        + json.dumps(job_match_data, ensure_ascii=False)
    )
    decision_data = await _run_json_agent(
        HIRING_DECISION_SYSTEM, level4_context, max_tokens=600, model=HIRING_DECISION_MODEL,
    )

    # Собираем упавших агентов — без тихих провалов
    failed_agents: list[str] = []
    for agent_name, data in (
        ("resume", resume_data),
        ("communication", comm_data),
        ("integrity", integrity_data),
        ("job_match", job_match_data),
        ("decision", decision_data),
    ):
        if "error" in data:
            failed_agents.append(agent_name)

    # Итоговый балл считается в Python по весам.
    # Если Decision AI упал — не считаем балл (иначе кандидат получит тихий 0)
    # и помечаем заявку на ручную проверку.
    if "decision" in failed_agents:
        total: float | None = None
        decision_data["total_score"] = None
        decision_data["decision"] = "needs_manual_review"
    else:
        total = _compute_total_score(decision_data.get("scores", {}))
        decision_data["total_score"] = total

    # Статус пайплайна: нужна ли ручная проверка
    if "decision" in failed_agents:
        status = "needs_manual_review"
    elif failed_agents:
        status = "partial"
    else:
        status = "completed"

    # ── Краткий текст для HR-чата (без AI, только Python) ─────────────────
    summary = _build_summary_text(resume_data, decision_data, job_match_data, integrity_data)

    # Явно помечаем незавершённую оценку в отчёте для HR
    if failed_agents:
        summary = (
            "⚠️ AI-оценка не завершена, требуется ручная проверка "
            f"(ошибки: {', '.join(failed_agents)})\n\n"
            + summary
        )

    return {
        "resume":       resume_data,
        "communication": comm_data,
        "integrity":    integrity_data,
        "job_match":    job_match_data,
        "decision":     decision_data,
        "total_score":  total,
        "status":       status,
        "failed_agents": failed_agents,
        "summary":      summary,
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
    """Строит читаемый текст отчёта для HR из JSON-ответов агентов."""
    lines: list[str] = []

    # Кандидат
    cand     = resume.get("candidate", {})
    name     = cand.get("name", "—") if isinstance(cand, dict) else "—"
    age      = cand.get("age", "—")  if isinstance(cand, dict) else "—"
    position = cand.get("position", "—") if isinstance(cand, dict) else "—"
    lines.append(f"👤 {name}, {age} лет — {position}")

    # Итоговый балл (None — оценка не завершена, см. предупреждение выше)
    total = decision.get("total_score")
    if total is None:
        lines.append("📊 Балл: — | ⚠️ Требуется ручная проверка")
    else:
        decision_key   = decision.get("decision", "")
        decision_label = _DECISION_LABELS.get(decision_key, decision_key)
        lines.append(f"📊 Балл: {total}/10 | {decision_label}")

    # Приоритет
    priority_key = decision.get("priority", "")
    if priority_key:
        lines.append(f"🎯 Приоритет: {_PRIORITY_LABELS.get(priority_key, priority_key)}")

    # Соответствие вакансии
    match_pct = job_match.get("match_percent")
    if match_pct is not None:
        lines.append(f"💼 Соответствие: {match_pct}%")

    # Риски
    risk = integrity.get("risk_level", "")
    if risk:
        lines.append(f"🛡 Риски: {_RISK_LABELS.get(risk, risk)}")

    # Причины решения
    reasons = _to_str_list(decision.get("reasons"))
    if reasons:
        lines.append("\n Ключевые факты: ")
        for r in reasons[:4]:
            lines.append(f"  • {r}")

    # Вопросы для HR
    questions = _to_str_list(decision.get("questions_for_hr"))
    if questions:
        lines.append("\n Уточнить на очном интервью: ")
        for q in questions[:3]:
            lines.append(f"  ❓ {q}")

    # Скиллы — безопасный срез через _to_str_list
    skills = _to_str_list(resume.get("skills"))
    if skills:
        lines.append(f"\n Навыки: {', '.join(skills[:6])}")

    return "\n".join(lines)
