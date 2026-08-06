# bot/keyboards/inline.py

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.core.config import SHEET_URL

_EMPTY_USERNAME: frozenset[str] = frozenset({"отсутствует", "none", ""})

# ─── Линии метро ─────────────────────────────────────────────
METRO_LINES: dict[str, tuple[str, str, str]] = {
    "red": ("🔴", "Чиланзарская", "Chilonzor"),
    "blue": ("🔵", "Узбекистанская", "O'zbekiston"),
    "green": ("🟢", "Юнусабадская", "Yunusobod"),
    "orange": ("🟠", "30-летия Независимости", "30 yillik Mustaqillik"),
}

def _skip_text(lang: str) -> str:
    return "O'tkazib yuborish" if lang == "uz" else "Пропустить"

def _cancel_text(lang: str) -> str:
    return "Bekor qilish" if lang == "uz" else "Отменить заполнение"

def get_metro_lines_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = []
    for line_id, (emoji, name_ru, name_uz) in METRO_LINES.items():
        name = name_uz if lang == "uz" else name_ru
        rows.append([InlineKeyboardButton(text=f"{emoji} {name}", callback_data=f"metro_line:{line_id}")])
    rows.append([InlineKeyboardButton(text=_skip_text(lang), callback_data="metro_line:skip")])
    rows.append([InlineKeyboardButton(text=_cancel_text(lang), callback_data="metro_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_metro_stations_keyboard(stations: list[dict], line: str, lang: str) -> InlineKeyboardMarkup:
    name_key = "name_uz" if lang == "uz" else "name_ru"
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for s in sorted(stations, key=lambda x: x.get("sort_order", 0)):
        pair.append(InlineKeyboardButton(text=s[name_key], callback_data=f"metro_station:{s['id']}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    back_text = "Ortga" if lang == "uz" else "Назад"
    rows.append([InlineKeyboardButton(text=back_text, callback_data="metro_back")])
    rows.append([InlineKeyboardButton(text=_cancel_text(lang), callback_data="metro_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Форма анкеты — Inline ────────────────────────────────────────────────────

def get_readiness_inline_keyboard(lang: str) -> InlineKeyboardMarkup:
    from bot.lexicon import LOCALIZATION  # noqa: PLC0415
    t = LOCALIZATION.get(lang, LOCALIZATION["ru"])
    cancel = _cancel_text(lang)
    skip = _skip_text(lang)
    keys = [
        ("readiness_today", "readiness:today"),
        ("readiness_tomorrow", "readiness:tomorrow"),
        ("readiness_week", "readiness:week"),
        ("readiness_two_weeks", "readiness:two_weeks"),
        ("readiness_month", "readiness:month"),
    ]
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for lex_key, cb_data in keys:
        pair.append(InlineKeyboardButton(text=t.get(lex_key, lex_key), callback_data=cb_data))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([InlineKeyboardButton(text=skip, callback_data="readiness:skip")])
    rows.append([InlineKeyboardButton(text=cancel, callback_data="form_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── HR-клавиатуры ───────────────────────────────────────────

def get_score_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{i}⭐", callback_data=f"score:{i}:{candidate_id}")
        for i in range(1, 6)
    ]])

def get_post_interview_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏆 Принять на работу", callback_data=f"hr_hire:{candidate_id}"),
            InlineKeyboardButton(text="❌ Не подошёл", callback_data=f"hr_reject:{candidate_id}"),
        ],
        [InlineKeyboardButton(text="⏸ На паузу", callback_data=f"hr_hold:{candidate_id}")],
    ])

def get_hr_action_keyboard(phone: str, username: str, candidate_id: int) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    clean = username.lstrip("@").strip().lower()
    if clean and clean not in _EMPTY_USERNAME:
        buttons.append([InlineKeyboardButton(text="💬 Telegram", url=f"https://t.me/{clean}")])
    buttons.append([
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"hr_accept:{candidate_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"hr_reject:{candidate_id}"),
    ])
    buttons.append([InlineKeyboardButton(text="⏸ На паузу", callback_data=f"hr_hold:{candidate_id}")])
    buttons.append([InlineKeyboardButton(text="📊 Google Таблица", url=SHEET_URL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_hr_hold_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="▶️ Вернуть в работу", callback_data=f"hr_accept:{candidate_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"hr_reject:{candidate_id}"),
    ]])


# ─── Admin: Главное меню (Inline) ────────────────────────────────────────────

def get_admin_menu_inline_kb() -> InlineKeyboardMarkup:
    """Главное меню панели администратора."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📢 Рассылка",        callback_data="admin:broadcast"),
            InlineKeyboardButton(text="💼 Вакансии",        callback_data="admin:vacancies"),
        ],
        [
            InlineKeyboardButton(text="🚇 Метро",           callback_data="admin:metro"),
            InlineKeyboardButton(text="📊 Дашборд",         callback_data="admin:dashboard"),
        ],
        [
            InlineKeyboardButton(text="👮 Администраторы",  callback_data="admin:adminlist"),
            InlineKeyboardButton(text="📋 Resend",          callback_data="admin:resend"),
        ],
    ])


# ─── Admin: Вакансии (Inline) ─────────────────────────────────────────────────

def get_admin_vacancies_inline_kb(vacancies: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for v in vacancies:
        status = "✅" if v["is_active"] else "❌"
        parts = [status]
        if v.get("emoji"):
            parts.append(v["emoji"])
        parts.append(v["name_ru"])
        label = " ".join(parts)
        pair.append(InlineKeyboardButton(text=label, callback_data=f"vac:select:{v['id']}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([
        InlineKeyboardButton(text="➕ Добавить", callback_data="vac:add"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data="vac:refresh"),
    ])
    rows.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="vac:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_admin_vacancy_item_inline_kb(vacancy_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "❌ Выключить" if is_active else "✅ Включить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"vac:toggle:{vacancy_id}")],
        [
            InlineKeyboardButton(text="✏️ Изменить", callback_data=f"vac:edit:{vacancy_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"vac:delete:{vacancy_id}"),
        ],
        [InlineKeyboardButton(text="◀️ К вакансиям", callback_data="vac:list")],
    ])


def get_admin_vacancy_edit_inline_kb(vacancy_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Название (рус)", callback_data=f"vac:editfield:{vacancy_id}:name_ru"),
            InlineKeyboardButton(text="🇺🇿 Название (узб)", callback_data=f"vac:editfield:{vacancy_id}:name_uz"),
        ],
        [InlineKeyboardButton(text="😊 Эмодзи", callback_data=f"vac:editfield:{vacancy_id}:emoji")],
        [InlineKeyboardButton(text="◀️ К вакансиям", callback_data="vac:list")],
    ])


def get_admin_vacancy_confirm_delete_inline_kb(vacancy_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"vac:confirm_delete:{vacancy_id}"),
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"vac:select:{vacancy_id}"),
        ],
    ])
