# bot/ai/interview.py
"""Recruiter AI — диалоговое интервью с кандидатом.

Оптимизация токенов (статефульный подход):
  Вместо полной истории Q&A отправляем compact state JSON +
  только последний обмен (O(1) вместо O(n)).
  Модель уже возвращала competency_status + answer_assessment;
  теперь они хранятся в FSM и передаются обратно.

Токены:
  4000 = ~2500-3000 reasoning + ~500-1000 content.
  Формат ответа: json_object (компетенции — динамические ключи, strict schema не подходит).
"""

import ast
import json
import logging
import re

from bot.ai.client import cf_chat
from bot.ai.models import INTERVIEW_MODEL
from bot.ai.prompts import INTERVIEW_SYSTEM
from bot.ai.schemas import JSON_OBJECT_FORMAT

logger = logging.getLogger(__name__)

MAX_QUESTIONS = 10
MIN_QUESTIONS = 5

_INTERVIEW_MAX_TOKENS = 4000
_SUMMARY_LINES_KEEP = 3


# ─── Парсинг ответа ───────────────────────────────────────────────────────────────────

def _extract_text(result: dict) -> str:
    inner = (result.get("result") or {}).get("response") or ""
    if isinstance(inner, dict):
        inner = inner.get("content") or inner.get("text") or str(inner)
    return str(inner).strip()


def _parse_step(raw: str) -> dict | None:
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


# ─── Состояние интервью (FSM) ────────────────────────────────────────────────────

def _make_empty_state() -> dict:
    return {"competency_status": {}, "candidate_summary": ""}


def _update_state(prev_state: dict, parsed: dict) -> dict:
    new_status = parsed.get("competency_status")
    if isinstance(new_status, dict) and new_status:
        competency_status = new_status
    else:
        competency_status = prev_state.get("competency_status", {})

    assessment = (parsed.get("answer_assessment") or "").strip()
    prev_summary = prev_state.get("candidate_summary", "")
    if assessment:
        lines = [ln for ln in prev_summary.split("\n") if ln.strip()]
        lines.append(f"— {assessment}")
        candidate_summary = "\n".join(lines[-_SUMMARY_LINES_KEEP:])
    else:
        candidate_summary = prev_summary

    return {"competency_status": competency_status, "candidate_summary": candidate_summary}


# ─── Построение сообщений ────────────────────────────────────────────────────────────

def _build_state_messages(
    form_data: dict,
    lang: str,
    interview_state: dict,
    last_qa: "dict | None",
    q_count: int,
) -> list[dict]:
    lang_hint = "Общайся на русском языке." if lang == "ru" else "O'zbek tilida gaplash."

    state: dict = {
        "vacancy": form_data.get("position", "—"),
        "lang_instruction": lang_hint,
        "questions_asked": q_count,
        "min_questions": MIN_QUESTIONS,
        "max_questions": MAX_QUESTIONS,
        "candidate_info": {
            "experience": form_data.get("experience", "—"),
        },
        "competency_status": interview_state.get("competency_status") or {},
        "candidate_summary": (
            interview_state.get("candidate_summary")
            or ("Интервью только начинается." if lang == "ru" else "Intervyu hozir boshlanmoqda.")
        ),
    }

    state_json = json.dumps(state, ensure_ascii=False, indent=2)
    context_label = "Текущее состояние интервью:" if lang == "ru" else "Joriy intervyu holati:"

    messages: list[dict] = [
        {"role": "system", "content": INTERVIEW_SYSTEM},
        {"role": "user",   "content": f"{context_label}\n{state_json}"},
    ]

    if last_qa:
        messages.append({"role": "assistant", "content": last_qa["q"]})
        messages.append({"role": "user",      "content": last_qa["a"]})

    return messages


# ─── Главная функция ──────────────────────────────────────────────────────────────────────

async def get_next_step(
    form_data: dict,
    lang: str,
    interview_state: dict,
    last_qa: "dict | None",
    q_count: int,
) -> dict:
    """Возвращает следующий шаг интервью.

    Returns:
        {
          "done": bool,
          "question": str,    # если done=False
          "reason": str,       # если done=True
          "new_state": dict,   # обновлённое состояние для FSM
        }
    """
    if q_count >= MAX_QUESTIONS:
        return {
            "done": True,
            "reason": f"Достигнут лимит {MAX_QUESTIONS} вопросов",
            "new_state": interview_state,
        }

    messages = _build_state_messages(
        form_data=form_data,
        lang=lang,
        interview_state=interview_state,
        last_qa=last_qa,
        q_count=q_count,
    )

    result = await cf_chat(
        model=INTERVIEW_MODEL,
        messages=messages,
        max_tokens=_INTERVIEW_MAX_TOKENS,
        text_format=JSON_OBJECT_FORMAT,   # competency_status — динамические ключи
    )

    if result is None:
        logger.warning("cf_chat вернул None — интервью завершается")
        return {"done": True, "reason": "AI недоступен", "new_state": interview_state}

    raw = _extract_text(result)
    logger.debug("CF raw ответ (интервью): %r", raw[:300] if raw else "<пусто>")

    if not raw:
        return {"done": True, "reason": "Пустой ответ AI", "new_state": interview_state}

    parsed = _parse_step(raw)

    if parsed is not None:
        new_state = _update_state(interview_state, parsed)

        if parsed.get("done"):
            return {
                "done": True,
                "reason": parsed.get("reason", "AI завершил интервью"),
                "new_state": new_state,
            }

        question = parsed.get("question", "").strip()
        if question:
            return {"done": False, "question": question, "new_state": new_state}

    # Модель вернула простой текст — это и есть вопрос
    return {
        "done": False,
        "question": raw,
        "new_state": {
            "competency_status": interview_state.get("competency_status", {}),
            "candidate_summary": interview_state.get("candidate_summary", ""),
        },
    }


def make_empty_state() -> dict:
    return _make_empty_state()
