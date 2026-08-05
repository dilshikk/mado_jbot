# bot/db/requests.py

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.application import Application
from bot.db.models.blacklist import Blacklist
from bot.db.models.interview import InterviewSession
from bot.db.models.metro_station import MetroStation
from bot.db.models.user import User
from bot.db.models.vacancy import Vacancy

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _to_dict(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


async def _latest_application_id(session: AsyncSession, user_id: int) -> int | None:
    """ID последней анкеты пользователя или None."""
    return await session.scalar(
        select(Application.id)
        .where(Application.user_id == user_id)
        .order_by(Application.created_at.desc())
        .limit(1)
    )


# ── Вакансии ──────────────────────────────────────────────────────────────────

async def get_active_vacancies(session: AsyncSession) -> list[dict]:
    rows = (await session.scalars(
        select(Vacancy).where(Vacancy.is_active == 1).order_by(Vacancy.sort_order, Vacancy.id)
    )).all()
    return [_to_dict(v) for v in rows]


async def get_all_vacancies(session: AsyncSession) -> list[dict]:
    rows = (await session.scalars(
        select(Vacancy).order_by(Vacancy.sort_order, Vacancy.id)
    )).all()
    return [_to_dict(v) for v in rows]


async def add_vacancy(session: AsyncSession, name_ru: str, name_uz: str, emoji: str = "") -> int:
    max_order = await session.scalar(select(func.coalesce(func.max(Vacancy.sort_order), -1)))
    vacancy = Vacancy(
        name_ru=name_ru, name_uz=name_uz, emoji=emoji,
        is_active=1, sort_order=(max_order or -1) + 1, created_at=_now(),
    )
    session.add(vacancy)
    await session.commit()
    return vacancy.id


async def toggle_vacancy(session: AsyncSession, vacancy_id: int) -> bool:
    vacancy = await session.get(Vacancy, vacancy_id)
    if not vacancy:
        return False
    vacancy.is_active = 1 - vacancy.is_active
    await session.commit()
    return bool(vacancy.is_active)


async def delete_vacancy(session: AsyncSession, vacancy_id: int) -> None:
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy:
        await session.delete(vacancy)
        await session.commit()


async def get_vacancy_by_id(session: AsyncSession, vacancy_id: int) -> dict | None:
    vacancy = await session.get(Vacancy, vacancy_id)
    return _to_dict(vacancy) if vacancy else None


async def update_vacancy(
    session: AsyncSession,
    vacancy_id: int,
    name_ru: str | None = None,
    name_uz: str | None = None,
    emoji: str | None = None,
) -> bool:
    """Обновляет поля вакансии. Возвращает True если запись найдена."""
    vacancy = await session.get(Vacancy, vacancy_id)
    if not vacancy:
        return False
    if name_ru is not None:
        vacancy.name_ru = name_ru
    if name_uz is not None:
        vacancy.name_uz = name_uz
    if emoji is not None:
        vacancy.emoji = emoji
    await session.commit()
    return True


# ── Станции метро ─────────────────────────────────────────────────────────────

async def get_metro_stations_by_line(session: AsyncSession, line: str) -> list[dict]:
    """Возвращает активные станции заданной линии, упорядоченные по sort_order."""
    rows = (await session.scalars(
        select(MetroStation)
        .where(MetroStation.line == line, MetroStation.active == 1)
        .order_by(MetroStation.sort_order)
    )).all()
    return [_to_dict(s) for s in rows]


async def get_all_metro_stations_by_line(session: AsyncSession, line: str) -> list[dict]:
    """Возвращает ВСЕ станции (включая неактивные) заданной линии."""
    rows = (await session.scalars(
        select(MetroStation)
        .where(MetroStation.line == line)
        .order_by(MetroStation.sort_order, MetroStation.id)
    )).all()
    return [_to_dict(s) for s in rows]


async def get_metro_station_by_id(session: AsyncSession, station_id: int) -> dict | None:
    """Возвращает станцию по ID или None."""
    station = await session.get(MetroStation, station_id)
    return _to_dict(station) if station else None


async def get_metro_station_name(
    session: AsyncSession,
    station_id: int | None,
    lang: str = "ru",
) -> str:
    """Возвращает локализованное название станции или «—» если не задано."""
    if station_id is None:
        return "—"
    station = await session.get(MetroStation, station_id)
    if not station:
        return "—"
    return station.name_uz if lang == "uz" else station.name_ru


async def count_metro_stations(
    session: AsyncSession,
    active_only: bool = False,
) -> int:
    """Возвращает количество станций (всех или только активных)."""
    q = select(func.count(MetroStation.id))
    if active_only:
        q = q.where(MetroStation.active == 1)
    return (await session.scalar(q)) or 0


async def add_metro_station(
    session: AsyncSession,
    name_ru: str,
    name_uz: str,
    line: str,
) -> int:
    """Добавляет новую станцию, возвращает её id."""
    max_order = await session.scalar(
        select(func.coalesce(func.max(MetroStation.sort_order), 0))
        .where(MetroStation.line == line)
    )
    station = MetroStation(
        name_ru=name_ru,
        name_uz=name_uz,
        line=line,
        sort_order=(max_order or 0) + 1,
        active=1,
    )
    session.add(station)
    await session.commit()
    return station.id


async def toggle_metro_station(session: AsyncSession, station_id: int) -> bool:
    """Переключает active 0↔1, возвращает новое значение."""
    station = await session.get(MetroStation, station_id)
    if not station:
        return False
    station.active = 1 - station.active
    await session.commit()
    return bool(station.active)


async def delete_metro_station(session: AsyncSession, station_id: int) -> None:
    """Удаляет станцию по ID."""
    station = await session.get(MetroStation, station_id)
    if station:
        await session.delete(station)
        await session.commit()


# ── Пользователи ──────────────────────────────────────────────────────────────

async def register_user(
    session: AsyncSession,
    user_id: int,
    username: str | None,
    first_name: str | None,
    lang: str = "ru",
) -> None:
    user = await session.get(User, user_id)
    if user:
        user.username   = username
        user.first_name = first_name
        user.lang       = lang
    else:
        session.add(User(
            user_id=user_id, username=username,
            first_name=first_name, lang=lang, created_at=_now(),
        ))
    await session.commit()


async def get_user_lang(session: AsyncSession, user_id: int) -> str:
    try:
        lang = await session.scalar(select(User.lang).where(User.user_id == user_id))
        return lang if lang else "ru"
    except Exception as e:
        logger.error("get_user_lang error user=%d: %s", user_id, e, exc_info=True)
        return "ru"


async def get_all_user_ids(session: AsyncSession) -> list[int]:
    try:
        rows = (await session.scalars(select(User.user_id))).all()
        return list(rows)
    except Exception as e:
        logger.error("get_all_user_ids error: %s", e, exc_info=True)
        return []


# ── Чёрный список ─────────────────────────────────────────────────────────────

async def block_user(session: AsyncSession, user_id: int, days: int = 30) -> None:
    entry = await session.get(Blacklist, user_id)
    if entry:
        entry.blocked_at = _now()
        entry.unblock_at = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    else:
        session.add(Blacklist(
            user_id=user_id,
            blocked_at=_now(),
            unblock_at=(datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S"),
        ))
    await session.commit()


async def is_user_blocked(session: AsyncSession, user_id: int) -> bool:
    try:
        row = await session.scalar(
            select(Blacklist.user_id)
            .where(Blacklist.user_id == user_id, Blacklist.unblock_at > _now())
        )
        return row is not None
    except Exception as e:
        logger.error("is_user_blocked error user=%d: %s", user_id, e, exc_info=True)
        return False


async def get_users_to_unblock(session: AsyncSession) -> list[int]:
    try:
        rows = (await session.scalars(
            select(Blacklist.user_id).where(Blacklist.unblock_at <= _now())
        )).all()
        return list(rows)
    except Exception as e:
        logger.error("get_users_to_unblock error: %s", e, exc_info=True)
        return []


async def unblock_user(session: AsyncSession, user_id: int) -> None:
    entry = await session.get(Blacklist, user_id)
    if entry:
        await session.delete(entry)
        await session.commit()


# ── Анкеты ────────────────────────────────────────────────────────────────────

async def save_application(
    session: AsyncSession,
    user_id: int,
    name: str,
    birthday: str,
    phone: str,
    position: str,
    experience: str = "—",
    metro_station_id: int | None = None,
) -> int:
    app = Application(
        user_id=user_id, name=name, birthday=birthday, phone=phone,
        position=position, experience=experience, status="pending",
        metro_station_id=metro_station_id,
        created_at=_now(),
    )
    session.add(app)
    await session.commit()
    return app.id


async def get_application_status(session: AsyncSession, user_id: int) -> str | None:
    try:
        return await session.scalar(
            select(Application.status)
            .where(Application.user_id == user_id)
            .order_by(Application.created_at.desc())
            .limit(1)
        )
    except Exception as e:
        logger.error("get_application_status error user=%d: %s", user_id, e, exc_info=True)
        return None


async def update_application_status(session: AsyncSession, user_id: int, status: str) -> None:
    app_id = await _latest_application_id(session, user_id)
    if app_id is not None:
        app = await session.get(Application, app_id)
        if app:
            app.status = status
            await session.commit()


async def get_applications_by_status(session: AsyncSession, status: str) -> list[dict]:
    rows = (await session.scalars(
        select(Application).where(Application.status == status).order_by(Application.created_at.desc())
    )).all()
    return [_to_dict(a) for a in rows]


async def get_applications_today(session: AsyncSession) -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    rows = (await session.scalars(
        select(Application)
        .where(Application.created_at.like(f"{today}%"))
        .order_by(Application.created_at.desc())
    )).all()
    return [_to_dict(a) for a in rows]


async def get_all_applications(session: AsyncSession) -> list[dict]:
    rows = (await session.scalars(
        select(Application).order_by(Application.created_at.desc())
    )).all()
    return [_to_dict(a) for a in rows]


async def search_applications_by_name(session: AsyncSession, query: str) -> list[dict]:
    rows = (await session.scalars(
        select(Application)
        .where(Application.name.like(f"%{query}%"))
        .order_by(Application.created_at.desc())
        .limit(20)
    )).all()
    return [_to_dict(a) for a in rows]


async def set_interview_time(session: AsyncSession, user_id: int, interview_iso: str) -> None:
    app_id = await _latest_application_id(session, user_id)
    if app_id is not None:
        app = await session.get(Application, app_id)
        if app:
            app.interview_time = interview_iso
            app.reminder_sent  = 0
            await session.commit()


async def get_pending_reminders(session: AsyncSession) -> list[dict]:
    now        = _now()
    in_2_hours = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        result = await session.execute(
            select(Application.id, Application.user_id, Application.interview_time, User.lang)
            .join(User, User.user_id == Application.user_id)
            .where(
                Application.status == "accepted",
                Application.interview_time.is_not(None),
                Application.reminder_sent == 0,
                Application.interview_time <= in_2_hours,
                Application.interview_time > now,
            )
        )
        return [dict(r) for r in result.mappings().all()]
    except Exception as e:
        logger.error("get_pending_reminders error: %s", e, exc_info=True)
        return []


async def mark_reminder_sent(session: AsyncSession, application_id: int) -> None:
    app = await session.get(Application, application_id)
    if app:
        app.reminder_sent = 1
        await session.commit()


async def increment_view_count(session: AsyncSession, user_id: int) -> int:
    app_id = await _latest_application_id(session, user_id)
    if app_id is None:
        return 0
    app = await session.get(Application, app_id)
    if not app:
        return 0
    app.view_count = (app.view_count or 0) + 1
    await session.commit()
    return app.view_count


async def get_stale_pending_applications(session: AsyncSession, days: int = 3) -> list[dict]:
    threshold = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        result = await session.execute(
            select(Application.id, Application.user_id, User.lang)
            .join(User, User.user_id == Application.user_id)
            .where(
                Application.status == "pending",
                Application.notified_pending == 0,
                Application.created_at <= threshold,
            )
        )
        return [dict(r) for r in result.mappings().all()]
    except Exception as e:
        logger.error("get_stale_pending_applications error: %s", e, exc_info=True)
        return []


async def mark_pending_notified(session: AsyncSession, application_id: int) -> None:
    app = await session.get(Application, application_id)
    if app:
        app.notified_pending = 1
        await session.commit()


async def save_hr_score(session: AsyncSession, user_id: int, score: int, comment: str = "") -> None:
    app_id = await _latest_application_id(session, user_id)
    if app_id is not None:
        app = await session.get(Application, app_id)
        if app:
            app.hr_score   = score
            app.hr_comment = comment
            await session.commit()


async def get_score_stats(session: AsyncSession) -> dict:
    try:
        row = (await session.execute(
            select(func.avg(Application.hr_score), func.count(Application.hr_score))
            .where(Application.hr_score.is_not(None))
        )).one()
        return {"avg_score": round(row[0] or 0, 1), "scored_count": row[1] or 0}
    except Exception as e:
        logger.error("get_score_stats error: %s", e, exc_info=True)
        return {"avg_score": 0, "scored_count": 0}


async def get_detailed_score_stats(session: AsyncSession) -> dict:
    try:
        dist_rows = (await session.execute(
            select(Application.hr_score, func.count())
            .where(Application.hr_score.is_not(None))
            .group_by(Application.hr_score)
        )).all()
        distribution = {score: cnt for score, cnt in dist_rows}
        avg_score = await session.scalar(
            select(func.avg(Application.hr_score)).where(Application.hr_score.is_not(None))
        )
        comments = (await session.execute(
            select(Application.name, Application.hr_score, Application.hr_comment)
            .where(Application.hr_comment.is_not(None), Application.hr_comment != "")
            .order_by(Application.created_at.desc())
            .limit(5)
        )).mappings().all()
        return {
            "distribution": distribution,
            "scored_count":  sum(distribution.values()),
            "avg_score":     round(avg_score or 0, 1),
            "top_comments":  [dict(c) for c in comments],
        }
    except Exception as e:
        logger.error("get_detailed_score_stats error: %s", e, exc_info=True)
        return {"distribution": {}, "scored_count": 0, "avg_score": 0, "top_comments": []}


# ── Статистика ────────────────────────────────────────────────────────────────

async def get_stats(session: AsyncSession) -> tuple[int, int]:
    try:
        total_users = await session.scalar(select(func.count(User.user_id)))
        total_apps  = await session.scalar(select(func.count(Application.id)))
        return total_users or 0, total_apps or 0
    except Exception as e:
        logger.error("get_stats error: %s", e, exc_info=True)
        return 0, 0


async def get_dashboard_stats(session: AsyncSession) -> dict:
    today    = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    async def count_where(*conditions) -> int:
        return (await session.scalar(select(func.count(Application.id)).where(*conditions))) or 0

    statuses = {
        s: await count_where(Application.status == s)
        for s in ("pending", "accepted", "rejected", "hold", "hired")
    }
    top_pos = (await session.execute(
        select(Application.position, func.count().label("count"))
        .group_by(Application.position)
        .order_by(func.count().desc())
        .limit(5)
    )).mappings().all()

    total_users = (await session.scalar(select(func.count(User.user_id)))) or 0
    new_today   = (await session.scalar(
        select(func.count(User.user_id)).where(User.created_at.like(f"{today}%"))
    )) or 0
    new_week = (await session.scalar(
        select(func.count(User.user_id)).where(User.created_at >= week_ago)
    )) or 0

    return {
        "total_users":        total_users,
        "new_today":          new_today,
        "new_week":           new_week,
        "total_apps":         await count_where(),
        "interviews_planned": await count_where(
            Application.interview_time.is_not(None), Application.status == "accepted"
        ),
        "interviews_today":   await count_where(
            Application.interview_time.like(f"{today}%"), Application.status == "accepted"
        ),
        "top_positions":      [dict(p) for p in top_pos],
        **statuses,
    }


async def get_weekly_trend(session: AsyncSession) -> list[dict]:
    week_ago = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    rows = (await session.execute(
        select(func.substr(Application.created_at, 1, 10).label("day"), func.count().label("count"))
        .where(Application.created_at >= week_ago)
        .group_by("day")
        .order_by("day")
    )).mappings().all()
    counts_by_day = {r["day"]: r["count"] for r in rows}
    result = []
    for i in range(6, -1, -1):
        dt = datetime.now() - timedelta(days=i)
        result.append({
            "label": dt.strftime("%d.%m"),
            "count": counts_by_day.get(dt.strftime("%Y-%m-%d"), 0),
        })
    return result


async def get_stats_by_position(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(
        select(
            Application.position,
            func.count().label("total"),
            func.sum(case((Application.status == "accepted", 1), else_=0)).label("accepted"),
        )
        .group_by(Application.position)
        .order_by(func.count().desc())
    )).mappings().all()
    return [dict(r) for r in rows]


# ── Видео-визитка HR ──────────────────────────────────────────────────────────

async def save_hr_video_msg_id(session: AsyncSession, user_id: int, msg_id: int) -> None:
    app_id = await _latest_application_id(session, user_id)
    if app_id is not None:
        app = await session.get(Application, app_id)
        if app:
            app.hr_video_msg_id = msg_id
            await session.commit()


async def get_latest_application(session: AsyncSession, user_id: int) -> dict | None:
    try:
        app = await session.scalar(
            select(Application)
            .where(Application.user_id == user_id)
            .order_by(Application.created_at.desc())
            .limit(1)
        )
        return _to_dict(app) if app else None
    except Exception as e:
        logger.error("get_latest_application error user=%d: %s", user_id, e, exc_info=True)
        return None


# ── AI-интервью ────────────────────────────────────────────────────────────────

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
    resume: "dict | str | None" = None,
    communication: "dict | str | None" = None,
    integrity: "dict | str | None" = None,
    job_match: "dict | str | None" = None,
    decision: "dict | str | None" = None,
    total_score: float | None = None,
    summary: str | None = None,
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
    obj.report_skills        = skills
    obj.report_personality   = personality

    await session.commit()
