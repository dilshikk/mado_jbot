from bot.keyboards.reply import (
    # Утилита
    remove_keyboard,
    # Пользовательские
    get_cancel_keyboard,
    get_interview_keyboard,
    get_language_keyboard,
    get_main_menu,
    get_phone_keyboard,
    get_skip_cancel_keyboard,
    # Административные
    ADMIN_BTN_BACK,
    ADMIN_BTN_CANCEL,
    get_admin_cancel_keyboard,
    get_admin_skip_cancel_keyboard,
    get_broadcast_photo_kb,
    get_broadcast_url_kb,
    get_broadcast_preview_kb,
    get_admin_metro_lines_kb,
    get_admin_metro_stations_kb,
    get_admin_station_item_kb,
    get_admin_station_confirm_delete_kb,
)
from bot.keyboards.inline import (
    get_admin_menu_inline_kb,
    get_hr_action_keyboard,
    get_hr_hold_keyboard,
    get_metro_lines_keyboard,
    get_metro_stations_keyboard,
    get_post_interview_keyboard,
    get_readiness_inline_keyboard,
    get_score_keyboard,
)
from bot.keyboards.inline_form import (
    get_confirmation_keyboard,
    get_evening_shifts_keyboard,
    get_experience_yn_keyboard,
    get_gender_keyboard,
    get_languages_keyboard,
    get_med_book_keyboard,
    get_positions_keyboard,
    get_schedule_keyboard,
    get_smoking_keyboard,
    get_weekends_keyboard,
)

__all__ = [
    # Утилита
    "remove_keyboard",
    # Пользовательские Reply
    "get_cancel_keyboard",
    "get_interview_keyboard",
    "get_language_keyboard",
    "get_main_menu",
    "get_phone_keyboard",
    "get_skip_cancel_keyboard",
    # Административные Reply
    "ADMIN_BTN_BACK",
    "ADMIN_BTN_CANCEL",
    "get_admin_cancel_keyboard",
    "get_admin_skip_cancel_keyboard",
    "get_broadcast_photo_kb",
    "get_broadcast_url_kb",
    "get_broadcast_preview_kb",
    "get_admin_metro_lines_kb",
    "get_admin_metro_stations_kb",
    "get_admin_station_item_kb",
    "get_admin_station_confirm_delete_kb",
    # Inline (Admin меню)
    "get_admin_menu_inline_kb",
    # Inline (HR и метро)
    "get_hr_action_keyboard",
    "get_hr_hold_keyboard",
    "get_metro_lines_keyboard",
    "get_metro_stations_keyboard",
    "get_post_interview_keyboard",
    "get_readiness_inline_keyboard",
    "get_score_keyboard",
    # Inline (форма анкеты)
    "get_confirmation_keyboard",
    "get_evening_shifts_keyboard",
    "get_experience_yn_keyboard",
    "get_gender_keyboard",
    "get_languages_keyboard",
    "get_med_book_keyboard",
    "get_positions_keyboard",
    "get_schedule_keyboard",
    "get_smoking_keyboard",
    "get_weekends_keyboard",
]
