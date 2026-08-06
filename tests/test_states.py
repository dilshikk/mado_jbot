"""Tests for FSM state groups, custom aiogram filters, and the rate-limit
middleware (bot/states/*, bot/filters/*, bot/middlewares/throttling.py).

We build minimal aiogram `Message`/`CallbackQuery` objects with
`model_construct` (bypasses pydantic validation) since we only need specific
attributes read by the filters/middleware under test — a full valid object
graph (chat, date, etc.) is not required for these pure logic checks.

Required settings env vars are injected *before* importing any bot module,
since `bot.core.config.Settings()` is instantiated at import time and
requires `BOT_TOKEN` / `ADMIN_IDS` to be present.
"""

import os

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1,2")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
from aiogram.types import CallbackQuery, Chat, Message, User

from bot.filters.common import IsCancelMessage, IsPrivateChat
from bot.filters.role import IsAdmin
from bot.middlewares.throttling import RateLimitMiddleware
from bot.states import (
    AddVacancy,
    Broadcast,
    DashboardFilter,
    EditVacancy,
    Form,
    HRReview,
    HRScore,
    Interview,
)


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


class _FakeAnswerable:
    """Wraps a real aiogram Message/CallbackQuery so `.answer()` is a no-op
    instead of raising because it isn't bound to a live Bot instance."""

    def __init__(self, wrapped):
        self._wrapped = wrapped

    def __getattr__(self, name):
        return getattr(self._wrapped, name)

    async def answer(self, *args, **kwargs) -> None:
        return None


def _make_message_answerable(user_id: int, chat_type: str = "private", text: str | None = None):
    return _FakeAnswerable(_make_message(user_id, chat_type=chat_type, text=text))


def _make_callback(user_id: int, chat_type: str = "private") -> CallbackQuery:
    message = _make_message(user_id, chat_type=chat_type)
    return CallbackQuery.model_construct(
        id="cb1",
        from_user=_make_user(user_id),
        chat_instance="ci",
        message=message,
        data="anything",
    )


def _make_callback_answerable(user_id: int, chat_type: str = "private"):
    return _FakeAnswerable(_make_callback(user_id, chat_type=chat_type))


# ── bot/filters/role.py: IsAdmin ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_is_admin_true_for_configured_admin_id() -> None:
    is_admin = IsAdmin()
    message = _make_message(user_id=1)
    assert await is_admin(message) is True


@pytest.mark.asyncio
async def test_is_admin_false_for_non_admin_id() -> None:
    is_admin = IsAdmin()
    message = _make_message(user_id=999)
    assert await is_admin(message) is False


# ── bot/filters/common.py: IsCancelMessage ──────────────────────────────────


@pytest.mark.parametrize("text", ["❌ Отменить заполнение", "❌ Bekor qilish"])
@pytest.mark.asyncio
async def test_is_cancel_message_matches_known_cancel_texts(text: str) -> None:
    is_cancel = IsCancelMessage()
    message = _make_message(user_id=1, text=text)
    assert await is_cancel(message) is True


@pytest.mark.asyncio
async def test_is_cancel_message_false_for_other_text() -> None:
    is_cancel = IsCancelMessage()
    message = _make_message(user_id=1, text="Привет")
    assert await is_cancel(message) is False


# ── bot/filters/common.py: IsPrivateChat ────────────────────────────────────


@pytest.mark.asyncio
async def test_is_private_chat_true_for_private_message() -> None:
    is_private = IsPrivateChat()
    message = _make_message(user_id=1, chat_type="private")
    assert await is_private(message) is True


@pytest.mark.asyncio
async def test_is_private_chat_false_for_group_message() -> None:
    is_private = IsPrivateChat()
    message = _make_message(user_id=1, chat_type="group")
    assert await is_private(message) is False


@pytest.mark.asyncio
async def test_is_private_chat_checks_underlying_message_for_callback() -> None:
    is_private = IsPrivateChat()
    callback = _make_callback(user_id=1, chat_type="group")
    assert await is_private(callback) is False


# ── bot/states: FSM state groups exist with expected states ────────────────
#
# aiogram's `StatesGroup.__all_states_names__` returns each state's *full*
# qualified name in the form "GroupName:state_name" (e.g. "Form:waiting_name"),
# not the bare attribute name. We check membership against that same
# qualified format below.


def test_form_state_group_has_expected_key_states() -> None:
    expected = {
        "waiting_for_lang", "waiting_name", "waiting_birthday", "waiting_phone",
        "waiting_metro", "waiting_position", "waiting_photo", "waiting_confirmation",
    }
    actual = {name.split(":", 1)[-1] for name in Form.__all_states_names__}
    assert expected <= actual


def test_interview_state_group_has_answering_state() -> None:
    assert "Interview:answering" in Interview.__all_states_names__


def test_hr_review_and_score_state_groups() -> None:
    assert "HRReview:waiting_for_interview_details" in HRReview.__all_states_names__
    assert "HRScore:waiting_for_comment" in HRScore.__all_states_names__


def test_broadcast_state_group_has_wizard_steps() -> None:
    expected = {
        "waiting_photo", "waiting_caption", "waiting_url",
        "waiting_url_title", "preview", "sending", "waiting_resend_id",
    }
    actual = {name.split(":", 1)[-1] for name in Broadcast.__all_states_names__}
    assert expected <= actual


def test_vacancy_state_groups() -> None:
    add_states = {name.split(":", 1)[-1] for name in AddVacancy.__all_states_names__}
    edit_states = {name.split(":", 1)[-1] for name in EditVacancy.__all_states_names__}
    assert {"waiting_name_ru", "waiting_name_uz", "waiting_emoji"} <= add_states
    assert {"choosing_field", "waiting_value"} <= edit_states


def test_dashboard_filter_state_group() -> None:
    actual = {name.split(":", 1)[-1] for name in DashboardFilter.__all_states_names__}
    assert {"waiting_position_filter", "waiting_date_from"} <= actual


# ── bot/middlewares/throttling.py: RateLimitMiddleware ──────────────────────


@pytest.mark.asyncio
async def test_rate_limit_allows_calls_under_message_limit() -> None:
    middleware = RateLimitMiddleware()
    message = _make_message_answerable(user_id=1)

    calls = 0

    async def handler(event, data: dict) -> str:
        nonlocal calls
        calls += 1
        return "ok"

    for _ in range(5):
        result = await middleware(handler, message, {})
        assert result == "ok"

    assert calls == 5


@pytest.mark.asyncio
async def test_rate_limit_blocks_calls_over_message_limit() -> None:
    middleware = RateLimitMiddleware()
    message = _make_message_answerable(user_id=1, text="hi")

    async def handler(event, data: dict) -> str:
        return "ok"

    # First 5 calls are allowed (the limit), the 6th within the same window
    # must be blocked.
    for _ in range(5):
        await middleware(handler, message, {})

    result = await middleware(handler, message, {})
    assert result is None


@pytest.mark.asyncio
async def test_rate_limit_tracks_users_independently() -> None:
    middleware = RateLimitMiddleware()
    user_1_message = _make_message_answerable(user_id=1)
    user_2_message = _make_message_answerable(user_id=2)

    async def handler(event, data: dict) -> str:
        return "ok"

    for _ in range(5):
        await middleware(handler, user_1_message, {})

    # User 1 is now rate-limited, but user 2 should be unaffected.
    assert await middleware(handler, user_1_message, {}) is None
    assert await middleware(handler, user_2_message, {}) == "ok"


@pytest.mark.asyncio
async def test_rate_limit_uses_higher_limit_for_callbacks() -> None:
    middleware = RateLimitMiddleware()
    callback = _make_callback_answerable(user_id=1)

    async def handler(event, data: dict) -> str:
        return "ok"

    # Callback limit (10) is higher than message limit (5); 8 calls should
    # all succeed even though that would exceed the message limit.
    results = [await middleware(handler, callback, {}) for _ in range(8)]
    assert results == ["ok"] * 8
