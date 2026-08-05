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
# interview_in_progress — AI-интервью началось, кандидат ещё отвечает на вопросы.
# screened     — AI завершил оценку, отчёт в HR-чате, ждёт решения человека.
# interview_failed не блокирует — кандидат может подать новую анкету.
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

@router.message(StateFilter(*_FORM_ACTIVE_STATES), IsCancelMessage())
@router.message(StateFilter(*_FORM_ACTIVE_STATES), Command("cancel"))
async def cancel_form(message: Message, state: FSMContext, lang: str) -> None:
    """\u041e\u0442\u043c\u0435\u043d\u0430 \u0430\u043d\u043a\u0435\u0442\u044b \u043d\u0430 \u043b\u044e\u0431\u043e\u043c \u0448\u0430\u0433\u0435 \u2014 \u043a\u043d\u043e\u043f\u043a\u043e\u0439 \u0438\u043b\u0438 \u043a\u043e\u043c\u0430\u043d\u0434\u043e\u0439 /cancel."""
    await state.clear()
    await state.update_data(lang=lang)
    await message.answer(LOCALIZATION[lang]["anketa_cancelled"], reply_markup=kb.get_main_menu(lang), parse_mode="HTML")

@router.message(F.text.in_(["\ud83d\udcdd \u0417\u0430\u043f\u043e\u043b\u043d\u0438\u0442\u044c \u0430\u043d\u043a\u0435\u0442\u0443", "\ud83d\udcdd Anketani to'ldirish"]))
async def start_anketa(message: Message, state: FSMContext, lang: str, session: AsyncSession) -> None:
    if await db.is_user_blocked(session, message.from_user.id):
        await message.answer(LOCALIZATION[lang]["user_blocked_text"], parse_mode="HTML")
        return

    vacancies = await db.get_active_vacancies(session)
    if not vacancies:
        await message.answer(
            "\u23f3 \u0412 \u0434\u0430\u043d\u043d\u044b\u0439 \u043c\u043e\u043c\u0435\u043d\u0442 \u043e\u0442\u043a\u0440\u044b\u0442\u044b\u0445 \u0432\u0430\u043a\u0430\u043d\u0441\u0438\u0439 \u043d\u0435\u0442. \n\n\u0421\u043b\u0435\u0434\u0438\u0442\u0435 \u0437\u0430 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f\u043c!"
            if lang == "ru" else
            "\u23f3 Hozirda ochiq vakansiyalar yo'q. \n\nYangilanishlarni kuzatib boring!",
            parse_mode="HTML",
        )
        return

    # Защита от дублей: активная заявка любого типа блокирует новую подачу
    # Для администраторов проверка пропускается — они могут тестировать анкету
    is_admin = message.from_user.id in ADMIN_IDS
    if not is_admin:
        status = await db.get_application_status(session, message.from_user.id)
        if status in BLOCKING_STATUSES:
            key = f"anketa_block_{status}"
            text = LOCALIZATION[lang].get(key) or LOCALIZATION[lang]["anketa_block_pending"]
            await message.answer(text, parse_mode="HTML")
            return

    # ── Раздел «Личные данные»: ФИО первым шагом ──
    await state.update_data(branch=VALID_BRANCH)
    await message.answer(LOCALIZATION[lang]["ask_name"], reply_markup=kb.get_cancel_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_name)

@router.message(Form.waiting_name)
async def process_name(message: Message, state: FSMContext, lang: str) -> None:
    text = (message.text or "").strip()
    if len(text) < 3 or any(ch.isdigit() for ch in text):
        await message.answer(LOCALIZATION[lang].get("bad_name", "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u043e\u0435 \u0424\u0418\u041e."), parse_mode="HTML")
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
            "\u0412\u043e\u0437\u0440\u0430\u0441\u0442 \u0434\u043e\u043b\u0436\u0435\u043d \u0431\u044b\u0442\u044c \u043e\u0442 18 \u0434\u043e 60 \u043b\u0435\u0442." if lang == "ru" else "Yosh 18 dan 60 yoshgacha bo'lishi kerak.",
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
            "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 \u043d\u043e\u043c\u0435\u0440: +998901234567 " if lang == "ru" else "To'g'ri raqam kiriting: +998901234567 ",
            parse_mode="HTML",
        )
        return
    await state.update_data(phone=phone)
    await message.answer(LOCALIZATION[lang]["ask_metro"], reply_markup=kb.get_metro_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_metro)

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
        await message.answer(LOCALIZATION[lang]["ask_metro"], reply_markup=kb.get_metro_keyboard(lang), parse_mode="HTML")
        return
    await state.update_data(metro=None if text == skip_value else text)
    await message.answer(LOCALIZATION[lang]["ask_languages"], reply_markup=kb.get_languages_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_languages)

# ── Раздел «Информация о работе»: должность → готовность → опыт → ... ──

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
                f"\u0412\u0438\u0434\u0435\u043e \u0441\u043b\u0438\u0448\u043a\u043e\u043c \u043a\u043e\u0440\u043e\u0442\u043a\u043e\u0435 ({duration} \u0441\u0435\u043a). \u041d\u0443\u0436\u043d\u043e \u2265{MIN_VIDEO_DURATION} \u0441\u0435\u043a."
                if lang == "ru" else
                f"Video qisqa ({duration}s). \u2265{MIN_VIDEO_DURATION}s kerak.",
                parse_mode="HTML",
            )
            return
        await state.update_data(video_file_id=file_id, is_video_note=is_note, video_duration=duration)
    # ── Итоговая сводка анкеты → подтверждение ──
    data = await state.get_data()
    summary = build_resume_text(data, lang)
    await message.answer(summary, reply_markup=kb.get_confirmation_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_confirmation)

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

    # ── АТОМАРНОСТЬ: проверка статуса + INSERT защищены одним локом
    # Гарантирует, что параллельный двойной тап / Telegram-ретрай не создадут
    # две анкеты pending для одного user_id.
    is_admin = user.id in ADMIN_IDS
    if not is_admin:
        async with submission_lock(user.id):
            status = await db.get_application_status(session, user.id)
            if status in BLOCKING_STATUSES:
                key = f"anketa_block_{status}"
                block_text = LOCALIZATION[lang].get(key) or LOCALIZATION[lang]["anketa_block_pending"]
                await message.answer(block_text, parse_mode="HTML")
                await state.clear()
                return

            app_id = await _do_save_application(session, user, data)
    else:
        app_id = await _do_save_application(session, user, data)

    logger.info("Анкета сохранена: app_id=%d user_id=%d", app_id, user.id)

    await state.clear()
    await state.update_data(lang=lang)

    confirm_text = LOCALIZATION[lang]["anketa_confirmed"]
    await message.answer(confirm_text, reply_markup=kb.get_main_menu(lang), parse_mode="HTML")

    # Дальнейшие шаги вынесены в фон (не блокируют подтверждение пользователя)
    asyncio.create_task(_post_confirm_tasks(message.bot, session, user, data, lang, app_id))


async def _do_save_application(session: AsyncSession, user, data: dict) -> int:
    """\u0421\u043e\u0445\u0440\u0430\u043d\u044f\u0435\u0442 \u0430\u043d\u043a\u0435\u0442\u0443 \u0432 \u0411\u0414. \u0412\u044b\u0437\u044b\u0432\u0430\u0435\u0442\u0441\u044f \u0432\u043d\u0443\u0442\u0440\u0438 submission_lock \u0438\u043b\u0438 \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0430."""
    metro_station_id: int | None = None
    metro_name = data.get("metro")
    if metro_name:
        for line in ("red", "blue", "circle"):
            stations = await db.get_metro_stations_by_line(session, line)
            for s in stations:
                if metro_name in (s.get("name_ru"), s.get("name_uz")):
                    metro_station_id = s["id"]
                    break
            if metro_station_id:
                break

    return await db.save_application(
        session,
        user_id=user.id,
        name=data.get("name", ""),
        birthday=data.get("birthday", ""),
        phone=data.get("phone", ""),
        position=data.get("position", ""),
        experience=data.get("experience") or "—",
        metro_station_id=metro_station_id,
    )


async def _post_confirm_tasks(
    bot: Bot,
    session: AsyncSession,
    user,
    data: dict,
    lang: str,
    app_id: int,
) -> None:
    """\u0424\u043e\u043d\u043e\u0432\u044b\u0435 \u0437\u0430\u0434\u0430\u0447\u0438 \u043f\u043e\u0441\u043b\u0435 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f \u0430\u043d\u043a\u0435\u0442\u044b: HR-\u043e\u0442\u043f\u0440\u0430\u0432\u043a\u0430, \u0433\u0440\u0430\u0444\u0438\u043a, AI-\u0441\u043a\u0440\u0438\u043d\u0438\u043d\u0433."""
    try:
        username_raw = user.username or LOCALIZATION["ru"]["none_text"]
        resume_text = build_hr_resume_text(data, user.id, username_raw)
        hr_keyboard = kb.get_hr_action_keyboard(
            phone=data.get("phone", ""),
            username=username_raw,
            candidate_id=user.id,
        )
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=resume_text,
            reply_markup=hr_keyboard,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("Ошибка HR-отправки: %s", e, exc_info=True)

    try:
        await append_to_sheet(data, user.id, user.username)
    except Exception as e:
        logger.warning("Ошибка Google Sheets: %s", e)

    try:
        await screen_application(bot, session, user.id, data)
    except Exception as e:
        logger.error("Ошибка AI-скрининга: %s", e, exc_info=True)

    try:
        from bot.handlers.user.interview import start_interview  # noqa: PLC0415
        await bot.send_message(
            chat_id=user.id,
            text=(
                "🤖 <b>Recruiter AI готов провести краткое интервью.</b>\n\n"
                "Я задам несколько вопросов, чтобы HR мог лучше вас узнать."
                if lang == "ru" else
                "🤖 <b>Recruiter AI qisqacha intervyu o'tkazmoqchi.</b>\n\n"
                "HR sizni yaxshiroq tanishi uchun bir necha savol beraman."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("Ошибка отправки intro-сообщения: %s", e, exc_info=True)
