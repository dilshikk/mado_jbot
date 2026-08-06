# bot/handlers/user/form.py

import asyncio
import logging
import re
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
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

logger = logging.getLogger(__name__)

MIN_VIDEO_DURATION = 15
VALID_BRANCH = "Tashkent City Mall"

# Статусы, при которых повторная подача анкеты запрещена (защита от дублей).
BLOCKING_STATUSES = {"pending", "interview_in_progress", "screened", "accepted", "hired", "hold"}

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
            name = (v.get(key) or "").strip()
            emoji = (v.get("emoji") or "").strip()
            if name:
                labels.add(f"{emoji} {name}".strip())
                labels.add(name)
    return labels


def _is_valid_full_name(text: str) -> bool:
    """Проверяет ФИО: минимум два слова, без цифр и служебных символов.

    Отсекает случаи, когда кандидат копирует текст подсказки
    (например «ФИО полностью:») вместо своего имени.
    """
    if len(text) < 5 or len(text) > 100:
        return False
    if any(ch.isdigit() for ch in text):
        return False
    if any(ch in text for ch in ":;/\\_@#*<>"):
        return False
    words = [w for w in re.split(r"[\s\-]+", text) if w]
    if len(words) < 2:
        return False
    # Каждое слово — минимум 2 буквы
    return all(len(w) >= 2 and all(ch.isalpha() or ch in "'’." for ch in w) for w in words)


@router.message(StateFilter(*_FORM_ACTIVE_STATES), IsCancelMessage())
@router.message(StateFilter(*_FORM_ACTIVE_STATES), Command("cancel"))
async def cancel_form(message: Message, state: FSMContext, lang: str) -> None:
    """Отмена анкеты на любом шаге — кнопкой или командой /cancel."""
    await state.clear()
    await state.update_data(lang=lang)
    await message.answer(LOCALIZATION[lang]["anketa_cancelled"], reply_markup=kb.get_main_menu(lang), parse_mode="HTML")


@router.message(F.text.in_(["📝 Заполнить анкету", "📝 Anketani to'ldirish"]))
async def start_anketa(message: Message, state: FSMContext, lang: str, session: AsyncSession) -> None:
    if await db.is_user_blocked(session, message.from_user.id):
        await message.answer(LOCALIZATION[lang]["user_blocked_text"], parse_mode="HTML")
        return

    vacancies = await db.get_active_vacancies(session)
    if not vacancies:
        await message.answer(
            "⏳ В данный момент открытых вакансий нет. \n\nСледите за обновлениям!"
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


@router.message(Form.waiting_name)
async def process_name(message: Message, state: FSMContext, lang: str) -> None:
    text = (message.text or "").strip()
    if not _is_valid_full_name(text):
        hint = (
            "❌ Введите ваше настоящее ФИО полностью, например: <b>Иванов Иван Иванович</b>"
            if lang == "ru" else
            "❌ To'liq ism-familiyangizni kiriting, masalan: <b>Aliyev Ali Alievich</b>"
        )
        await message.answer(LOCALIZATION[lang].get("bad_name") or hint, parse_mode="HTML")
        return
    await state.update_data(name=text)
    await message.answer(LOCALIZATION[lang]["ask_birthday"], reply_markup=kb.get_cancel_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_birthday)


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
    await message.answer(LOCALIZATION[lang]["ask_gender"], reply_markup=kb.get_gender_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_gender)


@router.message(Form.waiting_gender)
async def process_gender(message: Message, state: FSMContext, lang: str) -> None:
    if message.text not in {LOCALIZATION[lang]["gender_male"], LOCALIZATION[lang]["gender_female"]}:
        await message.answer(LOCALIZATION[lang]["ask_gender"], reply_markup=kb.get_gender_keyboard(lang), parse_mode="HTML")
        return
    await state.update_data(gender=message.text)
    await message.answer(LOCALIZATION[lang]["ask_phone"], reply_markup=kb.get_phone_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_phone)


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
    from bot.handlers.user.metro import ask_metro  # noqa: PLC0415
    await ask_metro(message, state, lang)


@router.message(Form.waiting_position)
async def process_position(message: Message, state: FSMContext, lang: str, session: AsyncSession) -> None:
    vacancies = await db.get_active_vacancies(session)
    valid = _valid_position_labels(vacancies)
    chosen = (message.text or "").strip()
    if chosen not in valid:
        await message.answer(
            LOCALIZATION[lang]["ask_position"],
            reply_markup=kb.get_positions_keyboard(lang, vacancies),
            parse_mode="HTML",
        )
        return
    await state.update_data(position=chosen)
    await message.answer(LOCALIZATION[lang]["ask_readiness"], reply_markup=kb.get_readiness_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_readiness)


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
    data = await state.get_data()
    summary = build_resume_text(data, lang)
    await message.answer(summary, reply_markup=kb.get_confirmation_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_confirmation)


@router.message(Form.waiting_confirmation)
async def process_confirmation(
    message: Message,
    state: FSMContext,
    lang: str,
    session: AsyncSession,
) -> None:
    data = await state.get_data()

    if message.text in {LOCALIZATION["ru"]["confirm_btn_no"], LOCALIZATION["uz"]["confirm_btn_no"]}:
        await state.clear()
        await state.update_data(lang=lang)
        await start_anketa(message, state, lang, session)
        return

    if message.text not in {LOCALIZATION["ru"]["confirm_btn_yes"], LOCALIZATION["uz"]["confirm_btn_yes"]}:
        return

    user = message.from_user

    is_admin = user.id in ADMIN_IDS
    if not is_admin:
        async with submission_lock(user.id):
            status = await db.get_application_status(session, user.id)
            if status in BLOCKING_STATUSES:
                key = f"anketa_block_{status}"
                block_text = LOCALIZATION[lang].get(key) or LOCALIZATION[lang]["anketa_block_pending"]
                await message.answer(block_text, parse_mode="HTML")
                return
            await _do_save_application(message, state, session, lang, data, user)
    else:
        await _do_save_application(message, state, session, lang, data, user)


async def _do_save_application(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    lang: str,
    data: dict,
    user,
) -> None:
    """Сохраняет анкету в БД, отправляет HR, затем запускает AI-интервью."""
    bot: Bot = message.bot

    # Реальная сигнатура: save_application(session, user_id, name, birthday, phone, position, experience)
    application_id = await db.save_application(
        session,
        user_id=user.id,
        name=data.get("name", ""),
        birthday=data.get("birthday", ""),
        phone=data.get("phone", ""),
        position=data.get("position", ""),
        experience=data.get("experience", "—"),
    )

    confirm_text = LOCALIZATION[lang]["anketa_confirmed"]
    await state.clear()
    await state.update_data(lang=lang)
    # Убираем reply-клавиатуру: во время интервью используются inline-кнопки,
    # иначе нажатие кнопки меню будет воспринято как ответ на вопрос AI.
    await message.answer(confirm_text, reply_markup=kb.remove_keyboard(), parse_mode="HTML")

    # HR-сообщение, Google Sheets и предварительный AI-скрининг — в фоне,
    # чтобы кандидат не ждал перед первым вопросом интервью.
    asyncio.create_task(_post_confirm_tasks(bot, session, user, data, application_id, lang))

    # ── Запуск AI-интервью ──
    from bot.handlers.user.interview import start_interview  # noqa: PLC0415
    try:
        await start_interview(message, state, session, data, lang)
    except Exception as e:
        logger.error("Не удалось запустить AI-интервью: %s", e, exc_info=True)
        await state.clear()
        await state.update_data(lang=lang)
        fallback = (
            "Ваша анкета принята. HR-менеджер свяжется с вами в ближайшее время."
            if lang == "ru" else
            "Anketangiz qabul qilindi. HR-menejer tez orada siz bilan bog'lanadi."
        )
        await message.answer(fallback, reply_markup=kb.get_main_menu(lang), parse_mode="HTML")


async def _post_confirm_tasks(
    bot: Bot,
    session: AsyncSession,
    user,
    data: dict,
    application_id: int,
    lang: str,
) -> None:
    """Фоновые задачи после подтверждения анкеты: HR-сообщение, таблица, AI-скрининг."""

    # ── 1. Отправка резюме в HR-чат ──
    # Реальная сигнатура: build_hr_resume_text(data, user_id, username)
    try:
        username_str = user.username or ""
        resume_text = build_hr_resume_text(data, user.id, username_str)
        await bot.send_message(ADMIN_CHAT_ID, resume_text, parse_mode="HTML")
        if data.get("photo_file_id"):
            await bot.send_photo(ADMIN_CHAT_ID, data["photo_file_id"])
        if data.get("video_file_id"):
            send_fn = bot.send_video_note if data.get("is_video_note") else bot.send_video
            await send_fn(ADMIN_CHAT_ID, data["video_file_id"])
    except Exception as e:
        logger.error("Ошибка отправки резюме в HR-чат: %s", e, exc_info=True)

    # ── 2. Google Sheets ──
    # Реальная сигнатура: append_to_sheet(data: list)
    try:
        sheet_row = [
            data.get("name", ""),
            data.get("birthday", ""),
            data.get("gender", ""),
            data.get("phone", ""),
            data.get("position", ""),
            data.get("experience", ""),
            data.get("address", ""),
            user.username or "",
            str(user.id),
        ]
        append_to_sheet(sheet_row)
    except Exception as e:
        logger.error("Ошибка записи в Google Sheets: %s", e, exc_info=True)

    # ── 3. AI-скрининг ──
    try:
        await screen_application(data)
    except Exception as e:
        logger.error("Ошибка AI-скрининга: %s", e, exc_info=True)
