"""Tests for the aiogram middleware stack: database session injection,
language resolution, and the required-channel subscription gate
(bot/middlewares/db.py, bot/middlewares/localization.py, bot/middlewares/auth.py).

We build minimal aiogram `Message`/`CallbackQuery` objects with
`model_construct` (bypasses pydantic validation) since only specific
attributes are read by the middlewares under test.

Required settings env vars are injected *before* importing any bot module,
since `bot.core.config.Settings()` is instantiated at import time and
requires `BOT_TOKEN` / `ADMIN_IDS` to be present. `REQUIRED_CHANNEL` is left
unset (default ""), which makes the subscription gate a no-op — exactly the
behavior exercised by most tests below, with no real Telegram API calls.
"""

import os

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
import pytest_asyncio
from aiogram.types import CallbackQuery, Chat, Message, User
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.core.config import settings
from bot.db import requests as db
from bot.db.base import Base
from bot.middlewares.auth import SubscriptionMiddleware, is_subscribed
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.localization import LangMiddleware


def _make_user(user_id: int) -> User:
    return User.model_construct(id=user_id, is_bot=False, first_name="Test")


def _make_message(user_id: int, chat_type: str = "private", text: str | None = None) -> Message:
    chat = Chat.model_construct(id=user_id, type=chat_type)
    return Message.model_construct(
        message_id=1,
        date=0,
        chat=chat,
        from_user=_make_user(user_id),
        text=text,
    )


def _make_callback(user_id: int, chat_type: str = "private", data: str = "anything") -> CallbackQuery:
    message = _make_message(user_id, chat_type=chat_type)
    return CallbackQuery.model_construct(
        id="cb1",
        from_user=_make_user(user_id),
        chat_instance="ci",
        message=message,
        data=data,
    )


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


# ── bot/middlewares/db.py: DbSessionMiddleware ──────────────────────────────


@pytest.mark.asyncio
async def test_db_session_middleware_injects_session_into_data() -> None:
    middleware = DbSessionMiddleware()
    message = _make_message(user_id=1)
    captured: dict = {}

    async def handler(event, data):
        captured["session"] = data.get("session")
        return "handled"

    result = await middleware(handler, message, {})

    assert result == "handled"
    assert isinstance(captured["session"], AsyncSession)


@pytest.mark.asyncio
async def test_db_session_middleware_closes_session_after_handler() -> None:
    middleware = DbSessionMiddleware()
    message = _make_message(user_id=1)
    captured: dict = {}

    async def handler(event, data):
        captured["session"] = data["session"]
        return "handled"

    await middleware(handler, message, {})

    # The session's underlying connection should be closed once the
    # `async with session_pool()` context in the middleware exits.
    assert captured["session"].is_active is False


# ── bot/middlewares/localization.py: LangMiddleware ─────────────────────────


@pytest.mark.asyncio
async def test_lang_middleware_prefers_db_language(session: AsyncSession) -> None:
    await db.register_user(session, user_id=1, username="alice", first_name="Alice", lang="uz")
    middleware = LangMiddleware()
    message = _make_message(user_id=1)
    captured: dict = {}

    async def handler(event, data):
        captured["lang"] = data["lang"]

    await middleware(handler, message, {"session": session})

    assert captured["lang"] == "uz"


@pytest.mark.asyncio
async def test_lang_middleware_falls_back_to_fsm_state_when_no_db_user(
    session: AsyncSession,
) -> None:
    middleware = LangMiddleware()
    message = _make_message(user_id=1)
    captured: dict = {}

    class FakeState:
        async def get_data(self) -> dict:
            return {"lang": "uz"}

    async def handler(event, data):
        captured["lang"] = data["lang"]

    await middleware(handler, message, {"session": session, "state": FakeState()})

    assert captured["lang"] == "uz"


@pytest.mark.asyncio
async def test_lang_middleware_defaults_to_russian_when_nothing_known(
    session: AsyncSession,
) -> None:
    middleware = LangMiddleware()
    message = _make_message(user_id=1)
    captured: dict = {}

    async def handler(event, data):
        captured["lang"] = data["lang"]

    await middleware(handler, message, {"session": session})

    assert captured["lang"] == "ru"


# ── bot/middlewares/auth.py: is_subscribed / SubscriptionMiddleware ────────


@pytest.mark.asyncio
async def test_is_subscribed_always_true_when_no_required_channel() -> None:
    assert settings.required_channel == ""
    assert await is_subscribed(bot=None, user_id=1) is True


@pytest.mark.asyncio
async def test_subscription_middleware_allows_free_commands() -> None:
    middleware = SubscriptionMiddleware()
    message = _make_message(user_id=1, text="/start")
    called = False

    async def handler(event, data):
        nonlocal called
        called = True
        return "ok"

    result = await middleware(handler, message, {"bot": None})
    assert called is True
    assert result == "ok"


@pytest.mark.asyncio
async def test_subscription_middleware_allows_group_chat_messages() -> None:
    middleware = SubscriptionMiddleware()
    message = _make_message(user_id=1, chat_type="group", text="anything")

    async def handler(event, data):
        return "ok"

    result = await middleware(handler, message, {"bot": None})
    assert result == "ok"


@pytest.mark.asyncio
async def test_subscription_middleware_allows_check_subscription_callback() -> None:
    middleware = SubscriptionMiddleware()
    callback = _make_callback(user_id=1, data="check_subscription")

    async def handler(event, data):
        return "ok"

    result = await middleware(handler, callback, {"bot": None})
    assert result == "ok"


@pytest.mark.asyncio
async def test_subscription_middleware_passes_through_when_channel_not_configured() -> None:
    # REQUIRED_CHANNEL defaults to "" in this test environment, so any
    # regular private message should pass straight through to the handler.
    middleware = SubscriptionMiddleware()
    message = _make_message(user_id=1, text="какой-то обычный текст")

    async def handler(event, data):
        return "ok"

    result = await middleware(handler, message, {"bot": None, "session": None})
    assert result == "ok"
