"""Tests for the AI interview question engine, its process-local locks, and
the fallback question picker used by the candidate interview FSM handler
(bot/ai/interview.py, bot/locks.py, bot/handlers/user/interview.py).

Only pure logic is exercised — no real network calls to Cloudflare. With no
`CLOUDFLARE_ACCOUNT_ID`/`CLOUDFLARE_API_TOKEN` secrets configured,
`settings.ai_available` is False, so `cf_chat()` (and therefore
`get_next_step()`) short-circuits to `None`/a "done" step without touching
the network — this is the real code path, not a mock.

Required settings env vars are injected *before* importing any bot module,
since `bot.core.config.Settings()` is instantiated at import time and
requires `BOT_TOKEN` / `ADMIN_IDS` to be present.
"""

import os

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import asyncio

import pytest

from bot.ai.interview import (
    MAX_QUESTIONS,
    MIN_QUESTIONS,
    _build_messages,
    _get_vacancy_context,
    _parse_step,
    get_next_step,
)
from bot.handlers.user.interview import _fallback_question
from bot.locks import interview_lock, submission_lock


# ── bot/ai/interview.py: _get_vacancy_context ───────────────────────────────


def test_get_vacancy_context_matches_known_position() -> None:
    context = _get_vacancy_context("Официант")
    assert "гостями" in context


def test_get_vacancy_context_matches_case_insensitively_and_partial() -> None:
    context = _get_vacancy_context("Старший бариста")
    assert "кофе" in context.lower()


def test_get_vacancy_context_falls_back_to_default_for_unknown_position() -> None:
    context = _get_vacancy_context("Космонавт")
    assert "мотивация работать в MADO" in context


# ── bot/ai/interview.py: _parse_step ─────────────────────────────────────────


def test_parse_step_extracts_json_object() -> None:
    raw = 'Вот шаг: {"done": false, "question": "Почему вы хотите эту работу?"}'
    parsed = _parse_step(raw)
    assert parsed == {"done": False, "question": "Почему вы хотите эту работу?"}


def test_parse_step_extracts_python_dict_with_single_quotes() -> None:
    raw = "{'done': True, 'reason': 'готово'}"
    parsed = _parse_step(raw)
    assert parsed == {"done": True, "reason": "готово"}


def test_parse_step_returns_none_when_no_done_key() -> None:
    raw = '{"question": "Без ключа done"}'
    assert _parse_step(raw) is None


def test_parse_step_returns_none_for_non_json_text() -> None:
    assert _parse_step("просто текст без скобок") is None


# ── bot/ai/interview.py: _build_messages ────────────────────────────────────


def test_build_messages_includes_system_prompt_and_position() -> None:
    messages = _build_messages(
        form_data={"position": "Повар", "name": "Иван"}, qa_log=[], lang="ru"
    )
    assert messages[0]["role"] == "system"
    assert "Повар" in messages[0]["content"]
    assert "Иван" in messages[0]["content"]


def test_build_messages_marks_known_fields_to_avoid_repeat_questions() -> None:
    messages = _build_messages(
        form_data={"position": "Официант", "phone": "+998900000000"},
        qa_log=[],
        lang="ru",
    )
    assert "+998900000000" in messages[0]["content"]


def test_build_messages_appends_qa_history_as_alternating_turns() -> None:
    qa_log = [{"q": "Вопрос 1?", "a": "Ответ 1"}, {"q": "Вопрос 2?", "a": "Ответ 2"}]
    messages = _build_messages(form_data={"position": "Кассир"}, qa_log=qa_log, lang="ru")

    # system + 2 pairs of (assistant question, user answer)
    assert len(messages) == 5
    assert messages[1] == {"role": "assistant", "content": "Вопрос 1?"}
    assert messages[2] == {"role": "user", "content": "Ответ 1"}
    assert messages[3] == {"role": "assistant", "content": "Вопрос 2?"}
    assert messages[4] == {"role": "user", "content": "Ответ 2"}


def test_build_messages_uses_uzbek_language_hint() -> None:
    messages = _build_messages(form_data={"position": "Повар"}, qa_log=[], lang="uz")
    assert "O'zbek tilida" in messages[0]["content"]


# ── bot/ai/interview.py: get_next_step ──────────────────────────────────────


@pytest.mark.asyncio
async def test_get_next_step_finishes_when_max_questions_reached() -> None:
    qa_log = [{"q": f"Q{i}", "a": f"A{i}"} for i in range(MAX_QUESTIONS)]
    step = await get_next_step(form_data={"position": "Повар"}, qa_log=qa_log, lang="ru")

    assert step["done"] is True
    assert str(MAX_QUESTIONS) in step["reason"]


@pytest.mark.asyncio
async def test_get_next_step_finishes_when_ai_unavailable() -> None:
    # No Cloudflare credentials configured in the test environment, so
    # cf_chat() short-circuits without any network call.
    step = await get_next_step(form_data={"position": "Повар"}, qa_log=[], lang="ru")

    assert step["done"] is True
    assert step["reason"] == "AI недоступен"


def test_min_questions_is_lower_than_max_questions() -> None:
    assert MIN_QUESTIONS < MAX_QUESTIONS


# ── bot/handlers/user/interview.py: _fallback_question ──────────────────────


def test_fallback_question_returns_unused_russian_question() -> None:
    asked = ["почему вы хотите работать в mado?"]
    question = _fallback_question("ru", qa_log=[], asked_questions=asked)

    assert question != "Почему вы хотите работать в MADO?"
    assert question.casefold() in asked


def test_fallback_question_returns_uzbek_question_for_uz_lang() -> None:
    question = _fallback_question("uz", qa_log=[], asked_questions=[])
    assert question == "Nega MADOda ishlamoqchisiz?"


def test_fallback_question_falls_back_to_first_when_pool_exhausted() -> None:
    pool_ru_first = "Почему вы хотите работать в MADO?"
    all_asked = [
        "почему вы хотите работать в mado?",
        "расскажите о вашем опыте работы с гостями.",
        "как вы обычно работаете в команде?",
        "как вы ведёте себя в стрессовой ситуации на работе?",
        "какие у вас карьерные цели на ближайший год?",
        "какой ваш самый полезный навык для этой вакансии?",
    ]
    question = _fallback_question("ru", qa_log=[], asked_questions=list(all_asked))
    assert question == pool_ru_first


# ── bot/locks.py: submission_lock / interview_lock ──────────────────────────


def test_submission_lock_returns_same_lock_instance_for_same_user() -> None:
    lock_a = submission_lock(user_id=1)
    lock_b = submission_lock(user_id=1)
    assert lock_a is lock_b


def test_submission_lock_returns_different_locks_for_different_users() -> None:
    lock_a = submission_lock(user_id=1)
    lock_b = submission_lock(user_id=2)
    assert lock_a is not lock_b


def test_interview_lock_returns_same_lock_instance_for_same_session() -> None:
    lock_a = interview_lock(session_id=100)
    lock_b = interview_lock(session_id=100)
    assert lock_a is lock_b


@pytest.mark.asyncio
async def test_interview_lock_serializes_concurrent_access() -> None:
    session_id = 200
    order: list[str] = []

    async def critical_section(name: str) -> None:
        async with interview_lock(session_id):
            order.append(f"{name}:start")
            await asyncio.sleep(0.01)
            order.append(f"{name}:end")

    await asyncio.gather(critical_section("a"), critical_section("b"))

    # One task must fully finish before the other starts — no interleaving.
    assert order in (
        ["a:start", "a:end", "b:start", "b:end"],
        ["b:start", "b:end", "a:start", "a:end"],
    )
