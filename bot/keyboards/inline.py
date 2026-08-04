# bot/keyboards/inline.py

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.core.config import SHEET_URL

_EMPTY_USERNAME: frozenset[str] = frozenset({"отсутствует", "none", ""})


def get_score_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    """Кнопки оценки кандидата 1–5 звёзд."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{i}⭐", callback_data=f"score:{i}:{candidate_id}")
        for i in range(1, 6)
    ]])


def get_post_interview_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    """Клавиатура после собеседования."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏆 Принять на работу", callback_data=f"hr_hire:{candidate_id}"),
            InlineKeyboardButton(text="❌ Не подошёл",         callback_data=f"hr_reject:{candidate_id}"),
        ],
        [InlineKeyboardButton(text="⏸ На паузу", callback_data=f"hr_hold:{candidate_id}")],
    ])


def get_hr_action_keyboard(phone: str, username: str, candidate_id: int) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    clean = username.lstrip("@").strip().lower()
    if clean and clean not in _EMPTY_USERNAME:
        buttons.append([InlineKeyboardButton(text="💬 Telegram", url=f"https://t.me/{clean}")])
    buttons.append([
        InlineKeyboardButton(text="✅ Одобрить",  callback_data=f"hr_accept:{candidate_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"hr_reject:{candidate_id}"),
    ])
    buttons.append([InlineKeyboardButton(text="⏸ На паузу", callback_data=f"hr_hold:{candidate_id}")])
    buttons.append([InlineKeyboardButton(text="📊 Google Таблица", url=SHEET_URL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_hr_hold_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="▶️ Вернуть в работу", callback_data=f"hr_accept:{candidate_id}"),
        InlineKeyboardButton(text="❌ Отклонить",         callback_data=f"hr_reject:{candidate_id}"),
    ]])
