# bot/keyboards/reply.py

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from bot.lexicon import LOCALIZATION


def _texts(lang: str) -> dict:
    return LOCALIZATION.get(lang, LOCALIZATION["ru"])


def _btn(lang: str, key: str, fallback: str = "") -> KeyboardButton:
    return KeyboardButton(text=_texts(lang).get(key, fallback))


def _row(*buttons: KeyboardButton) -> list[KeyboardButton]:
    return list(buttons)


def get_language_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇺🇿 O'zbekcha")]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Выберите язык / Tilni tanlang",
    )


def get_main_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(_btn(lang, "btn_apply", "📝 Заполнить анкету")),
            _row(
                _btn(lang, "btn_about", "🏢 О ресторане"),
                _btn(lang, "btn_change_lang", "🌐 Сменить язык"),
            ),
            _row(KeyboardButton(text="📋 Мой статус" if lang == "ru" else "📋 Mening statusim")),
        ],
        resize_keyboard=True,
    )


def get_cancel_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[_row(_btn(lang, "btn_cancel", "❌ Отменить заполнение"))],
        resize_keyboard=True,
    )


def get_phone_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(KeyboardButton(
                text=_texts(lang).get("btn_share_phone", "📱 Поделиться контактом"),
                request_contact=True,
            )),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
        input_field_placeholder="+998 XX XXX XX XX",
    )


def get_positions_keyboard(lang: str, vacancies: list[dict]) -> ReplyKeyboardMarkup:
    """Клавиатура вакансий (передаётся список из БД — только активные)."""
    name_key = "name_ru" if lang == "ru" else "name_uz"
    keyboard: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for v in vacancies:
        label = f"{v['emoji']} {v[name_key]}".strip()
        row.append(KeyboardButton(text=label))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append(_row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")))
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_branch_keyboard(lang: str) -> ReplyKeyboardMarkup:
    branches = [
        "📍 MADO (Tashkent City Mall)",
        # "📍 MADO (Yunusobod)",
    ]
    return ReplyKeyboardMarkup(
        keyboard=[
            *[[KeyboardButton(text=b)] for b in branches],
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )


def get_gender_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = _texts(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(
                KeyboardButton(text=t.get("gender_male", "Мужской")),
                KeyboardButton(text=t.get("gender_female", "Женский")),
            ),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )


def get_family_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = _texts(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(KeyboardButton(text=t.get("family_single",  "Холост/Не замужем"))),
            _row(KeyboardButton(text=t.get("family_married", "Женат/Замужем"))),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )


def get_citizenship_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = _texts(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(KeyboardButton(text=t.get("citizenship_uzb", "🇺🇿 Узбекистан"))),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )


def get_confirmation_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = _texts(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(KeyboardButton(text=t.get("confirm_btn_yes", "✅ Всё верно"))),
            _row(KeyboardButton(text=t.get("confirm_btn_no",  "🔄 Заполнить заново"))),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )


def get_experience_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(
                KeyboardButton(text="Нет опыта" if lang == "ru" else "Tajriba yo'q"),
                KeyboardButton(text="Менее 1 года" if lang == "ru" else "1 yildan kam"),
            ),
            _row(
                KeyboardButton(text="1–2 года" if lang == "ru" else "1–2 yil"),
                KeyboardButton(text="3–5 лет" if lang == "ru" else "3–5 yil"),
            ),
            _row(KeyboardButton(text="5+ лет" if lang == "ru" else "5+ yil")),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
