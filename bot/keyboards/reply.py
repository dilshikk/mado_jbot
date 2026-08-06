# bot/keyboards/reply.py

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from bot.lexicon import LOCALIZATION

# ── Утилиты ───────────────────────────────────────────────────────────────────

def _texts(lang: str) -> dict:
    return LOCALIZATION.get(lang, LOCALIZATION["ru"])

def _btn(lang: str, key: str, fallback: str = "") -> KeyboardButton:
    return KeyboardButton(text=_texts(lang).get(key, fallback))

def _row(*buttons: KeyboardButton) -> list[KeyboardButton]:
    return list(buttons)

# ── Пользовательские клавиатуры ───────────────────────────────────────────────

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

def get_skip_cancel_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(_btn(lang, "btn_skip", "⏭ Пропустить")),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
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
    branches = ["📍 MADO (Tashkent City Mall)"]
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

def get_citizenship_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = _texts(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(KeyboardButton(text=t.get("citizenship_uzb", "🇺🇿 Узбекистан"))),
            _row(_btn(lang, "citizenship_skip", "⏭ Пропустить")),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )

def get_confirmation_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = _texts(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(KeyboardButton(text=t.get("confirm_btn_yes", "✅ Всё верно"))),
            _row(KeyboardButton(text=t.get("confirm_btn_no", "🔄 Заполнить заново"))),
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

def get_experience_yn_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = _texts(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(KeyboardButton(text=t["exp_no"]), KeyboardButton(text=t["exp_yes"])),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )

def get_readiness_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = _texts(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(KeyboardButton(text=t["readiness_today"]), KeyboardButton(text=t["readiness_tomorrow"])),
            _row(KeyboardButton(text=t["readiness_week"]), KeyboardButton(text=t["readiness_two_weeks"])),
            _row(KeyboardButton(text=t["readiness_month"])),
            _row(_btn(lang, "btn_skip", "⏭ Пропустить")),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )

def get_schedule_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = _texts(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(KeyboardButton(text=t["schedule_6_1"]), KeyboardButton(text=t["schedule_5_2"])),
            _row(KeyboardButton(text=t["schedule_3_1"]), KeyboardButton(text=t["schedule_2_2"])),
            _row(KeyboardButton(text=t["schedule_full"])),
            _row(KeyboardButton(text=t["schedule_flex"]), KeyboardButton(text=t["schedule_any"])),
            _row(_btn(lang, "btn_skip", "⏭ Пропустить")),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )

def get_evening_shifts_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = _texts(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(
                KeyboardButton(text=t["evening_yes"]),
                KeyboardButton(text=t["evening_no"]),
                KeyboardButton(text=t["evening_agreement"]),
            ),
            _row(_btn(lang, "btn_skip", "⏭ Пропустить")),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )

def get_weekends_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = _texts(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(
                KeyboardButton(text=t["weekends_yes"]),
                KeyboardButton(text=t["weekends_no"]),
                KeyboardButton(text=t["weekends_sometimes"]),
            ),
            _row(_btn(lang, "btn_skip", "⏭ Пропустить")),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )

def get_smoking_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = _texts(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(KeyboardButton(text=t["smoking_no"]), KeyboardButton(text=t["smoking_yes"])),
            _row(_btn(lang, "btn_skip", "⏭ Пропустить")),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )

def get_med_book_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = _texts(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(
                KeyboardButton(text=t["med_book_yes"]),
                KeyboardButton(text=t["med_book_no"]),
                KeyboardButton(text=t["med_book_in_progress"]),
            ),
            _row(_btn(lang, "btn_skip", "⏭ Пропустить")),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )

def get_languages_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = _texts(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            _row(KeyboardButton(text=t["lang_opt_ru"]), KeyboardButton(text=t["lang_opt_uz"])),
            _row(KeyboardButton(text=t["lang_opt_en"]), KeyboardButton(text=t["lang_opt_tr"])),
            _row(KeyboardButton(text=t["lang_opt_other"])),
            _row(_btn(lang, "languages_done", "✅ Готово")),
            _row(_btn(lang, "btn_skip", "⏭ Пропустить")),
            _row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")),
        ],
        resize_keyboard=True,
    )

def get_metro_keyboard(lang: str) -> ReplyKeyboardMarkup:
    metros_ru = [
        "🚇 Буюк Ипак Йули", "🚇 Пушкин", "🚇 Хамида Алимджана",
        "🚇 Абдулла Кадыри", "🚇 Алишер Навои", "🚇 Узбекистан",
        "🚇 Космонавтов", "🚇 Ойбек", "🚇 Ташкент",
        "🚇 Минор", "🚇 Бадамзар", "🚇 Мустакиллик майдони",
    ]
    metros_uz = [
        "🚇 Buyuk Ipak Yo'li", "🚇 Pushkin", "🚇 Hamid Olimjon",
        "🚇 Abdulla Qodiriy", "🚇 Alisher Navoiy", "🚇 O'zbekiston",
        "🚇 Kosmonavtlar", "🚇 Oybek", "🚇 Toshkent",
        "🚇 Minor", "🚇 Bodomzor", "🚇 Mustaqillik maydoni",
    ]
    metros = metros_uz if lang == "uz" else metros_ru
    keyboard = [[KeyboardButton(text=name)] for name in metros]
    keyboard.append(_row(_btn(lang, "metro_skip", "⏭ Пропустить")))
    keyboard.append(_row(_btn(lang, "btn_cancel", "❌ Отменить заполнение")))
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_interview_keyboard(lang: str) -> ReplyKeyboardMarkup:
    if lang == "uz":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="⏭ Savolni o'tkazish")],
                [KeyboardButton(text="🚫 Intervyuni tugatish")],
            ],
            resize_keyboard=True,
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏭ Пропустить вопрос")],
            [KeyboardButton(text="🚫 Завершить интервью")],
        ],
        resize_keyboard=True,
    )

def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


# ── Административные клавиатуры ───────────────────────────────────────────────
#
# Правило: каждый «экран» администратора имеет свою Reply Keyboard.
# Переход между экранами всегда заменяет клавиатуру.
# «⬅️ Назад» / «❌ Отмена» — всегда возврат в главное меню /admin.
# Под-навигация (к вакансиям, к линиям и т.д.) использует отдельные тексты кнопок.

# Кнопки навигации (текстовые константы для единообразия)
ADMIN_BTN_BACK   = "⬅️ Назад"
ADMIN_BTN_CANCEL = "❌ Отмена"

# Главное меню /admin
def get_admin_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📢 Рассылка"),      KeyboardButton(text="💼 Вакансии")],
            [KeyboardButton(text="🚇 Метро"),          KeyboardButton(text="📊 Дашборд")],
            [KeyboardButton(text="👮 Администраторы"), KeyboardButton(text="📋 Resend")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел...",
    )

# Клавиатура «только Назад» — для простых разделов без FSM
def get_admin_back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=ADMIN_BTN_BACK)]],
        resize_keyboard=True,
    )

# Клавиатура «только Отмена» — во время FSM-шагов ввода текста
def get_admin_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=ADMIN_BTN_CANCEL)]],
        resize_keyboard=True,
    )

# Клавиатура «Пропустить + Отмена»
def get_admin_skip_cancel_keyboard(skip_label: str = "⏭ Пропустить") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=skip_label), KeyboardButton(text=ADMIN_BTN_CANCEL)]],
        resize_keyboard=True,
    )

# ── Рассылка ──────────────────────────────────────────────────────────────────

def get_broadcast_photo_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏭ Без фото"), KeyboardButton(text=ADMIN_BTN_CANCEL)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Отправьте фото...",
    )

def get_broadcast_url_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏭ Без ссылки"), KeyboardButton(text=ADMIN_BTN_CANCEL)],
        ],
        resize_keyboard=True,
        input_field_placeholder="https://...",
    )

def get_broadcast_preview_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Отправить всем")],
            [KeyboardButton(text="✏️ Изменить фото"),  KeyboardButton(text="✏️ Изменить текст")],
            [KeyboardButton(text="✏️ Изменить ссылку")],
            [KeyboardButton(text=ADMIN_BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )

# ── Вакансии ──────────────────────────────────────────────────────────────────

def _vacancy_label(v: dict) -> str:
    """Текст кнопки вакансии: статус + эмодзи + название."""
    status = "✅" if v["is_active"] else "❌"
    parts  = [status]
    if v.get("emoji"):
        parts.append(v["emoji"])
    parts.append(v["name_ru"])
    return " ".join(parts)

def get_admin_vacancies_kb(vacancies: list[dict]) -> ReplyKeyboardMarkup:
    """Главный экран раздела «Вакансии»: список как кнопки + действия."""
    keyboard: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for v in vacancies:
        row.append(KeyboardButton(text=_vacancy_label(v)))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([KeyboardButton(text="➕ Добавить вакансию")])
    keyboard.append([KeyboardButton(text="🔄 Обновить"), KeyboardButton(text=ADMIN_BTN_BACK)])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_admin_vacancy_item_kb(is_active: bool) -> ReplyKeyboardMarkup:
    """Экран отдельной вакансии: действия."""
    toggle = "❌ Выключить" if is_active else "✅ Включить"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=toggle)],
            [KeyboardButton(text="✏️ Изменить"), KeyboardButton(text="🗑 Удалить")],
            [KeyboardButton(text="◀️ К вакансиям")],
        ],
        resize_keyboard=True,
    )

def get_admin_vacancy_confirm_delete_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да, удалить"), KeyboardButton(text="◀️ К вакансиям")],
        ],
        resize_keyboard=True,
    )

def get_admin_vacancy_edit_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇷🇺 Название (рус)"), KeyboardButton(text="🇺🇿 Название (узб)")],
            [KeyboardButton(text="😊 Эмодзи")],
            [KeyboardButton(text="◀️ К вакансиям")],
        ],
        resize_keyboard=True,
    )

# ── Метро ─────────────────────────────────────────────────────────────────────

def get_admin_metro_lines_kb() -> ReplyKeyboardMarkup:
    """Главный экран раздела «Метро»: линии."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔴 Чиланзарская"),    KeyboardButton(text="🟢 Юнусабадская")],
            [KeyboardButton(text="🔵 Узбекистанская"),   KeyboardButton(text="🟠 30-летия независимости")],
            [KeyboardButton(text="➕ Добавить станцию")],
            [KeyboardButton(text="🔄 Обновить"),         KeyboardButton(text=ADMIN_BTN_BACK)],
        ],
        resize_keyboard=True,
    )

def get_admin_metro_stations_kb(stations: list[dict]) -> ReplyKeyboardMarkup:
    """Экран станций одной линии."""
    keyboard: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for s in stations:
        status = "✅" if s["active"] else "❌"
        row.append(KeyboardButton(text=f"{status} {s['name_ru']}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([KeyboardButton(text="➕ Добавить в эту линию")])
    keyboard.append([KeyboardButton(text="◀️ К линиям")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_admin_station_item_kb(is_active: bool) -> ReplyKeyboardMarkup:
    """Экран отдельной станции: действия."""
    toggle = "❌ Выключить" if is_active else "✅ Включить"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=toggle)],
            [KeyboardButton(text="🗑 Удалить")],
            [KeyboardButton(text="◀️ К станциям")],
        ],
        resize_keyboard=True,
    )

def get_admin_station_confirm_delete_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да, удалить станцию"), KeyboardButton(text="◀️ К станциям")],
        ],
        resize_keyboard=True,
    )
