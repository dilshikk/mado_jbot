# bot/handlers/user/form.py

import asyncio
import logging
import re
from contextlib import suppress
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import ADMIN_CHAT_ID, ADMIN_IDS
from bot.db import requests as db
from bot.filters.common import IsCancelMessage, IsPrivateChat
from bot import keyboards as kb
from bot.lexicon import LOCALIZATION
from bot.services.ai import screen_application
from bot.services.gsheets import append_to_sheet
from bot.states import Form
from bot.utils.formatters import build_hr_resume_text, build_resume_text

router = Router()
router.message.filter(IsPrivateChat())

logger = logging.getLogger(__name__)

MIN_VIDEO_DURATION = 15
VALID_BRANCH       = "Tashkent City Mall"

# Статусы, при которых повторная подача анкеты запрещена
BLOCKING_STATUSES = {"pending", "accepted", "hired", "hold"}

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
            key = f"anketa_block_{status}"
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
async def process_phone(message: Message, state: FSMContext, lang: str) -> None:
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
    with suppress(TelegramAPIError):
        await message.answer(
            LOCALIZATION[lang]["ask_metro"],
            reply_markup=kb.get_metro_keyboard(lang),
            parse_mode="HTML",
        )
    await state.set_state(Form.waiting_metro)


# ── Метро ─────────────────────────────────────────────────────────────────────

@router.message(Form.waiting_metro)
async def process_metro(message: Message, state: FSMContext, lang: str) -> None:
    text = (message.text or "").strip()
    skip_value = LOCALIZATION[lang].get("metro_skip", LOCALIZATION[lang]["btn_skip"])
    valid_values = {
        button.text
        for row in kb.get_metro_keyboard(lang).keyboard
        for button in row
        if button.text != LOCALIZATION[lang]["btn_cancel"]
    }
    if text not in valid_values:
        logger.debug("process_metro: invalid input user_id=%d input=%r", message.from_user.id, text)
        with suppress(TelegramAPIError):
            await message.answer(LOCALIZATION[lang]["bad_metro"], parse_mode="HTML")
        with suppress(TelegramAPIError):
            await message.answer(
                LOCALIZATION[lang]["ask_metro"],
                reply_markup=kb.get_metro_keyboard(lang),
                parse_mode="HTML",
            )
        return
    await state.update_data(metro=None if text == skip_value else text)
    logger.info("process_metro: user_id=%d metro=%r", message.from_user.id, text)
    with suppress(TelegramAPIError):
        await message.answer(
            LOCALIZATION[lang]["ask_languages"],
            reply_markup=kb.get_languages_keyboard(lang),
            parse_mode="HTML",
        )
    await state.set_state(Form.waiting_languages)


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
                reply_markup=kb.get_cancel_keyboard(lang),
                parse_mode="HTML",
            )
        return
    if message.video_note or message.video:
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
                    reply_markup=kb.get_cancel_keyboard(lang),
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
    bot: Bot     = message.bot

    await db.save_application(
        session,
        user_id=user.id,
        name=data.get("name"),
        birthday=data.get("birthday"),
        phone=data.get("phone"),
        position=data.get("position"),
        experience=data.get("experience", "—"),
    )
    logger.info(
        "process_confirmation: application saved user_id=%d position=%r",
        user.id, data.get("position"),
    )

    resume_text = build_hr_resume_text(data, user.id, username_raw)
    hr_keyboard = kb.get_hr_action_keyboard(
        phone=data.get("phone"), username=username_raw, candidate_id=user.id,
    )
    hr_msg = await bot.send_message(
        chat_id=ADMIN_CHAT_ID, text=resume_text, reply_markup=hr_keyboard, parse_mode="HTML",
    )

    # AI-скрининг анкеты
    ai_summary = await screen_application(data)
    if ai_summary:
        try:
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"🤖 <b>AI-скрининг</b>\n{'─'*24}\n{ai_summary}",
                parse_mode="HTML",
                reply_to_message_id=hr_msg.message_id,
            )
        except Exception as e:
            logger.error("Не удалось отправить AI-скрининг: %s", e)

    video_file_id = data.get("video_file_id")
    if video_file_id:
        try:
            if data.get("is_video_note"):
                video_msg = await bot.send_video_note(chat_id=ADMIN_CHAT_ID, video_note=video_file_id)
            else:
                video_msg = await bot.send_video(
                    chat_id=ADMIN_CHAT_ID,
                    video=video_file_id,
                    caption=f"🎥 {data.get('name')} (@{username_raw})",
                )
            await db.save_hr_video_msg_id(session, user.id, video_msg.message_id)
        except Exception as e:
            logger.error("Ошибка отправки видео HR: %s", e, exc_info=True)

    row_data = [
        now_str, data.get("branch"), data.get("position"), data.get("name"),
        data.get("birthday"), data.get("gender"), data.get("phone"),
        data.get("metro"),
        ", ".join(data.get("languages") or []) or None,
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
        error_text = (
            f"⚠️ <b>Google Sheets: ошибка записи!</b>\n\n"
            f"👤 Кандидат: <b>{data.get('name')}</b>\n"
            f"📱 <code>{data.get('phone')}</code>\n"
            f"💼 {data.get('position')}\n\n"
            f"<i>Данные в БД сохранены.</i>\n"
            f"🔴 Ошибка: <code>{e}</code>"
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(chat_id=admin_id, text=error_text, parse_mode="HTML")
            except Exception as notify_err:
                logger.error("Не удалось уведомить admin_id=%d: %s", admin_id, notify_err)

    with suppress(TelegramAPIError):
        await message.answer(
            LOCALIZATION[lang]["anketa_done"],
            reply_markup=kb.get_main_menu(lang),
            parse_mode="HTML",
        )

    # ── Запуск AI-интервью ────────────────────────────────────────────────────
    from bot.handlers.user.interview import start_interview  # noqa: PLC0415

    form_data_for_interview = dict(data)

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
