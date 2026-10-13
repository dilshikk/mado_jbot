"""Сервер API панели: список анкет и карточка кандидата."""

from __future__ import annotations

import hmac
import json
import logging
import os
from typing import Any

from aiohttp import web
from sqlalchemy import select

from bot.db.base import session_pool
from bot.db.models.application import Application
from bot.db.models.interview import InterviewSession
from bot.db.models.metro_station import MetroStation

logger = logging.getLogger(__name__)

MAX_LIMIT = 1000


def _json(value: str | None) -> Any:
    """Разбирает JSON-текст из БД; при ошибке возвращает None."""
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _dict_or_none(value: Any) -> dict | None:
    """Отчёты агентов с ключом error считаем отсутствующими."""
    if isinstance(value, dict) and "error" not in value:
        return value
    return None


def _summary(app: Application, session: InterviewSession | None) -> dict[str, Any]:
    decision = _dict_or_none(_json(session.report_decision)) if session else None
    return {
        "id": app.id,
        "user_id": app.user_id,
        "name": app.name,
        "phone": app.phone,
        "position": app.position,
        "branch": app.branch,
        "status": app.status,
        "created_at": app.created_at,
        "interview_time": app.interview_time,
        "hr_score": app.hr_score,
        "total_score": session.total_score if session else None,
        "decision": (decision or {}).get("decision"),
        "priority": (decision or {}).get("priority"),
    }


def _latest_sessions(sessions: list[InterviewSession]) -> dict[int, InterviewSession]:
    """Последняя сессия AI-интервью для каждого пользователя."""
    latest: dict[int, InterviewSession] = {}
    for s in sessions:  # отсортированы по id по возрастанию
        latest[s.user_id] = s
    return latest


@web.middleware
async def _auth(request: web.Request, handler):
    token = os.getenv("PANEL_API_TOKEN", "")
    header = request.headers.get("Authorization", "")
    expected = f"Bearer {token}"
    if not token or not hmac.compare_digest(header, expected):
        return web.json_response({"error": "unauthorized"}, status=401)
    return await handler(request)


async def list_applications(request: web.Request) -> web.Response:
    try:
        limit = max(1, min(int(request.query.get("limit", "200")), MAX_LIMIT))
    except ValueError:
        limit = 200

    async with session_pool() as session:
        apps = (
            await session.scalars(
                select(Application).order_by(Application.id.desc()).limit(limit)
            )
        ).all()
        user_ids = {a.user_id for a in apps}
        sessions = (
            await session.scalars(
                select(InterviewSession)
                .where(InterviewSession.user_id.in_(user_ids))
                .order_by(InterviewSession.id)
            )
        ).all() if user_ids else []

    latest = _latest_sessions(list(sessions))
    return web.json_response({"items": [_summary(a, latest.get(a.user_id)) for a in apps]})


async def get_application(request: web.Request) -> web.Response:
    try:
        app_id = int(request.match_info["app_id"])
    except ValueError:
        return web.json_response({"error": "bad_id"}, status=400)

    async with session_pool() as session:
        app = await session.get(Application, app_id)
        if app is None:
            return web.json_response({"error": "not_found"}, status=404)
        interview = (
            await session.scalars(
                select(InterviewSession)
                .where(InterviewSession.user_id == app.user_id)
                .order_by(InterviewSession.id.desc())
                .limit(1)
            )
        ).first()
        metro = (
            await session.get(MetroStation, app.metro_station_id)
            if app.metro_station_id
            else None
        )

    languages = _json(app.languages)
    detail = {
        **_summary(app, interview),
        "birthday": app.birthday,
        "gender": app.gender,
        "experience": app.experience,
        "languages": languages if isinstance(languages, list) else [],
        "readiness": app.readiness,
        "exp_company": app.exp_company,
        "exp_position": app.exp_position,
        "exp_duration": app.exp_duration,
        "exp_duties": app.exp_duties,
        "salary": app.salary,
        "schedule": app.schedule,
        "evening_shifts": app.evening_shifts,
        "weekends": app.weekends,
        "smoking": app.smoking,
        "med_book": app.med_book,
        "username": app.username,
        "hr_comment": app.hr_comment,
        "metro_station": metro.name_ru if metro else None,
    }

    interview_data = None
    if interview is not None:
        qa_log = _json(interview.qa_log)
        interview_data = {
            "status": interview.status,
            "q_count": interview.q_count,
            "created_at": interview.created_at,
            "finished_at": interview.finished_at,
            "qa_log": [
                {"q": str(e.get("q", "")), "a": str(e.get("a", ""))}
                for e in (qa_log if isinstance(qa_log, list) else [])
                if isinstance(e, dict)
            ],
            "summary": interview.report_summary,
            "decision": _dict_or_none(_json(interview.report_decision)),
            "job_match": _dict_or_none(_json(interview.report_job_match)),
            "communication": _dict_or_none(_json(interview.report_communication)),
            "integrity": _dict_or_none(_json(interview.report_integrity)),
        }

    return web.json_response({"application": detail, "interview": interview_data})


def create_api_app() -> web.Application:
    api = web.Application(middlewares=[_auth])
    api.router.add_get("/api/applications", list_applications)
    api.router.add_get("/api/applications/{app_id}", get_application)
    return api


async def start_api() -> web.AppRunner | None:
    """Запускает API, если задан PANEL_API_TOKEN. Возвращает runner для остановки."""
    if not os.getenv("PANEL_API_TOKEN"):
        logger.warning("PANEL_API_TOKEN не задан — API панели отключён.")
        return None
    host = os.getenv("PANEL_API_HOST", "0.0.0.0")
    port = int(os.getenv("PANEL_API_PORT", "8091"))
    runner = web.AppRunner(create_api_app())
    await runner.setup()
    await web.TCPSite(runner, host, port).start()
    logger.warning("API панели запущен на %s:%d", host, port)
    return runner
