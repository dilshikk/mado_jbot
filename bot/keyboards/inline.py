# bot/keyboards/inline.py

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.core.config import SHEET_URL

_EMPTY_USERNAME: frozenset[str] = frozenset({"отсутствует", "none", ""})

# ─── Линии метро ─────────────────────────────────────────────
# line_id → (emoji, name_ru, name_uz)
METRO_LINES: dict[str, tuple[str, str, str]] = {
    "red":    ("🔴", "Чиланзарская",          "Chilonzor"),
    "blue":   ("🔵", "Узбекистанская",         "O'zbekiston"),
    "green":  ("🟢", "Юнусабадская",           "Yunusobod"),
    "orange": ("🟠", "30-летия Независимости", "30 yillik Mustaqillik"),
}


def get_metro_lines_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Первый шаг — выбор линии метро."""
    rows = []
    for line_id, (emoji, name_ru, name_uz) in METRO_LINES.items():
        name = name_uz if lang == "uz" else name_ru
        rows.append([InlineKeyboardButton(
            text=f"{emoji} {name}",
            callback_data=f"metro_line:{line_id}",
        )])
    skip_text   = "⏭ O'tkazish" if lang == "uz" else "⏭ Пропустить"
    cancel_text = "❌ Bekor qilish" if lang == "uz" else "❌ Отменить заполнение"
    rows.append([InlineKeyboardButton(text=skip_text,   callback_data="metro_line:skip")])
    rows.append([InlineKeyboardButton(text=cancel_text, callback_data="metro_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_metro_stations_keyboard(
    stations: list[dict],
    line: str,
    lang: str,
) -> InlineKeyboardMarkup:
    """Второй шаг — выбор станции на выбранной линии.

    stations — список dict из БД (поля: id, name_ru, name_uz, sort_order).
    По 2 станции в ряд.
    """
    name_key = "name_uz" if lang == "uz" else "name_ru"
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for s in sorted(stations, key=lambda x: x.get("sort_order", 0)):
        pair.append(InlineKeyboardButton(
            text=s[name_key],
            callback_data=f"metro_station:{s['id']}",
        ))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)

    # Кнопка «Назад» с названием линии
    line_info = METRO_LINES.get(line)
    if line_info:
        back_label = line_info[2] if lang == "uz" else line_info[1]
        back_text  = f"⬅ {back_label}"
    else:
        back_text = "⬅ Назад" if lang != "uz" else "⬅ Ortga"
    rows.append([InlineKeyboardButton(text=back_text, callback_data="metro_back")])

    cancel_text = "❌ Bekor qilish" if lang == "uz" else "❌ Отменить заполнение"
    rows.append([InlineKeyboardButton(text=cancel_text, callback_data="metro_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── HR-клавиатуры ───────────────────────────────────────────

def get_score_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    """Кнопки оценки кандидата 1–5 звёзд."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{i}⭐", callback_data=f"score:{i}:{candidate_id}")
        for i in range(1, 6)
    ]])


def get_post_interview_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    """Клавиатура после собеседования."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏆 Принять на работу", callback_data=f"hr_hire:{candidate_id}"),
            InlineKeyboardButton(text="❌ Не подошёл",         callback_data=f"hr_reject:{candidate_id}"),
        ],
        [InlineKeyboardButton(text="⏸ На паузу", callback_data=f"hr_hold:{candidate_id}")],
    ])


def get_hr_action_keyboard(phone: str, username: str, candidate_id: int) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    clean = username.lstrip("@").strip().lower()
    if clean and clean not in _EMPTY_USERNAME:
        buttons.append([InlineKeyboardButton(text="💬 Telegram", url=f"https://t.me/{clean}")])
    buttons.append([
        InlineKeyboardButton(text="✅ Одобрить",  callback_data=f"hr_accept:{candidate_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"hr_reject:{candidate_id}"),
    ])
    buttons.append([InlineKeyboardButton(text="⏸ На паузу", callback_data=f"hr_hold:{candidate_id}")])
    buttons.append([InlineKeyboardButton(text="📊 Google Таблица", url=SHEET_URL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_hr_hold_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="▶️ Вернуть в работу", callback_data=f"hr_accept:{candidate_id}"),
        InlineKeyboardButton(text="❌ Отклонить",         callback_data=f"hr_reject:{candidate_id}"),
    ]])
