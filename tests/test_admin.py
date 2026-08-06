"""Tests for pure admin-panel helper functions: vacancy and metro station
management keyboards/text builders and the shared admin-only guard
(bot/handlers/admin/vacancies.py, bot/handlers/admin/metro_stations.py).

These are pure functions that build aiogram keyboard objects or format
plain text — no Telegram API calls, no database, no event loop needed.

Required settings env vars are injected *before* importing any bot module,
since `bot.core.config.Settings()` is instantiated at import time and
requires `BOT_TOKEN` / `ADMIN_IDS` to be present.
"""

import os

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1,2")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from bot.handlers.admin import metro_stations as ms
from bot.handlers.admin import vacancies as vac


# ── bot/handlers/admin/vacancies.py: _is_admin ──────────────────────────────


def test_vacancies_is_admin_true_for_configured_ids() -> None:
    assert vac._is_admin(1) is True
    assert vac._is_admin(2) is True


def test_vacancies_is_admin_false_for_unknown_id() -> None:
    assert vac._is_admin(999) is False


# ── bot/handlers/admin/vacancies.py: _vacancies_keyboard ────────────────────


def test_vacancies_keyboard_shows_active_and_inactive_status() -> None:
    vacancies = [
        {"id": 1, "name_ru": "Повар", "emoji": "👨‍🍳", "is_active": 1},
        {"id": 2, "name_ru": "Официант", "emoji": "🤵", "is_active": 0},
    ]
    markup = vac._vacancies_keyboard(vacancies)
    rows = markup.inline_keyboard

    assert rows[0][0].text.startswith("✅")
    assert rows[0][0].callback_data == "vac:toggle:1"
    assert rows[1][0].text.startswith("❌")
    assert rows[1][0].callback_data == "vac:toggle:2"


def test_vacancies_keyboard_includes_edit_and_delete_buttons_per_row() -> None:
    vacancies = [{"id": 5, "name_ru": "Кассир", "emoji": "💵", "is_active": 1}]
    markup = vac._vacancies_keyboard(vacancies)
    row = markup.inline_keyboard[0]

    callbacks = [btn.callback_data for btn in row]
    assert callbacks == ["vac:toggle:5", "vac:edit:5", "vac:delete:5"]


def test_vacancies_keyboard_appends_add_and_refresh_rows() -> None:
    markup = vac._vacancies_keyboard([])
    callbacks = [row[0].callback_data for row in markup.inline_keyboard]

    assert callbacks == ["vac:add", "vac:refresh"]


# ── bot/handlers/admin/vacancies.py: _vacancy_list_text ────────────────────


def test_vacancy_list_text_counts_active_and_total() -> None:
    vacancies = [
        {"is_active": 1}, {"is_active": 1}, {"is_active": 0},
    ]
    text = vac._vacancy_list_text(vacancies)

    assert "Всего: <b>3</b>" in text
    assert "Активных: <b>2</b>" in text


# ── bot/handlers/admin/vacancies.py: _confirm_delete_keyboard ───────────────


def test_confirm_delete_keyboard_has_confirm_and_cancel() -> None:
    markup = vac._confirm_delete_keyboard(vacancy_id=8)
    callbacks = [btn.callback_data for btn in markup.inline_keyboard[0]]

    assert callbacks == ["vac:delete_confirm:8", "vac:refresh"]


# ── bot/handlers/admin/vacancies.py: _edit_field_keyboard ──────────────────


def test_edit_field_keyboard_offers_name_and_emoji_fields() -> None:
    markup = vac._edit_field_keyboard(vacancy_id=4)
    callbacks = [row[0].callback_data for row in markup.inline_keyboard]

    assert callbacks == [
        "vac:edit_field:4:name_ru",
        "vac:edit_field:4:name_uz",
        "vac:edit_field:4:emoji",
        "vac:refresh",
    ]


# ── bot/handlers/admin/metro_stations.py: _is_admin ─────────────────────────


def test_metro_stations_is_admin_true_for_configured_ids() -> None:
    assert ms._is_admin(1) is True


def test_metro_stations_is_admin_false_for_unknown_id() -> None:
    assert ms._is_admin(999) is False


# ── bot/handlers/admin/metro_stations.py: _lines_keyboard ───────────────────


def test_lines_keyboard_has_a_row_per_line_plus_add_and_refresh() -> None:
    markup = ms._lines_keyboard()
    rows = markup.inline_keyboard

    assert len(rows) == len(ms.LINES) + 2
    line_callbacks = {row[0].callback_data for row in rows[: len(ms.LINES)]}
    assert line_callbacks == {f"ms:line:{key}" for key in ms.LINES}
    assert rows[-2][0].callback_data == "ms:add"
    assert rows[-1][0].callback_data == "ms:refresh"


# ── bot/handlers/admin/metro_stations.py: _stations_keyboard ───────────────


def test_stations_keyboard_shows_status_and_toggle_delete_buttons() -> None:
    stations = [
        {"id": 10, "name_ru": "Чиланзар", "active": 1},
        {"id": 11, "name_ru": "Бунёдкор", "active": 0},
    ]
    markup = ms._stations_keyboard(stations, line="red")
    rows = markup.inline_keyboard

    assert rows[0][0].text.startswith("✅")
    assert rows[0][0].callback_data == "ms:toggle:10:red"
    assert rows[0][1].callback_data == "ms:delete:10:red"
    assert rows[1][0].text.startswith("❌")
    assert rows[-1][0].callback_data == "ms:back"


# ── bot/handlers/admin/metro_stations.py: _confirm_delete_keyboard ─────────


def test_metro_confirm_delete_keyboard_has_confirm_and_cancel_for_line() -> None:
    markup = ms._confirm_delete_keyboard(station_id=7, line="blue")
    callbacks = [btn.callback_data for btn in markup.inline_keyboard[0]]

    assert callbacks == ["ms:delete_confirm:7:blue", "ms:line:blue"]


# ── bot/handlers/admin/metro_stations.py: _line_select_keyboard ────────────


def test_line_select_keyboard_uses_add_line_prefix() -> None:
    markup = ms._line_select_keyboard()
    callbacks = [row[0].callback_data for row in markup.inline_keyboard]

    assert callbacks[:-1] == [f"ms:add_line:{key}" for key in ms.LINES]
    assert callbacks[-1] == "ms:add_cancel"


# ── bot/handlers/admin/metro_stations.py: _metro_menu_text ──────────────────


def test_metro_menu_text_reports_totals() -> None:
    text = ms._metro_menu_text(total=42, active=40)

    assert "Всего: <b>42</b>" in text
    assert "Активных: <b>40</b>" in text
