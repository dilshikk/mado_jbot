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
        await message.answer(LOCALIZATION[lang].get("bad_name", "Введите корректное ФИО."), parse_mode="HTML")
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
    # Шаг выбора метро — полностью через inline-клавиатуру (metro.py)
    from bot.handlers.user.metro import ask_metro  # noqa: PLC0415
    await ask_metro(message, state, lang)


# ВАЖНО: обработчик process_metro (reply-клавиатура) удалён.
# Выбор станции метро полностью обрабатывается в metro.py через callback_query.


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
                f"Видео слишком короткое ({duration} сек). Нужно ≥{MIN_VIDEO_DURATION} сек."
                if lang == "ru" else
                f"Video qisqa ({duration}s). ≥{MIN_VIDEO_DURATION}s kerak.",
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

    # Фоновые задачи: HR-отправка, график, AI-скрининг, старт интервью
    # Передаём message и state чтобы start_interview мог установить новый FSM-стейт.
    asyncio.create_task(
        _post_confirm_tasks(message.bot, session, user, data, lang, app_id, message, state)
    )


async def _do_save_application(session: AsyncSession, user, data: dict) -> int:
    """Сохраняет анкету в БД. Вызывается внутри submission_lock или для админа."""
    # metro_station_id сохраняется напрямую из inline-выбора в metro.py
    metro_station_id: int | None = data.get("metro_station_id")

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
    message: Message,
    state: FSMContext,
) -> None:
    """Фоновые задачи после подтверждения: HR-отправка, график, AI-скрининг, старт интервью."""
    # ── 1. HR-отправка новой анкеты ──
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

    # ── 2. Google Sheets ──
    try:
        await append_to_sheet(data, user.id, user.username)
    except Exception as e:
        logger.warning("Ошибка Google Sheets: %s", e)

    # ── 3. AI-скрининг (резюме + проверка честности) ──
    try:
        await screen_application(bot, session, user.id, data)
    except Exception as e:
        logger.error("Ошибка AI-скрининга: %s", e, exc_info=True)

    # ── 4. AI-интервью ──
    # Импорт здесь а не на верху файла, чтобы избежать циклических зависимостей.
    from bot.handlers.user.interview import start_interview  # noqa: PLC0415
    try:
        await start_interview(
            message=message,
            state=state,
            session=session,
            form_data=data,
            lang=lang,
        )
    except Exception as e:
        logger.error(
            "Сбой start_interview user_id=%d: %s",
            user.id, e, exc_info=True,
        )
        # ── fallback: сообщаем пользователю, что HR свяжется напрямую ──
        fallback_text = (
            "✅ Анкета принята! \n\n"
            "Наш HR-менеджер рассмотрит её и свяжется с вами в ближайшее время."
            if lang == "ru" else
            "✅ Ariza qabul qilindi! \n\n"
            "HR menejerimiz uni ko'rib chiqadi va tez orada siz bilan bog'lanadi."
        )
        try:
            await bot.send_message(chat_id=user.id, text=fallback_text, parse_mode="HTML")
        except Exception as notify_err:
            logger.error("Ошибка отправки fallback-сообщения: %s", notify_err)

        # ── уведомляем HR чтобы связались с кандидатом сами ──
        hr_name = data.get("name") or f"user#{user.id}"
        hr_phone = data.get("phone") or "—"
        try:
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    f"⚠️ AI-интервью не запустилось — AI недоступен.\n"
                    f"👤 {hr_name} | user_id: {user.id} | 📱 {hr_phone}\n\n"
                    f"Свяжитесь с кандидатом напрямую."
                ),
                parse_mode="HTML",
            )
        except Exception as hr_err:
            logger.error("Ошибка HR-уведомления о сбое интервью: %s", hr_err)
