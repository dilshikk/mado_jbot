# keyboards.py

import database as db
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from config import SHEET_URL
from messages import LOCALIZATION

# Значения username которые считаются "отсутствующим"
_EMPTY_USERNAME: frozenset[str] = frozenset({"отсутствует", "none", ""})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _texts(lang: str) -> dict[str, str]:
    """Возвращает локализацию с фолбэком на русский."""
    return LOCALIZATION.get(lang, LOCALIZATION["ru"])


def _btn(lang: str, key: str, fallback: str = "") -> KeyboardButton:
    """Создаёт KeyboardButton по ключу локализации."""
    return KeyboardButton(text=_texts(lang).get(key, fallback))


def _row(*buttons: KeyboardButton) -> list[KeyboardButton]:
    """Синтаксический сахар для строки клавиатуры."""
    return list(buttons)


# ── Reply keyboards ───────────────────────────────────────────────────────────

def get_language_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇺🇿 O'zbekcha")]
        ],
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
            _row(KeyboardButton(
                text="📋 Мой статус" if lang == "ru" else "📋 Mening statusim"
            )),
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


def get_positions_keyboard(lang: str) -> ReplyKeyboardMarkup:
    """
    Клавиатура вакансий — берётся из БД (только активные).
    Каждая строка — одна вакансия с эмодзи и локализованным названием.
    """
    vacancies = db.get_active_vacancies()
    name_key  = "name_ru" if lang == "ru" else "name_uz"

    keyboard: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []

    for v in vacancies:
        label = f"{v['emoji']} {v[name_key]}".strip()
        row.append(KeyboardButton(text=label))
        if len(row) == 2:          # по 2 кнопки в строке
            keyboard.append(row)
            row = []

    if row:                        # остаток нечётных кнопок
        keyboard.append(row)

    keyboard.append(_row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")))

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_branch_keyboard(lang: str) -> ReplyKeyboardMarkup:
    """
    Вынесена отдельно для масштабируемости.
    Чтобы добавить новый филиал — просто раскомментируй строку.
    """
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
                KeyboardButton(text=t.get("gender_male",   "Мужской")),
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
            # _row(KeyboardButton(text=t.get("citizenship_kz", "🇰🇿 Казахстан"))),
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
            _row(
                KeyboardButton(text="5+ лет" if lang == "ru" else "5+ yil"),
            ),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


# ── Inline keyboards ──────────────────────────────────────────────────────────

def get_score_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    """Кнопки оценки кандидата 1–5 звёзд."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{i}⭐", callback_data=f"score:{i}:{candidate_id}")
        for i in range(1, 6)
    ]])


def get_post_interview_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    """Клавиатура после собеседования — принять на работу или отклонить."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🏆 Принять на работу",
                callback_data=f"hr_hire:{candidate_id}",
            ),
            InlineKeyboardButton(
                text="❌ Не подошёл",
                callback_data=f"hr_reject:{candidate_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="⏸ На паузу",
                callback_data=f"hr_hold:{candidate_id}",
            ),
        ],
    ])


def get_hr_action_keyboard(
    phone: str,
    username: str,
    candidate_id: int,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []

    clean = username.lstrip("@").strip().lower()
    if clean and clean not in _EMPTY_USERNAME:
        buttons.append([
            InlineKeyboardButton(text="💬 Telegram", url=f"https://t.me/{clean}")
        ])

    buttons.append([
        InlineKeyboardButton(text="✅ Одобрить",  callback_data=f"hr_accept:{candidate_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"hr_reject:{candidate_id}"),
    ])
    buttons.append([
        InlineKeyboardButton(text="⏸ На паузу", callback_data=f"hr_hold:{candidate_id}"),
    ])
    buttons.append([
        InlineKeyboardButton(text="📊 Google Таблица", url=SHEET_URL),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_hr_hold_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для кандидата на паузе — вернуть в работу или отклонить."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="▶️ Вернуть в работу", callback_data=f"hr_accept:{candidate_id}"),
        InlineKeyboardButton(text="❌ Отклонить",         callback_data=f"hr_reject:{candidate_id}"),
    ]])
