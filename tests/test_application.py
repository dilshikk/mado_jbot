"""Tests for application/vacancy management and reporting
(bot/db/requests.py: vacancies, HR scoring, reminders, dashboard stats).

Uses an in-memory SQLite database so tests run in isolation without touching
the real bot database. Required settings env vars are injected *before*
importing any bot module, since `bot.core.config.Settings()` is instantiated
at import time and requires `BOT_TOKEN` / `ADMIN_IDS` to be present.
"""

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


# ── Вакансии ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_vacancy_appears_in_active_and_all(session: AsyncSession) -> None:
    vacancy_id = await db.add_vacancy(session, name_ru="Повар", name_uz="Oshpaz", emoji="👨‍🍳")

    active = await db.get_active_vacancies(session)
    all_vacancies = await db.get_all_vacancies(session)

    assert any(v["id"] == vacancy_id for v in active)
    assert any(v["id"] == vacancy_id for v in all_vacancies)


@pytest.mark.asyncio
async def test_toggle_vacancy_removes_from_active_list(session: AsyncSession) -> None:
    vacancy_id = await db.add_vacancy(session, name_ru="Повар", name_uz="Oshpaz")

    is_active = await db.toggle_vacancy(session, vacancy_id)
    assert is_active is False

    active = await db.get_active_vacancies(session)
    assert not any(v["id"] == vacancy_id for v in active)

    all_vacancies = await db.get_all_vacancies(session)
    assert any(v["id"] == vacancy_id for v in all_vacancies)


@pytest.mark.asyncio
async def test_toggle_vacancy_returns_false_for_unknown_id(session: AsyncSession) -> None:
    result = await db.toggle_vacancy(session, vacancy_id=999)
    assert result is False


@pytest.mark.asyncio
async def test_update_vacancy_changes_fields(session: AsyncSession) -> None:
    vacancy_id = await db.add_vacancy(session, name_ru="Повар", name_uz="Oshpaz", emoji="👨‍🍳")

    updated = await db.update_vacancy(session, vacancy_id, name_ru="Су-шеф", emoji="🔪")
    assert updated is True

    vacancy = await db.get_vacancy_by_id(session, vacancy_id)
    assert vacancy is not None
    assert vacancy["name_ru"] == "Су-шеф"
    assert vacancy["emoji"] == "🔪"
    assert vacancy["name_uz"] == "Oshpaz"  # unchanged


@pytest.mark.asyncio
async def test_delete_vacancy_removes_it(session: AsyncSession) -> None:
    vacancy_id = await db.add_vacancy(session, name_ru="Повар", name_uz="Oshpaz")

    await db.delete_vacancy(session, vacancy_id)

    vacancy = await db.get_vacancy_by_id(session, vacancy_id)
    assert vacancy is None


# ── HR-оценки и статистика по анкетам ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_hr_score_updates_latest_application(session: AsyncSession) -> None:
    await _register(session)
    await db.save_application(
        session, user_id=1, name="Alice", birthday="2000-01-01",
        phone="+998900000001", position="Повар",
    )

    await db.save_hr_score(session, user_id=1, score=8, comment="Хороший кандидат")

    latest = await db.get_latest_application(session, user_id=1)
    assert latest is not None
    assert latest["hr_score"] == 8
    assert latest["hr_comment"] == "Хороший кандидат"


@pytest.mark.asyncio
async def test_get_score_stats_computes_average(session: AsyncSession) -> None:
    await _register(session, user_id=1)
    await _register(session, user_id=2)
    await db.save_application(
        session, user_id=1, name="Alice", birthday="2000-01-01",
        phone="+998900000001", position="Повар",
    )
    await db.save_application(
        session, user_id=2, name="Bob", birthday="1999-01-01",
        phone="+998900000002", position="Официант",
    )
    await db.save_hr_score(session, user_id=1, score=8)
    await db.save_hr_score(session, user_id=2, score=6)

    stats = await db.get_score_stats(session)
    assert stats["scored_count"] == 2
    assert stats["avg_score"] == 7.0


@pytest.mark.asyncio
async def test_increment_view_count_increases_on_each_call(session: AsyncSession) -> None:
    await _register(session)
    await db.save_application(
        session, user_id=1, name="Alice", birthday="2000-01-01",
        phone="+998900000001", position="Повар",
    )

    first = await db.increment_view_count(session, user_id=1)
    second = await db.increment_view_count(session, user_id=1)

    assert first == 1
    assert second == 2


@pytest.mark.asyncio
async def test_increment_view_count_returns_zero_when_no_application(
    session: AsyncSession,
) -> None:
    await _register(session)

    count = await db.increment_view_count(session, user_id=1)
    assert count == 0


@pytest.mark.asyncio
async def test_get_applications_today_filters_by_date(session: AsyncSession) -> None:
    await _register(session)
    await db.save_application(
        session, user_id=1, name="Alice", birthday="2000-01-01",
        phone="+998900000001", position="Повар",
    )

    today_apps = await db.get_applications_today(session)
    assert len(today_apps) == 1
    assert today_apps[0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_search_applications_by_name_matches_substring(session: AsyncSession) -> None:
    await _register(session, user_id=1)
    await _register(session, user_id=2)
    await db.save_application(
        session, user_id=1, name="Alice Smith", birthday="2000-01-01",
        phone="+998900000001", position="Повар",
    )
    await db.save_application(
        session, user_id=2, name="Bob Jones", birthday="1999-01-01",
        phone="+998900000002", position="Официант",
    )

    results = await db.search_applications_by_name(session, query="Alice")
    assert len(results) == 1
    assert results[0]["name"] == "Alice Smith"


@pytest.mark.asyncio
async def test_get_dashboard_stats_counts_totals(session: AsyncSession) -> None:
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
    await db.update_application_status(session, user_id=2, status="accepted")

    stats = await db.get_dashboard_stats(session)
    assert stats["total_users"] == 2
    assert stats["total_apps"] == 2
    assert stats["pending"] == 1
    assert stats["accepted"] == 1
    assert stats["top_positions"][0]["position"] == "Повар"
    assert stats["top_positions"][0]["count"] == 2


@pytest.mark.asyncio
async def test_set_interview_time_and_pending_reminders(session: AsyncSession) -> None:
    await _register(session)
    await db.save_application(
        session, user_id=1, name="Alice", birthday="2000-01-01",
        phone="+998900000001", position="Повар",
    )
    await db.update_application_status(session, user_id=1, status="accepted")

    soon = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    await db.set_interview_time(session, user_id=1, interview_iso=soon)

    reminders = await db.get_pending_reminders(session)
    assert len(reminders) == 1
    assert reminders[0]["user_id"] == 1


@pytest.mark.asyncio
async def test_mark_reminder_sent_excludes_from_pending(session: AsyncSession) -> None:
    await _register(session)
    app_id = await db.save_application(
        session, user_id=1, name="Alice", birthday="2000-01-01",
        phone="+998900000001", position="Повар",
    )
    await db.update_application_status(session, user_id=1, status="accepted")
    soon = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    await db.set_interview_time(session, user_id=1, interview_iso=soon)

    await db.mark_reminder_sent(session, application_id=app_id)

    reminders = await db.get_pending_reminders(session)
    assert reminders == []
