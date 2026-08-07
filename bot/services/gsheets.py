# bot/services/gsheets.py

import logging
from datetime import datetime
from functools import lru_cache
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from bot.core.config import CREDENTIALS_PATH, GOOGLE_SHEET_NAME

logger = logging.getLogger(__name__)

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "Дата", "Филиал", "Вакансия", "ФИО", "Дата рождения",
    "Пол", "Телефон", "Метро", "Языки",
    "Готовность к работе", "Опыт работы", "Компания", "Должность",
    "Стаж", "Обязанности", "Зарплатные ожидания", "График",
    "Вечерние смены", "Выходные", "Курение", "Мед. книжка",
    "Telegram ID", "Username",
]


@lru_cache(maxsize=1)
def _get_sheet() -> gspread.Worksheet:
    creds  = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet  = client.open(GOOGLE_SHEET_NAME).sheet1
    if sheet.row_count == 0 or not sheet.row_values(1):
        sheet.append_row(HEADERS, value_input_option="USER_ENTERED")
        logger.info("Заголовки добавлены в Google Sheets.")
    return sheet


def _val(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if isinstance(value, list):
        return ", ".join(map(str, value)) if value else "—"
    return str(value) if value is not None else "—"


def append_to_sheet(data: dict[str, Any], user: Any) -> bool:
    """Записывает анкету в Google Sheets.

    data — FSM-словарь анкеты.
    user — объект aiogram User (from_user).
    """
    try:
        sheet = _get_sheet()
        row = [
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            _val(data, "branch"),
            _val(data, "position"),
            _val(data, "name"),
            _val(data, "birthday"),
            _val(data, "gender"),
            _val(data, "phone"),
            data.get("metro_name") or "—",
            _val(data, "languages"),
            _val(data, "readiness"),
            _val(data, "experience"),
            _val(data, "exp_company"),
            _val(data, "exp_position"),
            _val(data, "exp_duration"),
            _val(data, "exp_duties"),
            _val(data, "salary"),
            _val(data, "schedule"),
            _val(data, "evening_shifts"),
            _val(data, "weekends"),
            _val(data, "smoking"),
            _val(data, "med_book"),
            str(user.id) if user else "—",
            f"@{user.username}" if (user and user.username) else "—",
        ]
        sheet.append_row(row, value_input_option="USER_ENTERED")
        logger.info("Запись в Google Sheets: user_id=%s", user.id if user else "?")
        return True
    except gspread.exceptions.APIError as e:
        logger.error("Google Sheets API error: %s", e)
        return False
    except Exception as e:
        _get_sheet.cache_clear()
        logger.error("Ошибка Google Sheets (кэш сброшен): %s", e, exc_info=True)
        return False
