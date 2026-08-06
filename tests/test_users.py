"""Tests for user-related database operations (bot/db/requests.py + bot/db/models/user.py).

Uses an in-memory SQLite database so tests run in isolation without touching
the real bot database. Required settings env vars are injected *before*
importing any bot module, since `bot.core.config.Settings()` is instantiated
at import time and requires `BOT_TOKEN` / `ADMIN_IDS` to be present.
"""

import os

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


@pytest.mark.asyncio
async def test_register_user_creates_new_user(session: AsyncSession) -> None:
    await db.register_user(session, user_id=1, username="alice", first_name="Alice", lang="ru")

    lang = await db.get_user_lang(session, user_id=1)
    assert lang == "ru"

    user_ids = await db.get_all_user_ids(session)
    assert user_ids == [1]


@pytest.mark.asyncio
async def test_register_user_updates_existing_user(session: AsyncSession) -> None:
    await db.register_user(session, user_id=1, username="alice", first_name="Alice", lang="ru")
    await db.register_user(session, user_id=1, username="alice_new", first_name="Alice N.", lang="uz")

    lang = await db.get_user_lang(session, user_id=1)
    assert lang == "uz"

    # Still only one row for this user_id after update
    user_ids = await db.get_all_user_ids(session)
    assert user_ids == [1]


@pytest.mark.asyncio
async def test_get_user_lang_defaults_to_ru_for_unknown_user(session: AsyncSession) -> None:
    lang = await db.get_user_lang(session, user_id=999)
    assert lang == "ru"


@pytest.mark.asyncio
async def test_get_all_user_ids_empty_by_default(session: AsyncSession) -> None:
    user_ids = await db.get_all_user_ids(session)
    assert user_ids == []


@pytest.mark.asyncio
async def test_block_and_check_user(session: AsyncSession) -> None:
    await db.register_user(session, user_id=1, username="bob", first_name="Bob")

    assert await db.is_user_blocked(session, user_id=1) is False

    await db.block_user(session, user_id=1, days=30)
    assert await db.is_user_blocked(session, user_id=1) is True


@pytest.mark.asyncio
async def test_unblock_user_removes_block(session: AsyncSession) -> None:
    await db.register_user(session, user_id=1, username="bob", first_name="Bob")
    await db.block_user(session, user_id=1, days=30)
    assert await db.is_user_blocked(session, user_id=1) is True

    await db.unblock_user(session, user_id=1)
    assert await db.is_user_blocked(session, user_id=1) is False


@pytest.mark.asyncio
async def test_get_users_to_unblock_returns_expired_blocks(session: AsyncSession) -> None:
    await db.register_user(session, user_id=1, username="bob", first_name="Bob")

    # Block with 0 days -> unblock_at is now, should already be eligible for unblocking.
    await db.block_user(session, user_id=1, days=0)

    expired = await db.get_users_to_unblock(session)
    assert 1 in expired


@pytest.mark.asyncio
async def test_get_stats_counts_users(session: AsyncSession) -> None:
    await db.register_user(session, user_id=1, username="alice", first_name="Alice")
    await db.register_user(session, user_id=2, username="bob", first_name="Bob")

    total_users, total_apps = await db.get_stats(session)
    assert total_users == 2
    assert total_apps == 0
