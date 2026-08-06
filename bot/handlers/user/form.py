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
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import ADMIN_CHAT_ID, ADMIN_IDS
from bot.db import requests as db
from bot.filters.common import IsCancelMessage, IsPrivateChat
from bot import keyboards as kb
from bot.lexicon import LOCALIZATION
from bot.locks import submission_lock
from bot.services.ai import screen_application
from bot.services.gsheets import append_to_sheet
from bot.states import Form
from bot.utils.formatters import build_hr_resume_text, build_resume_text

router = Router()
router.message.filter(IsPrivateChat())
router.callback_query.filter(IsPrivateChat())

logger = logging.getLogger(__name__)

MIN_VIDEO_DURATION = 15
VALID_BRANCH = "Tashkent City Mall"

BLOCKING_STATUSES = {"pending", "accepted", "hired", "hold"}

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

# ─── Recap labels ─────────────────────────────────────────────────────────────

_RECAP: dict[str, dict[str, str]] = {
    "ru": {
        "name":     "👤 ФИО",
        "birthday": "🎂 Дата рождения",
        "gender":   "⚧ Пол",
        "phone":    "📱 Телефон",
    },
    "uz": {
        "name":     "👤 FIO",
        "birthday": "🎂 Tug'ilgan kun",
        "gender":   "⚧ Jins",
        "phone":    "📱 Telefon",
    },
}

def _recap(lang: str, field: str, value: str | None) -> str | None:
    if not value:
        return None
    label = _RECAP.get(lang, _RECAP["ru"]).get(field, field)
    return f"{label}: <b>{value}</b>"


# ─── Отмена анкеты — Message ──────────────────────────────────────────────────

@router.message(StateFilter(*_FORM_ACTIVE_STATES), IsCancelMessage())
@router.message(StateFilter(*_FORM_ACTIVE_STATES), Command("cancel"))
async def cancel_form(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await state.update_data(lang=lang)
    await message.answer(LOCALIZATION[lang]["anketa_cancelled"], reply_markup=kb.get_main_menu(lang), parse_mode="HTML")


# ─── Отмена анкеты — Callback ─────────────────────────────────────────────────

@router.callback_query(StateFilter(*_FORM_ACTIVE_STATES), F.data == "form_cancel")
async def cancel_form_callback(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.clear()
    await state.update_data(lang=lang)
    with suppress(TelegramAPIError):
        await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        LOCALIZATION[lang]["anketa_cancelled"],
        reply_markup=kb.get_main_menu(lang),
        parse_mode="HTML",
    )
    with suppress(TelegramAPIError):
        await callback.answer()


# ─── Старт анкеты ─────────────────────────────────────────────────────────────

@router.message(F.text.in_(["📝 Заполнить анкету", "📝 Anketani to'ldirish"]))
async def start_anketa(message: Message, state: FSMContext, lang: str, session: AsyncSession) -> None:
    if await db.is_user_blocked(session, message.from_user.id):
        await message.answer(LOCALIZATION[lang]["user_blocked_text"], parse_mode="HTML")
        return

    vacancies = await db.get_active_vacancies(session)
    if not vacancies:
        await message.answer(
            "⏳ В данный момент открытых вакансий нет. \n\nСледите за обновлениями!"
            if lang == "ru" else
            "⏳ Hozirda ochiq vakansiyalar yo'q. \n\nYangilanishlarni kuzatib boring!",
            parse_mode="HTML",
        )
        return

    is_admin = message.from_user.id in ADMIN_IDS
    if not is_admin:
        status = await db.get_application_status(session, message.from_user.id)
        if status in BLOCKING_STATUSES:
            key = f"anketa_block_{status}"
            text = LOCALIZATION[lang].get(key) or LOCALIZATION[lang]["anketa_block_pending"]
            await message.answer(text, parse_mode="HTML")
            return

    await state.update_data(branch=VALID_BRANCH)
    await message.answer(LOCALIZATION[lang]["ask_name"], reply_markup=kb.get_cancel_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_name)


# ─── Шаг 1: Имя ───────────────────────────────────────────────────────────────

@router.message(Form.waiting_name)
async def process_name(message: Message, state: FSMContext, lang: str) -> None:
    text = (message.text or "").strip()
    if len(text) < 3 or any(ch.isdigit() for ch in text):
        await message.answer(LOCALIZATION[lang].get("bad_name", "Введите корректное ФИО."), parse_mode="HTML")
        return
    await state.update_data(name=text)
    if recap := _recap(lang, "name", text):
        await message.answer(recap, parse_mode="HTML")
    await message.answer(LOCALIZATION[lang]["ask_birthday"], reply_markup=kb.get_cancel_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_birthday)


# ─── Шаг 2: Дата рождения ─────────────────────────────────────────────────────

@router.message(Form.waiting_birthday)
async def process_birthday(message: Message, state: FSMContext, lang: str) -> None:
    text = (message.text or "").strip()
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", text):
        await message.answer(LOCALIZATION[lang]["bad_birthday"], parse_mode="HTML")
        return
    try:
        birth_date = datetime.strptime(text, "%d.%m.%Y")
        age = (datetime.now() - birth_date).days // 365
    except ValueError:
        await message.answer(LOCALIZATION[lang]["bad_birthday"], parse_mode="HTML")
        return
    if not (18 <= age <= 60):
        await message.answer(
            "Возраст должен быть от 18 до 60 лет." if lang == "ru" else "Yosh 18 dan 60 yoshgacha bo'lishi kerak.",
            parse_mode="HTML",
        )
        return
    await state.update_data(birthday=text)
    if recap := _recap(lang, "birthday", text):
        await message.answer(recap, parse_mode="HTML")
    with suppress(TelegramAPIError):
        stub = await message.answer("👤", reply_markup=kb.remove_keyboard())
    with suppress(TelegramAPIError):
        await stub.delete()
    await message.answer(
        LOCALIZATION[lang]["ask_gender"],
        reply_markup=kb.get_gender_keyboard(lang),
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_gender)


# ─── Шаг 3: Пол (Inline) ──────────────────────────────────────────────────────

@router.callback_query(Form.waiting_gender, F.data.startswith("gender:"))
async def process_gender(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    with suppress(TelegramAPIError):
        await callback.answer()
    choice = callback.data.split(":")[1]
    gender_text = LOCALIZATION[lang]["gender_male"] if choice == "male" else LOCALIZATION[lang]["gender_female"]
    await state.update_data(gender=gender_text)
    with suppress(TelegramAPIError):
        await callback.message.edit_reply_markup(reply_markup=None)
    if recap := _recap(lang, "gender", gender_text):
        await callback.message.answer(recap, parse_mode="HTML")
    await callback.message.answer(
        LOCALIZATION[lang]["ask_phone"],
        reply_markup=kb.get_phone_keyboard(lang),
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_phone)


# ─── Шаг 4: Телефон ───────────────────────────────────────────────────────────

@router.message(Form.waiting_phone)
async def process_phone(message: Message, state: FSMContext, lang: str) -> None:
    phone = message.contact.phone_number if message.contact else (message.text or "").strip()
    if not message.contact and not re.match(r"^\+?\d{7,15}$", phone):
        await message.answer(
            "Введите корректный номер: +998901234567 " if lang == "ru" else "To'g'ri raqam kiriting: +998901234567 ",
            parse_mode="HTML",
        )
        return
    await state.update_data(phone=phone)
    if recap := _recap(lang, "phone", phone):
        await message.answer(recap, parse_mode="HTML")
    from bot.handlers.user.metro import ask_metro  # noqa: PLC0415
    await ask_metro(message, state, lang)


# ─── Шаг N: Видео ─────────────────────────────────────────────────────────────

@router.message(Form.waiting_video)
async def process_video(message: Message, state: FSMContext, lang: str) -> None:
    if message.text == LOCALIZATION[lang]["btn_skip"]:
        await state.update_data(video_file_id=None, is_video_note=False, video_duration=0)
    elif message.video_note:
        duration, file_id, is_note = message.video_note.duration, message.video_note.file_id, True
    elif message.video:
        duration, file_id, is_note = message.video.duration, message.video.file_id, False
    else:
        await message.answer(LOCALIZATION[lang]["ask_video"], reply_markup=kb.get_cancel_keyboard(lang), parse_mode="HTML")
        return
    if message.video_note or message.video:
        if duration < MIN_VIDEO_DURATION:
            await message.answer(
                f"Видео слишком короткое ({duration} сек). Нужно ≥{MIN_VIDEO_DURATION} сек."
                if lang == "ru" else
                f"Video qisqa ({duration}s). ≥{MIN_VIDEO_DURATION}s kerak.",
                parse_mode="HTML",
            )
            return
        await state.update_data(video_file_id=file_id, is_video_note=is_note, video_duration=duration)

    # Показываем сводку анкеты с кнопками подтверждения
    data = await state.get_data()
    summary = build_resume_text(data, lang)
    with suppress(TelegramAPIError):
        stub = await message.answer("📋", reply_markup=kb.remove_keyboard())
    with suppress(TelegramAPIError):
        await stub.delete()
    await message.answer(summary, reply_markup=kb.get_confirmation_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_confirmation)


# ─── Подтверждение (Inline) ───────────────────────────────────────────────────

@router.callback_query(Form.waiting_confirmation, F.data.startswith("confirm:"))
async def process_confirmation_callback(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
    session: AsyncSession,
    bot: Bot,
) -> None:
    # Отвечаем на callback сразу — до любых await, чтобы не истёк таймаут
    with suppress(TelegramAPIError):
        await callback.answer()

    choice = callback.data.split(":")[1]

    if choice == "no":
        with suppress(TelegramAPIError):
            await callback.message.edit_reply_markup(reply_markup=None)
        await state.clear()
        await state.update_data(lang=lang)
        await start_anketa(callback.message, state, lang, session)
        return

    with suppress(TelegramAPIError):
        await callback.message.edit_reply_markup(reply_markup=None)

    data = await state.get_data()
    user = callback.from_user

    is_admin = user.id in ADMIN_IDS
    if not is_admin:
        async with submission_lock(user.id):
            status = await db.get_application_status(session, user.id)
            if status in BLOCKING_STATUSES:
                key = f"anketa_block_{status}"
                block_text = LOCALIZATION[lang].get(key) or LOCALIZATION[lang]["anketa_block_pending"]
                await callback.message.answer(block_text, parse_mode="HTML")
                return
            await _do_save_and_start_interview(callback.message, state, session, lang, data, user, bot)
    else:
        await _do_save_and_start_interview(callback.message, state, session, lang, data, user, bot)


async def _do_save_and_start_interview(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    lang: str,
    data: dict,
    user,
    bot: Bot,
) -> None:
    """Сохраняет анкету, отправляет HR и запускает AI-интервью с кандидатом."""
    app_id = await db.save_application(
        session,
        user_id=user.id,
        name=data.get("name", ""),
        birthday=data.get("birthday", ""),
        phone=data.get("phone", ""),
        position=data.get("position", ""),
        gender=data.get("gender"),
        branch=data.get("branch"),
        metro_station_id=data.get("metro_station_id"),
        languages=data.get("languages"),
        readiness=data.get("readiness"),
        experience=data.get("experience"),
        exp_company=data.get("exp_company"),
        exp_position=data.get("exp_position"),
        exp_duration=data.get("exp_duration"),
        exp_duties=data.get("exp_duties"),
        salary=data.get("salary"),
        schedule=data.get("schedule"),
        evening_shifts=data.get("evening_shifts"),
        weekends=data.get("weekends"),
        smoking=data.get("smoking"),
        med_book=data.get("med_book"),
        photo_file_id=data.get("photo_file_id"),
        video_file_id=data.get("video_file_id"),
        is_video_note=data.get("is_video_note", False),
        video_duration=data.get("video_duration", 0),
        username=user.username,
        telegram_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Уведомляем HR о новой анкете
    if ADMIN_CHAT_ID:
        resume_text = build_hr_resume_text(data, lang, user)
        try:
            if data.get("photo_file_id"):
                await bot.send_photo(
                    ADMIN_CHAT_ID,
                    photo=data["photo_file_id"],
                    caption=resume_text,
                    reply_markup=kb.get_hr_action_keyboard(
                        phone=data.get("phone", ""),
                        username=user.username or "",
                        candidate_id=user.id,
                    ),
                    parse_mode="HTML",
                )
            else:
                await bot.send_message(
                    ADMIN_CHAT_ID,
                    text=resume_text,
                    reply_markup=kb.get_hr_action_keyboard(
                        phone=data.get("phone", ""),
                        username=user.username or "",
                        candidate_id=user.id,
                    ),
                    parse_mode="HTML",
                )
        except TelegramAPIError as exc:
            logger.error("_do_save_and_start_interview: failed to notify HR: %s", exc)

    # Фоновые задачи (Google Sheets, AI скрининг)
    try:
        await asyncio.gather(
            append_to_sheet(data, user),
            screen_application(bot, session, app_id, data, user),
            return_exceptions=True,
        )
    except Exception as exc:
        logger.error("_do_save_and_start_interview: post-save tasks failed: %s", exc)

    # Запускаем AI-интервью
    from bot.handlers.user.interview import start_interview  # noqa: PLC0415
    await start_interview(
        message=message,
        state=state,
        session=session,
        form_data=data,
        lang=lang,
    )
