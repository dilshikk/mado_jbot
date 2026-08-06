"""
Inline-клавиатуры для пользовательской анкеты (форма).
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.lexicon.form_extra import FORM_EXTRA_TEXTS as _TEXTS


def _t(lang: str, key: str) -> str:
    return _TEXTS.get(lang, _TEXTS["ru"]).get(key, key)


# ─── Пол ──────────────────────────────────────────────────────────────────────

def get_gender_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_t(lang, "gender_male"),   callback_data="gender:male"),
            InlineKeyboardButton(text=_t(lang, "gender_female"), callback_data="gender:female"),
        ],
        [InlineKeyboardButton(text=_t(lang, "form_cancel"), callback_data="form_cancel")],
    ])


# ─── Опыт работы ──────────────────────────────────────────────────────────────

def get_experience_yn_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_t(lang, "exp_yes"), callback_data="experience:yes"),
            InlineKeyboardButton(text=_t(lang, "exp_no"),  callback_data="experience:no"),
        ],
        [InlineKeyboardButton(text=_t(lang, "form_cancel"), callback_data="form_cancel")],
    ])


# ─── График работы ────────────────────────────────────────────────────────────

_SCHEDULE_OPTIONS: list[tuple[str, str]] = [
    ("schedule_full",  "schedule:full"),
    ("schedule_part",  "schedule:part"),
    ("schedule_shift", "schedule:shift"),
    ("schedule_any",   "schedule:any"),
]

def get_schedule_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for lex_key, cb_data in _SCHEDULE_OPTIONS:
        pair.append(InlineKeyboardButton(text=_t(lang, lex_key), callback_data=cb_data))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([InlineKeyboardButton(text=_t(lang, "form_cancel"), callback_data="form_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Вечерние смены ───────────────────────────────────────────────────────────

def get_evening_shifts_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_t(lang, "evening_yes"), callback_data="evening:yes"),
            InlineKeyboardButton(text=_t(lang, "evening_no"),  callback_data="evening:no"),
        ],
        [InlineKeyboardButton(text=_t(lang, "form_cancel"), callback_data="form_cancel")],
    ])


# ─── Выходные дни ─────────────────────────────────────────────────────────────

def get_weekends_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_t(lang, "weekends_yes"), callback_data="weekends:yes"),
            InlineKeyboardButton(text=_t(lang, "weekends_no"),  callback_data="weekends:no"),
        ],
        [InlineKeyboardButton(text=_t(lang, "form_cancel"), callback_data="form_cancel")],
    ])


# ─── Медкнижка ────────────────────────────────────────────────────────────────

def get_med_book_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            # ВАЖНО: callback_data должен начинаться с "med_book:" — так ожидает хендлер
            InlineKeyboardButton(text=_t(lang, "med_yes"), callback_data="med_book:yes"),
            InlineKeyboardButton(text=_t(lang, "med_no"),  callback_data="med_book:no"),
        ],
        [InlineKeyboardButton(text=_t(lang, "form_cancel"), callback_data="form_cancel")],
    ])


# ─── Курение ──────────────────────────────────────────────────────────────────

def get_smoking_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_t(lang, "smoking_yes"), callback_data="smoking:yes"),
            InlineKeyboardButton(text=_t(lang, "smoking_no"),  callback_data="smoking:no"),
        ],
        [InlineKeyboardButton(text=_t(lang, "form_cancel"), callback_data="form_cancel")],
    ])


# ─── Вакансии (одиночный выбор) ───────────────────────────────────────────────

def get_positions_keyboard(lang: str, vacancies: list[dict]) -> InlineKeyboardMarkup:
    """
    Одиночный выбор вакансии. 2 кнопки в ряд.
    callback_data = "position:{id}" — так ожидает хендлер handle_position.
    """
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for v in vacancies:
        name  = v["name_uz"] if lang == "uz" else v["name_ru"]
        emoji = (v.get("emoji") or "") + " " if v.get("emoji") else ""
        pair.append(InlineKeyboardButton(
            text=f"{emoji}{name}",
            callback_data=f"position:{v['id']}",
        ))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([InlineKeyboardButton(text=_t(lang, "form_cancel"), callback_data="form_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Языки владения (мультиселект) ────────────────────────────────────────────

# (lex_key, callback_data, emoji_flag)
_LANGUAGE_OPTIONS: list[tuple[str, str, str]] = [
    ("lang_opt_ru",    "lang_toggle:ru",    "🇷🇺"),
    ("lang_opt_uz",    "lang_toggle:uz",    "🇺🇿"),
    ("lang_opt_en",    "lang_toggle:en",    "🇬🇧"),
    ("lang_opt_tr",    "lang_toggle:tr",    "🇹🇷"),
    ("lang_opt_other", "lang_toggle:other", "🌍"),
]

def get_languages_keyboard(lang: str, selected: set[str]) -> InlineKeyboardMarkup:
    """
    selected — набор уже выбранных кодов (например {"ru", "en"}).
    Раскладка: 2 кнопки в ряд; «Другое» — отдельная строка.
    """
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for lex_key, cb_data, flag in _LANGUAGE_OPTIONS:
        code  = cb_data.split(":")[1]
        check = "✅ " if code in selected else ""
        label = f"{check}{flag} {_t(lang, lex_key)}"
        btn   = InlineKeyboardButton(text=label, callback_data=cb_data)
        if lex_key == "lang_opt_other":
            if pair:
                rows.append(pair)
                pair = []
            rows.append([btn])
        else:
            pair.append(btn)
            if len(pair) == 2:
                rows.append(pair)
                pair = []
    if pair:
        rows.append(pair)
    rows.append([
        InlineKeyboardButton(text=_t(lang, "languages_done"), callback_data="lang_toggle:done"),
        InlineKeyboardButton(text=_t(lang, "btn_skip"),       callback_data="lang_toggle:skip"),
    ])
    rows.append([InlineKeyboardButton(text=_t(lang, "form_cancel"), callback_data="form_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Подтверждение анкеты ─────────────────────────────────────────────────────

def get_confirmation_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_t(lang, "confirm_send"),   callback_data="confirm:send"),
            InlineKeyboardButton(text=_t(lang, "confirm_cancel"), callback_data="confirm:cancel"),
        ],
    ])
