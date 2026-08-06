"""Tests for the AI screening pipeline building blocks
(bot/ai/parser.py, bot/ai/schemas.py, bot/ai/models.py, bot/ai/agents.py helpers).

These tests avoid any real network calls to Cloudflare Workers AI — they only
exercise pure parsing/validation/scoring logic, which is where regressions
are most likely and cheapest to catch.

Required settings env vars are injected *before* importing any bot module,
since `bot.core.config.Settings()` is instantiated at import time and
requires `BOT_TOKEN` / `ADMIN_IDS` to be present.
"""

import os

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest

from bot.ai import models as ai_models
from bot.ai.agents import _compute_total_score, _is_language_sensitive, _safe_score
from bot.ai.parser import extract_json, extract_text
from bot.ai.schemas import DecisionResult, ResumeResult, parse_agent_result


# ── bot/ai/parser.py: extract_text ─────────────────────────────────────────────


def test_extract_text_handles_string_response() -> None:
    result = {"result": {"response": "  hello world  "}}
    assert extract_text(result) == "hello world"


def test_extract_text_handles_dict_response() -> None:
    result = {"result": {"response": {"content": "hello from dict"}}}
    assert extract_text(result) == "hello from dict"


def test_extract_text_handles_list_response() -> None:
    result = {"result": {"response": [{"content": "hello from list"}]}}
    assert extract_text(result) == "hello from list"


def test_extract_text_returns_none_for_empty_result() -> None:
    assert extract_text(None) is None
    assert extract_text({}) is None


def test_extract_text_returns_none_for_blank_string() -> None:
    result = {"result": {"response": "   "}}
    assert extract_text(result) is None


# ── bot/ai/parser.py: extract_json ─────────────────────────────────────────────


def test_extract_json_parses_valid_json() -> None:
    text = 'Here is the result: {"decision": "invite", "total_score": 8.5}'
    parsed = extract_json(text)
    assert parsed == {"decision": "invite", "total_score": 8.5}


def test_extract_json_fixes_single_quotes() -> None:
    text = "{'decision': 'invite', 'total_score': 8.5}"
    parsed = extract_json(text)
    assert parsed == {"decision": "invite", "total_score": 8.5}


def test_extract_json_returns_error_dict_when_no_json_found() -> None:
    parsed = extract_json("no json here at all")
    assert parsed["error"] == "no_json"


def test_extract_json_never_raises_on_garbage() -> None:
    parsed = extract_json("{not: valid, at: all!!!")
    assert isinstance(parsed, dict)
    assert "error" in parsed


# ── bot/ai/schemas.py: parse_agent_result ──────────────────────────────────────


def test_parse_agent_result_valid_data() -> None:
    raw = {
        "candidate": {"name": "Alice", "age": 25, "position_applied": "Повар"},
        "confidence": 0.9,
    }
    result = parse_agent_result(ResumeResult, raw, "resume")
    assert isinstance(result, ResumeResult)
    assert result.candidate.name == "Alice"
    assert result.error is None


def test_parse_agent_result_propagates_upstream_error() -> None:
    raw = {"error": "no_response"}
    result = parse_agent_result(ResumeResult, raw, "resume")
    assert result.error == "no_response"


def test_parse_agent_result_falls_back_on_invalid_shape() -> None:
    # "candidate" should be an object, not a string -> ValidationError -> fallback
    raw = {"candidate": "not-an-object"}
    result = parse_agent_result(ResumeResult, raw, "resume")
    assert result.error == "validation_error"


def test_decision_result_clamps_total_score_out_of_range() -> None:
    result = DecisionResult.model_validate({"total_score": 15})
    assert result.total_score == 10.0

    result_low = DecisionResult.model_validate({"total_score": -5})
    assert result_low.total_score == 0.0


# ── bot/ai/models.py: model selection constants ────────────────────────────────


def test_model_constants_are_assigned_expected_sizes() -> None:
    # Level 3 structured-comparison agents should use the cheaper 8B model.
    assert ai_models.COMMUNICATION_MODEL == ai_models.LLAMA_8B
    assert ai_models.JOB_MATCH_MODEL == ai_models.LLAMA_8B

    # Agents needing deep reasoning or generation should use the 70B model.
    assert ai_models.RESUME_MODEL == ai_models.LLAMA_70B
    assert ai_models.INTEGRITY_MODEL == ai_models.LLAMA_70B
    assert ai_models.HIRING_DECISION_MODEL == ai_models.LLAMA_70B
    assert ai_models.INTERVIEW_MODEL == ai_models.LLAMA_70B


# ── bot/ai/agents.py: pure helper functions ────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        (5, 5.0),
        ("7.5", 7.5),
        (15, 10.0),   # clamped to hi
        (-3, 0.0),    # clamped to lo
        (None, 0.0),  # invalid -> lo
        ("not-a-number", 0.0),
    ],
)
def test_safe_score_clamps_and_defaults(raw: object, expected: float) -> None:
    assert _safe_score(raw) == expected


@pytest.mark.parametrize(
    "position,expected",
    [
        ("Администратор", True),
        ("HR менеджер", True),
        ("Повар", False),
        ("Официант", False),
        ("", False),
    ],
)
def test_is_language_sensitive_detects_sensitive_positions(
    position: str, expected: bool
) -> None:
    assert _is_language_sensitive({"position": position}) is expected


def test_compute_total_score_uses_weighted_average() -> None:
    decision = DecisionResult.model_validate(
        {
            "scores": {
                "motivation": {"score": 10},
                "experience": {"score": 10},
                "communication": {"score": 5},
                "integrity": {"score": 5},
            }
        }
    )
    # 0.30*10 + 0.30*10 + 0.20*5 + 0.20*5 = 3 + 3 + 1 + 1 = 8.0
    assert _compute_total_score(decision) == 8.0
