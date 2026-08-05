# bot/handlers/user/form_extra.py
"""
Хендлеры для шагов анкеты «Информация о работе» и «Дополнительно»:
- Языки владения (inline multiselect — CallbackQuery)
- Готовность к работе
- Ветвление Да/Нет для опыта работы (4 под-шага)
- Зарплатные ожидания
- График работы
- Вечерние смены
- Выходные и праздники
- Курение
- Медицинская книжка
- Фото кандидата
"""
from __future__ import annotations

import logging

from aiogram import F, Router
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


# ─── 1. Языки владения (inline multiselect) ───────────────────────────────────

def _languages_prompt(lang: str) -> str:
    if lang == "uz":
        return "🌐 Qaysi tillarni bilasiz?\n(Bir nechta tanlash mumkin)"
    return "🌐 Какими языками вы владеете?\n(Можно выбрать несколько)"


@router.callback_query(Form.waiting_languages, F.data.startswith("lang_toggle:"))
async def languages_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    """Переключить выбор одного языка (добавить/убрать)."""
    await callback.answer()
    data = await state.get_data()
    lang = _lang(data)
    key = callback.data.split(":")[1]

    selected: list[str] = list(data.get("languages_selected", []))
    if key in selected:
        selected.remove(key)
    else:
        selected.append(key)

    await state.update_data(languages_selected=selected)
    await callback.message.edit_reply_markup(
        reply_markup=kb.get_languages_inline_keyboard(lang, selected),
    )


@router.callback_query(Form.waiting_languages, F.data == "lang_none")
async def languages_none(callback: CallbackQuery) -> None:
    """Нажали «Готово» без выбора — подсказка."""
    await callback.answer(
        "Выберите хотя бы один язык" if callback.message and "Выберите" in (callback.message.text or "")
        else "Selezioa almeno una lingua",
        show_alert=True,
    )


@router.callback_query(Form.waiting_languages, F.data == "lang_skip")
async def languages_skip(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Пропустить шаг языков."""
    await callback.answer()
    data = await state.get_data()
    lang = _lang(data)
    await state.update_data(languages=None, languages_selected=[])
    await callback.message.edit_reply_markup(reply_markup=None)
    await _ask_position_after_languages(callback.message, state, session, lang)


@router.callback_query(Form.waiting_languages, F.data == "lang_done")
async def languages_done(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Подтвердить выбранные языки и перейти к вакансии."""
    await callback.answer()
    data = await state.get_data()
    lang = _lang(data)
    selected: list[str] = data.get("languages_selected", [])

    # Переводим ключи → читаемые названия для хранения
    _LABELS_RU = {"ru": "Русский", "uz": "Узбекский", "en": "Английский", "tr": "Турецкий", "other": "Другой"}
    _LABELS_UZ = {"ru": "Rus tili", "uz": "O'zbek tili", "en": "Ingliz tili", "tr": "Turk tili", "other": "Boshqa"}
    labels = _LABELS_UZ if lang == "uz" else _LABELS_RU
    readable = [labels.get(k, k) for k in selected]

    await state.update_data(languages=", ".join(readable), languages_selected=selected)
    await callback.message.edit_reply_markup(reply_markup=None)
    await _ask_position_after_languages(callback.message, state, session, lang)


# Вызывается из form.py после шага метро
async def ask_languages(message: Message, state: FSMContext, lang: str) -> None:
    """Отправляет вопрос о языках с inline-клавиатурой."""
    await state.update_data(languages_selected=[])
    await state.set_state(Form.waiting_languages)
    await message.answer(
        _languages_prompt(lang),
        reply_markup=kb.get_languages_inline_keyboard(lang, []),
    )


async def _ask_position_after_languages(
    message: Message, state: FSMContext, session: AsyncSession, lang: str,
) -> None:
    """Раздел «Информация о работе»: первый шаг — выбор должности."""
    vacancies = await db.get_active_vacancies(session)
    await state.set_state(Form.waiting_position)
    await message.answer(
        LOCALIZATION[lang]["ask_position"],
        reply_markup=kb.get_positions_keyboard(lang, vacancies),
        parse_mode="HTML",
    )


# ─── 2. Готовность к работе → Опыт работы ────────────────────────────────────

@router.message(Form.waiting_readiness)
async def handle_readiness(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    valid = {value for value in (
        _t(lang, "readiness_today"), _t(lang, "readiness_tomorrow"), _t(lang, "readiness_week"),
        _t(lang, "readiness_two_weeks"), _t(lang, "readiness_month"), _skip_text(lang),
    )}
    if text not in valid:
        await message.answer(_t(lang, "ask_readiness"), reply_markup=kb.get_readiness_keyboard(lang))
        return
    await state.update_data(readiness=None if text == _skip_text(lang) else text)
    await state.set_state(Form.waiting_experience)
    await message.answer(
        _t(lang, "ask_experience_yn"),
        reply_markup=kb.get_experience_yn_keyboard(lang),
    )
    logger.info("handle_readiness: user_id=%d readiness=%r", message.from_user.id, text)


# ─── 3. Опыт работы — ветвление Да / Нет ─────────────────────────────────────

@router.message(Form.waiting_experience)
async def handle_experience_yn(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()

    if text == _t(lang, "exp_no"):
        await state.update_data(
            experience=_t(lang, "exp_no", "Нет"),
            exp_company=None, exp_position=None,
            exp_duration=None, exp_duties=None,
        )
        await _ask_salary(message, state, lang)
    elif text == _t(lang, "exp_yes"):
        await state.update_data(experience=_t(lang, "exp_yes", "Да"))
        await state.set_state(Form.waiting_exp_company)
        await message.answer(
            _t(lang, "ask_exp_company"),
            reply_markup=kb.get_cancel_keyboard(lang),
        )
    else:
        await message.answer(_t(lang, "ask_experience_yn"), reply_markup=kb.get_experience_yn_keyboard(lang))
        return
    logger.info("handle_experience_yn: user_id=%d has_experience=%s", message.from_user.id, text == _t(lang, "exp_yes"))


# ─── 4. Под-шаги опыта ────────────────────────────────────────────────────────

@router.message(Form.waiting_exp_company)
async def handle_exp_company(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    await state.update_data(exp_company=(message.text or "").strip() or None)
    await state.set_state(Form.waiting_exp_position)
    await message.answer(_t(lang, "ask_exp_position"), reply_markup=kb.get_cancel_keyboard(lang))
    logger.info("handle_exp_company: user_id=%d company=%r", message.from_user.id, message.text)


@router.message(Form.waiting_exp_position)
async def handle_exp_position(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    await state.update_data(exp_position=None if text == _skip_text(lang) else text or None)
    await state.set_state(Form.waiting_exp_duration)
    await message.answer(_t(lang, "ask_exp_duration"), reply_markup=kb.get_cancel_keyboard(lang))
    logger.info("handle_exp_position: user_id=%d position=%r", message.from_user.id, text or None)


@router.message(Form.waiting_exp_duration)
async def handle_exp_duration(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    await state.update_data(exp_duration=None if text == _skip_text(lang) else text or None)
    await state.set_state(Form.waiting_exp_duties)
    await message.answer(_t(lang, "ask_exp_duties"), reply_markup=kb.get_cancel_keyboard(lang))
    logger.info("handle_exp_duration: user_id=%d duration=%r", message.from_user.id, text or None)


@router.message(Form.waiting_exp_duties)
async def handle_exp_duties(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    await state.update_data(exp_duties=None if text == _skip_text(lang) else text or None)
    await _ask_salary(message, state, lang)
    logger.info("handle_exp_duties: user_id=%d duties=%r", message.from_user.id, text or None)


# ─── 5. Зарплатные ожидания ──────────────────────────────────────────────────

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
    await message.answer(_t(lang, "ask_schedule"), reply_markup=kb.get_schedule_keyboard(lang))
    logger.info("handle_salary: user_id=%d salary=%r", message.from_user.id, text or None)


# ─── 6. График работы ─────────────────────────────────────────────────────────

@router.message(Form.waiting_schedule)
async def handle_schedule(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    valid = {_t(lang, key) for key in (
        "schedule_6_1", "schedule_5_2", "schedule_3_1",
        "schedule_2_2", "schedule_full", "schedule_flex", "schedule_any",
    )}
    valid.add(_skip_text(lang))
    if text not in valid:
        await message.answer(_t(lang, "ask_schedule"), reply_markup=kb.get_schedule_keyboard(lang))
        return
    await state.update_data(schedule=None if text == _skip_text(lang) else text)
    await state.set_state(Form.waiting_evening_shifts)
    await message.answer(_t(lang, "ask_evening_shifts"), reply_markup=kb.get_evening_shifts_keyboard(lang))
    logger.info("handle_schedule: user_id=%d schedule=%r", message.from_user.id, text)


# ─── 7. Вечерние смены ────────────────────────────────────────────────────────

@router.message(Form.waiting_evening_shifts)
async def handle_evening_shifts(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    valid = {_t(lang, "evening_yes"), _t(lang, "evening_no"), _t(lang, "evening_agreement"), _skip_text(lang)}
    if text not in valid:
        await message.answer(_t(lang, "ask_evening_shifts"), reply_markup=kb.get_evening_shifts_keyboard(lang))
        return
    await state.update_data(evening_shifts=None if text == _skip_text(lang) else text)
    await state.set_state(Form.waiting_weekends)
    await message.answer(_t(lang, "ask_weekends"), reply_markup=kb.get_weekends_keyboard(lang))
    logger.info("handle_evening_shifts: user_id=%d evening_shifts=%r", message.from_user.id, text)


# ─── 8. Выходные и праздники ──────────────────────────────────────────────────

@router.message(Form.waiting_weekends)
async def handle_weekends(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    valid = {_t(lang, "weekends_yes"), _t(lang, "weekends_no"), _t(lang, "weekends_sometimes"), _skip_text(lang)}
    if text not in valid:
        await message.answer(_t(lang, "ask_weekends"), reply_markup=kb.get_weekends_keyboard(lang))
        return
    await state.update_data(weekends=None if text == _skip_text(lang) else text)
    await state.set_state(Form.waiting_smoking)
    await message.answer(_t(lang, "ask_smoking"), reply_markup=kb.get_smoking_keyboard(lang))
    logger.info("handle_weekends: user_id=%d weekends=%r", message.from_user.id, text)


# ─── 9. Курение ───────────────────────────────────────────────────────────────

@router.message(Form.waiting_smoking)
async def handle_smoking(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    valid = {_t(lang, "smoking_no"), _t(lang, "smoking_yes"), _skip_text(lang)}
    if text not in valid:
        await message.answer(_t(lang, "ask_smoking"), reply_markup=kb.get_smoking_keyboard(lang))
        return
    await state.update_data(smoking=None if text == _skip_text(lang) else text)
    await state.set_state(Form.waiting_med_book)
    await message.answer(_t(lang, "ask_med_book"), reply_markup=kb.get_med_book_keyboard(lang))
    logger.info("handle_smoking: user_id=%d smoking=%r", message.from_user.id, text)
