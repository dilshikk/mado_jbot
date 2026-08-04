# handlers/form.py

import asyncio
import logging
import re
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import database as db
import keyboards as kb
from config import ADMIN_CHAT_ID, ADMIN_IDS
from filters.common import IsCancelMessage, IsPrivateChat
from gsheets import append_to_sheet
from messages import LOCALIZATION
from states import Form
from utils.formatters import build_hr_resume_text, build_resume_text

router = Router()
router.message.filter(IsPrivateChat())

logger = logging.getLogger(__name__)

MIN_VIDEO_DURATION = 15
VALID_BRANCH       = "Tashkent City Mall"
EXPERIENCE_OPTIONS_RU = {"Нет опыта", "Менее 1 года", "1–2 года", "3–5 лет", "5+ лет"}
EXPERIENCE_OPTIONS_UZ = {"Tajriba yo'q", "1 yildan kam", "1–2 yil", "3–5 yil", "5+ yil"}


# ── Отмена ────────────────────────────────────────────────────────────────────

@router.message(IsCancelMessage(), Form.waiting_branch)
@router.message(IsCancelMessage(), Form.waiting_position)
@router.message(IsCancelMessage(), Form.waiting_name)
@router.message(IsCancelMessage(), Form.waiting_birthday)
@router.message(IsCancelMessage(), Form.waiting_gender)
@router.message(IsCancelMessage(), Form.waiting_family)
@router.message(IsCancelMessage(), Form.waiting_citizenship)
@router.message(IsCancelMessage(), Form.waiting_address)
@router.message(IsCancelMessage(), Form.waiting_experience)
@router.message(IsCancelMessage(), Form.waiting_phone)
@router.message(IsCancelMessage(), Form.waiting_video)
@router.message(IsCancelMessage(), Form.waiting_confirmation)
async def cancel_form(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await state.update_data(lang=lang)
    await message.answer(
        LOCALIZATION[lang]["anketa_cancelled"],
        reply_markup=kb.get_main_menu(lang),
        parse_mode="HTML",
    )


# ── Точка входа ───────────────────────────────────────────────────────────────

@router.message(F.text.in_(["📝 Заполнить анкету", "📝 Anketani to'ldirish"]))
async def start_anketa(message: Message, state: FSMContext, lang: str) -> None:
    if db.is_user_blocked(message.from_user.id):
        await message.answer(
            LOCALIZATION[lang]["user_blocked_text"], parse_mode="HTML"
        )
        return

    status = db.get_application_status(message.from_user.id)

    if status == "hired":
        await message.answer(
            "🏆 <b>Вы уже являетесь сотрудником MADO!</b>\n\n"
            "Для вопросов обратитесь к вашему HR-менеджеру."
            if lang == "ru" else
            "🏆 <b>Siz allaqachon MADO xodimisiniz!</b>\n\n"
            "Savollar uchun HR menejeringizga murojaat qiling.",
            parse_mode="HTML",
        )
        return

    if status == "accepted":
        await message.answer(
            "✅ <b>Вы уже приглашены на собеседование!</b>\n\n"
            "Ожидайте — HR-менеджер свяжется с вами."
            if lang == "ru" else
            "✅ <b>Siz allaqachon suhbatga taklif etilgansiz!</b>\n\n"
            "Kuting — HR menejer siz bilan bog'lanadi.",
            parse_mode="HTML",
        )
        return

    if status == "pending":
        await message.answer(
            "⏳ <b>Ваша анкета уже на рассмотрении.</b>\n\n"
            "Пожалуйста, ожидайте — HR свяжется с вами в ближайшее время."
            if lang == "ru" else
            "⏳ <b>Arizangiz allaqachon ko'rib chiqilmoqda.</b>\n\n"
            "Iltimos, kuting — HR tez orada siz bilan bog'lanadi.",
            parse_mode="HTML",
        )
        return

    await message.answer(
        LOCALIZATION[lang]["ask_branch"],
        reply_markup=kb.get_branch_keyboard(lang),
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_branch)


# ── Шаг 1: Филиал ─────────────────────────────────────────────────────────────

@router.message(Form.waiting_branch)
async def process_branch(message: Message, state: FSMContext, lang: str) -> None:
    if VALID_BRANCH not in (message.text or ""):
        return
    await state.update_data(branch=message.text)
    await message.answer(
        LOCALIZATION[lang]["ask_position"],
        reply_markup=kb.get_positions_keyboard(lang),
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_position)


# ── Шаг 2: Должность ──────────────────────────────────────────────────────────

@router.message(Form.waiting_position)
async def process_position(message: Message, state: FSMContext, lang: str) -> None:
    position_keys   = ("pos_cook", "pos_waiter", "pos_runner", "pos_barista", "pos_cleaner")
    valid_positions = [LOCALIZATION[lang].get(k) for k in position_keys]

    if not any(
        p and (message.text or "").strip().startswith(p.split()[0])
        for p in valid_positions
    ):
        return

    await state.update_data(position=message.text)
    await message.answer(
        LOCALIZATION[lang]["ask_name"],
        reply_markup=kb.get_cancel_keyboard(lang),
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_name)


# ── Шаг 3: ФИО ────────────────────────────────────────────────────────────────

@router.message(Form.waiting_name)
async def process_name(message: Message, state: FSMContext, lang: str) -> None:
    text = (message.text or "").strip()

    if len(text) < 3 or any(ch.isdigit() for ch in text):
        await message.answer(
            LOCALIZATION[lang].get(
                "bad_name",
                "Введите корректное ФИО." if lang == "ru" else "To'g'ri ism-familiya kiriting.",
            ),
            parse_mode="HTML",
        )
        return

    await state.update_data(name=text)
    await message.answer(
        LOCALIZATION[lang]["ask_birthday"],
        reply_markup=kb.get_cancel_keyboard(lang),
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_birthday)


# ── Шаг 4: Дата рождения ──────────────────────────────────────────────────────

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
        age_error = (
            "Возраст должен быть от <b>18 до 60 лет</b>."
            if lang == "ru" else
            "Yosh <b>18 dan 60 yoshgacha</b> bo'lishi kerak."
        )
        await message.answer(age_error, parse_mode="HTML")
        return

    await state.update_data(birthday=text)
    await message.answer(
        LOCALIZATION[lang]["ask_gender"],
        reply_markup=kb.get_gender_keyboard(lang),
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_gender)


# ── Шаг 5: Пол ────────────────────────────────────────────────────────────────

@router.message(Form.waiting_gender)
async def process_gender(message: Message, state: FSMContext, lang: str) -> None:
    valid = {LOCALIZATION[lang]["gender_male"], LOCALIZATION[lang]["gender_female"]}
    if message.text not in valid:
        return

    await state.update_data(gender=message.text)
    await message.answer(
        LOCALIZATION[lang]["ask_family"],
        reply_markup=kb.get_family_keyboard(lang),
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_family)


# ── Шаг 6: Семейное положение ─────────────────────────────────────────────────

@router.message(Form.waiting_family)
async def process_family(message: Message, state: FSMContext, lang: str) -> None:
    valid = {LOCALIZATION[lang]["family_single"], LOCALIZATION[lang]["family_married"]}
    if message.text not in valid:
        return

    await state.update_data(family=message.text)
    await message.answer(
        LOCALIZATION[lang]["ask_citizenship"],
        reply_markup=kb.get_citizenship_keyboard(lang),
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_citizenship)


# ── Шаг 7: Гражданство ────────────────────────────────────────────────────────

@router.message(Form.waiting_citizenship)
async def process_citizenship(message: Message, state: FSMContext, lang: str) -> None:
    if not (message.text or "").strip():
        return

    await state.update_data(citizenship=message.text)
    await message.answer(
        LOCALIZATION[lang]["ask_address"],
        reply_markup=kb.get_cancel_keyboard(lang),
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_address)


# ── Шаг 8: Адрес ──────────────────────────────────────────────────────────────

@router.message(Form.waiting_address)
async def process_address(message: Message, state: FSMContext, lang: str) -> None:
    if len((message.text or "").strip()) < 4:
        return

    await state.update_data(address=message.text)
    await message.answer(
        "Есть ли у вас опыт работы в ресторанном бизнесе?"
        if lang == "ru" else
        "Restoran biznesida ish tajribangiz bormi?",
        reply_markup=kb.get_experience_keyboard(lang),
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_experience)


# ── Шаг 9: Опыт работы ───────────────────────────────────────────────────────

@router.message(Form.waiting_experience)
async def process_experience(message: Message, state: FSMContext, lang: str) -> None:
    valid = EXPERIENCE_OPTIONS_RU | EXPERIENCE_OPTIONS_UZ
    if (message.text or "").strip() not in valid:
        return

    await state.update_data(experience=message.text)
    await message.answer(
        LOCALIZATION[lang]["ask_phone"],
        reply_markup=kb.get_phone_keyboard(lang),
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_phone)


# ── Шаг 10: Телефон ───────────────────────────────────────────────────────────

@router.message(Form.waiting_phone)
async def process_phone(message: Message, state: FSMContext, lang: str) -> None:
    phone = (
        message.contact.phone_number
        if message.contact
        else (message.text or "").strip()
    )

    if not message.contact and not re.match(r"^\+?\d{7,15}$", phone):
        bad_phone = (
            "Введите корректный номер телефона, например: <code>+998901234567</code>"
            if lang == "ru" else
            "To'g'ri telefon raqamini kiriting, masalan: <code>+998901234567</code>"
        )
        await message.answer(bad_phone, parse_mode="HTML")
        return

    await state.update_data(phone=phone)

    ask_video = (
        "Пожалуйста, запишите и отправьте короткую <b>видео-визитку</b> "
        "(кружок или обычное видео).\n"
        "⚠️ Расскажите немного о себе. <b>Минимум — 15 секунд.</b>"
        if lang == "ru" else
        "Iltimos, qisqa <b>video-vizitka</b> yuboring "
        "(dumaloq yoki oddiy video).\n"
        "⚠️ O'zingiz haqingizda gapirib bering. <b>Minimal — 15 soniya.</b>"
    )
    await message.answer(
        ask_video,
        reply_markup=kb.get_cancel_keyboard(lang),
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_video)


# ── Шаг 11: Видео-визитка ─────────────────────────────────────────────────────

@router.message(Form.waiting_video)
async def process_video(message: Message, state: FSMContext, lang: str) -> None:
    if message.video_note:
        duration = message.video_note.duration
        file_id  = message.video_note.file_id
        is_note  = True
    elif message.video:
        duration = message.video.duration
        file_id  = message.video.file_id
        is_note  = False
    else:
        warning = (
            "Пожалуйста, отправьте именно <b>видео-сообщение</b> или кружок."
            if lang == "ru" else
            "Iltimos, aynan <b>video-xabar</b> yoki dumaloq video yuboring."
        )
        await message.answer(warning, parse_mode="HTML")
        return

    if duration < MIN_VIDEO_DURATION:
        error = (
            f"Видео слишком короткое ({duration} сек). "
            f"Нужно <b>не менее {MIN_VIDEO_DURATION} секунд</b>."
            if lang == "ru" else
            f"Video juda qisqa ({duration} soniya). "
            f"<b>Kamida {MIN_VIDEO_DURATION} soniya</b> bo'lishi kerak."
        )
        await message.answer(error, parse_mode="HTML")
        return

    await state.update_data(video_file_id=file_id, is_video_note=is_note, video_duration=duration)
    data    = await state.get_data()
    summary = build_resume_text(data, lang)

    await message.answer(
        summary,
        reply_markup=kb.get_confirmation_keyboard(lang),
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_confirmation)


# ── Шаг 12: Подтверждение и отправка ─────────────────────────────────────────

@router.message(Form.waiting_confirmation)
async def process_confirmation(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()

    if message.text in {LOCALIZATION["ru"]["confirm_btn_no"], LOCALIZATION["uz"]["confirm_btn_no"]}:
        await state.clear()
        await state.update_data(lang=lang)
        await start_anketa(message, state, lang)
        return

    if message.text not in {
        LOCALIZATION["ru"]["confirm_btn_yes"],
        LOCALIZATION["uz"]["confirm_btn_yes"],
    }:
        return

    now_str      = datetime.now().strftime("%d.%m.%Y %H:%M")
    user         = message.from_user
    username_raw = user.username or LOCALIZATION["ru"]["none_text"]
    bot: Bot     = message.bot

    db.save_application(
        user_id=user.id,
        name=data.get("name"),
        birthday=data.get("birthday"),
        phone=data.get("phone"),
        position=data.get("position"),
        experience=data.get("experience", "—"),
    )

    resume_text = build_hr_resume_text(data, user.id, username_raw)
    hr_keyboard = kb.get_hr_action_keyboard(
        phone=data.get("phone"),
        username=username_raw,
        candidate_id=user.id,
    )
    await bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=resume_text,
        reply_markup=hr_keyboard,
        parse_mode="HTML",
    )

    video_file_id = data.get("video_file_id")
    if video_file_id:
        caption = f"🎥 Видео-визитка: {data.get('name')} (@{username_raw})"
        try:
            if data.get("is_video_note"):
                video_msg = await bot.send_video_note(
                    chat_id=ADMIN_CHAT_ID,
                    video_note=video_file_id,
                )
            else:
                video_msg = await bot.send_video(
                    chat_id=ADMIN_CHAT_ID,
                    video=video_file_id,
                    caption=caption,
                )
            db.save_hr_video_msg_id(user.id, video_msg.message_id)
        except Exception as e:
            logger.error("Ошибка отправки видео HR: %s", e, exc_info=True)

    # ── Запись в Google Sheets с уведомлением при ошибке ──────────────────────
    row_data = [
        now_str,
        data.get("branch"),      data.get("position"),   data.get("name"),
        data.get("birthday"),    data.get("gender"),      data.get("family"),
        data.get("citizenship"), data.get("address"),     data.get("experience", "—"),
        data.get("phone"),
    ]
    try:
        success = await asyncio.to_thread(append_to_sheet, row_data)
        if not success:
            raise RuntimeError("append_to_sheet вернул False")
    except Exception as e:
        logger.error("Ошибка Google Sheets: %s", e, exc_info=True)
        # Уведомляем всех администраторов о сбое
        error_text = (
            f"⚠️ <b>Google Sheets: ошибка записи!</b>\n\n"
            f"👤 Кандидат: <b>{data.get('name')}</b>\n"
            f"📱 Телефон: <code>{data.get('phone')}</code>\n"
            f"💼 Вакансия: {data.get('position')}\n\n"
            f"<i>Данные сохранены в БД, но не попали в таблицу.\n"
            f"Проверьте credentials.json и доступ к Google Sheets.</i>\n\n"
            f"🔴 Ошибка: <code>{e}</code>"
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=error_text,
                    parse_mode="HTML",
                )
            except Exception as notify_err:
                logger.error(
                    "Не удалось уведомить admin_id=%d: %s", admin_id, notify_err
                )

    await message.answer(
        LOCALIZATION[lang]["anketa_done"],
        reply_markup=kb.get_main_menu(lang),
        parse_mode="HTML",
    )
    await state.clear()
    await state.update_data(lang=lang)
