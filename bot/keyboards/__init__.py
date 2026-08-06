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
    # Административные (только для возможных legacy)
    ADMIN_BTN_BACK,
    ADMIN_BTN_CANCEL,
    get_admin_cancel_keyboard,
    get_admin_skip_cancel_keyboard,
)
from bot.keyboards.inline import (
    # Admin: главное меню
    get_admin_menu_inline_kb,
    # Admin: вакансии
    get_admin_vacancies_inline_kb,
    get_admin_vacancy_item_inline_kb,
    get_admin_vacancy_edit_inline_kb,
    get_admin_vacancy_confirm_delete_inline_kb,
    # Admin: рассылка
    get_broadcast_photo_inline_kb,
    get_broadcast_cancel_inline_kb,
    get_broadcast_url_inline_kb,
    get_broadcast_preview_inline_kb,
    # Admin: resend
    get_resend_cancel_inline_kb,
    # Admin: метро
    get_admin_metro_home_inline_kb,
    get_admin_metro_stations_inline_kb,
    get_admin_metro_station_item_inline_kb,
    get_admin_metro_station_confirm_delete_inline_kb,
    get_admin_metro_add_line_inline_kb,
    get_admin_metro_fsm_cancel_inline_kb,
    # HR и форма
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
    # Reply (пользовательские)
    "get_cancel_keyboard",
    "get_interview_keyboard",
    "get_language_keyboard",
    "get_main_menu",
    "get_phone_keyboard",
    "get_skip_cancel_keyboard",
    # Reply (legacy)
    "ADMIN_BTN_BACK",
    "ADMIN_BTN_CANCEL",
    "get_admin_cancel_keyboard",
    "get_admin_skip_cancel_keyboard",
    # Inline (Admin меню)
    "get_admin_menu_inline_kb",
    # Inline (Вакансии)
    "get_admin_vacancies_inline_kb",
    "get_admin_vacancy_item_inline_kb",
    "get_admin_vacancy_edit_inline_kb",
    "get_admin_vacancy_confirm_delete_inline_kb",
    # Inline (Рассылка)
    "get_broadcast_photo_inline_kb",
    "get_broadcast_cancel_inline_kb",
    "get_broadcast_url_inline_kb",
    "get_broadcast_preview_inline_kb",
    # Inline (Resend)
    "get_resend_cancel_inline_kb",
    # Inline (Метро)
    "get_admin_metro_home_inline_kb",
    "get_admin_metro_stations_inline_kb",
    "get_admin_metro_station_item_inline_kb",
    "get_admin_metro_station_confirm_delete_inline_kb",
    "get_admin_metro_add_line_inline_kb",
    "get_admin_metro_fsm_cancel_inline_kb",
    # Inline (HR + форма)
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
