# bot/handlers/user/form.py

import asyncio
import logging
import re
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.db import database as db
from bot import keyboards as kb
from config import ADMIN_CHAT_ID, ADMIN_IDS
from bot.filters.common import IsCancelMessage, IsPrivateChat
from bot.services.gsheets import append_to_sheet
from bot.messages import LOCALIZATION
from bot.states import Form
from bot.utils.formatters import build_hr_resume_text, build_resume_text

router = Router()
router.message.filter(IsPrivateChat())

logger = logging.getLogger(__name__)

MIN_VIDEO_DURATION    = 15
VALID_BRANCH          = "Tashkent City Mall"
EXPERIENCE_OPTIONS_RU = {"Нет опыта", "Менее 1 года", "1–2 года", "3–5 лет", "5+ лет"}
EXPERIENCE_OPTIONS_UZ = {"Tajriba yo'q", "1 yildan kam", "1–2 yil", "3–5 yil", "5+ yil"}


def _get_valid_position_labels() -> set[str]:
    vacancies = db.get_active_vacancies()
    labels: set[str] = set()
    for v in vacancies:
        for key in ("name_ru", "name_uz"):
            name  = v.get(key, "").strip()
            emoji = v.get("emoji", "").strip()
            if name:
                labels.add(f"{emoji} {name}".strip())
                labels.add(name)
    return labels


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
    await message.answer(LOCALIZATION[lang]["anketa_cancelled"], reply_markup=kb.get_main_menu(lang), parse_mode="HTML")


@router.message(F.text.in_(["📝 Заполнить анкету", "📝 Anketani to'ldirish"]))
async def start_anketa(message: Message, state: FSMContext, lang: str) -> None:
    if db.is_user_blocked(message.from_user.id):
        await message.answer(LOCALIZATION[lang]["user_blocked_text"], parse_mode="HTML")
        return
    if not db.get_active_vacancies():
        await message.answer(
            "⏳ <b>В данный момент открытых вакансий нет.</b>\n\nСледите за обновлениями!"
            if lang == "ru" else
            "⏳ <b>Hozirda ochiq vakansiyalar yo'q.</b>\n\nYangilanishlarni kuzatib boring!",
            parse_mode="HTML",
        )
        return
    status = db.get_application_status(message.from_user.id)
    if status == "hired":
        await message.answer("🏆 <b>Вы уже являетесь сотрудником MADO!</b>" if lang == "ru" else "🏆 <b>Siz allaqachon MADO xodimisiniz!</b>", parse_mode="HTML")
        return
    if status == "accepted":
        await message.answer("✅ <b>Вы уже приглашены на собеседование!</b>" if lang == "ru" else "✅ <b>Siz allaqachon suhbatga taklif etilgansiz!</b>", parse_mode="HTML")
        return
    if status == "pending":
        await message.answer("⏳ <b>Ваша анкета уже на рассмотрении.</b>" if lang == "ru" else "⏳ <b>Arizangiz allaqachon ko'rib chiqilmoqda.</b>", parse_mode="HTML")
        return
    await message.answer(LOCALIZATION[lang]["ask_branch"], reply_markup=kb.get_branch_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_branch)


@router.message(Form.waiting_branch)
async def process_branch(message: Message, state: FSMContext, lang: str) -> None:
    if VALID_BRANCH not in (message.text or ""):
        return
    await state.update_data(branch=message.text)
    await message.answer(LOCALIZATION[lang]["ask_position"], reply_markup=kb.get_positions_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_position)


@router.message(Form.waiting_position)
async def process_position(message: Message, state: FSMContext, lang: str) -> None:
    valid  = _get_valid_position_labels()
    chosen = (message.text or "").strip()
    if chosen not in valid:
        await message.answer(LOCALIZATION[lang]["ask_position"], reply_markup=kb.get_positions_keyboard(lang), parse_mode="HTML")
        return
    await state.update_data(position=chosen)
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
        await message.answer("Возраст должен быть от <b>18 до 60 лет</b>." if lang == "ru" else "Yosh <b>18 dan 60 yoshgacha</b> bo'lishi kerak.", parse_mode="HTML")
        return
    await state.update_data(birthday=text)
    await message.answer(LOCALIZATION[lang]["ask_gender"], reply_markup=kb.get_gender_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_gender)


@router.message(Form.waiting_gender)
async def process_gender(message: Message, state: FSMContext, lang: str) -> None:
    if message.text not in {LOCALIZATION[lang]["gender_male"], LOCALIZATION[lang]["gender_female"]}:
        return
    await state.update_data(gender=message.text)
    await message.answer(LOCALIZATION[lang]["ask_family"], reply_markup=kb.get_family_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_family)


@router.message(Form.waiting_family)
async def process_family(message: Message, state: FSMContext, lang: str) -> None:
    if message.text not in {LOCALIZATION[lang]["family_single"], LOCALIZATION[lang]["family_married"]}:
        return
    await state.update_data(family=message.text)
    await message.answer(LOCALIZATION[lang]["ask_citizenship"], reply_markup=kb.get_citizenship_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_citizenship)


@router.message(Form.waiting_citizenship)
async def process_citizenship(message: Message, state: FSMContext, lang: str) -> None:
    if not (message.text or "").strip():
        return
    await state.update_data(citizenship=message.text)
    await message.answer(LOCALIZATION[lang]["ask_address"], reply_markup=kb.get_cancel_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_address)


@router.message(Form.waiting_address)
async def process_address(message: Message, state: FSMContext, lang: str) -> None:
    if len((message.text or "").strip()) < 4:
        return
    await state.update_data(address=message.text)
    await message.answer(
        "Есть ли у вас опыт работы в ресторанном бизнесе?" if lang == "ru" else "Restoran biznesida ish tajribangiz bormi?",
        reply_markup=kb.get_experience_keyboard(lang), parse_mode="HTML",
    )
    await state.set_state(Form.waiting_experience)


@router.message(Form.waiting_experience)
async def process_experience(message: Message, state: FSMContext, lang: str) -> None:
    if (message.text or "").strip() not in (EXPERIENCE_OPTIONS_RU | EXPERIENCE_OPTIONS_UZ):
        return
    await state.update_data(experience=message.text)
    await message.answer(LOCALIZATION[lang]["ask_phone"], reply_markup=kb.get_phone_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_phone)


@router.message(Form.waiting_phone)
async def process_phone(message: Message, state: FSMContext, lang: str) -> None:
    phone = message.contact.phone_number if message.contact else (message.text or "").strip()
    if not message.contact and not re.match(r"^\+?\d{7,15}$", phone):
        await message.answer("Введите корректный номер: <code>+998901234567</code>" if lang == "ru" else "To'g'ri raqam kiriting: <code>+998901234567</code>", parse_mode="HTML")
        return
    await state.update_data(phone=phone)
    ask_video = (
        "Отправьте <b>видео-визитку</b> (кружок или видео).\n⚠️ Минимум — <b>15 секунд</b>."
        if lang == "ru" else
        "<b>Video-vizitka</b> yuboring (dumaloq yoki video).\n⚠️ Minimal — <b>15 soniya</b>."
    )
    await message.answer(ask_video, reply_markup=kb.get_cancel_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_video)


@router.message(Form.waiting_video)
async def process_video(message: Message, state: FSMContext, lang: str) -> None:
    if message.video_note:
        duration, file_id, is_note = message.video_note.duration, message.video_note.file_id, True
    elif message.video:
        duration, file_id, is_note = message.video.duration, message.video.file_id, False
    else:
        await message.answer("Отправьте <b>видео-сообщение</b> или кружок." if lang == "ru" else "<b>Video-xabar</b> yoki dumaloq video yuboring.", parse_mode="HTML")
        return
    if duration < MIN_VIDEO_DURATION:
        await message.answer(f"Видео слишком короткое ({duration} сек). Нужно <b>≥{MIN_VIDEO_DURATION} сек</b>." if lang == "ru" else f"Video qisqa ({duration}s). <b>≥{MIN_VIDEO_DURATION}s</b> kerak.", parse_mode="HTML")
        return
    await state.update_data(video_file_id=file_id, is_video_note=is_note, video_duration=duration)
    data    = await state.get_data()
    summary = build_resume_text(data, lang)
    await message.answer(summary, reply_markup=kb.get_confirmation_keyboard(lang), parse_mode="HTML")
    await state.set_state(Form.waiting_confirmation)


@router.message(Form.waiting_confirmation)
async def process_confirmation(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    if message.text in {LOCALIZATION["ru"]["confirm_btn_no"], LOCALIZATION["uz"]["confirm_btn_no"]}:
        await state.clear()
        await state.update_data(lang=lang)
        await start_anketa(message, state, lang)
        return
    if message.text not in {LOCALIZATION["ru"]["confirm_btn_yes"], LOCALIZATION["uz"]["confirm_btn_yes"]}:
        return
    now_str      = datetime.now().strftime("%d.%m.%Y %H:%M")
    user         = message.from_user
    username_raw = user.username or LOCALIZATION["ru"]["none_text"]
    bot: Bot     = message.bot
    db.save_application(user_id=user.id, name=data.get("name"), birthday=data.get("birthday"), phone=data.get("phone"), position=data.get("position"), experience=data.get("experience", "—"))
    resume_text = build_hr_resume_text(data, user.id, username_raw)
    hr_keyboard = kb.get_hr_action_keyboard(phone=data.get("phone"), username=username_raw, candidate_id=user.id)
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text=resume_text, reply_markup=hr_keyboard, parse_mode="HTML")
    video_file_id = data.get("video_file_id")
    if video_file_id:
        try:
            if data.get("is_video_note"):
                video_msg = await bot.send_video_note(chat_id=ADMIN_CHAT_ID, video_note=video_file_id)
            else:
                video_msg = await bot.send_video(chat_id=ADMIN_CHAT_ID, video=video_file_id, caption=f"🎥 {data.get('name')} (@{username_raw})")
            db.save_hr_video_msg_id(user.id, video_msg.message_id)
        except Exception as e:
            logger.error("Ошибка отправки видео HR: %s", e, exc_info=True)
    row_data = [now_str, data.get("branch"), data.get("position"), data.get("name"), data.get("birthday"), data.get("gender"), data.get("family"), data.get("citizenship"), data.get("address"), data.get("experience", "—"), data.get("phone")]
    try:
        success = await asyncio.to_thread(append_to_sheet, row_data)
        if not success:
            raise RuntimeError("append_to_sheet вернул False")
    except Exception as e:
        logger.error("Ошибка Google Sheets: %s", e, exc_info=True)
        error_text = (
            f"⚠️ <b>Google Sheets: ошибка записи!</b>\n\n"
            f"👤 Кандидат: <b>{data.get('name')}</b>\n📱 <code>{data.get('phone')}</code>\n💼 {data.get('position')}\n\n"
            f"<i>Данные в БД сохранены.</i>\n🔴 Ошибка: <code>{e}</code>"
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(chat_id=admin_id, text=error_text, parse_mode="HTML")
            except Exception as notify_err:
                logger.error("Не удалось уведомить admin_id=%d: %s", admin_id, notify_err)
    await message.answer(LOCALIZATION[lang]["anketa_done"], reply_markup=kb.get_main_menu(lang), parse_mode="HTML")
    await state.clear()
    await state.update_data(lang=lang)
