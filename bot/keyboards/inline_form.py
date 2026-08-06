# bot/keyboards/inline_form.py
"""Inline-клавиатуры для всех шагов анкеты кандидата."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.lexicon import LOCALIZATION


def _t(lang: str, key: str) -> str:
    return LOCALIZATION[lang].get(key, key)


def _cancel_text(lang: str) -> str:
    return "Bekor qilish" if lang == "uz" else "Отменить заполнение"


def _cancel_row(lang: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=_cancel_text(lang), callback_data="form_cancel")]


# ─── Пол ─────────────────────────────────────────────────────────────────────

def get_gender_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_t(lang, "gender_male"),   callback_data="gender:male"),
            InlineKeyboardButton(text=_t(lang, "gender_female"), callback_data="gender:female"),
        ],
        _cancel_row(lang),
    ])


# ─── Выбор вакансии ───────────────────────────────────────────────────────────

def get_positions_keyboard(lang: str, vacancies: list[dict]) -> InlineKeyboardMarkup:
    """Кнопки вакансий; callback_data = position:<vacancy_id>."""
    name_key = "name_ru" if lang == "ru" else "name_uz"
    rows: list[list[InlineKeyboardButton]] = []
    for v in vacancies:
        label = f"{v.get('emoji', '')} {v.get(name_key, '')}".strip()
        rows.append([InlineKeyboardButton(text=label, callback_data=f"position:{v['id']}")])
    rows.append(_cancel_row(lang))
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Опыт работы (Да / Нет) ───────────────────────────────────────────────────

def get_experience_yn_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_t(lang, "exp_no"),  callback_data="experience:no"),
            InlineKeyboardButton(text=_t(lang, "exp_yes"), callback_data="experience:yes"),
        ],
        _cancel_row(lang),
    ])


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
    rows.append(_cancel_row(lang))
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
        _cancel_row(lang),
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
        _cancel_row(lang),
    ])


# ─── Курение ──────────────────────────────────────────────────────────────────

def get_smoking_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_t(lang, "smoking_no"),  callback_data="smoking:no"),
            InlineKeyboardButton(text=_t(lang, "smoking_yes"), callback_data="smoking:yes"),
        ],
        [InlineKeyboardButton(text=_t(lang, "btn_skip"), callback_data="smoking:skip")],
        _cancel_row(lang),
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
        _cancel_row(lang),
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
    rows: list[list[InlineKeyboardButton]] = []
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
    rows.append(_cancel_row(lang))
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Подтверждение анкеты ─────────────────────────────────────────────────────

def get_confirmation_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_t(lang, "confirm_btn_yes"), callback_data="confirm:yes")],
        [InlineKeyboardButton(text=_t(lang, "confirm_btn_no"),  callback_data="confirm:no")],
    ])
