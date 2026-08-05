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

# ─── Языки (ключ → (текст_ru, текст_uz)) ─────────────────────
_LANGUAGES: dict[str, tuple[str, str]] = {
    "ru":    ("🇷🇺 Русский",    "🇷🇺 Rus tili"),
    "uz":    ("🇺🇿 Узбекский",  "🇺🇿 O'zbek tili"),
    "en":    ("🇬🇧 Английский", "🇬🇧 Ingliz tili"),
    "tr":    ("🇹🇷 Турецкий",   "🇹🇷 Turk tili"),
    "other": ("🌐 Другой",      "🌐 Boshqa"),
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

    back_text = "Ortga" if lang == "uz" else "Назад"
    rows.append([InlineKeyboardButton(text=back_text, callback_data="metro_back")])
    rows.append([InlineKeyboardButton(text=_cancel_text(lang), callback_data="metro_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Языки владения (inline multiselect) ─────────────────────

def get_languages_inline_keyboard(
    lang: str,
    selected: list[str],
) -> InlineKeyboardMarkup:
    """Inline-клавиатура мультиселекта языков.

    selected — список уже выбранных ключей (например ['ru', 'en']).
    Выбранные помечаются ✅, не выбранные — пустые.
    """
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []

    for key, (text_ru, text_uz) in _LANGUAGES.items():
        label = text_uz if lang == "uz" else text_ru
        check = "✅ " if key in selected else ""
        pair.append(InlineKeyboardButton(
            text=f"{check}{label}",
            callback_data=f"lang_toggle:{key}",
        ))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)

    # Кнопка «Готово» — активна только если хоть что-то выбрано
    done_text = (
        ("✅ Tayyor" if lang == "uz" else "✅ Готово")
        if selected
        else ("⬆️ Tanlang" if lang == "uz" else "⬆️ Выберите хотя бы один")
    )
    rows.append([InlineKeyboardButton(
        text=done_text,
        callback_data="lang_done" if selected else "lang_none",
    )])
    rows.append([InlineKeyboardButton(
        text=_skip_text(lang),
        callback_data="lang_skip",
    )])
    rows.append([InlineKeyboardButton(
        text=_cancel_text(lang),
        callback_data="metro_cancel",  # переиспользуем metro_cancel → общий отмены анкеты
    )])
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
            InlineKeyboardButton(text="❌ Не подошёл",        callback_data=f"hr_reject:{candidate_id}"),
        ],
        [InlineKeyboardButton(text="⏸ На паузу", callback_data=f"hr_hold:{candidate_id}")],
    ])

def get_hr_action_keyboard(phone: str, username: str, candidate_id: int) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    clean = username.lstrip("@").strip().lower()
    if clean and clean not in _EMPTY_USERNAME:
        buttons.append([InlineKeyboardButton(text="💬 Telegram", url=f"https://t.me/{clean}")])
    buttons.append([
        InlineKeyboardButton(text="✅ Одобрить",   callback_data=f"hr_accept:{candidate_id}"),
        InlineKeyboardButton(text="❌ Отклонить",  callback_data=f"hr_reject:{candidate_id}"),
    ])
    buttons.append([InlineKeyboardButton(text="⏸ На паузу", callback_data=f"hr_hold:{candidate_id}")])
    buttons.append([InlineKeyboardButton(text="📊 Google Таблица", url=SHEET_URL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_hr_hold_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="▶️ Вернуть в работу", callback_data=f"hr_accept:{candidate_id}"),
        InlineKeyboardButton(text="❌ Отклонить",         callback_data=f"hr_reject:{candidate_id}"),
    ]])
