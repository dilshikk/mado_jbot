# bot/keyboards/inline_form.py
"""Inline-клавиатуры для новых шагов анкеты кандидата."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.lexicon import LOCALIZATION


def _t(lang: str, key: str) -> str:
    return LOCALIZATION[lang].get(key, key)


# ─── Опыт работы (Да / Нет) ───────────────────────────────────────────────────

def get_experience_yn_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_t(lang, "exp_no"),  callback_data="experience:no"),
            InlineKeyboardButton(text=_t(lang, "exp_yes"), callback_data="experience:yes"),
        ],
    ])


# ─── Готовность к работе ──────────────────────────────────────────────────────

def get_readiness_keyboard(lang: str) -> InlineKeyboardMarkup:
    options = [
        ("readiness_today",      "readiness:today"),
        ("readiness_tomorrow",   "readiness:tomorrow"),
        ("readiness_week",       "readiness:week"),
        ("readiness_two_weeks",  "readiness:two_weeks"),
        ("readiness_month",      "readiness:month"),
    ]
    rows = [[InlineKeyboardButton(text=_t(lang, k), callback_data=cd)] for k, cd in options]
    rows.append([InlineKeyboardButton(text=_t(lang, "btn_skip"), callback_data="readiness:skip")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── График работы ────────────────────────────────────────────────────────────

def get_schedule_keyboard(lang: str) -> InlineKeyboardMarkup:
    options = [
        ("schedule_6_1",  "schedule:6_1"),
        ("schedule_5_2",  "schedule:5_2"),
        ("schedule_3_1",  "schedule:3_1"),
        ("schedule_2_2",  "schedule:2_2"),
        ("schedule_full", "schedule:full"),
        ("schedule_flex", "schedule:flex"),
        ("schedule_any",  "schedule:any"),
    ]
    rows = [[InlineKeyboardButton(text=_t(lang, k), callback_data=cd)] for k, cd in options]
    rows.append([InlineKeyboardButton(text=_t(lang, "btn_skip"), callback_data="schedule:skip")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Вечерние смены ───────────────────────────────────────────────────────────

def get_evening_shifts_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_t(lang, "evening_yes"),       callback_data="evening:yes"),
            InlineKeyboardButton(text=_t(lang, "evening_no"),        callback_data="evening:no"),
            InlineKeyboardButton(text=_t(lang, "evening_agreement"), callback_data="evening:agreement"),
        ],
        [InlineKeyboardButton(text=_t(lang, "btn_skip"), callback_data="evening:skip")],
    ])


# ─── Выходные и праздники ─────────────────────────────────────────────────────

def get_weekends_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_t(lang, "weekends_yes"),       callback_data="weekends:yes"),
            InlineKeyboardButton(text=_t(lang, "weekends_no"),        callback_data="weekends:no"),
            InlineKeyboardButton(text=_t(lang, "weekends_sometimes"), callback_data="weekends:sometimes"),
        ],
        [InlineKeyboardButton(text=_t(lang, "btn_skip"), callback_data="weekends:skip")],
    ])


# ─── Курение ──────────────────────────────────────────────────────────────────

def get_smoking_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_t(lang, "smoking_no"),  callback_data="smoking:no"),
            InlineKeyboardButton(text=_t(lang, "smoking_yes"), callback_data="smoking:yes"),
        ],
        [InlineKeyboardButton(text=_t(lang, "btn_skip"), callback_data="smoking:skip")],
    ])


# ─── Медицинская книжка ───────────────────────────────────────────────────────

def get_med_book_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_t(lang, "med_book_yes"),         callback_data="med_book:yes"),
            InlineKeyboardButton(text=_t(lang, "med_book_no"),          callback_data="med_book:no"),
            InlineKeyboardButton(text=_t(lang, "med_book_in_progress"), callback_data="med_book:in_progress"),
        ],
        [InlineKeyboardButton(text=_t(lang, "btn_skip"), callback_data="med_book:skip")],
    ])


# ─── Языки владения (мультиселект) ────────────────────────────────────────────

_LANGUAGE_OPTIONS: list[tuple[str, str]] = [
    ("lang_opt_ru",    "lang_toggle:ru"),
    ("lang_opt_uz",    "lang_toggle:uz"),
    ("lang_opt_en",    "lang_toggle:en"),
    ("lang_opt_tr",    "lang_toggle:tr"),
    ("lang_opt_other", "lang_toggle:other"),
]


def get_languages_keyboard(lang: str, selected: set[str]) -> InlineKeyboardMarkup:
    """
    selected — набор уже выбранных кодов (например {"ru", "en"}).
    Выбранные помечаются ✅.
    """
    rows = []
    for text_key, callback_data in _LANGUAGE_OPTIONS:
        code = callback_data.split(":")[1]
        prefix = "✅ " if code in selected else ""
        rows.append([InlineKeyboardButton(
            text=prefix + _t(lang, text_key),
            callback_data=callback_data,
        )])

    rows.append([
        InlineKeyboardButton(text=_t(lang, "languages_done"), callback_data="lang_toggle:done"),
        InlineKeyboardButton(text=_t(lang, "btn_skip"),       callback_data="lang_toggle:skip"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
