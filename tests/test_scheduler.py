"""Tests for the background reminder/notification jobs
(bot/services/scheduler.py): interview reminders, stale-application nudges,
and automatic blacklist expiry.

We use an in-memory SQLite database with the real SQLAlchemy models (no
mocking of DB/business logic) and a fake aiogram Bot that records outbound
messages instead of calling the real Telegram API. `bot.db.base.session_pool`
is monkeypatched (via monkeypatch fixture) to point at the in-memory test
database, since these service functions open their own sessions internally
rather than receiving one as an argument.

Required settings env vars are injected *before* importing any bot module,
since `bot.core.config.Settings()` is instantiated at import time and
requires `BOT_TOKEN` / `ADMIN_IDS` to be present.
"""

import os

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import bot.db.base as db_base
from bot.db import requests as db
from bot.db.base import Base
from bot.services import scheduler


@pytest_asyncio.fixture
async def test_session_pool(monkeypatch: pytest.MonkeyPatch):
    """Points bot.db.base.session_pool at a fresh in-memory SQLite database
    and patches the scheduler module's reference to it, since scheduler
    functions call `session_pool()` directly rather than accepting a session.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    pool = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_base, "session_pool", pool)
    monkeypatch.setattr(scheduler, "session_pool", pool)

    yield pool

    await engine.dispose()


class FakeBot:
    """Records outgoing Telegram calls; can simulate blocked users."""

    def __init__(self, forbidden_for: set | None = None) -> None:
        self.forbidden_for = forbidden_for or set()
        self.sent_messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        if chat_id in self.forbidden_for:
            raise TelegramForbiddenError(method="sendMessage", message="bot was blocked")
        self.sent_messages.append((chat_id, text))


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# ── bot/services/scheduler.py: _format_interview_time ───────────────────────


def test_format_interview_time_russian_style() -> None:
    text = scheduler._format_interview_time("2026-08-10 14:30", lang="ru")
    assert text == "10.08.2026 в 14:30"


def test_format_interview_time_uzbek_style() -> None:
    text = scheduler._format_interview_time("2026-08-10 14:30", lang="uz")
    assert text == "10.08.2026, 14:30"


def test_format_interview_time_returns_raw_on_unparseable_input() -> None:
    text = scheduler._format_interview_time("not-a-date", lang="ru")
    assert text == "not-a-date"


# ── bot/services/scheduler.py: send_interview_reminders ─────────────────────


@pytest.mark.asyncio
async def test_send_interview_reminders_notifies_candidates_due_soon(test_session_pool) -> None:
    async with test_session_pool() as session:
        await db.register_user(session, user_id=1, username="a", first_name="A", lang="ru")
        await db.save_application(
            session, user_id=1, name="Alice", birthday="01.01.2000",
            phone="+998900000001", position="Повар",
        )
        soon = _fmt(datetime.now() + timedelta(hours=1))
        await db.set_interview_time(session, user_id=1, interview_iso=soon)

    bot = FakeBot()
    await scheduler.send_interview_reminders(bot)

    assert len(bot.sent_messages) == 1
    assert bot.sent_messages[0][0] == 1

    async with test_session_pool() as session:
        pending = await db.get_pending_reminders(session)
    assert pending == []  # marked as sent, won't be reminded again


@pytest.mark.asyncio
async def test_send_interview_reminders_skips_interviews_too_far_in_future(test_session_pool) -> None:
    async with test_session_pool() as session:
        await db.register_user(session, user_id=2, username="b", first_name="B", lang="ru")
        await db.save_application(
            session, user_id=2, name="Bob", birthday="01.01.2000",
            phone="+998900000002", position="Официант",
        )
        far_future = _fmt(datetime.now() + timedelta(days=5))
        await db.set_interview_time(session, user_id=2, interview_iso=far_future)

    bot = FakeBot()
    await scheduler.send_interview_reminders(bot)

    assert bot.sent_messages == []


@pytest.mark.asyncio
async def test_send_interview_reminders_marks_sent_even_when_delivery_blocked(test_session_pool) -> None:
    async with test_session_pool() as session:
        await db.register_user(session, user_id=3, username="c", first_name="C", lang="ru")
        await db.save_application(
            session, user_id=3, name="Cara", birthday="01.01.2000",
            phone="+998900000003", position="Кассир",
        )
        soon = _fmt(datetime.now() + timedelta(hours=1))
        await db.set_interview_time(session, user_id=3, interview_iso=soon)

    bot = FakeBot(forbidden_for={3})
    await scheduler.send_interview_reminders(bot)

    assert bot.sent_messages == []
    async with test_session_pool() as session:
        pending = await db.get_pending_reminders(session)
    assert pending == []  # still marked sent despite the delivery failure


# ── bot/services/scheduler.py: notify_stale_applications ────────────────────


@pytest.mark.asyncio
async def test_notify_stale_applications_notifies_old_pending_candidates(test_session_pool) -> None:
    async with test_session_pool() as session:
        await db.register_user(session, user_id=4, username="d", first_name="D", lang="ru")
        await db.save_application(
            session, user_id=4, name="Dan", birthday="01.01.2000",
            phone="+998900000004", position="Хостес",
        )
        # Backdate creation so it looks like it's been pending for 4 days.
        from bot.db.models.application import Application
        app = await session.get(Application, (await db._latest_application_id(session, 4)))
        app.created_at = _fmt(datetime.now() - timedelta(days=4))
        await session.commit()

    bot = FakeBot()
    await scheduler.notify_stale_applications(bot)

    assert len(bot.sent_messages) == 1
    assert bot.sent_messages[0][0] == 4


@pytest.mark.asyncio
async def test_notify_stale_applications_skips_recent_applications(test_session_pool) -> None:
    async with test_session_pool() as session:
        await db.register_user(session, user_id=5, username="e", first_name="E", lang="ru")
        await db.save_application(
            session, user_id=5, name="Eve", birthday="01.01.2000",
            phone="+998900000005", position="Бариста",
        )

    bot = FakeBot()
    await scheduler.notify_stale_applications(bot)

    assert bot.sent_messages == []


# ── bot/services/scheduler.py: auto_unblock_users ───────────────────────────


@pytest.mark.asyncio
async def test_auto_unblock_users_unblocks_and_notifies_expired_entries(test_session_pool) -> None:
    async with test_session_pool() as session:
        await db.register_user(session, user_id=6, username="f", first_name="F", lang="ru")
        await db.block_user(session, user_id=6, days=30)
        # Force the unblock date into the past.
        from bot.db.models.blacklist import Blacklist
        entry = await session.get(Blacklist, 6)
        entry.unblock_at = _fmt(datetime.now() - timedelta(days=1))
        await session.commit()

    bot = FakeBot()
    await scheduler.auto_unblock_users(bot)

    assert len(bot.sent_messages) == 1
    assert bot.sent_messages[0][0] == 6

    async with test_session_pool() as session:
        assert await db.is_user_blocked(session, 6) is False


@pytest.mark.asyncio
async def test_auto_unblock_users_leaves_still_blocked_users_untouched(test_session_pool) -> None:
    async with test_session_pool() as session:
        await db.register_user(session, user_id=7, username="g", first_name="G", lang="ru")
        await db.block_user(session, user_id=7, days=30)

    bot = FakeBot()
    await scheduler.auto_unblock_users(bot)

    assert bot.sent_messages == []
    async with test_session_pool() as session:
        assert await db.is_user_blocked(session, 7) is True
