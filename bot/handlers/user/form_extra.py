# bot/handlers/user/form_extra.py
"""
Хендлеры для шагов анкеты «Информация о работе» и «Дополнительно»:
- Готовность к работе
- Ветвление Да/Нет для опыта работы (4 под-шага)
- Зарплатные ожидания
- График работы
- Вечерние смены
- Выходные и праздники
- Курение
- Медицинская книжка
- Языки владения (мультиселект)
- Фото кандидата
"""
from __future__ import annotations

import logging
from contextlib import suppress

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message
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


# ─── 1. Языки владения (мультиселект) ────────────────────────────────────────

@router.message(Form.waiting_languages)
async def handle_languages(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text   = (message.text or "").strip()
    uid    = message.from_user.id

    if text == _skip_text(lang):
        await state.update_data(languages=None)
        logger.info("handle_languages: user_id=%d skipped", uid)
        await _ask_position_after_languages(message, state, session, lang)
        return

    if text == _t(lang, "languages_done"):
        selected = data.get("languages", [])
        if not selected:
            with suppress(TelegramAPIError):
                await message.answer(_t(lang, "languages_done_empty"))
            return
        logger.info("handle_languages: user_id=%d selected=%s", uid, selected)
        await _ask_position_after_languages(message, state, session, lang)
        return

    options = {_t(lang, key) for key in ("lang_opt_ru", "lang_opt_uz", "lang_opt_en", "lang_opt_tr", "lang_opt_other")}
    if text not in options:
        logger.debug("handle_languages: invalid input user_id=%d input=%r", uid, text)
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "bad_languages"), parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "ask_languages"), reply_markup=kb.get_languages_keyboard(lang))
        return

    selected = data.get("languages", [])
    selected = selected if isinstance(selected, list) else []
    if text in selected:
        selected.remove(text)
    else:
        selected.append(text)
    await state.update_data(languages=selected)
    with suppress(TelegramAPIError):
        await message.answer(_t(lang, "ask_languages"), reply_markup=kb.get_languages_keyboard(lang))


async def _ask_position_after_languages(
    message: Message, state: FSMContext, session: AsyncSession, lang: str,
) -> None:
    """Раздел «Информация о работе»: первый шаг — выбор должности."""
    vacancies = await db.get_active_vacancies(session)
    await state.set_state(Form.waiting_position)
    with suppress(TelegramAPIError):
        await message.answer(
            LOCALIZATION[lang]["ask_position"],
            reply_markup=kb.get_positions_keyboard(lang, vacancies),
            parse_mode="HTML",
        )


# ─── 2. Готовность к работе ──────────────────────────────────────────────────

@router.message(Form.waiting_readiness)
async def handle_readiness(message: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text   = (message.text or "").strip()
    uid    = message.from_user.id
    valid  = {value for value in (
        _t(lang, "readiness_today"), _t(lang, "readiness_tomorrow"), _t(lang, "readiness_week"),
        _t(lang, "readiness_two_weeks"), _t(lang, "readiness_month"), _skip_text(lang),
    )}
    if text not in valid:
        logger.debug("handle_readiness: invalid input user_id=%d input=%r", uid, text)
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "bad_readiness"), parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "ask_readiness"), reply_markup=kb.get_readiness_keyboard(lang))
        return
    await state.update_data(readiness=None if text == _skip_text(lang) else text)
    logger.info("handle_readiness: user_id=%d readiness=%r", uid, text)
    await state.set_state(Form.waiting_experience)
    with suppress(TelegramAPIError):
        await message.answer(
            _t(lang, "ask_experience_yn"),
            reply_markup=kb.get_experience_yn_keyboard(lang),
        )


# ─── 3. Опыт работы — ветвление Да / Нет ────────────────────────────────────

@router.message(Form.waiting_experience)
async def handle_experience_yn(message: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text   = (message.text or "").strip()
    uid    = message.from_user.id

    if text == _t(lang, "exp_no"):
        await state.update_data(
            experience=_t(lang, "exp_no", "Нет"),
            exp_company=None, exp_position=None,
            exp_duration=None, exp_duties=None,
        )
        logger.info("handle_experience_yn: user_id=%d no_experience", uid)
        await _ask_salary(message, state, lang)
    elif text == _t(lang, "exp_yes"):
        await state.update_data(experience=_t(lang, "exp_yes", "Да"))
        logger.info("handle_experience_yn: user_id=%d has_experience", uid)
        await state.set_state(Form.waiting_exp_company)
        with suppress(TelegramAPIError):
            await message.answer(
                _t(lang, "ask_exp_company"),
                reply_markup=kb.get_cancel_keyboard(lang),
            )
    else:
        logger.debug("handle_experience_yn: invalid input user_id=%d input=%r", uid, text)
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "bad_experience_yn"), parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "ask_experience_yn"), reply_markup=kb.get_experience_yn_keyboard(lang))


# ─── 4. Под-шаги опыта ───────────────────────────────────────────────────────

@router.message(Form.waiting_exp_company)
async def handle_exp_company(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    val  = (message.text or "").strip() or None
    await state.update_data(exp_company=val)
    logger.info("handle_exp_company: user_id=%d company=%r", message.from_user.id, val)
    await state.set_state(Form.waiting_exp_position)
    with suppress(TelegramAPIError):
        await message.answer(
            _t(lang, "ask_exp_position"),
            reply_markup=kb.get_cancel_keyboard(lang),
        )


@router.message(Form.waiting_exp_position)
async def handle_exp_position(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    val  = None if text == _skip_text(lang) else text or None
    await state.update_data(exp_position=val)
    logger.info("handle_exp_position: user_id=%d position=%r", message.from_user.id, val)
    await state.set_state(Form.waiting_exp_duration)
    with suppress(TelegramAPIError):
        await message.answer(
            _t(lang, "ask_exp_duration"),
            reply_markup=kb.get_cancel_keyboard(lang),
        )


@router.message(Form.waiting_exp_duration)
async def handle_exp_duration(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    val  = None if text == _skip_text(lang) else text or None
    await state.update_data(exp_duration=val)
    logger.info("handle_exp_duration: user_id=%d duration=%r", message.from_user.id, val)
    await state.set_state(Form.waiting_exp_duties)
    with suppress(TelegramAPIError):
        await message.answer(
            _t(lang, "ask_exp_duties"),
            reply_markup=kb.get_cancel_keyboard(lang),
        )


@router.message(Form.waiting_exp_duties)
async def handle_exp_duties(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    text = (message.text or "").strip()
    val  = None if text == _skip_text(lang) else text or None
    await state.update_data(exp_duties=val)
    logger.info("handle_exp_duties: user_id=%d duties=%r", message.from_user.id, val)
    await _ask_salary(message, state, lang)


# ─── 5. Зарплатные ожидания ──────────────────────────────────────────────────

async def _ask_salary(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(Form.waiting_salary)
    with suppress(TelegramAPIError):
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
    val  = None if text == _skip_text(lang) else text or None
    await state.update_data(salary=val)
    logger.info("handle_salary: user_id=%d salary=%r", message.from_user.id, val)
    await state.set_state(Form.waiting_schedule)
    with suppress(TelegramAPIError):
        await message.answer(
            _t(lang, "ask_schedule"),
            reply_markup=kb.get_schedule_keyboard(lang),
        )


# ─── 6. График работы ────────────────────────────────────────────────────────

@router.message(Form.waiting_schedule)
async def handle_schedule(message: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text   = (message.text or "").strip()
    uid    = message.from_user.id
    valid  = {_t(lang, key) for key in (
        "schedule_6_1", "schedule_5_2", "schedule_3_1", "schedule_2_2",
        "schedule_full", "schedule_flex", "schedule_any",
    )}
    valid.add(_skip_text(lang))
    if text not in valid:
        logger.debug("handle_schedule: invalid input user_id=%d input=%r", uid, text)
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "bad_schedule"), parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "ask_schedule"), reply_markup=kb.get_schedule_keyboard(lang))
        return
    await state.update_data(schedule=None if text == _skip_text(lang) else text)
    logger.info("handle_schedule: user_id=%d schedule=%r", uid, text)
    await state.set_state(Form.waiting_evening_shifts)
    with suppress(TelegramAPIError):
        await message.answer(
            _t(lang, "ask_evening_shifts"),
            reply_markup=kb.get_evening_shifts_keyboard(lang),
        )


# ─── 7. Вечерние смены ───────────────────────────────────────────────────────

@router.message(Form.waiting_evening_shifts)
async def handle_evening_shifts(message: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text   = (message.text or "").strip()
    uid    = message.from_user.id
    valid  = {_t(lang, "evening_yes"), _t(lang, "evening_no"), _t(lang, "evening_agreement"), _skip_text(lang)}
    if text not in valid:
        logger.debug("handle_evening_shifts: invalid input user_id=%d input=%r", uid, text)
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "bad_evening_shifts"), parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "ask_evening_shifts"), reply_markup=kb.get_evening_shifts_keyboard(lang))
        return
    await state.update_data(evening_shifts=None if text == _skip_text(lang) else text)
    logger.info("handle_evening_shifts: user_id=%d evening_shifts=%r", uid, text)
    await state.set_state(Form.waiting_weekends)
    with suppress(TelegramAPIError):
        await message.answer(
            _t(lang, "ask_weekends"),
            reply_markup=kb.get_weekends_keyboard(lang),
        )


# ─── 8. Выходные и праздники ─────────────────────────────────────────────────

@router.message(Form.waiting_weekends)
async def handle_weekends(message: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text   = (message.text or "").strip()
    uid    = message.from_user.id
    valid  = {_t(lang, "weekends_yes"), _t(lang, "weekends_no"), _t(lang, "weekends_sometimes"), _skip_text(lang)}
    if text not in valid:
        logger.debug("handle_weekends: invalid input user_id=%d input=%r", uid, text)
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "bad_weekends"), parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "ask_weekends"), reply_markup=kb.get_weekends_keyboard(lang))
        return
    await state.update_data(weekends=None if text == _skip_text(lang) else text)
    logger.info("handle_weekends: user_id=%d weekends=%r", uid, text)
    await state.set_state(Form.waiting_smoking)
    with suppress(TelegramAPIError):
        await message.answer(
            _t(lang, "ask_smoking"),
            reply_markup=kb.get_smoking_keyboard(lang),
        )


# ─── 9. Курение ──────────────────────────────────────────────────────────────

@router.message(Form.waiting_smoking)
async def handle_smoking(message: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text   = (message.text or "").strip()
    uid    = message.from_user.id
    valid  = {_t(lang, "smoking_no"), _t(lang, "smoking_yes"), _skip_text(lang)}
    if text not in valid:
        logger.debug("handle_smoking: invalid input user_id=%d input=%r", uid, text)
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "bad_smoking"), parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "ask_smoking"), reply_markup=kb.get_smoking_keyboard(lang))
        return
    await state.update_data(smoking=None if text == _skip_text(lang) else text)
    logger.info("handle_smoking: user_id=%d smoking=%r", uid, text)
    await state.set_state(Form.waiting_med_book)
    with suppress(TelegramAPIError):
        await message.answer(
            _t(lang, "ask_med_book"),
            reply_markup=kb.get_med_book_keyboard(lang),
        )


# ─── 10. Медицинская книжка ──────────────────────────────────────────────────

@router.message(Form.waiting_med_book)
async def handle_med_book(message: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    lang   = _lang(data)
    text   = (message.text or "").strip()
    uid    = message.from_user.id
    valid  = {_t(lang, "med_book_yes"), _t(lang, "med_book_no"), _t(lang, "med_book_in_progress"), _skip_text(lang)}
    if text not in valid:
        logger.debug("handle_med_book: invalid input user_id=%d input=%r", uid, text)
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "bad_med_book"), parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "ask_med_book"), reply_markup=kb.get_med_book_keyboard(lang))
        return
    await state.update_data(med_book=None if text == _skip_text(lang) else text)
    logger.info("handle_med_book: user_id=%d med_book=%r", uid, text)
    await state.set_state(Form.waiting_photo)
    with suppress(TelegramAPIError):
        await message.answer(
            _t(lang, "ask_photo"),
            reply_markup=kb.get_cancel_keyboard(lang),
            parse_mode="HTML",
        )


# ─── 11. Фото кандидата ──────────────────────────────────────────────────────

@router.message(Form.waiting_photo)
async def handle_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang(data)
    uid  = message.from_user.id

    if message.text == _skip_text(lang):
        await state.update_data(photo=None)
        logger.info("handle_photo: user_id=%d skipped", uid)
    elif message.photo:
        photo_id = message.photo[-1].file_id
        await state.update_data(photo=photo_id)
        logger.info("handle_photo: user_id=%d photo saved", uid)
    else:
        logger.debug("handle_photo: invalid content user_id=%d", uid)
        with suppress(TelegramAPIError):
            await message.answer(_t(lang, "bad_photo"), parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(
                _t(lang, "ask_photo"),
                reply_markup=kb.get_cancel_keyboard(lang),
                parse_mode="HTML",
            )
        return

    await state.set_state(Form.waiting_video)
    with suppress(TelegramAPIError):
        await message.answer(
            _t(lang, "ask_video"),
            reply_markup=kb.get_cancel_keyboard(lang),
            parse_mode="HTML",
        )
