# bot/core/config.py

import logging
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

PHOTOS_DIR = BASE_DIR / "photos"
PHOTOS_DIR.mkdir(exist_ok=True)

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str
    admin_chat_id: int | None = None
    admin_ids: str | None = None

    google_sheet_name: str = "Анкеты MADO"
    credentials_path: str = str(BASE_DIR / "credentials.json")
    fsm_storage_path: str = str(BASE_DIR / "fsm_storage.db")
    sheet_url: str = (
        "https://docs.google.com/spreadsheets/d/"
        "1rxds0GNVRZPF-D0RFfkdp0ZY4zEgl8TJjIyZ0Apl6rk/edit"
    )
    required_channel: str = ""

    log_path: str = str(LOGS_DIR / "bot.log")
    log_level: str = "WARNING"

    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR / 'database.db'}"

    @property
    def admin_ids_list(self) -> tuple[int, ...]:
        raw = self.admin_ids or (str(self.admin_chat_id) if self.admin_chat_id else "")
        ids = []
        for part in raw.split(","):
            part = part.strip()
            if part.lstrip("-").isdigit():
                ids.append(int(part))
        if not ids:
            raise ValueError("Задайте ADMIN_IDS или ADMIN_CHAT_ID в .env")
        return tuple(ids)

    @property
    def effective_admin_chat_id(self) -> int:
        return self.admin_chat_id if self.admin_chat_id is not None else self.admin_ids_list[0]

    @property
    def log_level_int(self) -> int:
        raw = self.log_level.upper().strip()
        if raw not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"Неверное значение LOG_LEVEL='{self.log_level}'. "
                f"Допустимые: DEBUG, INFO, WARNING, ERROR, CRITICAL."
            )
        return logging.getLevelName(raw)


settings = Settings()

# ── Удобные константы (back-compat) ──────────────────────────────────────────

BOT_TOKEN         = settings.bot_token
ADMIN_CHAT_ID     = settings.effective_admin_chat_id
ADMIN_IDS         = settings.admin_ids_list
GOOGLE_SHEET_NAME = settings.google_sheet_name
CREDENTIALS_PATH  = settings.credentials_path
FSM_STORAGE_PATH  = settings.fsm_storage_path
SHEET_URL         = settings.sheet_url
REQUIRED_CHANNEL  = settings.required_channel
LOG_PATH          = settings.log_path
LOG_LEVEL         = settings.log_level_int
DATABASE_URL      = settings.database_url
