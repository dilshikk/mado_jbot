# bot/handlers/user/form_extra.py
"""
Хендлеры для шагов анкеты «Информация о работе» и «Дополнительно»:
- Языки владения (Inline мультиселект)
- Готовность к работе (Inline CallbackQuery)
- Опыт работы — ветвление Да/Нет (Inline) + 4 под-шага (текст)
- Зарплатные ожидания (текст)
- График работы (Inline)
- Вечерние смены (Inline)
- Выходные и праздники (Inline)
- Курение (Inline)
- Медицинская книжка (Inline)
- Фото кандидата (обычное сообщение)
"""
from __future__ import annotations

import logging
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards as kb
from bot.db import requests as db
from bot.lexicon import LOCALIZATION
from bot.states import Form

router = Router()
logger = logging.getLogger(__name__)

# ─── Вспомогательные функции ──────────────────────────────────────────────────

def _lang(data: dict) -> str:
    return data.get("lang", "ru")

def _t(lang: str, key: str, fallback: str = "") -> str:
    return LOCALIZATION[lang].get(key, fallback)

def _skip_text(lang: str) -> str:
    return _t(lang, "btn_skip", "⏭ Пропустить")


# ─── Публичная функция — вызов из metro.py ────────────────────────────────────

async def ask_languages(message: Message, state: FSMContext, lang: str) -> None:
    """Отправляет inline-клавиатуру выбора языков. Вызывается из metro.py."""
    await state.set_state(Form.waiting_languages)
    selected: set[str] = set()
    await message.answer(
        _t(lang, "ask_languages"),
        reply_markup=kb.get_languages_keyboard(lang, selected),
    )


# ─── 1. Языки владения (Inline мультиселект) ──────────────────────────────────

@router.callback_query(Form.waiting_languages, F.data.startswith("lang_toggle:"))
async def handle_languages(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    data = await state.get_data()
    lang = _lang(data)
    code = callback.data.split(":")[1]

    if code == "skip":
        await state.update_data(languages=None)
        with suppress(TelegramAPIError):
            await callback.message.edit_reply_markup(reply_markup=None)
        await _ask_position_after_languages(callback.message, state, session, lang)
        return

    if code == "done":
        selected_list = data.get("languages", [])
        if not selected_list:
            await callback.answer(_t(lang, "languages_done_empty"), show_alert=True)
            return
        with suppress(TelegramAPIError):
            await callback.message.edit_reply_markup(reply_markup=None)
        await _ask_position_after_languages(callback.message, state, session, lang)
        return

    selected: set[str] = set(data.get("languages") or [])
    if code in selected:
        selected.discard(code)
    else:
        selected.add(code)
    await state.update_data(languages=list(selected))
    with suppress(TelegramAPIError):
        await callback.message.edit_reply_markup(
            reply_markup=kb.get_languages_keyboard(lang, selected)
        )


async def _ask_position_after_languages(
    message: Message, state: FSMContext, session: AsyncSession, lang: str,
) -> None:
    vacancies = await db.get_active_vacancies(session)
    await state.set_state(Form.waiting_position)
    await message.answer(
        LOCALIZATION[lang]["ask_position"],
        reply_markup=kb.get_positions_keyboard(lang, vacancies),
        parse_mode="HTML",
    )


# ─── 2. Выбор вакансии (Inline) ───────────────────────────────────────────────

@router.callback_query(Form.waiting_position, F.data.startswith("position:"))
async def handle_position(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    data = await state.get_data()
    lang = _lang(data)
    vacancy_id_str = callback.data.split(":")[1]
    try:
        vacancy_id = int(vacancy_id_str)
    except ValueError:
        return
    vacancy = await db.get_vacancy_by_id(session, vacancy_id)
    if not vacancy:
        return
    name_key = "name_ru" if lang == "ru" else "name_uz"
    position_label = f"{vacancy.get('emoji', '')} {vacancy.get(name_key, '')}".strip()
    await state.update_data(position=position_label)
    with suppress(TelegramAPIError):
        await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        LOCALIZATION[lang]["ask_readiness"],
        reply_markup=kb.get_readiness_inline_keyboard(lang),
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_readiness)


# ─── 3. Готовность к работе (Inline CallbackQuery) ───────────────────────────

@router.callback_query(Form.waiting_readiness, F.data.startswith("readiness:"))
async def handle_readiness(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    lang = _lang(data)
    key = callback.data.split(":")[1]  # today, tomorrow, week, two_weeks, month, skip
    value = None if key == "skip" else _t(lang, f"readiness_{key}", key)
    await state.update_data(readiness=value)
    with suppress(TelegramAPIError):
        await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.waiting_experience)
    await callback.message.answer(
        _t(lang, "ask_experience_yn"),
        reply_markup=kb.get_experience_yn_keyboard(lang),
    )
    logger.info("handle_readiness: user_id=%d readiness=%r", callback.from_user.id, value)


# ─── 4. Опыт работы — ветвление Да / Нет (Inline) ────────────────────────────

@router.callback_query(Form.waiting_experience, F.data.startswith("experience:"))
async def handle_experience_yn(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    lang = _lang(data)
    choice = callback.data.split(":")[1]
    with suppress(TelegramAPIError):
        await callback.message.edit_reply_markup(reply_markup=None)

    if choice == "no":
        await state.update_data(
            experience=_t(lang, "exp_no", "Нет"),
            exp_company=None, exp_position=None,
            exp_duration=None, exp_duties=None,
        )
        await _ask_salary(callback.message, state, lang)
    else:
        await state.update_data(experience=_t(lang, "exp_yes", "Да"))
        await state.set_state(Form.waiting_exp_company)
        await callback.message.answer(
            _t(lang, "ask_exp_company"),
            reply_markup=kb.get_cancel_keyboard(lang),
        )


# ─── 5. Под-шаги опыта (текст) ────────────────────────────────────────────────

@router.message(Form.waiting_exp_company)
async def handle_exp_company(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    await state.update_data(exp_company=(message.text or "").strip() or None)
    await state.set_state(Form.waiting_exp_position)
    await message.answer(_t(lang, "ask_exp_position"), reply_markup=kb.get_cancel_keyboard(lang))

@router.message(Form.waiting_exp_position)
async def handle_exp_position(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    await state.update_data(exp_position=None if text == _skip_text(lang) else text or None)
    await state.set_state(Form.waiting_exp_duration)
    await message.answer(_t(lang, "ask_exp_duration"), reply_markup=kb.get_cancel_keyboard(lang))

@router.message(Form.waiting_exp_duration)
async def handle_exp_duration(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    await state.update_data(exp_duration=None if text == _skip_text(lang) else text or None)
    await state.set_state(Form.waiting_exp_duties)
    await message.answer(_t(lang, "ask_exp_duties"), reply_markup=kb.get_cancel_keyboard(lang))

@router.message(Form.waiting_exp_duties)
async def handle_exp_duties(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    await state.update_data(exp_duties=None if text == _skip_text(lang) else text or None)
    await _ask_salary(message, state, lang)


# ─── 6. Зарплатные ожидания (текст) ──────────────────────────────────────────

async def _ask_salary(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(Form.waiting_salary)
    await message.answer(
        _t(lang, "ask_salary"),
        reply_markup=kb.get_cancel_keyboard(lang),
        parse_mode="HTML",
    )

@router.message(Form.waiting_salary)
async def handle_salary(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    await state.update_data(salary=None if text == _skip_text(lang) else text or None)
    await state.set_state(Form.waiting_schedule)
    await message.answer(
        _t(lang, "ask_schedule"),
        reply_markup=kb.get_schedule_keyboard(lang),
    )


# ─── 7. График работы (Inline) ────────────────────────────────────────────────

@router.callback_query(Form.waiting_schedule, F.data.startswith("schedule:"))
async def handle_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    lang = _lang(data)
    key = callback.data.split(":")[1]
    value = None if key == "skip" else _t(lang, f"schedule_{key}", key)
    await state.update_data(schedule=value)
    with suppress(TelegramAPIError):
        await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.waiting_evening_shifts)
    await callback.message.answer(
        _t(lang, "ask_evening_shifts"),
        reply_markup=kb.get_evening_shifts_keyboard(lang),
    )


# ─── 8. Вечерние смены (Inline) ──────────────────────────────────────────────

@router.callback_query(Form.waiting_evening_shifts, F.data.startswith("evening:"))
async def handle_evening_shifts(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    lang = _lang(data)
    key = callback.data.split(":")[1]
    value = None if key == "skip" else _t(lang, f"evening_{key}", key)
    await state.update_data(evening_shifts=value)
    with suppress(TelegramAPIError):
        await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.waiting_weekends)
    await callback.message.answer(
        _t(lang, "ask_weekends"),
        reply_markup=kb.get_weekends_keyboard(lang),
    )


# ─── 9. Выходные и праздники (Inline) ────────────────────────────────────────

@router.callback_query(Form.waiting_weekends, F.data.startswith("weekends:"))
async def handle_weekends(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    lang = _lang(data)
    key = callback.data.split(":")[1]
    value = None if key == "skip" else _t(lang, f"weekends_{key}", key)
    await state.update_data(weekends=value)
    with suppress(TelegramAPIError):
        await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.waiting_smoking)
    await callback.message.answer(
        _t(lang, "ask_smoking"),
        reply_markup=kb.get_smoking_keyboard(lang),
    )


# ─── 10. Курение (Inline) ─────────────────────────────────────────────────────

@router.callback_query(Form.waiting_smoking, F.data.startswith("smoking:"))
async def handle_smoking(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    lang = _lang(data)
    key = callback.data.split(":")[1]
    value = None if key == "skip" else _t(lang, f"smoking_{key}", key)
    await state.update_data(smoking=value)
    with suppress(TelegramAPIError):
        await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.waiting_med_book)
    await callback.message.answer(
        _t(lang, "ask_med_book"),
        reply_markup=kb.get_med_book_keyboard(lang),
    )


# ─── 11. Медицинская книжка (Inline) ─────────────────────────────────────────

@router.callback_query(Form.waiting_med_book, F.data.startswith("med_book:"))
async def handle_med_book(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    lang = _lang(data)
    key = callback.data.split(":")[1]
    value = None if key == "skip" else _t(lang, f"med_book_{key}", key)
    await state.update_data(med_book=value)
    with suppress(TelegramAPIError):
        await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.waiting_photo)
    await callback.message.answer(
        _t(lang, "ask_photo"),
        reply_markup=kb.get_skip_cancel_keyboard(lang),
        parse_mode="HTML",
    )


# ─── 12. Фото кандидата (обычное сообщение) ──────────────────────────────────

@router.message(Form.waiting_photo)
async def handle_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()

    if text == _skip_text(lang):
        await state.update_data(photo_file_id=None)
    elif message.photo:
        photo_id = message.photo[-1].file_id
        await state.update_data(photo_file_id=photo_id)
        logger.info("handle_photo: user_id=%d photo saved", message.from_user.id)
    else:
        await message.answer(
            _t(lang, "bad_photo"),
            reply_markup=kb.get_skip_cancel_keyboard(lang),
            parse_mode="HTML",
        )
        return

    await state.set_state(Form.waiting_video)
    from bot.lexicon import LOCALIZATION as LOC  # noqa: PLC0415
    await message.answer(
        LOC[lang].get("ask_video", "Пришлите видеовизитку (≥15 сек) или пропустите."),
        reply_markup=kb.get_skip_cancel_keyboard(lang),
        parse_mode="HTML",
    )
    logger.info("handle_photo: user_id=%d -> waiting_video", message.from_user.id)
