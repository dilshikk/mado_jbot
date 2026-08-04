# gsheets.py

import logging
from functools import lru_cache

import gspread
from google.oauth2.service_account import Credentials

from config import CREDENTIALS_PATH, GOOGLE_SHEET_NAME

logger = logging.getLogger(__name__)

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# Заголовки таблицы — добавляются автоматически если лист пустой
HEADERS = [
    "Дата", "Филиал", "Вакансия", "ФИО",
    "Дата рождения", "Пол", "Семейное положение",
    "Гражданство", "Адрес", "Телефон",
]


@lru_cache(maxsize=1)
def _get_sheet() -> gspread.Worksheet:
    """
    Создаёт и кэширует подключение к таблице.
    lru_cache гарантирует одно подключение на весь процесс —
    не нужно авторизоваться при каждой записи.
    """
    creds  = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet  = client.open(GOOGLE_SHEET_NAME).sheet1

    # Добавляем заголовки если таблица пустая
    if sheet.row_count == 0 or not sheet.row_values(1):
        sheet.append_row(HEADERS, value_input_option="USER_ENTERED")
        logger.info("Заголовки добавлены в Google Sheets.")

    return sheet


def append_to_sheet(data: list) -> bool:
    """
    Записывает строку данных в таблицу.
    Возвращает True при успехе, False при ошибке.
    При сетевой ошибке сбрасывает кэш и пробует переподключиться.
    """
    try:
        sheet = _get_sheet()
        sheet.append_row(data, value_input_option="USER_ENTERED")
        logger.info("Запись в Google Sheets: %s", data)
        return True

    except gspread.exceptions.APIError as e:
        logger.error("Google Sheets API error: %s", e)
        return False

    except Exception as e:
        # Сброс кэша — при следующем вызове переподключится заново
        _get_sheet.cache_clear()
        logger.error("Ошибка Google Sheets (кэш сброшен): %s", e, exc_info=True)
        return False
