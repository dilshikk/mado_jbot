# bot/handlers/user/interview.py
"""FSM-хендлер AI-интервью с кандидатом.

Новая логика:
- анкета сохраняется в БД со статусом "interview_in_progress"
- интервью запускается сразу после анкеты
- в HR-группу отправляется ЕДИНЫЙ пакет только после статуса "completed"
- при ошибке любого AI-агента — сообщение в HR не отправляется, задача помечается для повтора
"""

import json
import logging
from contextlib import suppress
from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.ai.agents import run_all_agents
from bot.ai.interview import get_next_step
from bot.core.config import ADMIN_CHAT_ID
from bot.db import requests as db
from bot.filters.common import IsPrivateChat
from bot.states import Interview
from bot.utils.formatters import build_hr_resume_text

router = Router()
router.message.filter(IsPrivateChat())

logger = logging.getLogger(__name__)
MIN_QUESTIONS = 5

_SKIP_KB_RU = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="⏭ Пропустить вопрос",   callback_data="interview:skip"),
    InlineKeyboardButton(text="🚫 Завершить интервью",  callback_data="interview:finish"),
]])
_SKIP_KB_UZ = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="⏭ Savolni o'tkazish",  callback_data="interview:skip"),
    InlineKeyboardButton(text="🚫 Intervyuni tugatish", callback_data="interview:finish"),
]])


def _skip_kb(lang: str) -> InlineKeyboardMarkup:
    return _SKIP_KB_UZ if lang == "uz" else _SKIP_KB_RU


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ─── Отправка итогового пакета в HR-группу ───────────────────────────────────

async def _send_hr_package(
    bot,
    session: AsyncSession,
    session_id: int,
    user_id: int,
    form_data: dict,
) -> None:
    """Формирует и отправляет ЕДИНЫЙ пакет кандидата в HR-группу.

    Содержит:
    - полную анкету
    - ответы AI Interview (Q&A)
    - резюме, навыки, коммуникацию, целостность, соответствие вакансии
    - итоговое заключение и рейтинг
    Фото и видео отправляются отдельными сообщениями после основного.
    """
    interview = await db.get_interview_session(session, session_id)
    if not interview:
        logger.error("_send_hr_package: сессия %d не найдена", session_id)
        return

    app = await db.get_latest_application(session, user_id)
    username = (app or {}).get("username") or f"user_{user_id}"

    # ── 1. Полная анкета ─────────────────────────────────────────────────────
    anketa_block = build_hr_resume_text(form_data, user_id, username)

    # ── 2. Ответы интервью Q&A ───────────────────────────────────────────────
    qa_block = ""
    try:
        qa_log: list[dict] = json.loads(interview.get("qa_log") or "[]")
        if qa_log:
            lines = ["\n\n🤖 <b>Ответы AI-интервью:</b>"]
            for i, entry in enumerate(qa_log, 1):
                q = entry.get("q", "")
                a = entry.get("a", "")
                lines.append(f"<b>{i}. {q}</b>\n   ➜ {a}")
            qa_block = "\n".join(lines)
    except Exception as e:
        logger.warning("_send_hr_package: ошибка парсинга qa_log: %s", e)

    # ── 3. AI-анализ (summary уже содержит навыки, коммуникацию, решение) ───
    ai_block = ""
    summary = interview.get("report_summary") or ""
    if summary:
        ai_block = f"\n\n{'─'*30}\n🤖 <b>AI-анализ кандидата:</b>\n{summary}"

    # ── 4. Итоговый балл и решение ───────────────────────────────────────────
    decision_block = ""
    decision_raw = interview.get("report_decision")
    if decision_raw:
        try:
            dec = json.loads(decision_raw)
            total         = dec.get("total_score", "—")
            decision_key  = dec.get("decision", "")
            _labels       = {"invite": "✅ Пригласить", "review": "⚠️ Рассмотреть", "reject": "❌ Отклонить"}
            conf          = dec.get("confidence")
            conf_str      = f"  (уверенность: {conf:.0%})" if isinstance(conf, float) else ""
            priority_map  = {"high": "🔴 Высокий", "medium": "🟡 Средний", "low": "🟢 Низкий"}
            priority      = priority_map.get(dec.get("priority", ""), "")
            decision_block = (
                f"\n\n{'─'*30}\n"
                f"🏁 <b>Решение: {_labels.get(decision_key, decision_key)}</b>{conf_str}\n"
                f"📊 Рейтинг: <b>{total}/10</b>\n"
            )
            if priority:
                decision_block += f"🎯 Приоритет: {priority}\n"
        except Exception as e:
            logger.warning("_send_hr_package: ошибка парсинга report_decision: %s", e)

    # ── Собираем итоговый текст ──────────────────────────────────────────────
    full_text = anketa_block + qa_block + ai_block + decision_block

    # Telegram лимит 4096 символов
    if len(full_text) > 4000:
        full_text = full_text[:3990] + "\n<i>…(обрезано)</i>"

    # ── Отправляем основное сообщение ────────────────────────────────────────
    from bot import keyboards as kb  # noqa: PLC0415
    hr_keyboard = kb.get_hr_action_keyboard(
        phone=form_data.get("phone"),
        username=username,
        candidate_id=user_id,
    )
    try:
        hr_msg = await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=full_text,
            reply_markup=hr_keyboard,
            parse_mode="HTML",
        )
        logger.info("_send_hr_package: основное сообщение отправлено msg_id=%d", hr_msg.message_id)
    except Exception as e:
        logger.error("_send_hr_package: ошибка отправки основного сообщения: %s", e)
        return

    # ── Фото ────────────────────────────────────────────────────────────────
    photo_id = form_data.get("photo")
    if photo_id:
        with suppress(TelegramAPIError):
            await bot.send_photo(
                chat_id=ADMIN_CHAT_ID,
                photo=photo_id,
                caption=f"📸 Фото кандидата: {form_data.get('name', '')}",
                reply_to_message_id=hr_msg.message_id,
            )

    # ── Видео ────────────────────────────────────────────────────────────────
    video_id = form_data.get("video_file_id")
    if video_id:
        try:
            if form_data.get("is_video_note"):
                video_msg = await bot.send_video_note(
                    chat_id=ADMIN_CHAT_ID,
                    video_note=video_id,
                    reply_to_message_id=hr_msg.message_id,
                )
            else:
                video_msg = await bot.send_video(
                    chat_id=ADMIN_CHAT_ID,
                    video=video_id,
                    caption=f"🎥 Видео-визитка: {form_data.get('name', '')} (@{username})",
                    reply_to_message_id=hr_msg.message_id,
                )
            await db.save_hr_video_msg_id(session, user_id, video_msg.message_id)
        except Exception as e:
            logger.error("_send_hr_package: ошибка отправки видео: %s", e)


# ─── Запуск интервью ─────────────────────────────────────────────────────────

async def start_interview(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    form_data: dict,
    lang: str,
) -> None:
    """Запускает интервью — вызывается из form.py после сохранения анкеты.

    Статус анкеты меняется на "interview_in_progress".
    В HR-группу НЕ отправляется ничего до завершения.
    """
    # Статус → интервью в процессе
    await db.update_application_status(session, message.from_user.id, "interview_in_progress")

    session_id = await db.create_interview_session(session, message.from_user.id)
    step = await get_next_step(form_data=form_data, qa_log=[], lang=lang)

    if step.get("done"):
        await _finish_interview(message, state, session, session_id, form_data, lang)
        return

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
    )

    intro = (
        "🤖 <b>Recruiter AI</b>\n\n"
        "Отлично! Теперь я задам вам несколько вопросов по вакансии, чтобы лучше вас узнать.\n\n"
        if lang == "ru" else
        "🤖 <b>Recruiter AI</b>\n\n"
        "Juda yaxshi! Endi men sizga vakansiya bo'yicha bir necha savol beraman.\n\n"
    )
    with suppress(TelegramAPIError):
        await message.answer(
            intro + f"<b>{question}</b>",
            parse_mode="HTML",
            reply_markup=_skip_kb(lang),
        )


# ─── Обработка ответов ───────────────────────────────────────────────────────

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

    step     = await get_next_step(form_data=form_data, qa_log=qa_log, lang=lang)
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
    with suppress(TelegramAPIError):
        await message.answer(f"🤖 <b>{question}</b>", parse_mode="HTML", reply_markup=_skip_kb(lang))


@router.callback_query(Interview.answering, F.data == "interview:skip")
async def skip_question(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    with suppress(TelegramAPIError):
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

    step     = await get_next_step(form_data=form_data, qa_log=qa_log, lang=lang)
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
    with suppress(TelegramAPIError):
        await callback.message.answer(
            f"🤖 <b>{question}</b>", parse_mode="HTML", reply_markup=_skip_kb(lang),
        )


@router.callback_query(Interview.answering, F.data == "interview:finish")
async def force_finish(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    with suppress(TelegramAPIError):
        await callback.answer()
    data       = await state.get_data()
    session_id = data.get("interview_session_id")
    form_data  = data.get("interview_form_data", {})
    lang       = data.get("interview_lang", "ru")
    qa_log     = data.get("interview_qa_log", [])
    await _finish_interview(callback.message, state, session, session_id, form_data, lang, qa_log)


# ─── Завершение интервью ─────────────────────────────────────────────────────

async def _finish_interview(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    session_id: int,
    form_data: dict,
    lang: str,
    qa_log: list[dict] | None = None,
) -> None:
    """Завершает интервью: запускает AI-пайплайн, отправляет единый пакет в HR.

    Правила:
    - В HR отправляется ТОЛЬКО после статуса "completed"
    - При ошибке любого AI-агента: пакет НЕ отправляется, задача помечается для повтора
    - Промежуточные сообщения в HR не отправляются
    """
    if qa_log is None:
        qa_log = []

    await state.clear()
    user_id = message.from_user.id if message.from_user else message.chat.id

    # Уведомляем кандидата
    thanks = (
        "✅ <b>Интервью завершено!</b>\n\nСпасибо за ответы. HR-менеджер свяжется с вами в ближайшее время."
        if lang == "ru" else
        "✅ <b>Intervyu yakunlandi!</b>\n\nJavoblaringiz uchun rahmat. HR-menejer tez orada siz bilan bog'lanadi."
    )
    with suppress(TelegramAPIError):
        await message.answer(thanks, parse_mode="HTML")

    logger.info(
        "_finish_interview: запуск AI-пайплайна user_id=%d session_id=%d qa_count=%d",
        user_id, session_id, len(qa_log),
    )

    # ── Запускаем 5-уровневый AI-пайплайн ───────────────────────────────────
    reports: dict = {}
    pipeline_failed = False
    failed_agents: list[str] = []

    try:
        reports = await run_all_agents(form_data, qa_log)
    except Exception as e:
        logger.error("_finish_interview: AI-пайплайн упал: %s", e, exc_info=True)
        pipeline_failed = True
        failed_agents.append("pipeline")

    # Проверяем что каждый агент вернул результат без ошибок
    if not pipeline_failed:
        agent_checks = {
            "resume":        reports.get("resume"),
            "communication": reports.get("communication"),
            "integrity":     reports.get("integrity"),
            "job_match":     reports.get("job_match"),
            "decision":      reports.get("decision"),
        }
        for agent_name, result in agent_checks.items():
            if result is None or (isinstance(result, dict) and "error" in result):
                logger.error(
                    "_finish_interview: агент %s вернул ошибку: %s", agent_name, result,
                )
                failed_agents.append(agent_name)

    # ── Сохраняем результаты в БД ────────────────────────────────────────────
    if not pipeline_failed:
        try:
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
        except Exception as e:
            logger.error("_finish_interview: ошибка сохранения отчётов: %s", e, exc_info=True)
            pipeline_failed = True
            failed_agents.append("db_save")

    # ── Если есть ошибки — не отправляем в HR, помечаем для повтора ─────────
    if failed_agents:
        await db.update_interview_session(session, session_id, status="failed")
        await db.update_application_status(session, user_id, "interview_failed")
        logger.error(
            "_finish_interview: ПАКЕТ В HR НЕ ОТПРАВЛЕН. "
            "Ошибки агентов: %s. user_id=%d session_id=%d. "
            "Статус установлен 'interview_failed' для повторной обработки.",
            failed_agents, user_id, session_id,
        )
        return

    # ── Устанавливаем статус "completed" ─────────────────────────────────────
    await db.update_interview_session(session, session_id, status="completed")
    await db.update_application_status(session, user_id, "pending")

    logger.info(
        "_finish_interview: интервью завершено, отправляем пакет в HR. user_id=%d session_id=%d",
        user_id, session_id,
    )

    # ── Отправляем ЕДИНЫЙ пакет в HR-группу ──────────────────────────────────
    await _send_hr_package(message.bot, session, session_id, user_id, form_data)


# ─── Fallback-вопросы (если AI не ответил) ───────────────────────────────────

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
    return pool[min(len(qa_log), len(pool) - 1)]
