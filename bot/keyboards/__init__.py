# bot/keyboards package

from bot.keyboards.inline import (
    get_hr_action_keyboard,
    get_hr_hold_keyboard,
    get_post_interview_keyboard,
    get_score_keyboard,
)
from bot.keyboards.reply import (
    get_branch_keyboard,
    get_cancel_keyboard,
    get_citizenship_keyboard,
    get_confirmation_keyboard,
    get_experience_keyboard,
    get_family_keyboard,
    get_gender_keyboard,
    get_language_keyboard,
    get_main_menu,
    get_phone_keyboard,
    get_positions_keyboard,
    remove_keyboard,
)

__all__ = [
    "get_hr_action_keyboard", "get_hr_hold_keyboard",
    "get_post_interview_keyboard", "get_score_keyboard",
    "get_branch_keyboard", "get_cancel_keyboard", "get_citizenship_keyboard",
    "get_confirmation_keyboard", "get_experience_keyboard", "get_family_keyboard",
    "get_gender_keyboard", "get_language_keyboard", "get_main_menu",
    "get_phone_keyboard", "get_positions_keyboard", "remove_keyboard",
]
