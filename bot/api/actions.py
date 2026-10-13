"""Действия панели над кандидатом: статус + уведомление через бота.

Повторяют логику HR-кнопок из bot/handlers/hr/actions.py.
"""

from __future__ import annotations

import logging
from contextlib import suppress

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiohttp import web

from bot.db import requests as db
from bot.db.base import session_pool
from bot.handlers.hr.actions import _parse_interview_datetime
from bot.lexicon import LOCALIZATION

logger = logging.getLogger(__name__)

MAX_MESSAGE_LEN = 3500


async def _notify(bot: Bot, chat_id: int, text: str) -> bool:
    """Отправляет сообщение кандидату; False, если Telegram отказал."""
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        return True
    except TelegramAPIError as e:
        logger.warning("Не удалось написать кандидату %d: %s", chat_id, e)
        return False


async def _find_candidate(app_id: int) -> int | None:
    """user_id (он же chat_id в Telegram) по id анкеты."""
    from bot.db.models.application import Application

    async with session_pool() as session:
        app = await session.get(Application, app_id)
        return app.user_id if app else None


async def apply_action(request: web.Request) -> web.Response:
    bot: Bot = request.app["bot"]
    try:
        app_id = int(request.match_info["app_id"])
        body = await request.json()
    except (ValueError, TypeError):
        return web.json_response({"error": "bad_request"}, status=400)

    action = body.get("action")
    candidate_id = await _find_candidate(app_id)
    if candidate_id is None:
        return web.json_response({"error": "not_found"}, status=404)

    async with session_pool() as session:
        lang = await db.get_user_lang(session, candidate_id) or "ru"
        texts = LOCALIZATION[lang]

        if action == "invite":
            interview_text = str(body.get("interview_text", "")).strip()
            if not interview_text:
                return web.json_response({"error": "interview_text_required"}, status=400)
            iso = _parse_interview_datetime(interview_text)
            if iso:
                await db.set_interview_time(session, candidate_id, iso)
            await db.update_application_status(session, candidate_id, "accepted")
            notice = texts["candidate_accepted_notice"].format(interview_text=interview_text)
            status = "accepted"
        elif action == "hold":
            await db.update_application_status(session, candidate_id, "hold")
            notice, status = texts["candidate_hold_notice"], "hold"
        elif action == "hire":
            await db.update_application_status(session, candidate_id, "hired")
            notice, status = texts["candidate_hired_notice"], "hired"
        elif action == "reject":
            await db.block_user(session, candidate_id, days=30)
            await db.update_application_status(session, candidate_id, "rejected")
            notice, status = texts["candidate_rejected_notice"], "rejected"
        else:
            return web.json_response({"error": "unknown_action"}, status=400)

    delivered = await _notify(bot, candidate_id, notice)
    logger.warning("Панель: анкета %d -> %s (доставлено=%s)", app_id, status, delivered)
    return web.json_response({"status": status, "delivered": delivered})


async def send_message(request: web.Request) -> web.Response:
    bot: Bot = request.app["bot"]
    try:
        app_id = int(request.match_info["app_id"])
        body = await request.json()
    except (ValueError, TypeError):
        return web.json_response({"error": "bad_request"}, status=400)

    text = str(body.get("text", "")).strip()
    if not text or len(text) > MAX_MESSAGE_LEN:
        return web.json_response({"error": "bad_text"}, status=400)
    candidate_id = await _find_candidate(app_id)
    if candidate_id is None:
        return web.json_response({"error": "not_found"}, status=404)

    # Без parse_mode: текст HR показываем кандидату как есть
    try:
        await bot.send_message(chat_id=candidate_id, text=text)
    except TelegramAPIError as e:
        logger.warning("Сообщение кандидату %d не доставлено: %s", candidate_id, e)
        return web.json_response({"error": "telegram_failed"}, status=502)
    return web.json_response({"delivered": True})
