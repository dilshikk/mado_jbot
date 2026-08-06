"""Tests for the candidate registration/application flow
(bot/db/requests.py: save_application, get_application_status,
update_application_status, get_latest_application).

Uses an in-memory SQLite database so tests run in isolation without touching
the real bot database. Required settings env vars are injected *before*
importing any bot module, since `bot.core.config.Settings()` is instantiated
at import time and requires `BOT_TOKEN` / `ADMIN_IDS` to be present.
"""

import os

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.db.base import Base
from bot.db import requests as db
from bot.db.models.application import Application

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

@pytest.mark.asyncio
async def test_save_application_creates_pending_application(session: AsyncSession) -> None:
    await _register(session)

    app_id = await db.save_application(
        session,
        user_id=1,
        name="Alice Smith",
        birthday="2000-01-01",
        phone="+998901234567",
        position="Повар",
    )

    assert app_id is not None

    status = await db.get_application_status(session, user_id=1)
    assert status == "pending"

@pytest.mark.asyncio
async def test_get_application_status_returns_none_when_no_application(
    session: AsyncSession,
) -> None:
    await _register(session)

    status = await db.get_application_status(session, user_id=1)
    assert status is None

@pytest.mark.asyncio
async def test_update_application_status_updates_latest_application(
    session: AsyncSession,
) -> None:
    await _register(session)
    await db.save_application(
        session,
        user_id=1,
        name="Alice Smith",
        birthday="2000-01-01",
        phone="+998901234567",
        position="Повар",
    )

    await db.update_application_status(session, user_id=1, status="accepted")

    status = await db.get_application_status(session, user_id=1)
    assert status == "accepted"

@pytest.mark.asyncio
async def test_update_application_status_noop_when_no_application(
    session: AsyncSession,
) -> None:
    await _register(session)

    # Should not raise even though there is no application for this user.
    await db.update_application_status(session, user_id=1, status="accepted")

    status = await db.get_application_status(session, user_id=1)
    assert status is None

@pytest.mark.asyncio
async def test_get_latest_application_returns_most_recent_submission(
    session: AsyncSession,
) -> None:
    await _register(session)

    first_id = await db.save_application(
        session,
        user_id=1,
        name="Alice Smith",
        birthday="2000-01-01",
        phone="+998901234567",
        position="Повар",
    )
    second_id = await db.save_application(
        session,
        user_id=1,
        name="Alice Smith",
        birthday="2000-01-01",
        phone="+998901234567",
        position="Официант",
    )

    second_app = await session.get(Application, second_id)
    assert second_app is not None
    first_app = await session.get(Application, first_id)
    assert first_app is not None

    # Сдвигаем created_at второй анкеты на 1 секунду вперёд через timedelta,
    # чтобы гарантировать правильный порядок независимо от последней цифры.
    dt = datetime.strptime(first_app.created_at, "%Y-%m-%d %H:%M:%S")
    second_app.created_at = (dt + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
    await session.commit()

    latest = await db.get_latest_application(session, user_id=1)
    assert latest is not None
    assert latest["id"] == second_id
    assert latest["position"] == "Официант"

@pytest.mark.asyncio
async def test_get_latest_application_returns_none_when_none_exist(
    session: AsyncSession,
) -> None:
    await _register(session)

    latest = await db.get_latest_application(session, user_id=1)
    assert latest is None

@pytest.mark.asyncio
async def test_save_application_with_metro_station(session: AsyncSession) -> None:
    await _register(session)

    station_id = await db.add_metro_station(
        session, name_ru="Чиланзар", name_uz="Chilonzor", line="red"
    )
    await db.save_application(
        session,
        user_id=1,
        name="Alice Smith",
        birthday="2000-01-01",
        phone="+998901234567",
        position="Повар",
        metro_station_id=station_id,
    )

    latest = await db.get_latest_application(session, user_id=1)
    assert latest is not None
    assert latest["metro_station_id"] == station_id

@pytest.mark.asyncio
async def test_get_applications_by_status_filters_correctly(session: AsyncSession) -> None:
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
    await db.update_application_status(session, user_id=2, status="accepted")

    pending = await db.get_applications_by_status(session, status="pending")
    accepted = await db.get_applications_by_status(session, status="accepted")

    assert len(pending) == 1
    assert pending[0]["name"] == "Alice"
    assert len(accepted) == 1
    assert accepted[0]["name"] == "Bob"
