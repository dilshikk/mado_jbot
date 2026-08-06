"""Tests for outbound notification helpers: the admin broadcast wizard's
pure helpers and the actual broadcast send loop
(bot/handlers/admin/broadcast.py).

We use lightweight fake aiogram Bot/Message/CallbackQuery/FSMContext objects
that implement only the methods these handlers call, so no real Telegram
API calls are made. Delivery failures (blocked users, bad requests) are
simulated by raising aiogram's real exception classes from the fake bot,
exercising the actual except branches in the handler.

Required settings env vars are injected *before* importing any bot module,
since `bot.core.config.Settings()` is instantiated at import time and
requires `BOT_TOKEN` / `ADMIN_IDS` to be present.
"""

import os

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
import pytest_asyncio
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.db import requests as db
from bot.db.base import Base
from bot.handlers.admin import broadcast


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


class FakeMessage:
    """Minimal stand-in for aiogram's Message.

    `answer()` returns `self` (rather than a fresh instance) so that a
    message sent in reply to a callback — e.g. the broadcast progress
    message, which is later mutated via `edit_text()` — stays reachable
    from the same reference the handler returned, exactly like the real
    aiogram `Message.answer()` return value would be used by callers that
    keep it around to edit later.
    """

    def __init__(self, chat_id: int = 1, user_id: int | None = None) -> None:
        self.chat = type("Chat", (), {"id": chat_id})()
        self.from_user = type("User", (), {"id": user_id if user_id is not None else chat_id})()
        self.text: str | None = None
        self.answered_texts: list[str] = []

    async def answer(self, text: str, **kwargs) -> "FakeMessage":
        self.answered_texts.append(text)
        return self

    async def answer_photo(self, photo, **kwargs) -> "FakeMessage":
        self.answered_texts.append(kwargs.get("caption", ""))
        return self

    async def edit_text(self, text: str, **kwargs) -> None:
        self.answered_texts.append(text)


class FakeCallbackQuery:
    """Minimal stand-in for aiogram's CallbackQuery."""

    def __init__(self, user_id: int, data: str, message: FakeMessage) -> None:
        self.from_user = type("User", (), {"id": user_id})()
        self.data = data
        self.message = message
        self.bot: "FakeBot | None" = None
        self.answered_alerts: list[str] = []

    async def answer(self, text: str = "", show_alert: bool = False) -> None:
        self.answered_alerts.append(text)


class FakeBot:
    """Records send attempts; can be configured to fail for specific users."""

    def __init__(self, forbidden_for: set | None = None, bad_request_for: set | None = None) -> None:
        self.forbidden_for = forbidden_for or set()
        self.bad_request_for = bad_request_for or set()
        self.sent_to: list[int] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        if chat_id in self.forbidden_for:
            raise TelegramForbiddenError(method="sendMessage", message="bot was blocked")
        if chat_id in self.bad_request_for:
            raise TelegramBadRequest(method="sendMessage", message="bad request")
        self.sent_to.append(chat_id)

    async def send_photo(self, chat_id: int, photo, **kwargs) -> None:
        await self.send_message(chat_id, text=kwargs.get("caption", ""))


class FakeFSMContext:
    """Minimal stand-in for aiogram's FSMContext backed by a plain dict."""

    def __init__(self, initial: dict | None = None) -> None:
        self._data: dict = dict(initial or {})
        self.state: object | None = None

    async def get_data(self) -> dict:
        return dict(self._data)

    async def update_data(self, **kwargs) -> None:
        self._data.update(kwargs)

    async def set_state(self, state) -> None:
        self.state = state

    async def clear(self) -> None:
        self._data = {}
        self.state = None


# ── bot/handlers/admin/broadcast.py: _is_admin ──────────────────────────────


def test_broadcast_is_admin_true_for_configured_id() -> None:
    assert broadcast._is_admin(1) is True


def test_broadcast_is_admin_false_for_unknown_id() -> None:
    assert broadcast._is_admin(999) is False


# ── bot/handlers/admin/broadcast.py: keyboards ──────────────────────────────


def test_admin_menu_keyboard_has_expected_actions() -> None:
    markup = broadcast._admin_menu_keyboard()
    callbacks = {btn.callback_data for row in markup.inline_keyboard for btn in row}

    assert callbacks == {
        "admin:broadcast", "admin:adminlist", "admin:vacancies",
        "admin:metro", "admin:dashboard", "admin:resend",
    }


def test_photo_keyboard_offers_skip_and_cancel() -> None:
    markup = broadcast._photo_kb()
    callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert callbacks == ["broadcast:skip_photo", "broadcast:cancel"]


def test_url_skip_keyboard_offers_skip_and_cancel() -> None:
    markup = broadcast._url_skip_kb()
    callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert callbacks == ["broadcast:skip_url", "broadcast:cancel"]


def test_preview_keyboard_includes_url_row_only_when_has_url() -> None:
    with_url = broadcast._preview_keyboard(has_url=True)
    without_url = broadcast._preview_keyboard(has_url=False)

    with_url_callbacks = [btn.callback_data for row in with_url.inline_keyboard for btn in row]
    without_url_callbacks = [btn.callback_data for row in without_url.inline_keyboard for btn in row]

    assert "noop" in with_url_callbacks
    assert "noop" not in without_url_callbacks
    assert "broadcast:send" in with_url_callbacks
    assert "broadcast:send" in without_url_callbacks


def test_url_keyboard_returns_none_without_url() -> None:
    assert broadcast._url_keyboard(url=None, title="Открыть") is None


def test_url_keyboard_uses_custom_title_when_provided() -> None:
    markup = broadcast._url_keyboard(url="https://example.com", title="Открыть меню")
    assert markup.inline_keyboard[0][0].text == "Открыть меню"
    assert markup.inline_keyboard[0][0].url == "https://example.com"


def test_url_keyboard_falls_back_to_default_title_when_empty() -> None:
    markup = broadcast._url_keyboard(url="https://example.com", title="")
    assert markup.inline_keyboard[0][0].text == "🔗 Подробнее"


# ── bot/handlers/admin/broadcast.py: broadcast_got_url validation ──────────


@pytest.mark.asyncio
async def test_broadcast_got_url_rejects_non_http_url() -> None:
    message = FakeMessage(user_id=1)
    message.text = "not-a-url"
    state = FakeFSMContext()

    await broadcast.broadcast_got_url(message, state)

    assert "https://" in message.answered_texts[0]
    assert await state.get_data() == {}


@pytest.mark.asyncio
async def test_broadcast_got_url_accepts_http_url_and_advances_state() -> None:
    message = FakeMessage(user_id=1)
    message.text = "https://example.com/menu"
    state = FakeFSMContext()

    await broadcast.broadcast_got_url(message, state)

    data = await state.get_data()
    assert data["url"] == "https://example.com/menu"


# ── bot/handlers/admin/broadcast.py: broadcast_send ─────────────────────────


@pytest.mark.asyncio
async def test_broadcast_send_delivers_to_all_registered_users(session: AsyncSession) -> None:
    await db.register_user(session, user_id=1, username="a", first_name="A", lang="ru")
    await db.register_user(session, user_id=2, username="b", first_name="B", lang="ru")

    bot = FakeBot()
    message = FakeMessage(user_id=1)
    callback = FakeCallbackQuery(user_id=1, data="broadcast:send", message=message)
    callback.bot = bot
    state = FakeFSMContext(initial={"caption": "🔥 Новое меню!", "photo_file_id": None})

    await broadcast.broadcast_send(callback, state, session)

    assert sorted(bot.sent_to) == [1, 2]
    assert await state.get_data() == {}


@pytest.mark.asyncio
async def test_broadcast_send_counts_blocked_and_failed_separately(session: AsyncSession) -> None:
    await db.register_user(session, user_id=1, username="a", first_name="A", lang="ru")
    await db.register_user(session, user_id=2, username="b", first_name="B", lang="ru")
    await db.register_user(session, user_id=3, username="c", first_name="C", lang="ru")

    bot = FakeBot(forbidden_for={2}, bad_request_for={3})
    message = FakeMessage(user_id=1)
    callback = FakeCallbackQuery(user_id=1, data="broadcast:send", message=message)
    callback.bot = bot
    state = FakeFSMContext(initial={"caption": "Привет", "photo_file_id": None})

    await broadcast.broadcast_send(callback, state, session)

    assert bot.sent_to == [1]
    # broadcast_send() replies once with a progress message, then repeatedly
    # calls `.edit_text()` on that *same* returned message object to update
    # and finally report the final counts — our FakeMessage.answer() returns
    # `self`, so both the initial progress text and every edit land in the
    # same `answered_texts` list; the final report is always the last entry.
    final_report = message.answered_texts[-1]
    assert "Отправлено: <b>1</b>" in final_report
    assert "Заблокировали: <b>1</b>" in final_report
    assert "Ошибок: <b>1</b>" in final_report


@pytest.mark.asyncio
async def test_broadcast_send_rejects_non_admin(session: AsyncSession) -> None:
    await db.register_user(session, user_id=1, username="a", first_name="A", lang="ru")
    bot = FakeBot()
    message = FakeMessage(user_id=999)
    callback = FakeCallbackQuery(user_id=999, data="broadcast:send", message=message)
    callback.bot = bot
    state = FakeFSMContext(initial={"caption": "Привет"})

    await broadcast.broadcast_send(callback, state, session)

    assert bot.sent_to == []
    assert callback.answered_alerts[0].startswith("⛔️")
