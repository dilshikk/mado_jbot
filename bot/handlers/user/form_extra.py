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

from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards as kb
from bot.lexicon import LOCALIZATION
from bot.states import Form

router = Router()


# ─── Вспомогательные функции ──────────────────────────────────────────────────

def _lang(data: dict) -> str:
    return data.get("lang", "ru")


def _t(lang: str, key: str, fallback: str = "") -> str:
    return LOCALIZATION[lang].get(key, fallback)


def _skip_text(lang: str) -> str:
    return _t(lang, "btn_skip", "⏭ Пропустить")


# ─── 1. Опыт работы — ветвление Да / Нет ─────────────────────────────────────
@router.message(Form.waiting_experience)
async def handle_experience_yn(message: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text = (message.text or "").strip()

    if text == _t(lang, "exp_no"):
        await state.update_data(
            experience=_t(lang, "exp_no", "Нет"),
            exp_company=None, exp_position=None,
            exp_duration=None, exp_duties=None,
        )
        await _ask_readiness(message, state, lang)
    elif text == _t(lang, "exp_yes"):
        await state.update_data(experience=_t(lang, "exp_yes", "Да"))
        await state.set_state(Form.waiting_exp_company)
        await message.answer(
            _t(lang, "ask_exp_company"),
            reply_markup=kb.get_cancel_keyboard(lang),
        )
    else:
        await message.answer(_t(lang, "ask_experience_yn"), reply_markup=kb.get_experience_yn_keyboard(lang))


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


@router.message(Form.waiting_readiness)
async def handle_readiness(message: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text = (message.text or "").strip()
    valid = {value for value in (
        _t(lang, "readiness_today"), _t(lang, "readiness_tomorrow"), _t(lang, "readiness_week"),
        _t(lang, "readiness_two_weeks"), _t(lang, "readiness_month"), _skip_text(lang),
    )}
    if text not in valid:
        await _ask_readiness(message, state, lang)
        return
    await state.update_data(readiness=None if text == _skip_text(lang) else text)
    await state.set_state(Form.waiting_salary)
    await message.answer(
        _t(lang, "ask_salary"),
        reply_markup=kb.get_cancel_keyboard(lang),
        parse_mode="HTML",
    )


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

@router.message(Form.waiting_schedule)
async def handle_schedule(message: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text = (message.text or "").strip()
    valid = {_t(lang, key) for key in ("schedule_6_1", "schedule_5_2", "schedule_3_1", "schedule_2_2", "schedule_full", "schedule_flex", "schedule_any")}
    valid.add(_skip_text(lang))
    if text not in valid:
        await message.answer(_t(lang, "ask_schedule"), reply_markup=kb.get_schedule_keyboard(lang))
        return
    await state.update_data(schedule=None if text == _skip_text(lang) else text)
    await state.set_state(Form.waiting_evening_shifts)
    await message.answer(
        _t(lang, "ask_evening_shifts"),
        reply_markup=kb.get_evening_shifts_keyboard(lang),
    )


# ─── 6. Вечерние смены ────────────────────────────────────────────────────────

@router.message(Form.waiting_evening_shifts)
async def handle_evening_shifts(message: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text = (message.text or "").strip()
    valid = {_t(lang, "evening_yes"), _t(lang, "evening_no"), _t(lang, "evening_agreement"), _skip_text(lang)}
    if text not in valid:
        await message.answer(_t(lang, "ask_evening_shifts"), reply_markup=kb.get_evening_shifts_keyboard(lang))
        return
    await state.update_data(evening_shifts=None if text == _skip_text(lang) else text)
    await state.set_state(Form.waiting_weekends)
    await message.answer(
        _t(lang, "ask_weekends"),
        reply_markup=kb.get_weekends_keyboard(lang),
    )


# ─── 7. Выходные и праздники ──────────────────────────────────────────────────

@router.message(Form.waiting_weekends)
async def handle_weekends(message: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text = (message.text or "").strip()
    valid = {_t(lang, "weekends_yes"), _t(lang, "weekends_no"), _t(lang, "weekends_sometimes"), _skip_text(lang)}
    if text not in valid:
        await message.answer(_t(lang, "ask_weekends"), reply_markup=kb.get_weekends_keyboard(lang))
        return
    await state.update_data(weekends=None if text == _skip_text(lang) else text)
    await state.set_state(Form.waiting_smoking)
    await message.answer(
        _t(lang, "ask_smoking"),
        reply_markup=kb.get_smoking_keyboard(lang),
    )


# ─── 8. Курение ───────────────────────────────────────────────────────────────

@router.message(Form.waiting_smoking)
async def handle_smoking(message: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text = (message.text or "").strip()
    valid = {_t(lang, "smoking_no"), _t(lang, "smoking_yes"), _skip_text(lang)}
    if text not in valid:
        await message.answer(_t(lang, "ask_smoking"), reply_markup=kb.get_smoking_keyboard(lang))
        return
    await state.update_data(smoking=None if text == _skip_text(lang) else text)
    await state.set_state(Form.waiting_med_book)
    await message.answer(
        _t(lang, "ask_med_book"),
        reply_markup=kb.get_med_book_keyboard(lang),
    )


# ─── 9. Медицинская книжка ────────────────────────────────────────────────────

@router.message(Form.waiting_med_book)
async def handle_med_book(message: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text = (message.text or "").strip()
    valid = {_t(lang, "med_book_yes"), _t(lang, "med_book_no"), _t(lang, "med_book_in_progress"), _skip_text(lang)}
    if text not in valid:
        await message.answer(_t(lang, "ask_med_book"), reply_markup=kb.get_med_book_keyboard(lang))
        return
    await state.update_data(med_book=None if text == _skip_text(lang) else text)
    await state.set_state(Form.waiting_languages)
    await message.answer(
        _t(lang, "ask_languages"),
        reply_markup=kb.get_languages_keyboard(lang),
    )


# ─── 10. Языки владения (мультиселект) ───────────────────────────────────────

@router.message(Form.waiting_languages)
async def handle_languages(message: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text = (message.text or "").strip()
    if text == _skip_text(lang):
        await state.update_data(languages=None)
        await _ask_phone(message, state, lang)
        return

    options = {_t(lang, key) for key in ("lang_opt_ru", "lang_opt_uz", "lang_opt_en", "lang_opt_tr", "lang_opt_other")}
    if text not in options:
        await message.answer(_t(lang, "ask_languages"), reply_markup=kb.get_languages_keyboard(lang))
        return
    selected = data.get("languages", [])
    selected = selected if isinstance(selected, list) else []
    if text not in selected:
        selected.append(text)
    await state.update_data(languages=selected)
    await _ask_phone(message, state, lang)


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
