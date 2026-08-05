# bot/db/requests.py — только изменённая функция save_interview_reports
# (полный файл: добавить поля communication / integrity / decision / total_score)

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.application import Application
from bot.db.models.blacklist import Blacklist
from bot.db.models.interview import InterviewSession
from bot.db.models.user import User
from bot.db.models.vacancy import Vacancy

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _to_dict(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


# ─────────────────────────────────────────────────────────────────────────────
# Все функции до AI-раздела остаются без изменений.
# Здесь только AI-функции, чтобы не дублировать весь файл.
# ─────────────────────────────────────────────────────────────────────────────

async def create_interview_session(session: AsyncSession, user_id: int) -> int:
    """Создаёт новую сессию интервью, возвращает её id."""
    obj = InterviewSession(
        user_id=user_id,
        qa_log="[]",
        q_count=0,
        status="active",
        created_at=_now(),
    )
    session.add(obj)
    await session.commit()
    return obj.id


async def get_interview_session(session: AsyncSession, session_id: int) -> dict | None:
    obj = await session.get(InterviewSession, session_id)
    return _to_dict(obj) if obj else None


async def update_interview_session(
    session: AsyncSession,
    session_id: int,
    q_count: int | None = None,
    status: str | None = None,
) -> None:
    obj = await session.get(InterviewSession, session_id)
    if not obj:
        return
    if q_count is not None:
        obj.q_count = q_count
    if status is not None:
        obj.status = status
    await session.commit()


async def append_qa(session: AsyncSession, session_id: int, qa_log: list[dict]) -> None:
    """Перезаписывает qa_log в сессии интервью."""
    obj = await session.get(InterviewSession, session_id)
    if obj:
        obj.qa_log  = json.dumps(qa_log, ensure_ascii=False)
        obj.q_count = len(qa_log)
        await session.commit()


async def save_interview_reports(
    session: AsyncSession,
    session_id: int,
    finished_at: str,
    # Новые поля пайплайна (JSON-словари → сериализуем в Text)
    resume: "dict | str | None" = None,
    communication: "dict | str | None" = None,
    integrity: "dict | str | None" = None,
    job_match: "dict | str | None" = None,
    decision: "dict | str | None" = None,
    total_score: float | None = None,
    summary: str | None = None,
    # Обратная совместимость со старыми вызовами
    skills: str | None = None,
    personality: str | None = None,
    **_extra,
) -> None:
    """Сохраняет результаты AI-пайплайна в сессию интервью."""

    def _to_json(val: "dict | str | None") -> str | None:
        if val is None:
            return None
        if isinstance(val, dict):
            return json.dumps(val, ensure_ascii=False)
        return str(val)

    obj = await session.get(InterviewSession, session_id)
    if not obj:
        return

    obj.status               = "done"
    obj.finished_at          = finished_at
    obj.report_resume        = _to_json(resume)
    obj.report_communication = _to_json(communication)
    obj.report_integrity     = _to_json(integrity)
    obj.report_job_match     = _to_json(job_match)
    obj.report_decision      = _to_json(decision)
    obj.report_summary       = summary
    obj.total_score          = total_score
    # Обратная совместимость
    obj.report_skills        = skills
    obj.report_personality   = personality

    await session.commit()
