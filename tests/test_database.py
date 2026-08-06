"""Tests for lower-level database operations not covered by the other test
modules: metro stations, the blacklist expiry logic, AI interview sessions,
and cross-cutting statistics helpers (bot/db/requests.py, bot/db/base.py).

Uses an in-memory SQLite database so tests run in isolation without touching
the real bot database. Required settings env vars are injected *before*
importing any bot module, since `bot.core.config.Settings()` is instantiated
at import time and requires `BOT_TOKEN` / `ADMIN_IDS` to be present.
"""

import json
import os
from datetime import datetime, timedelta

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.db.base import Base
from bot.db import requests as db


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """Fresh in-memory SQLite database with all tables created for each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_pool = async_sessionmaker(engine, expire_on_commit=False)
    async with session_pool() as db_session:
        yield db_session

    await engine.dispose()


async def _register(session: AsyncSession, user_id: int = 1) -> None:
    await db.register_user(
        session, user_id=user_id, username="alice", first_name="Alice", lang="ru"
    )


# ── Станции метро ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_metro_station_assigns_incrementing_sort_order(
    session: AsyncSession,
) -> None:
    first_id = await db.add_metro_station(session, name_ru="Чиланзар", name_uz="Chilonzor", line="red")
    second_id = await db.add_metro_station(session, name_ru="Бунёдкор", name_uz="Bunyodkor", line="red")

    first = await db.get_metro_station_by_id(session, first_id)
    second = await db.get_metro_station_by_id(session, second_id)

    assert first is not None and second is not None
    assert second["sort_order"] > first["sort_order"]


@pytest.mark.asyncio
async def test_get_metro_stations_by_line_filters_active_only(session: AsyncSession) -> None:
    red_id = await db.add_metro_station(session, name_ru="Чиланзар", name_uz="Chilonzor", line="red")
    await db.add_metro_station(session, name_ru="Тошкент", name_uz="Toshkent", line="blue")

    await db.toggle_metro_station(session, red_id)  # deactivate

    red_active = await db.get_metro_stations_by_line(session, line="red")
    red_all = await db.get_all_metro_stations_by_line(session, line="red")

    assert red_active == []
    assert len(red_all) == 1


@pytest.mark.asyncio
async def test_get_metro_station_name_uses_language(session: AsyncSession) -> None:
    station_id = await db.add_metro_station(
        session, name_ru="Чиланзар", name_uz="Chilonzor", line="red"
    )

    name_ru = await db.get_metro_station_name(session, station_id, lang="ru")
    name_uz = await db.get_metro_station_name(session, station_id, lang="uz")

    assert name_ru == "Чиланзар"
    assert name_uz == "Chilonzor"


@pytest.mark.asyncio
async def test_get_metro_station_name_returns_placeholder_for_missing_id(
    session: AsyncSession,
) -> None:
    assert await db.get_metro_station_name(session, None) == "—"
    assert await db.get_metro_station_name(session, 999) == "—"


@pytest.mark.asyncio
async def test_count_metro_stations_respects_active_only_flag(session: AsyncSession) -> None:
    red_id = await db.add_metro_station(session, name_ru="Чиланзар", name_uz="Chilonzor", line="red")
    await db.add_metro_station(session, name_ru="Тошкент", name_uz="Toshkent", line="blue")
    await db.toggle_metro_station(session, red_id)  # deactivate one

    assert await db.count_metro_stations(session) == 2
    assert await db.count_metro_stations(session, active_only=True) == 1


@pytest.mark.asyncio
async def test_delete_metro_station_removes_it(session: AsyncSession) -> None:
    station_id = await db.add_metro_station(
        session, name_ru="Чиланзар", name_uz="Chilonzor", line="red"
    )

    await db.delete_metro_station(session, station_id)

    assert await db.get_metro_station_by_id(session, station_id) is None


# ── Чёрный список ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_block_user_sets_blocked_until_expiry(session: AsyncSession) -> None:
    await _register(session)

    await db.block_user(session, user_id=1, days=30)

    assert await db.is_user_blocked(session, user_id=1) is True


@pytest.mark.asyncio
async def test_is_user_blocked_false_after_unblock_window_passed(
    session: AsyncSession,
) -> None:
    await _register(session)
    await db.block_user(session, user_id=1, days=30)

    # Simulate the block having already expired by rewriting unblock_at to the past.
    from bot.db.models.blacklist import Blacklist

    entry = await session.get(Blacklist, 1)
    assert entry is not None
    entry.unblock_at = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    await session.commit()

    assert await db.is_user_blocked(session, user_id=1) is False


@pytest.mark.asyncio
async def test_get_users_to_unblock_returns_expired_entries(session: AsyncSession) -> None:
    await _register(session, user_id=1)
    await db.block_user(session, user_id=1, days=30)

    from bot.db.models.blacklist import Blacklist

    entry = await session.get(Blacklist, 1)
    assert entry is not None
    entry.unblock_at = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    await session.commit()

    to_unblock = await db.get_users_to_unblock(session)
    assert to_unblock == [1]


@pytest.mark.asyncio
async def test_unblock_user_removes_blacklist_entry(session: AsyncSession) -> None:
    await _register(session)
    await db.block_user(session, user_id=1, days=30)

    await db.unblock_user(session, user_id=1)

    assert await db.is_user_blocked(session, user_id=1) is False


# ── AI-интервью ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_interview_session_starts_active_with_empty_log(
    session: AsyncSession,
) -> None:
    await _register(session)

    session_id = await db.create_interview_session(session, user_id=1)

    interview = await db.get_interview_session(session, session_id)
    assert interview is not None
    assert interview["status"] == "active"
    assert json.loads(interview["qa_log"]) == []
    assert interview["q_count"] == 0


@pytest.mark.asyncio
async def test_append_qa_updates_log_and_count(session: AsyncSession) -> None:
    await _register(session)
    session_id = await db.create_interview_session(session, user_id=1)

    qa_log = [{"q": "Почему хотите работать в MADO?", "a": "Люблю рестораны"}]
    await db.append_qa(session, session_id, qa_log)

    interview = await db.get_interview_session(session, session_id)
    assert interview is not None
    assert json.loads(interview["qa_log"]) == qa_log
    assert interview["q_count"] == 1


@pytest.mark.asyncio
async def test_update_interview_session_changes_status_and_count(
    session: AsyncSession,
) -> None:
    await _register(session)
    session_id = await db.create_interview_session(session, user_id=1)

    await db.update_interview_session(session, session_id, q_count=5, status="done")

    interview = await db.get_interview_session(session, session_id)
    assert interview is not None
    assert interview["q_count"] == 5
    assert interview["status"] == "done"


@pytest.mark.asyncio
async def test_save_interview_reports_persists_all_fields(session: AsyncSession) -> None:
    await _register(session)
    session_id = await db.create_interview_session(session, user_id=1)

    await db.save_interview_reports(
        session,
        session_id=session_id,
        finished_at="2026-01-01 12:00:00",
        resume={"candidate": {"name": "Alice"}},
        decision={"decision": "invite"},
        total_score=8.5,
        summary="Хороший кандидат",
    )

    interview = await db.get_interview_session(session, session_id)
    assert interview is not None
    assert interview["status"] == "done"
    assert interview["total_score"] == 8.5
    assert interview["report_summary"] == "Хороший кандидат"
    assert json.loads(interview["report_resume"]) == {"candidate": {"name": "Alice"}}
    assert json.loads(interview["report_decision"]) == {"decision": "invite"}


@pytest.mark.asyncio
async def test_save_interview_reports_is_idempotent(session: AsyncSession) -> None:
    await _register(session)
    session_id = await db.create_interview_session(session, user_id=1)

    await db.save_interview_reports(
        session,
        session_id=session_id,
        finished_at="2026-01-01 12:00:00",
        decision={"decision": "invite"},
        total_score=8.5,
        summary="Первый отчёт",
    )
    # A second call must be ignored since report_decision is already set.
    await db.save_interview_reports(
        session,
        session_id=session_id,
        finished_at="2026-01-02 12:00:00",
        decision={"decision": "reject"},
        total_score=1.0,
        summary="Второй отчёт",
    )

    interview = await db.get_interview_session(session, session_id)
    assert interview is not None
    assert interview["total_score"] == 8.5
    assert interview["report_summary"] == "Первый отчёт"


# ── Дополнительная статистика ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_stats_by_position_counts_accepted(session: AsyncSession) -> None:
    await _register(session, user_id=1)
    await _register(session, user_id=2)
    await db.save_application(
        session, user_id=1, name="Alice", birthday="2000-01-01",
        phone="+998900000001", position="Повар",
    )
    await db.save_application(
        session, user_id=2, name="Bob", birthday="1999-01-01",
        phone="+998900000002", position="Повар",
    )
    await db.update_application_status(session, user_id=1, status="accepted")

    stats = await db.get_stats_by_position(session)
    powar_stats = next(s for s in stats if s["position"] == "Повар")

    assert powar_stats["total"] == 2
    assert powar_stats["accepted"] == 1


@pytest.mark.asyncio
async def test_get_weekly_trend_returns_seven_days(session: AsyncSession) -> None:
    await _register(session)
    await db.save_application(
        session, user_id=1, name="Alice", birthday="2000-01-01",
        phone="+998900000001", position="Повар",
    )

    trend = await db.get_weekly_trend(session)

    assert len(trend) == 7
    assert sum(day["count"] for day in trend) == 1


@pytest.mark.asyncio
async def test_get_stale_pending_applications_finds_old_unnotified(
    session: AsyncSession,
) -> None:
    await _register(session)
    app_id = await db.save_application(
        session, user_id=1, name="Alice", birthday="2000-01-01",
        phone="+998900000001", position="Повар",
    )

    # Backdate the application so it looks like it was submitted 5 days ago.
    from bot.db.models.application import Application

    app = await session.get(Application, app_id)
    assert app is not None
    app.created_at = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    await session.commit()

    stale = await db.get_stale_pending_applications(session, days=3)
    assert len(stale) == 1
    assert stale[0]["user_id"] == 1


@pytest.mark.asyncio
async def test_mark_pending_notified_excludes_from_stale_list(
    session: AsyncSession,
) -> None:
    await _register(session)
    app_id = await db.save_application(
        session, user_id=1, name="Alice", birthday="2000-01-01",
        phone="+998900000001", position="Повар",
    )

    from bot.db.models.application import Application

    app = await session.get(Application, app_id)
    assert app is not None
    app.created_at = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    await session.commit()

    await db.mark_pending_notified(session, application_id=app_id)

    stale = await db.get_stale_pending_applications(session, days=3)
    assert stale == []
