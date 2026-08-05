# bot/handlers/user/form.py

import asyncio
import logging
import re
from contextlib import suppress
from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import ADMIN_IDS
from bot.db import requests as db
from bot.filters.common import IsCancelMessage, IsPrivateChat
from bot import keyboards as kb
from bot.lexicon import LOCALIZATION
from bot.services.gsheets import append_to_sheet
from bot.states import Form
from bot.utils.formatters import build_resume_text

router = Router()
router.message.filter(IsPrivateChat())

logger = logging.getLogger(__name__)

MIN_VIDEO_DURATION = 15
VALID_BRANCH       = "Tashkent City Mall"

# Статусы, при которых повторная подача анкеты запрещена
# interview_in_progress и interview_failed не блокируют — кандидат может повторить
BLOCKING_STATUSES = {"pending", "accepted", "hired", "hold", "interview_in_progress"}

# Все активные шаги анкеты (waiting_for_lang исключён — там своя логика)
_FORM_ACTIVE_STATES = (
    Form.waiting_name, Form.waiting_birthday, Form.waiting_gender,
    Form.waiting_phone, Form.waiting_metro,
    Form.waiting_languages,
    Form.waiting_position, Form.waiting_readiness, Form.waiting_experience,
    Form.waiting_exp_company, Form.waiting_exp_position, Form.waiting_exp_duration,
    Form.waiting_exp_duties, Form.waiting_salary,
    Form.waiting_schedule, Form.waiting_evening_shifts, Form.waiting_weekends,
    Form.waiting_smoking, Form.waiting_med_book,
    Form.waiting_photo, Form.waiting_video, Form.waiting_confirmation,
)


def _valid_position_labels(vacancies: list[dict]) -> set[str]:
    labels: set[str] = set()
    for v in vacancies:
        for key in ("name_ru", "name_uz"):
            name  = (v.get(key) or "").strip()
            emoji = (v.get("emoji") or "").strip()
            if name:
                labels.add(f"{emoji} {name}".strip())
                labels.add(name)
    return labels


def _languages_str(data: dict) -> str | None:
    """Возвращает строку языков независимо от того, строка или список хранится в FSM."""
    val = data.get("languages")
    if not val:
        return None
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val)


@router.message(StateFilter(*_FORM_ACTIVE_STATES), IsCancelMessage())
@router.message(StateFilter(*_FORM_ACTIVE_STATES), Command("cancel"))
async def cancel_form(message: Message, state: FSMContext, lang: str) -> None:
    """Отмена анкеты на любом шаге — кнопкой или командой /cancel."""
    await state.clear()
    await state.update_data(lang=lang)
    with suppress(TelegramAPIError):
        await message.answer(
            LOCALIZATION[lang]["anketa_cancelled"],
            reply_markup=kb.get_main_menu(lang),
            parse_mode="HTML",
        )


@router.message(F.text.in_(["📝 Заполнить анкету", "📝 Anketani to'ldirish"]))
async def start_anketa(message: Message, state: FSMContext, lang: str, session: AsyncSession) -> None:
    if await db.is_user_blocked(session, message.from_user.id):
        with suppress(TelegramAPIError):
            await message.answer(LOCALIZATION[lang]["user_blocked_text"], parse_mode="HTML")
        return

    vacancies = await db.get_active_vacancies(session)
    if not vacancies:
        with suppress(TelegramAPIError):
            await message.answer(
                "⏳ <b>В данный момент открытых вакансий нет.</b>\n\nСледите за обновлениями!"
                if lang == "ru" else
                "⏳ <b>Hozirda ochiq vakansiyalar yo'q.</b>\n\nYangilanishlarni kuzatib boring!",
                parse_mode="HTML",
            )
        return

    is_admin = message.from_user.id in ADMIN_IDS
    if not is_admin:
        status = await db.get_application_status(session, message.from_user.id)
        if status in BLOCKING_STATUSES:
            key  = f"anketa_block_{status}"
            text = LOCALIZATION[lang].get(key) or LOCALIZATION[lang]["anketa_block_pending"]
            with suppress(TelegramAPIError):
                await message.answer(text, parse_mode="HTML")
            return

    await state.update_data(branch=VALID_BRANCH)
    with suppress(TelegramAPIError):
        await message.answer(
            LOCALIZATION[lang]["ask_name"],
            reply_markup=kb.get_cancel_keyboard(lang),
            parse_mode="HTML",
        )
    await state.set_state(Form.waiting_name)


# ── ФИО ──────────────────────────────────────────────────────────────────────

@router.message(Form.waiting_name)
async def process_name(message: Message, state: FSMContext, lang: str) -> None:
    text = (message.text or "").strip()
    if len(text) < 3 or any(ch.isdigit() for ch in text):
        logger.debug("process_name: validation failed user_id=%d input=%r", message.from_user.id, text)
        with suppress(TelegramAPIError):
            await message.answer(
                LOCALIZATION[lang].get("bad_name", "❌ Введите корректное ФИО."),
                parse_mode="HTML",
            )
        with suppress(TelegramAPIError):
            await message.answer(
                LOCALIZATION[lang]["ask_name"],
                reply_markup=kb.get_cancel_keyboard(lang),
                parse_mode="HTML",
            )
        return
    await state.update_data(name=text)
    logger.info("process_name: user_id=%d name=%r", message.from_user.id, text)
    with suppress(TelegramAPIError):
        await message.answer(
            LOCALIZATION[lang]["ask_birthday"],
            reply_markup=kb.get_cancel_keyboard(lang),
            parse_mode="HTML",
        )
    await state.set_state(Form.waiting_birthday)


# ── Дата рождения ─────────────────────────────────────────────────────────────

@router.message(Form.waiting_birthday)
async def process_birthday(message: Message, state: FSMContext, lang: str) -> None:
    text = (message.text or "").strip()
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", text):
        logger.debug("process_birthday: bad format user_id=%d input=%r", message.from_user.id, text)
        with suppress(TelegramAPIError):
            await message.answer(LOCALIZATION[lang]["bad_birthday"], parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(
                LOCALIZATION[lang]["ask_birthday"],
                reply_markup=kb.get_cancel_keyboard(lang),
                parse_mode="HTML",
            )
        return
    try:
        birth_date = datetime.strptime(text, "%d.%m.%Y")
        age = (datetime.now() - birth_date).days // 365
    except ValueError:
        logger.debug("process_birthday: strptime failed user_id=%d input=%r", message.from_user.id, text)
        with suppress(TelegramAPIError):
            await message.answer(LOCALIZATION[lang]["bad_birthday"], parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(
                LOCALIZATION[lang]["ask_birthday"],
                reply_markup=kb.get_cancel_keyboard(lang),
                parse_mode="HTML",
            )
        return
    if not (18 <= age <= 60):
        logger.debug("process_birthday: age out of range user_id=%d age=%d", message.from_user.id, age)
        with suppress(TelegramAPIError):
            await message.answer(LOCALIZATION[lang]["bad_age"], parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(
                LOCALIZATION[lang]["ask_birthday"],
                reply_markup=kb.get_cancel_keyboard(lang),
                parse_mode="HTML",
            )
        return
    await state.update_data(birthday=text)
    logger.info("process_birthday: user_id=%d birthday=%r age=%d", message.from_user.id, text, age)
    with suppress(TelegramAPIError):
        await message.answer(
            LOCALIZATION[lang]["ask_gender"],
            reply_markup=kb.get_gender_keyboard(lang),
            parse_mode="HTML",
        )
    await state.set_state(Form.waiting_gender)


# ── Пол ───────────────────────────────────────────────────────────────────────

@router.message(Form.waiting_gender)
async def process_gender(message: Message, state: FSMContext, lang: str) -> None:
    if message.text not in {LOCALIZATION[lang]["gender_male"], LOCALIZATION[lang]["gender_female"]}:
        logger.debug("process_gender: invalid input user_id=%d input=%r", message.from_user.id, message.text)
        with suppress(TelegramAPIError):
            await message.answer(LOCALIZATION[lang]["bad_gender"], parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(
                LOCALIZATION[lang]["ask_gender"],
                reply_markup=kb.get_gender_keyboard(lang),
                parse_mode="HTML",
            )
        return
    await state.update_data(gender=message.text)
    logger.info("process_gender: user_id=%d gender=%r", message.from_user.id, message.text)
    with suppress(TelegramAPIError):
        await message.answer(
            LOCALIZATION[lang]["ask_phone"],
            reply_markup=kb.get_phone_keyboard(lang),
            parse_mode="HTML",
        )
    await state.set_state(Form.waiting_phone)


# ── Телефон ───────────────────────────────────────────────────────────────────

@router.message(Form.waiting_phone)
async def process_phone(message: Message, state: FSMContext, lang: str, session: AsyncSession) -> None:
    phone = message.contact.phone_number if message.contact else (message.text or "").strip()
    if not message.contact and not re.match(r"^\+?\d{7,15}$", phone):
        logger.debug("process_phone: invalid phone user_id=%d input=%r", message.from_user.id, phone)
        with suppress(TelegramAPIError):
            await message.answer(LOCALIZATION[lang]["bad_phone"], parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(
                LOCALIZATION[lang]["ask_phone"],
                reply_markup=kb.get_phone_keyboard(lang),
                parse_mode="HTML",
            )
        return
    await state.update_data(phone=phone)
    logger.info("process_phone: user_id=%d phone=%r", message.from_user.id, phone)

    # ── Переходим к inline-выбору метро ──────────────────────────────────────
    from bot.handlers.user.metro import ask_metro  # noqa: PLC0415
    await ask_metro(message, state, lang)


# ── Желаемая должность ────────────────────────────────────────────────────────

@router.message(Form.waiting_position)
async def process_position(message: Message, state: FSMContext, lang: str, session: AsyncSession) -> None:
    vacancies = await db.get_active_vacancies(session)
    valid     = _valid_position_labels(vacancies)
    chosen    = (message.text or "").strip()
    if chosen not in valid:
        logger.debug("process_position: invalid input user_id=%d input=%r", message.from_user.id, chosen)
        with suppress(TelegramAPIError):
            await message.answer(LOCALIZATION[lang]["bad_position"], parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(
                LOCALIZATION[lang]["ask_position"],
                reply_markup=kb.get_positions_keyboard(lang, vacancies),
                parse_mode="HTML",
            )
        return
    await state.update_data(position=chosen)
    logger.info("process_position: user_id=%d position=%r", message.from_user.id, chosen)
    with suppress(TelegramAPIError):
        await message.answer(
            LOCALIZATION[lang]["ask_readiness"],
            reply_markup=kb.get_readiness_keyboard(lang),
            parse_mode="HTML",
        )
    await state.set_state(Form.waiting_readiness)


# ── Видео-визитка ─────────────────────────────────────────────────────────────

@router.message(Form.waiting_video)
async def process_video(message: Message, state: FSMContext, lang: str) -> None:
    btn_skip = LOCALIZATION[lang].get("btn_skip", "⏭ Пропустить")
    duration = 0
    file_id  = None
    is_note  = False

    if message.text == btn_skip:
        await state.update_data(video_file_id=None, is_video_note=False, video_duration=0)
        logger.info("process_video: user_id=%d skipped", message.from_user.id)
    elif message.video_note:
        duration, file_id, is_note = message.video_note.duration, message.video_note.file_id, True
    elif message.video:
        duration, file_id, is_note = message.video.duration, message.video.file_id, False
    else:
        logger.debug("process_video: invalid content user_id=%d", message.from_user.id)
        with suppress(TelegramAPIError):
            await message.answer(
                LOCALIZATION[lang].get("bad_video", "❌ Отправьте видео или нажмите «⏭ Пропустить»."),
                parse_mode="HTML",
            )
        with suppress(TelegramAPIError):
            await message.answer(
                LOCALIZATION[lang]["ask_video"],
                reply_markup=kb.get_skip_cancel_keyboard(lang),
                parse_mode="HTML",
            )
        return

    if file_id is not None:
        if duration < MIN_VIDEO_DURATION:
            logger.debug(
                "process_video: too short user_id=%d duration=%d min=%d",
                message.from_user.id, duration, MIN_VIDEO_DURATION,
            )
            tpl = LOCALIZATION[lang].get("bad_video_short", "")
            error_text = tpl.format(duration=duration, min_duration=MIN_VIDEO_DURATION) if tpl else (
                f"❌ Видео слишком короткое ({duration} сек). Нужно <b>≥{MIN_VIDEO_DURATION} сек</b>."
                if lang == "ru" else
                f"❌ Video qisqa ({duration}s). <b>≥{MIN_VIDEO_DURATION}s</b> kerak."
            )
            with suppress(TelegramAPIError):
                await message.answer(error_text, parse_mode="HTML")
            with suppress(TelegramAPIError):
                await message.answer(
                    LOCALIZATION[lang]["ask_video"],
                    reply_markup=kb.get_skip_cancel_keyboard(lang),
                    parse_mode="HTML",
                )
            return
        await state.update_data(video_file_id=file_id, is_video_note=is_note, video_duration=duration)
        logger.info(
            "process_video: user_id=%d duration=%d is_note=%s",
            message.from_user.id, duration, is_note,
        )

    # ── Итоговая сводка анкеты → подтверждение ──
    data    = await state.get_data()
    summary = build_resume_text(data, lang)
    with suppress(TelegramAPIError):
        await message.answer(summary, reply_markup=kb.get_confirmation_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_confirmation)


# ── Подтверждение анкеты ──────────────────────────────────────────────────────

@router.message(Form.waiting_confirmation)
async def process_confirmation(message: Message, state: FSMContext, lang: str, session: AsyncSession) -> None:
    data = await state.get_data()

    if message.text in {LOCALIZATION["ru"]["confirm_btn_no"], LOCALIZATION["uz"]["confirm_btn_no"]}:
        await state.clear()
        await state.update_data(lang=lang)
        await start_anketa(message, state, lang, session)
        return

    if message.text not in {LOCALIZATION["ru"]["confirm_btn_yes"], LOCALIZATION["uz"]["confirm_btn_yes"]}:
        return

    user = message.from_user

    # Финальная защита от дублей (для не-админов)
    is_admin = user.id in ADMIN_IDS
    if not is_admin:
        status = await db.get_application_status(session, user.id)
        if status in BLOCKING_STATUSES:
            with suppress(TelegramAPIError):
                await message.answer(
                    LOCALIZATION[lang]["anketa_already_exists"],
                    reply_markup=kb.get_main_menu(lang),
                    parse_mode="HTML",
                )
            await state.clear()
            await state.update_data(lang=lang)
            return

    now_str      = datetime.now().strftime("%d.%m.%Y %H:%M")
    username_raw = user.username or LOCALIZATION["ru"]["none_text"]

    # ── 1. Сохраняем анкету в БД ─────────────────────────────────────────────
    await db.save_application(
        session,
        user_id=user.id,
        name=data.get("name"),
        birthday=data.get("birthday"),
        phone=data.get("phone"),
        position=data.get("position"),
        experience=data.get("experience", "—"),
        metro_station_id=data.get("metro_station_id"),
    )
    logger.info(
        "process_confirmation: application saved user_id=%d position=%r metro_station_id=%s",
        user.id, data.get("position"), data.get("metro_station_id"),
    )

    # ── 2. Записываем в Google Sheets ────────────────────────────────────────
    metro_name = data.get("metro_name") or "—"
    # languages хранится как строка "Русский, Турецкий" (или None)
    languages_str = _languages_str(data)

    row_data = [
        now_str, data.get("branch"), data.get("position"), data.get("name"),
        data.get("birthday"), data.get("gender"), data.get("phone"),
        metro_name,
        languages_str,
        data.get("readiness"), data.get("experience", "—"),
        data.get("exp_company"), data.get("exp_position"),
        data.get("exp_duration"), data.get("exp_duties"),
        data.get("salary"), data.get("schedule"), data.get("evening_shifts"),
        data.get("weekends"), data.get("smoking"), data.get("med_book"),
    ]
    try:
        success = await asyncio.to_thread(append_to_sheet, row_data)
        if not success:
            raise RuntimeError("append_to_sheet вернул False")
    except Exception as e:
        logger.error("Ошибка Google Sheets: %s", e, exc_info=True)
        from bot.core.config import ADMIN_IDS as _AIDS  # noqa: PLC0415
        error_text = (
            f"⚠️ <b>Google Sheets: ошибка записи!</b>\n\n"
            f"👤 Кандидат: <b>{data.get('name')}</b>\n"
            f"📱 <code>{data.get('phone')}</code>\n"
            f"💼 {data.get('position')}\n\n"
            f"<i>Данные в БД сохранены.</i>\n"
            f"🔴 Ошибка: <code>{e}</code>"
        )
        from aiogram import Bot as _Bot  # noqa: PLC0415
        _bot: _Bot = message.bot
        for admin_id in _AIDS:
            with suppress(Exception):
                await _bot.send_message(chat_id=admin_id, text=error_text, parse_mode="HTML")

    # ── 3. Уведомляем кандидата об успешной подаче анкеты ────────────────────
    with suppress(TelegramAPIError):
        await message.answer(
            LOCALIZATION[lang]["anketa_done"],
            reply_markup=kb.get_main_menu(lang),
            parse_mode="HTML",
        )

    # ── 4. В HR-группу НИЧЕГО не отправляем — только после завершения интервью ──

    # ── 5. Запускаем AI-интервью ──────────────────────────────────────────────
    from bot.handlers.user.interview import start_interview  # noqa: PLC0415

    form_data_for_interview = dict(data)
    form_data_for_interview["username"] = username_raw
    if not form_data_for_interview.get("metro_name"):
        form_data_for_interview["metro_name"] = "—"

    await state.clear()
    await state.update_data(lang=lang)

    try:
        await start_interview(
            message=message,
            state=state,
            session=session,
            form_data=form_data_for_interview,
            lang=lang,
        )
    except Exception as e:
        logger.error("Ошибка запуска интервью для user_id=%d: %s", user.id, e, exc_info=True)
        await db.update_application_status(session, user.id, "interview_failed")
