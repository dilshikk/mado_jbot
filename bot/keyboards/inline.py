# bot/keyboards/inline.py

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.core.config import SHEET_URL

_EMPTY_USERNAME: frozenset[str] = frozenset({"отсутствует", "none", ""})

# ─── Линии метро ─────────────────────────────────────────────
# line_id → (emoji, name_ru, name_uz)
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


def get_languages_inline_keyboard(lang: str, selected: list[str]) -> InlineKeyboardMarkup:
    """Мультивыбор языков с toggle-кнопками."""
    options = [
        ("ru", "🇷🇺 Русский" if lang == "ru" else "🇷🇺 Rus"),
        ("uz", "🇺🇿 Узбекский" if lang == "ru" else "🇺🇿 O'zbek"),
        ("en", "🇬🇧 Английский" if lang == "ru" else "🇬🇧 Ingliz"),
        ("tr", "🇹🇷 Турецкий" if lang == "ru" else "🇹🇷 Turk"),
        ("other", "Другой" if lang == "ru" else "Boshqa"),
    ]
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for key, label in options:
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
    done_text = "✅ Tayyor" if lang == "uz" else "✅ Готово"
    rows.append([InlineKeyboardButton(text=done_text, callback_data="lang_done")])
    rows.append([InlineKeyboardButton(text=_skip_text(lang), callback_data="lang_skip")])
    rows.append([InlineKeyboardButton(text=_cancel_text(lang), callback_data="metro_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Форма анкеты — Inline ────────────────────────────────────────────────────

def get_gender_inline_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Выбор пола."""
    male = "🚹 Мужской" if lang == "ru" else "🚹 Erkak"
    female = "🚺 Женский" if lang == "ru" else "🚺 Ayol"
    cancel = _cancel_text(lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=male, callback_data="gender:male"),
            InlineKeyboardButton(text=female, callback_data="gender:female"),
        ],
        [InlineKeyboardButton(text=cancel, callback_data="form_cancel")],
    ])


def get_positions_inline_keyboard(lang: str, vacancies: list[dict]) -> InlineKeyboardMarkup:
    """Выбор вакансии (данные из БД)."""
    name_key = "name_ru" if lang == "ru" else "name_uz"
    cancel = _cancel_text(lang)
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for v in vacancies:
        name = (v.get(name_key) or "").strip()
        emoji = (v.get("emoji") or "").strip()
        label = f"{emoji} {name}".strip() if emoji else name
        pair.append(InlineKeyboardButton(
            text=label,
            callback_data=f"position:{v['id']}",
        ))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([InlineKeyboardButton(text=cancel, callback_data="form_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_schedule_inline_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Выбор графика работы."""
    from bot.lexicon import LOCALIZATION  # noqa: PLC0415
    t = LOCALIZATION.get(lang, LOCALIZATION["ru"])
    cancel = _cancel_text(lang)
    skip = _skip_text(lang)
    keys = [
        "schedule_6_1", "schedule_5_2", "schedule_3_1",
        "schedule_2_2", "schedule_full", "schedule_flex", "schedule_any",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for key in keys:
        pair.append(InlineKeyboardButton(text=t.get(key, key), callback_data=f"schedule:{key}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([InlineKeyboardButton(text=skip, callback_data="schedule:skip")])
    rows.append([InlineKeyboardButton(text=cancel, callback_data="form_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_smoking_inline_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Курите?"""
    from bot.lexicon import LOCALIZATION  # noqa: PLC0415
    t = LOCALIZATION.get(lang, LOCALIZATION["ru"])
    cancel = _cancel_text(lang)
    skip = _skip_text(lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t.get("smoking_no", "🚭 Нет"), callback_data="smoking:no"),
            InlineKeyboardButton(text=t.get("smoking_yes", "🚬 Да"), callback_data="smoking:yes"),
        ],
        [InlineKeyboardButton(text=skip, callback_data="smoking:skip")],
        [InlineKeyboardButton(text=cancel, callback_data="form_cancel")],
    ])


def get_med_book_inline_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Медицинская книжка."""
    from bot.lexicon import LOCALIZATION  # noqa: PLC0415
    t = LOCALIZATION.get(lang, LOCALIZATION["ru"])
    cancel = _cancel_text(lang)
    skip = _skip_text(lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t.get("med_book_yes", "✅ Да"), callback_data="med_book:yes"),
            InlineKeyboardButton(text=t.get("med_book_no", "❌ Нет"), callback_data="med_book:no"),
        ],
        [InlineKeyboardButton(
            text=t.get("med_book_in_progress", "⏳ В процессе"),
            callback_data="med_book:in_progress",
        )],
        [InlineKeyboardButton(text=skip, callback_data="med_book:skip")],
        [InlineKeyboardButton(text=cancel, callback_data="form_cancel")],
    ])


def get_confirmation_inline_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Подтверждение анкеты."""
    from bot.lexicon import LOCALIZATION  # noqa: PLC0415
    t = LOCALIZATION.get(lang, LOCALIZATION["ru"])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t.get("confirm_btn_yes", "✅ Всё верно — отправить"),
            callback_data="confirm:yes",
        )],
        [InlineKeyboardButton(
            text=t.get("confirm_btn_no", "🔄 Заполнить заново"),
            callback_data="confirm:no",
        )],
    ])


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
