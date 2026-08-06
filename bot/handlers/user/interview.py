# bot/handlers/user/interview.py
"""FSM-хендлер AI-интервью с кандидатом."""

import asyncio
import json
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.ai.agents import run_all_agents
from bot.ai.interview import get_next_step, HARD_MAX_QUESTIONS
from bot.core.config import ADMIN_CHAT_ID
from bot.db import requests as db
from bot.filters.common import IsPrivateChat
from bot import keyboards as kb
from bot.locks import interview_lock
from bot.states import Interview
from bot.utils.formatters import build_hr_resume_text

router = Router()
router.message.filter(IsPrivateChat())

logger = logging.getLogger(__name__)

# Минимальное число вопросов до того, как принять решение AI о завершении.
# Защищает от случайного раннего done= true из-за сбоя модели.
MIN_QUESTIONS = 4

_TYPING_INTERVAL = 4

_SKIP_KB_RU = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="⏭ Пропустить вопрос",   callback_data="interview:skip"),
    InlineKeyboardButton(text="🚫 Завершить интервью", callback_data="interview:finish"),
]])
_SKIP_KB_UZ = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="⏭ Savolni o'tkazish",    callback_data="interview:skip"),
    InlineKeyboardButton(text="🚫 Intervyuni tugatish", callback_data="interview:finish"),
]])

def _skip_kb(lang: str) -> InlineKeyboardMarkup:
    return _SKIP_KB_UZ if lang == "uz" else _SKIP_KB_RU

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def _typing_loop(chat_id: int, bot, stop: asyncio.Event) -> None:
    try:
        while not stop.is_set():
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.wait_for(asyncio.shield(stop.wait()), timeout=_TYPING_INTERVAL)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass
    except Exception as exc:
        logger.debug("_typing_loop завершился с ошибкой: %s", exc)


async def _get_next_step_with_typing(
    chat_id: int,
    bot,
    form_data: dict,
    qa_log: list[dict],
    lang: str,
) -> dict:
    stop = asyncio.Event()
    task = asyncio.create_task(_typing_loop(chat_id, bot, stop))
    try:
        return await get_next_step(form_data=form_data, qa_log=qa_log, lang=lang)
    finally:
        stop.set()
        task.cancel()


async def _send_combined_hr_card(
    bot,
    session: AsyncSession,
    session_id: int,
    user_id: int,
    form_data: dict,
    lang: str,
    user,
) -> None:
    """Отправляет в HR-чат объединённую карточку: анкета + AI-анализ."""
    if not ADMIN_CHAT_ID:
        return

    interview = await db.get_interview_session(session, session_id)

    # ── Блок 1: анкета ────────────────────────────────────────────────────────
    resume_block = build_hr_resume_text(form_data, lang, user)

    # ── Блок 2: AI-анализ ─────────────────────────────────────────────────────
    ai_block = ""
    if interview:
        summary = interview.get("report_summary") or ""
        decision_raw = interview.get("report_decision")
        decision_block = ""
        if decision_raw:
            try:
                dec = json.loads(decision_raw)
                total = dec.get("total_score", "—")
                decision_key = dec.get("decision", "")
                _labels = {
                    "invite":  "✅ Пригласить",
                    "review":  "⚠️ Рассмотреть",
                    "reject":  "❌ Отклонить",
                }
                conf = dec.get("confidence", None)
                conf_str = f" (уверенность: {conf:.0%})" if isinstance(conf, float) else ""
                decision_block = (
                    f"\n🏁 <b>Решение AI:</b> {_labels.get(decision_key, decision_key)}{conf_str}\n"
                    f"⭐ <b>Балл:</b> {total}/10\n"
                )
            except Exception:
                pass

        q_count = interview.get("q_count", 0)
        ai_block = (
            f"\n{'─'*30}\n"
            f"🤖 <b>AI-анализ интервью</b> (вопросов: {q_count})\n"
            f"{'─'*30}\n"
            f"{summary}"
            f"{decision_block}"
        )

    full_text = resume_block + ai_block
    if len(full_text) > 4096:
        full_text = full_text[:4080] + "\n…(обрезано)"

    hr_kb = kb.get_hr_action_keyboard(
        phone=form_data.get("phone", ""),
        username=getattr(user, "username", "") or "",
        candidate_id=user_id,
    )

    try:
        photo_id = form_data.get("photo_file_id")
        if photo_id:
            await bot.send_photo(
                ADMIN_CHAT_ID,
                photo=photo_id,
                caption=full_text,
                reply_markup=hr_kb,
                parse_mode="HTML",
            )
        else:
            await bot.send_message(
                ADMIN_CHAT_ID,
                text=full_text,
                reply_markup=hr_kb,
                parse_mode="HTML",
            )
    except Exception as exc:
        logger.error("_send_combined_hr_card: ошибка отправки в HR-чат: %s", exc)


async def start_interview(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    form_data: dict,
    lang: str,
) -> None:
    """Запускает интервью — вызывается из form.py после сохранения анкеты."""
    user_id    = message.from_user.id
    session_id = await db.create_interview_session(session, user_id)

    step = await _get_next_step_with_typing(
        message.chat.id, message.bot, form_data, [], lang,
    )

    if step.get("done"):
        await _finish_interview(
            message, state, session, session_id, form_data, lang,
            user=message.from_user,
        )
        return

    question = step["question"]
    topic    = step.get("topic", "")
    await db.update_interview_session(session, session_id, q_count=1)
    await db.update_application_status(session, user_id, "interview_in_progress")

    await state.set_state(Interview.answering)
    await state.update_data(
        interview_session_id=session_id,
        interview_form_data=form_data,
        interview_lang=lang,
        interview_qa_log=[],
        interview_current_q=question,
        interview_current_topic=topic,
        interview_asked_questions=[question.casefold()],
        interview_user_id=message.from_user.id,
        interview_username=message.from_user.username,
        interview_first_name=message.from_user.first_name,
        interview_last_name=message.from_user.last_name,
    )

    intro = (
        "🤖 Recruiter AI \n\nОтлично! Теперь я задам вам несколько вопросов, чтобы лучше вас узнать.\n\n"
        if lang == "ru" else
        "🤖 Recruiter AI \n\nJuda yaxshi! Endi men sizga bir necha savol beraman.\n\n"
    )
    await message.answer(intro + f" {question} ", parse_mode="HTML", reply_markup=_skip_kb(lang))


@router.message(Interview.answering)
async def process_answer(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data            = await state.get_data()
    session_id      = data.get("interview_session_id")
    form_data       = data.get("interview_form_data", {})
    lang            = data.get("interview_lang", "ru")
    qa_log          = data.get("interview_qa_log", [])
    current_q       = data.get("interview_current_q", "")
    current_topic   = data.get("interview_current_topic", "")
    asked_questions = data.get("interview_asked_questions", [])

    # Сохраняем ответ вместе с темой — модель использует topic для трекинга компетенций
    qa_log.append({"q": current_q, "a": (message.text or "").strip(), "topic": current_topic})
    await db.append_qa(session, session_id, qa_log)

    step     = await _get_next_step_with_typing(message.chat.id, message.bot, form_data, qa_log, lang)
    question = (step.get("question") or "").strip()

    # Завершаем только если AI сказал done=true И задано хотя бы MIN_QUESTIONS
    if step.get("done") and len(qa_log) >= MIN_QUESTIONS:
        await _finish_interview(message, state, session, session_id, form_data, lang, qa_log)
        return
    # Абсолютный лимит
    if len(qa_log) >= HARD_MAX_QUESTIONS:
        await _finish_interview(message, state, session, session_id, form_data, lang, qa_log)
        return

    topic = step.get("topic", "")
    if not question:
        question = _fallback_question(lang, qa_log, asked_questions)
        topic = ""
    else:
        normalized = question.casefold()
        if normalized in asked_questions:
            question = _fallback_question(lang, qa_log, asked_questions)
            topic = ""
        else:
            asked_questions.append(normalized)

    await db.update_interview_session(session, session_id, q_count=len(qa_log) + 1)
    await state.update_data(
        interview_qa_log=qa_log,
        interview_current_q=question,
        interview_current_topic=topic,
        interview_asked_questions=asked_questions,
    )
    await message.answer(f"🤖 {question} ", parse_mode="HTML", reply_markup=_skip_kb(lang))


@router.callback_query(Interview.answering, F.data == "interview:skip")
async def skip_question(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()

    data            = await state.get_data()
    session_id      = data.get("interview_session_id")
    form_data       = data.get("interview_form_data", {})
    lang            = data.get("interview_lang", "ru")
    qa_log          = data.get("interview_qa_log", [])
    current_q       = data.get("interview_current_q", "")
    current_topic   = data.get("interview_current_topic", "")
    asked_questions = data.get("interview_asked_questions", [])

    skip_text = "— (пропущен)" if lang == "ru" else "— (o'tkazildi)"
    qa_log.append({"q": current_q, "a": skip_text, "topic": current_topic})
    await db.append_qa(session, session_id, qa_log)

    step     = await _get_next_step_with_typing(callback.message.chat.id, callback.bot, form_data, qa_log, lang)
    question = (step.get("question") or "").strip()

    if step.get("done") and len(qa_log) >= MIN_QUESTIONS:
        await _finish_interview(callback.message, state, session, session_id, form_data, lang, qa_log)
        return
    if len(qa_log) >= HARD_MAX_QUESTIONS:
        await _finish_interview(callback.message, state, session, session_id, form_data, lang, qa_log)
        return

    topic = step.get("topic", "")
    if not question:
        question = _fallback_question(lang, qa_log, asked_questions)
        topic = ""
    else:
        normalized = question.casefold()
        if normalized in asked_questions:
            question = _fallback_question(lang, qa_log, asked_questions)
            topic = ""
        else:
            asked_questions.append(normalized)

    await db.update_interview_session(session, session_id, q_count=len(qa_log) + 1)
    await state.update_data(
        interview_qa_log=qa_log,
        interview_current_q=question,
        interview_current_topic=topic,
        interview_asked_questions=asked_questions,
    )
    await callback.message.answer(f"🤖 {question} ", parse_mode="HTML", reply_markup=_skip_kb(lang))


@router.callback_query(Interview.answering, F.data == "interview:finish")
async def force_finish(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    data       = await state.get_data()
    session_id = data.get("interview_session_id")
    form_data  = data.get("interview_form_data", {})
    lang       = data.get("interview_lang", "ru")
    qa_log     = data.get("interview_qa_log", [])
    await _finish_interview(callback.message, state, session, session_id, form_data, lang, qa_log)


async def _finish_interview(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    session_id: int,
    form_data: dict,
    lang: str,
    qa_log: list[dict] | None = None,
    user=None,
) -> None:
    """Завершает интервью: запускает AI-пайплайн, отправляет объединённую карточку в HR."""
    if qa_log is None:
        qa_log = []

    if user is None:
        user = message.from_user

    fsm_data = await state.get_data()
    if not form_data:
        form_data = fsm_data.get("interview_form_data", {})
    if not lang:
        lang = fsm_data.get("interview_lang", "ru")

    await state.clear()

    thanks = (
        "✅ Интервью завершено! \n\nСпасибо за ответы. HR-менеджер свяжется с вами в ближайшее время."
        if lang == "ru" else
        "✅ Intervyu yakunlandi! \n\nJavoblaringiz uchun rahmat. HR-menejer tez orada siz bilan bog'lanadi."
    )
    await message.answer(thanks, parse_mode="HTML")

    user_id = user.id if user else (message.from_user.id if message.from_user else message.chat.id)

    async with interview_lock(session_id):
        existing = await db.get_interview_session(session, session_id)
        if existing and existing.get("report_decision"):
            logger.info(
                "_finish_interview: отчёт уже есть для session_id=%d user_id=%d",
                session_id, user_id,
            )
            await _send_combined_hr_card(
                message.bot, session, session_id, user_id, form_data, lang, user,
            )
            return

        if ADMIN_CHAT_ID:
            try:
                app  = await db.get_latest_application(session, user_id)
                name = (app or {}).get("name", f"user#{user_id}")
                await message.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"⏳ AI обрабатывает интервью кандидата <b>{name}</b>...",
                    parse_mode="HTML",
                )
            except Exception:
                pass

        logger.info(
            "_finish_interview: запуск AI-пайплайна user_id=%d session_id=%d qa_count=%d",
            user_id, session_id, len(qa_log),
        )

        try:
            reports = await run_all_agents(form_data, qa_log)
        except Exception as exc:
            logger.error("_finish_interview: AI-пайплайн упал: %s", exc, exc_info=True)
            await db.update_application_status(session, user_id, "interview_failed")
            return

        await db.save_interview_reports(
            session,
            session_id=session_id,
            finished_at=_now(),
            resume=reports.get("resume"),
            communication=reports.get("communication"),
            integrity=reports.get("integrity"),
            job_match=reports.get("job_match"),
            decision=reports.get("decision"),
            total_score=reports.get("total_score"),
            summary=reports.get("summary"),
        )
        await db.update_application_status(session, user_id, "screened")

    await _send_combined_hr_card(
        message.bot, session, session_id, user_id, form_data, lang, user,
    )


def _fallback_question(lang: str, qa_log: list[dict], asked_questions: list[str]) -> str:
    """Резервные вопросы на случай сбоя модели."""
    pool_ru = [
        "Почему вы хотите работать в MADO?",
        "Расскажите о вашем опыте работы с гостями.",
        "Как вы обычно работаете в команде?",
        "Как вы ведёте себя в стрессовой ситуации на работе?",
        "Какие у вас карьерные цели на ближайший год?",
        "Какой ваш самый полезный навык для этой вакансии?",
    ]
    pool_uz = [
        "Nega MADOda ishlamoqchisiz?",
        "Mehmonlar bilan ishlash tajribangiz haqida aytib bering.",
        "Jamoada odatda qanday ishlaysiz?",
        "Ishdagi stressli vaziyatda o'zingizni qanday tutasiz?",
        "Yaqin bir yil uchun karyera maqsadlaringiz qanday?",
        "Bu vakansiya uchun eng foydali ko'nikmangiz qaysi?",
    ]
    pool = pool_uz if lang == "uz" else pool_ru
    for question in pool:
        if question.casefold() not in asked_questions:
            asked_questions.append(question.casefold())
            return question
    return pool[0]
