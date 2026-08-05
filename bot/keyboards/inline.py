# bot/keyboards/inline.py

from datetime import datetime, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.core.config import SHEET_URL

_EMPTY_USERNAME: frozenset[str] = frozenset({"отсутствует", "none", ""})

# ─── Линии метро ─────────────────────────────────────────────
# line_id → (emoji, name_ru, name_uz)
METRO_LINES: dict[str, tuple[str, str, str]] = {
    "red":    ("🔴", "Чиланзарская",             "Chilonzor"),
    "blue":   ("🔵", "Узбекистанская",            "O'zbekiston"),
    "green":  ("🟢", "Юнусабадская",              "Yunusobod"),
    "orange": ("🟠", "30-летия Независимости",    "30 yillik Mustaqillik"),
}

def _skip_text(lang: str) -> str:
    return "O'tkazib yuborish" if lang == "uz" else "Пропустить"

def _cancel_text(lang: str) -> str:
    return "Bekor qilish" if lang == "uz" else "Отменить заполнение"

def get_metro_lines_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Первый шаг — выбор линии метро."""
    rows = []
    for line_id, (emoji, name_ru, name_uz) in METRO_LINES.items():
        name = name_uz if lang == "uz" else name_ru
        rows.append([InlineKeyboardButton(
            text=f"{emoji} {name}",
            callback_data=f"metro_line:{line_id}",
        )])
    rows.append([InlineKeyboardButton(text=_skip_text(lang), callback_data="metro_line:skip")])
    rows.append([InlineKeyboardButton(text=_cancel_text(lang), callback_data="metro_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_metro_stations_keyboard(
    stations: list[dict],
    line: str,
    lang: str,
) -> InlineKeyboardMarkup:
    """Второй шаг — выбор станции на выбранной линии."""
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

    back_text = "Ortga" if lang == "uz" else "Назад"
    rows.append([InlineKeyboardButton(text=back_text, callback_data="metro_back")])
    rows.append([InlineKeyboardButton(text=_cancel_text(lang), callback_data="metro_cancel")])
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

def get_interview_schedule_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    """Inline-клавиатура быстрого выбора даты собеседования.

    Показывает ближайшие 6 дней × 3 популярных времени (10:00, 14:00, 17:00).
    HR может также ввести дату вручную — просто написать сообщением.
    Кнопка «❌ Отмена» прерывает FSM без изменений.
    """
    today = datetime.now()
    rows: list[list[InlineKeyboardButton]] = []

    times = ["10:00", "14:00", "17:00"]
    months_ru = [
        "", "янв", "фев", "мар", "апр", "май", "июн",
        "июл", "авг", "сен", "окт", "ноя", "дек",
    ]

    for day_offset in range(0, 6):
        day = today + timedelta(days=day_offset)
        label_date = f"{day.day} {months_ru[day.month]}"
        row = []
        for t in times:
            label = f"{label_date} {t}"
            # Передаём дату в формате ДД.ММ в callback чтобы парсер подхватил
            value = f"{day.strftime('%d.%m')} в {t}"
            row.append(InlineKeyboardButton(
                text=label,
                callback_data=f"hr_schedule:{candidate_id}:{value}",
            ))
        rows.append(row)

    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"hr_schedule_cancel:{candidate_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
