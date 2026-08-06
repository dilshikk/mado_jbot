"""Tests for bot/ai/resume.py — the legacy single-shot AI screening helper
used as a fallback before/without the full interview pipeline.

Required settings env vars are injected *before* importing any bot module,
since `bot.core.config.Settings()` is instantiated at import time and
requires `BOT_TOKEN` / `ADMIN_IDS` to be present. We deliberately do NOT set
Cloudflare credentials, so `settings.ai_available` stays False and
`screen_application` never performs a real network call — it exercises the
"AI unavailable" short-circuit path, which is safe and deterministic to test.
"""

import os

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest

from bot.ai.resume import _build_prompt, _calc_age, screen_application
from bot.core.config import settings


# ── _calc_age ───────────────────────────────────────────────────────────────


def test_calc_age_computes_correct_age_for_past_birthday_this_year() -> None:
    from datetime import datetime

    today = datetime.now()
    # A birthday earlier in the year than today guarantees the birthday
    # has already passed, so age = today.year - birth.year.
    birthday = f"01.01.{today.year - 25}"
    assert _calc_age(birthday) == 25


def test_calc_age_returns_none_for_missing_birthday() -> None:
    assert _calc_age(None) is None
    assert _calc_age("") is None


def test_calc_age_returns_none_for_invalid_format() -> None:
    assert _calc_age("not-a-date") is None
    assert _calc_age("2000-01-01") is None  # wrong format (expects dd.mm.yyyy)


def test_calc_age_accounts_for_birthday_not_yet_reached_this_year() -> None:
    from datetime import datetime, timedelta

    today = datetime.now()
    future_date = today + timedelta(days=7)
    # Birthday is a week from now but N years ago -> hasn't occurred yet this year.
    birthday = future_date.strftime(f"%d.%m.{today.year - 30}")
    assert _calc_age(birthday) == 29


# ── _build_prompt ───────────────────────────────────────────────────────────


def test_build_prompt_includes_all_known_fields() -> None:
    data = {
        "position": "Повар",
        "birthday": "01.01.2000",
        "experience": "3 года",
        "gender": "Мужской",
        "family": "Не женат",
        "citizenship": "Узбекистан",
        "address": "Ташкент",
        "video_duration": 20,
    }
    prompt = _build_prompt(data)

    assert "Повар" in prompt
    assert "3 года" in prompt
    assert "Мужской" in prompt
    assert "Не женат" in prompt
    assert "Узбекистан" in prompt
    assert "Ташкент" in prompt
    assert "20" in prompt


def test_build_prompt_uses_placeholder_for_missing_fields() -> None:
    prompt = _build_prompt({})

    assert "—" in prompt
    assert "неизвестен" in prompt  # age placeholder when birthday is missing


# ── screen_application ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_screen_application_returns_none_when_ai_unavailable() -> None:
    # No Cloudflare credentials configured in this test environment.
    assert settings.ai_available is False

    result = await screen_application({"position": "Официант"})
    assert result is None
