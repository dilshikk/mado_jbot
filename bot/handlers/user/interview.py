# bot/handlers/user/interview.py
"""FSM-хендлер AI-интервью с кандидатом."""

import asyncio
import json
import logging
from contextlib import suppress
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.ai.agents import run_all_agents
from bot.ai.interview import get_next_step, make_empty_state
from bot.core.config import ADMIN_CHAT_ID
from bot.db import requests as db
from bot.filters.common import IsPrivateChat
from bot.states import Interview

router = Router()
router.message.filter(IsPrivateChat())

logger = logging.getLogger(__name__)
MIN_QUESTIONS = 5

_SKIP_KB_RU = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="⏭ Пропустить вопрос", callback_data="interview:skip"),
    InlineKeyboardButton(text="🚫 Завершить интервью", callback_data="interview:finish"),
]])
_SKIP_KB_UZ = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="⏭ Savolni o'tkazish", callback_data="interview:skip"),
    InlineKeyboardButton(text="🚫 Intervyuni tugatish", callback_data="interview:finish"),
]])


def _skip_kb(lang: str) -> InlineKeyboardMarkup:
    return _SKIP_KB_UZ if lang == "uz" else _SKIP_KB_RU


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def _typing_loop(bot: Bot, chat_id: int, stop_event: asyncio.Event) -> None:
    """Отправляет «печатает...» каждые 4 секунды пока AI думает.

    Telegram сам сбрасывает индикатор через 5 сек, поэтому повторяем каждые 4.
    """
    while not stop_event.is_set():
        with suppress(TelegramAPIError, Exception):
            await bot.send_chat_action(chat_id=chat_id, action="typing")
        try:
            await asyncio.wait_for(asyncio.shield(stop_event.wait()), timeout=4.0)
        except asyncio.TimeoutError:
            pass


async def _ask_ai_with_typing(
    bot: Bot,
    chat_id: int,
    *,
    form_data: dict,
    lang: str,
    interview_state: dict,
    last_qa: "dict | None",
    q_count: int,
) -> dict:
    """Запрашивает AI и показывает 'печатает...' весь время ожидания."""
    stop = asyncio.Event()
    typing_task = asyncio.create_task(_typing_loop(bot, chat_id, stop))
    try:
        result = await get_next_step(
            form_data=form_data,
            lang=lang,
            interview_state=interview_state,
            last_qa=last_qa,
            q_count=q_count,
        )
    finally:
        stop.set()
        with suppress(Exception):
            await typing_task
    return result


async def _send_hr_report(bot: Bot, session: AsyncSession, session_id: int, user_id: int) -> None:
    """Отправляет итоговый отчёт в HR-чат."""
    interview = await db.get_interview_session(session, session_id)
    if not interview:
        return

    app = await db.get_latest_application(session, user_id)
    name = (app or {}).get("name", f"user#{user_id}")

    header = (
        f"🤖 AI-Отчёт по интервью \n"
        f"{'─'*30}\n"
        f"👤 {name} | user_id: {user_id} \n"
        f"💼 {(app or {}).get('position', '—')}\n"
        f"Вопросов задано: {interview['q_count']}\n"
        f"{'─'*30}\n"
    )

    summary = interview.get("report_summary") or ""

    decision_raw = interview.get("report_decision")
    decision_block = ""
    if decision_raw:
        try:
            dec = json.loads(decision_raw)
            total = dec.get("total_score", "—")
            decision_key = dec.get("decision", "")
            _labels = {"invite": "✅ Пригласить", "review": "⚠️ Рассмотреть", "reject": "❌ Отклонить"}
            conf = dec.get("confidence", None)
            conf_str = f" (уверенность: {conf:.0%})" if isinstance(conf, float) else ""
            decision_block = (
                f"\n 🏁 Решение: {_labels.get(decision_key, decision_key)} {conf_str}\n"
                f"Балл: {total}/10 \n"
            )
        except Exception:
            pass

    full_text = header + summary + decision_block
    if len(full_text) > 4000:
        full_text = full_text[:3990] + "\n …(обрезано) "

    try:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=full_text, parse_mode="HTML")
    except Exception as e:
        logger.error("Ошибка отправки AI-отчёта в HR-чат: %s", e)


async def start_interview(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    form_data: dict,
    lang: str,
) -> None:
    """Запускает интервью — вызывается из form.py после сохранения анкеты."""
    session_id = await db.create_interview_session(session, message.from_user.id)
    interview_state = make_empty_state()

    step = await _ask_ai_with_typing(
        message.bot,
        message.chat.id,
        form_data=form_data,
        lang=lang,
        interview_state=interview_state,
        last_qa=None,
        q_count=0,
    )
    interview_state = step.get("new_state", interview_state)

    if step.get("done") or not step.get("question"):
        logger.warning(
            "start_interview: AI вернул done/пусто на первом шаге — "
            "используем fallback-вопрос (user_id=%d)",
            message.from_user.id,
        )
        question = _fallback_question(lang, [], [])
    else:
        question = step["question"]

    await db.update_interview_session(session, session_id, q_count=1)

    await state.set_state(Interview.answering)
    await state.update_data(
        interview_session_id=session_id,
        interview_form_data=form_data,
        interview_lang=lang,
        interview_qa_log=[],
        interview_current_q=question,
        interview_asked_questions=[question.casefold()],
        interview_state=interview_state,
    )

    intro = (
        "🤖 Recruiter AI \n\nОтлично! Теперь я задам вам несколько вопросов, чтобы лучше вас узнать.\n\n"
        if lang == "ru" else
        "🤖 Recruiter AI \n\nJuda yaxshi! Endi men sizga bir necha savol beraman.\n\n"
    )
    await message.answer(intro + f" {question} ", parse_mode="HTML", reply_markup=_skip_kb(lang))


@router.message(Interview.answering)
async def process_answer(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    session_id = data.get("interview_session_id")
    form_data = data.get("interview_form_data", {})
    lang = data.get("interview_lang", "ru")
    qa_log = data.get("interview_qa_log", [])
    current_q = data.get("interview_current_q", "")
    asked_questions = data.get("interview_asked_questions", [])
    interview_state = data.get("interview_state") or make_empty_state()

    answer_text = (message.text or "").strip()
    last_qa = {"q": current_q, "a": answer_text}

    step = await _ask_ai_with_typing(
        message.bot,
        message.chat.id,
        form_data=form_data,
        lang=lang,
        interview_state=interview_state,
        last_qa=last_qa,
        q_count=len(qa_log),
    )

    qa_log.append(last_qa)
    await db.append_qa(session, session_id, qa_log)

    interview_state = step.get("new_state", interview_state)

    question = (step.get("question") or "").strip()
    if len(qa_log) >= MIN_QUESTIONS and (step.get("done") or not question):
        await state.update_data(interview_qa_log=qa_log, interview_state=interview_state)
        await _finish_interview(message, state, session, session_id, form_data, lang, qa_log)
        return

    if not question:
        question = _fallback_question(lang, qa_log, asked_questions)
    else:
        normalized = question.casefold()
        if normalized in asked_questions:
            question = _fallback_question(lang, qa_log, asked_questions)
        else:
            asked_questions.append(normalized)

    await db.update_interview_session(session, session_id, q_count=len(qa_log) + 1)
    await state.update_data(
        interview_qa_log=qa_log,
        interview_current_q=question,
        interview_asked_questions=asked_questions,
        interview_state=interview_state,
    )
    await message.answer(f"🤖 {question} ", parse_mode="HTML", reply_markup=_skip_kb(lang))


@router.callback_query(Interview.answering, F.data == "interview:skip")
async def skip_question(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    data = await state.get_data()
    session_id = data.get("interview_session_id")
    form_data = data.get("interview_form_data", {})
    lang = data.get("interview_lang", "ru")
    qa_log = data.get("interview_qa_log", [])
    current_q = data.get("interview_current_q", "")
    asked_questions = data.get("interview_asked_questions", [])
    interview_state = data.get("interview_state") or make_empty_state()

    skip_text = "— (пропущен)" if lang == "ru" else "— (o'tkazildi)"
    last_qa = {"q": current_q, "a": skip_text}

    step = await _ask_ai_with_typing(
        callback.bot,
        callback.message.chat.id,
        form_data=form_data,
        lang=lang,
        interview_state=interview_state,
        last_qa=last_qa,
        q_count=len(qa_log),
    )

    qa_log.append(last_qa)
    await db.append_qa(session, session_id, qa_log)

    interview_state = step.get("new_state", interview_state)

    question = (step.get("question") or "").strip()
    if len(qa_log) >= MIN_QUESTIONS and (step.get("done") or not question):
        await state.update_data(interview_qa_log=qa_log, interview_state=interview_state)
        await _finish_interview(callback.message, state, session, session_id, form_data, lang, qa_log)
        return

    if not question:
        question = _fallback_question(lang, qa_log, asked_questions)
    else:
        normalized = question.casefold()
        if normalized in asked_questions:
            question = _fallback_question(lang, qa_log, asked_questions)
        else:
            asked_questions.append(normalized)

    await db.update_interview_session(session, session_id, q_count=len(qa_log) + 1)
    await state.update_data(
        interview_qa_log=qa_log,
        interview_current_q=question,
        interview_asked_questions=asked_questions,
        interview_state=interview_state,
    )
    await callback.message.answer(f"🤖 {question} ", parse_mode="HTML", reply_markup=_skip_kb(lang))


@router.callback_query(Interview.answering, F.data == "interview:finish")
async def force_finish(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    data = await state.get_data()
    session_id = data.get("interview_session_id")
    form_data = data.get("interview_form_data", {})
    lang = data.get("interview_lang", "ru")
    qa_log = data.get("interview_qa_log", [])
    await _finish_interview(callback.message, state, session, session_id, form_data, lang, qa_log)


async def _finish_interview(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    session_id: int,
    form_data: dict,
    lang: str,
    qa_log: "list[dict] | None" = None,
) -> None:
    """Завершает интервью: запускает пайплайн, сохраняет, отправляет HR."""
    if qa_log is None:
        qa_log = []

    await state.clear()

    thanks = (
        "✅ Интервью завершено! \n\nСпасибо за ответы. HR-менеджер свяжется с вами в ближайшее время."
        if lang == "ru" else
        "✅ Intervyu yakunlandi! \n\nJavoblaringiz uchun rahmat. HR-menejer tez orada siz bilan bog'lanadi."
    )
    await message.answer(thanks, parse_mode="HTML")

    user_id = message.from_user.id if message.from_user else message.chat.id
    bot: Bot = message.bot

    if not qa_log:
        logger.warning(
            "_finish_interview: qa_log пуст — пайплайн пропущен (user_id=%d session_id=%d)",
            user_id, session_id,
        )
        await db.update_interview_session(session, session_id, status="done")
        try:
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    f"⚠️ Интервью завершено без ответов.\n"
                    f"user_id={user_id} | session_id={session_id}\n"
                    "AI не смог задать первый вопрос (проверьте токены OpenAI)."
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    try:
        app = await db.get_latest_application(session, user_id)
        name = (app or {}).get("name", f"user#{user_id}")
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"⏳ AI обрабатывает интервью кандидата {name}... (вопросов: {len(qa_log)})",
            parse_mode="HTML",
        )
    except Exception:
        pass

    logger.info(
        "_finish_interview: запуск AI-пайплайна user_id=%d session_id=%d qa_count=%d",
        user_id, session_id, len(qa_log),
    )

    reports = await run_all_agents(form_data, qa_log)

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

    await _send_hr_report(bot, session, session_id, user_id)


def _fallback_question(lang: str, qa_log: list[dict], asked_questions: list[str]) -> str:
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
            return question
    return pool[0]
