"""Tests for the HR dashboard and HR candidate-action flows
(bot/handlers/hr/dashboard.py, bot/handlers/hr/actions.py).

We use an in-memory SQLite database with the real SQLAlchemy models (no
mocking of DB/business logic) and lightweight fake aiogram objects (fake
Bot/Message/CallbackQuery/FSMContext) that only implement the methods these
handlers actually call, so no real Telegram API calls are made.

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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.db import requests as db
from bot.db.base import Base
from bot.handlers.hr import actions as hr_actions
from bot.handlers.hr import dashboard as hr_dashboard


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
    """Minimal stand-in for aiogram's Message: records outgoing calls."""

    def __init__(self, chat_id: int = 1, message_id: int = 1, text: str | None = None) -> None:
        self.chat = type("Chat", (), {"id": chat_id})()
        self.message_id = message_id
        self.text = text
        self.bot: FakeBot | None = None
        self.answered_texts: list[str] = []
        self.answered_documents: list[bytes] = []
        self.edited_texts: list[str] = []
        self.deleted = False

    async def answer(self, text: str, **kwargs) -> "FakeMessage":
        self.answered_texts.append(text)
        return FakeMessage(chat_id=self.chat.id, message_id=self.message_id + 1)

    async def answer_document(self, document, **kwargs) -> None:
        self.answered_documents.append(document.data)

    async def edit_text(self, text: str, **kwargs) -> None:
        self.edited_texts.append(text)

    async def delete(self) -> None:
        self.deleted = True


class FakeCallbackQuery:
    """Minimal stand-in for aiogram's CallbackQuery."""

    def __init__(self, user_id: int, data: str, message: FakeMessage) -> None:
        self.from_user = type("User", (), {"id": user_id})()
        self.data = data
        self.message = message
        self.answered_alerts: list[str] = []

    async def answer(self, text: str = "", show_alert: bool = False) -> None:
        self.answered_alerts.append(text)


class FakeBot:
    """Records outgoing Telegram calls instead of hitting the real API."""

    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str]] = []
        self.edited_messages: list[tuple[int, int, str]] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        self.sent_messages.append((chat_id, text))

    async def edit_message_text(self, chat_id: int, message_id: int, text: str, **kwargs) -> None:
        self.edited_messages.append((chat_id, message_id, text))


class FakeFSMContext:
    """Minimal stand-in for aiogram's FSMContext backed by a plain dict."""

    def __init__(self) -> None:
        self._data: dict = {}
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


# ── bot/handlers/hr/dashboard.py: _is_admin ─────────────────────────────────


def test_dashboard_is_admin_true_for_configured_id() -> None:
    assert hr_dashboard._is_admin(1) is True


def test_dashboard_is_admin_false_for_unknown_id() -> None:
    assert hr_dashboard._is_admin(999) is False


# ── bot/handlers/hr/dashboard.py: keyboards ─────────────────────────────────


def test_dashboard_keyboard_has_expected_callback_actions() -> None:
    markup = hr_dashboard._dashboard_keyboard()
    callbacks = {btn.callback_data for row in markup.inline_keyboard for btn in row}

    assert callbacks == {
        "dash:list:pending", "dash:list:screened",
        "dash:list:accepted", "dash:list:rejected",
        "dash:list:today", "dash:positions",
        "dash:scores", "dash:search",
        "dash:export", "dash:refresh",
    }


def test_dashboard_back_keyboard_returns_to_refresh() -> None:
    markup = hr_dashboard._back_keyboard()
    assert markup.inline_keyboard[0][0].callback_data == "dash:refresh"


# ── bot/handlers/hr/dashboard.py: _send_dashboard ───────────────────────────


@pytest.mark.asyncio
async def test_send_dashboard_reports_totals_from_real_data(session: AsyncSession) -> None:
    await db.register_user(session, user_id=1, username="alice", first_name="Alice", lang="ru")
    await db.register_user(session, user_id=2, username="bob", first_name="Bob", lang="ru")
    await db.save_application(
        session, user_id=1, name="Alice", birthday="01.01.2000",
        phone="+998900000001", position="Повар",
    )
    await db.update_application_status(session, user_id=1, status="accepted")

    message = FakeMessage()
    await hr_dashboard._send_dashboard(message, session)

    assert len(message.answered_texts) == 1
    text = message.answered_texts[0]
    assert "Всего: 2" in text  # total_users
    assert "Всего: 1" in text  # total_apps


# ── bot/handlers/hr/dashboard.py: dashboard_export ──────────────────────────


@pytest.mark.asyncio
async def test_dashboard_export_produces_csv_with_application_rows(session: AsyncSession) -> None:
    await db.register_user(session, user_id=1, username="alice", first_name="Alice", lang="ru")
    await db.save_application(
        session, user_id=1, name="Alice", birthday="01.01.2000",
        phone="+998900000001", position="Повар",
    )

    message = FakeMessage()
    callback = FakeCallbackQuery(user_id=1, data="dash:export", message=message)

    await hr_dashboard.dashboard_export(callback, session)

    assert len(message.answered_documents) == 1
    csv_content = message.answered_documents[0].decode("utf-8-sig")
    assert "Alice" in csv_content
    assert "Повар" in csv_content


@pytest.mark.asyncio
async def test_dashboard_export_rejects_non_admin(session: AsyncSession) -> None:
    message = FakeMessage()
    callback = FakeCallbackQuery(user_id=999, data="dash:export", message=message)

    await hr_dashboard.dashboard_export(callback, session)

    assert message.answered_documents == []


# ── bot/handlers/hr/actions.py: hr_hire_callback ────────────────────────────


@pytest.mark.asyncio
async def test_hr_hire_marks_application_hired_and_notifies_candidate(
    session: AsyncSession,
) -> None:
    await db.register_user(session, user_id=42, username="cand", first_name="Cand", lang="ru")
    await db.save_application(
        session, user_id=42, name="Cand", birthday="01.01.2000",
        phone="+998900000002", position="Официант",
    )

    bot = FakeBot()
    message = FakeMessage(chat_id=42)
    message.bot = bot
    callback = FakeCallbackQuery(user_id=1, data="hr_hire:42", message=message)
    callback.bot = bot

    await hr_actions.hr_hire_callback(callback, session)

    status = await db.get_application_status(session, 42)
    assert status == "hired"
    assert bot.sent_messages[0][0] == 42


# ── bot/handlers/hr/actions.py: hr_reject_callback ──────────────────────────


@pytest.mark.asyncio
async def test_hr_reject_marks_application_rejected_and_blocks_candidate(
    session: AsyncSession,
) -> None:
    await db.register_user(session, user_id=43, username="cand2", first_name="Cand2", lang="ru")
    await db.save_application(
        session, user_id=43, name="Cand2", birthday="01.01.2000",
        phone="+998900000003", position="Официант",
    )

    bot = FakeBot()
    message = FakeMessage(chat_id=43)
    message.bot = bot
    callback = FakeCallbackQuery(user_id=1, data="hr_reject:43", message=message)
    callback.bot = bot

    await hr_actions.hr_reject_callback(callback, session)

    status = await db.get_application_status(session, 43)
    assert status == "rejected"
    assert await db.is_user_blocked(session, 43) is True


# ── bot/handlers/hr/actions.py: score + comment flow ────────────────────────


@pytest.mark.asyncio
async def test_hr_score_callback_stores_pending_score_in_state(session: AsyncSession) -> None:
    message = FakeMessage()
    callback = FakeCallbackQuery(user_id=1, data="score:4:55", message=message)
    state = FakeFSMContext()

    await hr_actions.hr_score_callback(callback, state)

    data = await state.get_data()
    assert data["score_candidate_id"] == 55
    assert data["score_value"] == 4


@pytest.mark.asyncio
async def test_process_score_comment_saves_score_and_comment(session: AsyncSession) -> None:
    await db.register_user(session, user_id=55, username="cand3", first_name="Cand3", lang="ru")
    await db.save_application(
        session, user_id=55, name="Cand3", birthday="01.01.2000",
        phone="+998900000004", position="Хостес",
    )

    state = FakeFSMContext()
    await state.update_data(score_candidate_id=55, score_value=5)
    message = FakeMessage(text="Отличный кандидат")

    await hr_actions.process_score_comment(message, state, session)

    stats = await db.get_score_stats(session)
    assert stats["scored_count"] == 1
    assert message.answered_texts[0].startswith("✅ Оценка сохранена")
    assert await state.get_data() == {}
