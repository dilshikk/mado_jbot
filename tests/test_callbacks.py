"""Tests for inline-keyboard callback data generation and callback-data
parsing logic used across the metro selection flow and the HR review flow
(bot/keyboards/inline.py, bot/handlers/hr/actions.py).

These are pure functions that build aiogram keyboard objects or parse plain
strings — no Telegram API calls, no database, no event loop needed.

Required settings env vars are injected *before* importing any bot module,
since `bot.core.config.Settings()` is instantiated at import time and
requires `BOT_TOKEN` / `ADMIN_IDS` to be present.
"""

import os

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from datetime import datetime

import pytest

from bot.handlers.hr.actions import _parse_interview_datetime
from bot.keyboards.inline import (
    METRO_LINES,
    get_hr_action_keyboard,
    get_hr_hold_keyboard,
    get_languages_inline_keyboard,
    get_metro_lines_keyboard,
    get_metro_stations_keyboard,
    get_post_interview_keyboard,
    get_score_keyboard,
)


# ── get_metro_lines_keyboard ────────────────────────────────────────────────


def test_metro_lines_keyboard_has_a_row_per_line_plus_skip_and_cancel() -> None:
    markup = get_metro_lines_keyboard("ru")
    rows = markup.inline_keyboard

    # One row per metro line + "skip" row + "cancel" row.
    assert len(rows) == len(METRO_LINES) + 2

    line_callbacks = {row[0].callback_data for row in rows[: len(METRO_LINES)]}
    assert line_callbacks == {f"metro_line:{line_id}" for line_id in METRO_LINES}

    assert rows[-2][0].callback_data == "metro_line:skip"
    assert rows[-1][0].callback_data == "metro_cancel"


def test_metro_lines_keyboard_uses_uzbek_labels_for_uz_lang() -> None:
    markup_ru = get_metro_lines_keyboard("ru")
    markup_uz = get_metro_lines_keyboard("uz")

    ru_label = markup_ru.inline_keyboard[0][0].text
    uz_label = markup_uz.inline_keyboard[0][0].text

    assert ru_label != uz_label
    assert "Чиланзарская" in ru_label
    assert "Chilonzor" in uz_label


# ── get_metro_stations_keyboard ─────────────────────────────────────────────


def test_metro_stations_keyboard_pairs_stations_two_per_row() -> None:
    stations = [
        {"id": 1, "name_ru": "Чиланзар", "name_uz": "Chilonzor", "sort_order": 1},
        {"id": 2, "name_ru": "Бунёдкор", "name_uz": "Bunyodkor", "sort_order": 2},
        {"id": 3, "name_ru": "Новза", "name_uz": "Novza", "sort_order": 3},
    ]
    markup = get_metro_stations_keyboard(stations, line="red", lang="ru")
    rows = markup.inline_keyboard

    # 3 stations -> 2 rows of stations (2 + 1), then back row, then cancel row.
    assert len(rows[0]) == 2
    assert len(rows[1]) == 1
    assert rows[-2][0].callback_data == "metro_back"
    assert rows[-1][0].callback_data == "metro_cancel"


def test_metro_stations_keyboard_orders_by_sort_order() -> None:
    stations = [
        {"id": 2, "name_ru": "Бунёдкор", "name_uz": "Bunyodkor", "sort_order": 2},
        {"id": 1, "name_ru": "Чиланзар", "name_uz": "Chilonzor", "sort_order": 1},
    ]
    markup = get_metro_stations_keyboard(stations, line="red", lang="ru")

    first_row = markup.inline_keyboard[0]
    assert first_row[0].callback_data == "metro_station:1"
    assert first_row[1].callback_data == "metro_station:2"


def test_metro_stations_keyboard_uses_requested_language_names() -> None:
    stations = [{"id": 1, "name_ru": "Чиланзар", "name_uz": "Chilonzor", "sort_order": 1}]

    markup_ru = get_metro_stations_keyboard(stations, line="red", lang="ru")
    markup_uz = get_metro_stations_keyboard(stations, line="red", lang="uz")

    assert markup_ru.inline_keyboard[0][0].text == "Чиланзар"
    assert markup_uz.inline_keyboard[0][0].text == "Chilonzor"


# ── get_languages_inline_keyboard ───────────────────────────────────────────


def test_languages_inline_keyboard_marks_selected_options() -> None:
    markup = get_languages_inline_keyboard("ru", selected=["ru", "en"])

    all_buttons = [btn for row in markup.inline_keyboard for btn in row]
    ru_button = next(b for b in all_buttons if b.callback_data == "lang_toggle:ru")
    uz_button = next(b for b in all_buttons if b.callback_data == "lang_toggle:uz")

    assert ru_button.text.startswith("✅")
    assert not uz_button.text.startswith("✅")


def test_languages_inline_keyboard_includes_done_and_skip() -> None:
    markup = get_languages_inline_keyboard("ru", selected=[])
    last_row_callbacks = {btn.callback_data for btn in markup.inline_keyboard[-1]}

    assert last_row_callbacks == {"lang_done", "lang_skip"}


# ── get_score_keyboard ──────────────────────────────────────────────────────


def test_score_keyboard_has_five_star_buttons_with_candidate_id() -> None:
    markup = get_score_keyboard(candidate_id=42)
    buttons = markup.inline_keyboard[0]

    assert len(buttons) == 5
    assert [b.callback_data for b in buttons] == [f"score:{i}:42" for i in range(1, 6)]


# ── get_hr_action_keyboard ───────────────────────────────────────────────────


def test_hr_action_keyboard_includes_telegram_link_for_valid_username() -> None:
    markup = get_hr_action_keyboard(phone="+998900000000", username="@alice", candidate_id=7)
    first_row = markup.inline_keyboard[0]

    assert first_row[0].url == "https://t.me/alice"


@pytest.mark.parametrize("username", ["", "None", "отсутствует", "  "])
def test_hr_action_keyboard_omits_telegram_link_for_empty_username(username: str) -> None:
    markup = get_hr_action_keyboard(phone="+998900000000", username=username, candidate_id=7)
    first_row = markup.inline_keyboard[0]

    # No Telegram link row -> first row is directly the accept/reject row.
    assert first_row[0].callback_data == "hr_accept:7"


def test_hr_action_keyboard_always_includes_accept_reject_hold_and_sheet() -> None:
    markup = get_hr_action_keyboard(phone="+998900000000", username="", candidate_id=7)
    callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row if btn.callback_data]

    assert "hr_accept:7" in callbacks
    assert "hr_reject:7" in callbacks
    assert "hr_hold:7" in callbacks


def test_hr_hold_keyboard_offers_resume_and_reject() -> None:
    markup = get_hr_hold_keyboard(candidate_id=9)
    callbacks = [btn.callback_data for btn in markup.inline_keyboard[0]]

    assert callbacks == ["hr_accept:9", "hr_reject:9"]


def test_post_interview_keyboard_offers_hire_reject_hold() -> None:
    markup = get_post_interview_keyboard(candidate_id=3)
    callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]

    assert callbacks == ["hr_hire:3", "hr_reject:3", "hr_hold:3"]


# ── _parse_interview_datetime ────────────────────────────────────────────────


def test_parse_interview_datetime_with_full_date_and_dash_separator() -> None:
    result = _parse_interview_datetime("05.08.2026 в 10:00")
    assert result == "2026-08-05 10:00"


def test_parse_interview_datetime_with_full_date_no_connector() -> None:
    result = _parse_interview_datetime("05.08.2026 10:00")
    assert result == "2026-08-05 10:00"


def test_parse_interview_datetime_infers_current_year_when_missing() -> None:
    current_year = datetime.now().year
    result = _parse_interview_datetime("25.12 в 14:00")
    assert result == f"{current_year}-12-25 14:00"


def test_parse_interview_datetime_returns_none_for_unparseable_text() -> None:
    assert _parse_interview_datetime("как-нибудь на следующей неделе") is None


def test_parse_interview_datetime_extracts_from_surrounding_text() -> None:
    # The quick-schedule keyboard sends values like "05.08 в 10:00" embedded
    # in longer callback payloads; the parser must find the date anywhere.
    result = _parse_interview_datetime("Собеседование назначено на 05.08 в 10:00, будьте готовы")
    current_year = datetime.now().year
    assert result == f"{current_year}-08-05 10:00"
