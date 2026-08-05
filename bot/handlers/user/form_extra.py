# bot/handlers/user/form_extra.py
"""
Хендлеры для недостающих шагов анкеты:
- Ветвление Да/Нет для опыта работы (4 под-шага)
- Готовность к работе
- Зарплатные ожидания
- График работы
- Вечерние смены
- Выходные и праздники
- Курение
- Медицинская книжка
- Языки владения (мультиселект)
- Фото кандидата

Подключить в bot/handlers/__init__.py или bot/core/loader.py:
    from bot.handlers.user.form_extra import router as form_extra_router
    dp.include_router(form_extra_router)
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards as kb
from bot.lexicon import LOCALIZATION
from bot.states import Form

logger = logging.getLogger(__name__)
router = Router()


# ─── Вспомогательные функции ──────────────────────────────────────────────────

def _lang(data: dict) -> str:
    return data.get("lang", "ru")


def _t(lang: str, key: str, fallback: str = "") -> str:
    return LOCALIZATION[lang].get(key, fallback)


def _skip_text(lang: str) -> str:
    return _t(lang, "btn_skip", "⏭ Пропустить")


# ─── 1. Опыт работы — ветвление Да / Нет ─────────────────────────────────────
# Этот хендлер перехватывает callback ВМЕСТО старого router.message(waiting_experience).
# Старый process_experience в form.py теперь отвечает только за валидацию кнопки,
# а финальный переход делает handle_experience_yn.

@router.callback_query(Form.waiting_experience, F.data.startswith("experience:"))
async def handle_experience_yn(callback: CallbackQuery, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    answer = callback.data.split(":")[1]  # "yes" или "no"

    await callback.message.edit_reply_markup(reply_markup=None)

    if answer == "no":
        await state.update_data(
            experience=_t(lang, "exp_no", "Нет"),
            exp_company=None, exp_position=None,
            exp_duration=None, exp_duties=None,
        )
        await _ask_readiness(callback.message, state, lang)
    else:
        await state.update_data(experience=_t(lang, "exp_yes", "Да"))
        await state.set_state(Form.waiting_exp_company)
        await callback.message.answer(
            _t(lang, "ask_exp_company"),
            reply_markup=kb.get_cancel_keyboard(lang),
        )
    await callback.answer()


# ─── 2. Под-шаги опыта ────────────────────────────────────────────────────────

@router.message(Form.waiting_exp_company)
async def handle_exp_company(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    await state.update_data(exp_company=(message.text or "").strip() or None)
    await state.set_state(Form.waiting_exp_position)
    await message.answer(
        _t(lang, "ask_exp_position"),
        reply_markup=kb.get_cancel_keyboard(lang),
    )


@router.message(Form.waiting_exp_position)
async def handle_exp_position(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    await state.update_data(exp_position=None if text == _skip_text(lang) else text or None)
    await state.set_state(Form.waiting_exp_duration)
    await message.answer(
        _t(lang, "ask_exp_duration"),
        reply_markup=kb.get_cancel_keyboard(lang),
    )


@router.message(Form.waiting_exp_duration)
async def handle_exp_duration(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    await state.update_data(exp_duration=None if text == _skip_text(lang) else text or None)
    await state.set_state(Form.waiting_exp_duties)
    await message.answer(
        _t(lang, "ask_exp_duties"),
        reply_markup=kb.get_cancel_keyboard(lang),
    )


@router.message(Form.waiting_exp_duties)
async def handle_exp_duties(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    await state.update_data(exp_duties=None if text == _skip_text(lang) else text or None)
    await _ask_readiness(message, state, lang)


# ─── 3. Готовность к работе ───────────────────────────────────────────────────

async def _ask_readiness(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(Form.waiting_readiness)
    await message.answer(
        _t(lang, "ask_readiness"),
        reply_markup=kb.get_readiness_keyboard(lang),
    )


@router.callback_query(Form.waiting_readiness, F.data.startswith("readiness:"))
async def handle_readiness(callback: CallbackQuery, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    answer = callback.data.split(":")[1]
    await state.update_data(readiness=None if answer == "skip" else answer)
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.waiting_salary)
    await callback.message.answer(
        _t(lang, "ask_salary"),
        reply_markup=kb.get_cancel_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()


# ─── 4. Зарплатные ожидания ───────────────────────────────────────────────────

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


# ─── 5. График работы ─────────────────────────────────────────────────────────

@router.callback_query(Form.waiting_schedule, F.data.startswith("schedule:"))
async def handle_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    answer = callback.data.split(":")[1]
    await state.update_data(schedule=None if answer == "skip" else answer)
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.waiting_evening_shifts)
    await callback.message.answer(
        _t(lang, "ask_evening_shifts"),
        reply_markup=kb.get_evening_shifts_keyboard(lang),
    )
    await callback.answer()


# ─── 6. Вечерние смены ────────────────────────────────────────────────────────

@router.callback_query(Form.waiting_evening_shifts, F.data.startswith("evening:"))
async def handle_evening_shifts(callback: CallbackQuery, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    answer = callback.data.split(":")[1]
    await state.update_data(evening_shifts=None if answer == "skip" else answer)
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.waiting_weekends)
    await callback.message.answer(
        _t(lang, "ask_weekends"),
        reply_markup=kb.get_weekends_keyboard(lang),
    )
    await callback.answer()


# ─── 7. Выходные и праздники ──────────────────────────────────────────────────

@router.callback_query(Form.waiting_weekends, F.data.startswith("weekends:"))
async def handle_weekends(callback: CallbackQuery, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    answer = callback.data.split(":")[1]
    await state.update_data(weekends=None if answer == "skip" else answer)
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.waiting_smoking)
    await callback.message.answer(
        _t(lang, "ask_smoking"),
        reply_markup=kb.get_smoking_keyboard(lang),
    )
    await callback.answer()


# ─── 8. Курение ───────────────────────────────────────────────────────────────

@router.callback_query(Form.waiting_smoking, F.data.startswith("smoking:"))
async def handle_smoking(callback: CallbackQuery, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    answer = callback.data.split(":")[1]
    await state.update_data(smoking=None if answer == "skip" else answer)
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.waiting_med_book)
    await callback.message.answer(
        _t(lang, "ask_med_book"),
        reply_markup=kb.get_med_book_keyboard(lang),
    )
    await callback.answer()


# ─── 9. Медицинская книжка ────────────────────────────────────────────────────

@router.callback_query(Form.waiting_med_book, F.data.startswith("med_book:"))
async def handle_med_book(callback: CallbackQuery, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    answer = callback.data.split(":")[1]
    await state.update_data(med_book=None if answer == "skip" else answer)
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.waiting_languages)
    await state.update_data(languages_selected=[])
    await callback.message.answer(
        _t(lang, "ask_languages"),
        reply_markup=kb.get_languages_keyboard(lang, set()),
    )
    await callback.answer()


# ─── 10. Языки владения (мультиселект) ───────────────────────────────────────

@router.callback_query(Form.waiting_languages, F.data.startswith("lang_toggle:"))
async def handle_languages_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    action = callback.data.split(":")[1]

    if action == "skip":
        await state.update_data(languages=None)
        await callback.message.edit_reply_markup(reply_markup=None)
        await _ask_phone(callback.message, state, lang)
        await callback.answer()
        return

    if action == "done":
        selected: list[str] = data.get("languages_selected", [])
        await state.update_data(languages=selected or None)
        await callback.message.edit_reply_markup(reply_markup=None)
        await _ask_phone(callback.message, state, lang)
        await callback.answer()
        return

    # Переключить выбор языка
    selected_set: set[str] = set(data.get("languages_selected", []))
    if action in selected_set:
        selected_set.discard(action)
    else:
        selected_set.add(action)

    await state.update_data(languages_selected=list(selected_set))
    try:
        await callback.message.edit_reply_markup(
            reply_markup=kb.get_languages_keyboard(lang, selected_set)
        )
    except Exception as exc:
        logger.warning("Не удалось обновить выбор языков: %s", exc)
    await callback.answer()


# ─── 11. Фото кандидата ───────────────────────────────────────────────────────

async def _ask_phone(message: Message, state: FSMContext, lang: str) -> None:
    """Запрашивает необязательное фото перед номером телефона."""
    await state.set_state(Form.waiting_photo)
    await message.answer(
        _t(lang, "ask_photo"),
        reply_markup=kb.get_cancel_keyboard(lang),
        parse_mode="HTML",
    )


@router.message(Form.waiting_photo)
async def handle_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)

    if message.text == _skip_text(lang):
        await state.update_data(photo=None)
    elif message.photo:
        photo_id = message.photo[-1].file_id
        await state.update_data(photo=photo_id)
    else:
        # Неверный ввод — просим снова
        await message.answer(
            _t(lang, "ask_photo"),
            reply_markup=kb.get_cancel_keyboard(lang),
            parse_mode="HTML",
        )
        return

    # Переходим к телефону (существующий шаг waiting_phone)
    await state.set_state(Form.waiting_phone)
    await message.answer(
        LOCALIZATION[lang].get("ask_phone", "📱 Отправьте ваш номер телефона:"),
        reply_markup=kb.get_phone_keyboard(lang),
        parse_mode="HTML",
    )
