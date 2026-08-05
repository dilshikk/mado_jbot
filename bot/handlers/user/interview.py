# bot/handlers/user/interview.py
"""FSM-хендлер AI-интервью с кандидатом."""

import asyncio
import json
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.ai.agents import run_all_agents
from bot.ai.interview import get_next_step
from bot.core.config import ADMIN_CHAT_ID
from bot.db import requests as db
from bot.filters.common import IsPrivateChat
from bot.locks import interview_lock
from bot.states import Interview

router = Router()
router.message.filter(IsPrivateChat())

logger = logging.getLogger(__name__)
MIN_QUESTIONS = 5

# Длительность таймаута send_chat_action — 5с.
# Мы обновляем его каждые _TYPING_INTERVAL секунды.
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
    """Луп обновления chat_action=typing до установки stop.
    Видимо пользователю до тех пор, пока Cloudflare генерирует ответ.
    """
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
    """Вызывает get_next_step с параллельным показом анимации «печатает»."""
    stop = asyncio.Event()
    task = asyncio.create_task(_typing_loop(chat_id, bot, stop))
    try:
        return await get_next_step(form_data=form_data, qa_log=qa_log, lang=lang)
    finally:
        stop.set()
        task.cancel()


async def _send_hr_report(bot, session: AsyncSession, session_id: int, user_id: int) -> None:
    """\u041e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u0435\u0442 \u0438\u0442\u043e\u0433\u043e\u0432\u044b\u0439 \u043e\u0442\u0447\u0451\u0442 \u0432 HR-\u0447\u0430\u0442."""
    interview = await db.get_interview_session(session, session_id)
    if not interview:
        return

    app  = await db.get_latest_application(session, user_id)
    name = (app or {}).get("name", f"user#{user_id}")

    header = (
        f"🤖 AI-Отчёт по интервью \n"
        f"{'─'*30}\n"
        f"👤 {name} | user_id: {user_id} \n"
        f"💼 {(app or {}).get('position', '—')}\n"
        f"Вопросов задано: {interview['q_count']}\n"
        f"{'─'*30}\n"
    )

    summary      = interview.get("report_summary") or ""
    decision_raw = interview.get("report_decision")
    decision_block = ""
    if decision_raw:
        try:
            dec          = json.loads(decision_raw)
            total        = dec.get("total_score", "—")
            decision_key = dec.get("decision", "")
            _labels      = {"invite": "✅ Пригласить", "review": "⚠️ Рассмотреть", "reject": "❌ Отклонить"}
            conf         = dec.get("confidence", None)
            conf_str     = f" (уверенность: {conf:.0%})" if isinstance(conf, float) else ""
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
    """\u0417\u0430\u043f\u0443\u0441\u043a\u0430\u0435\u0442 \u0438\u043d\u0442\u0435\u0440\u0432\u044c\u044e \u2014 \u0432\u044b\u0437\u044b\u0432\u0430\u0435\u0442\u0441\u044f \u0438\u0437 form.py \u043f\u043e\u0441\u043b\u0435 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u044f \u0430\u043d\u043a\u0435\u0442\u044b."""
    user_id    = message.from_user.id
    session_id = await db.create_interview_session(session, user_id)

    # Показываем анимацию «печатает» пока AI генерирует первый вопрос
    step = await _get_next_step_with_typing(
        message.chat.id, message.bot, form_data, [], lang,
    )

    if step.get("done"):
        await _finish_interview(message, state, session, session_id, form_data, lang)
        return

    question = step["question"]
    await db.update_interview_session(session, session_id, q_count=1)
    await db.update_application_status(session, user_id, "interview_in_progress")

    await state.set_state(Interview.answering)
    await state.update_data(
        interview_session_id=session_id,
        interview_form_data=form_data,
        interview_lang=lang,
        interview_qa_log=[],
        interview_current_q=question,
        interview_asked_questions=[question.casefold()],
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
    asked_questions = data.get("interview_asked_questions", [])

    qa_log.append({"q": current_q, "a": (message.text or "").strip()})
    await db.append_qa(session, session_id, qa_log)

    # Показываем анимацию «печатает» пока AI думает над следующим вопросом
    step     = await _get_next_step_with_typing(message.chat.id, message.bot, form_data, qa_log, lang)
    question = (step.get("question") or "").strip()

    if len(qa_log) >= MIN_QUESTIONS and (step.get("done") or not question):
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
    asked_questions = data.get("interview_asked_questions", [])

    skip_text = "— (пропущен)" if lang == "ru" else "— (o'tkazildi)"
    qa_log.append({"q": current_q, "a": skip_text})
    await db.append_qa(session, session_id, qa_log)

    # Показываем анимацию «печатает» пока AI генерирует следующий вопрос
    step     = await _get_next_step_with_typing(callback.message.chat.id, callback.bot, form_data, qa_log, lang)
    question = (step.get("question") or "").strip()

    if len(qa_log) >= MIN_QUESTIONS and (step.get("done") or not question):
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
) -> None:
    """\u0417\u0430\u0432\u0435\u0440\u0448\u0430\u0435\u0442 \u0438\u043d\u0442\u0435\u0440\u0432\u044c\u044e: \u0437\u0430\u043f\u0443\u0441\u043a\u0430\u0435\u0442 \u043f\u0430\u0439\u043f\u043b\u0430\u0439\u043d, \u0441\u043e\u0445\u0440\u0430\u043d\u044f\u0435\u0442, \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u0435\u0442 HR."""
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

    # ── АТОМАРНОСТЬ: проверка + run_all_agents внутри interview_lock ──
    async with interview_lock(session_id):
        existing = await db.get_interview_session(session, session_id)
        if existing and existing.get("report_decision"):
            logger.info(
                "_finish_interview: отчёт уже есть для session_id=%d user_id=%d",
                session_id, user_id,
            )
            await _send_hr_report(message.bot, session, session_id, user_id)
            return

        # Уведомляем HR что идёт обработка
        try:
            app  = await db.get_latest_application(session, user_id)
            name = (app or {}).get("name", f"user#{user_id}")
            await message.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"⏳ AI обрабатывает интервью кандидата {name}...",
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
        except Exception as e:
            logger.error("_finish_interview: AI-пайплайн упал: %s", e, exc_info=True)
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

    # _send_hr_report — чистое чтение, вынесено за лок
    await _send_hr_report(message.bot, session, session_id, user_id)


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
            asked_questions.append(question.casefold())
            return question
    return pool[0]
