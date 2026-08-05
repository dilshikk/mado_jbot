# bot/handlers/hr/actions.py

import logging
import re
from contextlib import suppress
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import requests as db
from bot import keyboards as kb
from bot.lexicon import LOCALIZATION
from bot.states import HRReview, HRScore

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data.startswith("hr_accept:"))
async def hr_accept_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    candidate_id = int(callback.data.split(":")[1])
    view_count = await db.increment_view_count(session, candidate_id)
    logger.info("Анкета user_id=%d просмотрена HR, просмотров: %d", candidate_id, view_count)
    await state.update_data(
        reviewing_candidate_id=candidate_id,
        hr_chat_id=callback.message.chat.id,
        hr_msg_id=callback.message.message_id,
        candidate_anketa_text=callback.message.text or "",
    )
    await state.set_state(HRReview.waiting_for_interview_details)
    await callback.message.reply(LOCALIZATION["ru"]["hr_ask_interview"], parse_mode="HTML")
    with suppress(TelegramAPIError):
        await callback.answer()

@router.message(HRReview.waiting_for_interview_details, F.text.in_(["/cancel", "отмена", "Отмена", "bekor qilish"]))
async def cancel_hr_review(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(LOCALIZATION["ru"]["hr_action_cancelled"], parse_mode="HTML")

@router.message(HRReview.waiting_for_interview_details)
async def process_interview_details(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.text:
        return
    bot: Bot = message.bot
    hr_data = await state.get_data()
    candidate_id = hr_data["reviewing_candidate_id"]
    hr_chat_id = hr_data["hr_chat_id"]
    hr_msg_id = hr_data["hr_msg_id"]
    anketa_text = hr_data.get("candidate_anketa_text", "")
    interview_text = message.text

    interview_iso = _parse_interview_datetime(interview_text)

    # Если дата не распознана — предупреждаем HR, не меняем статус кандидата
    if not interview_iso:
        await message.answer(
            "⚠️ <b>Не удалось распознать дату и время.</b>\n\n"
            "Примеры корректного формата:\n"
            "• <code>25.07.2025 в 14:00</code>\n"
            "• <code>25.07.2025 14:00</code>\n"
            "• <code>25.07 в 14:00</code>\n\n"
            "Попробуйте ещё раз или отправьте <code>/cancel</code> для отмены.",
            parse_mode="HTML",
        )
        return

    await db.set_interview_time(session, candidate_id, interview_iso)
    await db.update_application_status(session, candidate_id, "accepted")

    candidate_lang = await db.get_user_lang(session, candidate_id) or "ru"
    notice = LOCALIZATION[candidate_lang]["candidate_accepted_notice"].format(interview_text=interview_text)
    status = LOCALIZATION["ru"]["hr_status_accepted"].format(interview_text=interview_text)

    with suppress(TelegramAPIError):
        await bot.send_message(chat_id=candidate_id, text=notice, parse_mode="HTML")
    with suppress(TelegramAPIError):
        await bot.edit_message_text(
            chat_id=hr_chat_id, message_id=hr_msg_id,
            text=f"{anketa_text}\n\n{status}", parse_mode="HTML",
            reply_markup=kb.get_post_interview_keyboard(candidate_id),
        )
    await message.answer(LOCALIZATION["ru"]["hr_success_sent"], parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data.startswith("hr_hire:"))
async def hr_hire_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    candidate_id = int(callback.data.split(":")[1])
    bot: Bot = callback.bot

    await db.update_application_status(session, candidate_id, "hired")
    candidate_lang = await db.get_user_lang(session, candidate_id) or "ru"
    notice = LOCALIZATION[candidate_lang]["candidate_hired_notice"]
    with suppress(TelegramAPIError):
        await bot.send_message(chat_id=candidate_id, text=notice, parse_mode="HTML")
    with suppress(TelegramAPIError):
        await callback.message.edit_reply_markup(reply_markup=None)
    with suppress(TelegramAPIError):
        await callback.message.answer(
            "🏆 Кандидат принят на работу!\n\nОцените кандидата для статистики:",
            reply_markup=kb.get_score_keyboard(candidate_id),
        )
    with suppress(TelegramAPIError):
        await callback.answer("🏆 Кандидат принят на работу!", show_alert=True)
    logger.info("Кандидат user_id=%d принят на работу", candidate_id)

@router.callback_query(F.data.startswith("hr_reject:"))
async def hr_reject_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    candidate_id = int(callback.data.split(":")[1])
    bot: Bot = callback.bot

    await db.block_user(session, candidate_id, days=30)
    await db.update_application_status(session, candidate_id, "rejected")

    candidate_lang = await db.get_user_lang(session, candidate_id) or "ru"
    notice = LOCALIZATION[candidate_lang]["candidate_rejected_notice"]

    with suppress(TelegramAPIError):
        await bot.send_message(chat_id=candidate_id, text=notice, parse_mode="HTML")
    with suppress(TelegramAPIError):
        await callback.message.delete()

    app = await db.get_latest_application(session, candidate_id)
    if app and app.get("hr_video_msg_id"):
        with suppress(TelegramAPIError):
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=app["hr_video_msg_id"])
    with suppress(TelegramAPIError):
        await callback.answer(LOCALIZATION["ru"]["hr_alert_rejected"], show_alert=True)

@router.callback_query(F.data.startswith("hr_hold:"))
async def hr_hold_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    candidate_id = int(callback.data.split(":")[1])
    bot: Bot = callback.bot
    await db.update_application_status(session, candidate_id, "hold")

    # Уведомляем кандидата о переносе анкеты на паузу
    candidate_lang = await db.get_user_lang(session, candidate_id) or "ru"
    with suppress(TelegramAPIError):
        await bot.send_message(
            chat_id=candidate_id,
            text=LOCALIZATION[candidate_lang]["candidate_hold_notice"],
            parse_mode="HTML",
        )

    with suppress(TelegramAPIError):
        await bot.edit_message_text(
            chat_id=callback.message.chat.id, message_id=callback.message.message_id,
            text=f"{callback.message.text}\n\n{LOCALIZATION['ru']['hr_status_hold']}",
            parse_mode="HTML", reply_markup=kb.get_hr_hold_keyboard(candidate_id),
        )
    with suppress(TelegramAPIError):
        await callback.answer("⏸ Кандидат отложен.")

@router.callback_query(F.data.startswith("score:"))
async def hr_score_callback(callback: CallbackQuery, state: FSMContext) -> None:
    _, score_str, candidate_id_str = callback.data.split(":")
    score = int(score_str)
    candidate_id = int(candidate_id_str)
    await state.update_data(
        score_candidate_id=candidate_id, score_value=score,
        score_msg_id=callback.message.message_id, score_chat_id=callback.message.chat.id,
    )
    await state.set_state(HRScore.waiting_for_comment)
    stars = "⭐️" * score + "☆" * (5 - score)
    await callback.message.answer(
        f"Оценка {stars} принята.\n\n💬 Напишите комментарий (или /skip):",
        parse_mode="HTML",
    )
    with suppress(TelegramAPIError):
        await callback.answer()

@router.message(HRScore.waiting_for_comment, F.text.in_(["/cancel", "отмена", "Отмена"]))
async def cancel_score(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(LOCALIZATION["ru"]["hr_action_cancelled"], parse_mode="HTML")

@router.message(HRScore.waiting_for_comment)
async def process_score_comment(message: Message, state: FSMContext, session: AsyncSession) -> None:
    hr_data = await state.get_data()
    candidate_id = hr_data["score_candidate_id"]
    score = hr_data["score_value"]
    comment = "" if message.text == "/skip" else (message.text or "")

    await db.save_hr_score(session, candidate_id, score, comment)
    stars = "⭐️" * score + "☆" * (5 - score)
    confirm = f"✅ Оценка сохранена: {stars} " + (f"\n💬 {comment}" if comment else "")
    await message.answer(confirm, parse_mode="HTML")
    await state.clear()

def _parse_interview_datetime(text: str) -> str | None:
    current_year = datetime.now().year
    patterns: list[tuple[str, str, bool]] = [
        (r"\d{2}\.\d{2}\.\d{4}\s+в\s+\d{2}:\d{2}", "%d.%m.%Y в %H:%M", False),
        (r"\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}", "%d.%m.%Y %H:%M", False),
        (r"\d{2}\.\d{2}\s+в\s+\d{2}:\d{2}", "%d.%m в %H:%M", True),
    ]
    for pattern, fmt, needs_year in patterns:
        match = re.search(pattern, text)
        if match:
            raw = match.group(0)
            try:
                if needs_year:
                    raw = f"{raw.split(' в ')[0]}.{current_year} в {raw.split(' в ')[1]}"
                    fmt = "%d.%m.%Y в %H:%M"
                return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M")
            except ValueError:
                continue
    return None
