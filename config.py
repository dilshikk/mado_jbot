# config.py

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR   = Path(__file__).parent
PHOTOS_DIR = BASE_DIR / "photos"
PHOTOS_DIR.mkdir(exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"Переменная окружения '{key}' не задана.")
    return value


def _parse_admin_ids() -> tuple[int, ...]:
    """
    Читает ADMIN_IDS из .env — список через запятую.
    Если ADMIN_IDS не задан — фолбэк на ADMIN_CHAT_ID.
    Пример в .env:  ADMIN_IDS=123456789,987654321
    """
    raw = os.getenv("ADMIN_IDS") or os.getenv("ADMIN_CHAT_ID", "")
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            ids.append(int(part))
    if not ids:
        raise EnvironmentError("Задайте ADMIN_IDS или ADMIN_CHAT_ID в .env")
    return tuple(ids)


# ── Config dataclass ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Config:
    bot_token:          str
    admin_chat_id:      int
    admin_ids:          tuple[int, ...]
    google_sheet_name:  str
    credentials_path:   Path
    fsm_storage_path:   str
    sheet_url:          str
    required_channel:   str           


def load_config() -> Config:
    admin_ids = _parse_admin_ids()

    admin_chat_id_raw = os.getenv("ADMIN_CHAT_ID")
    admin_chat_id     = int(admin_chat_id_raw) if admin_chat_id_raw else admin_ids[0]

    return Config(
        bot_token         = _require("BOT_TOKEN"),
        admin_chat_id     = admin_chat_id,
        admin_ids         = admin_ids,
        google_sheet_name = os.getenv("GOOGLE_SHEET_NAME", "Анкеты MADO"),
        credentials_path  = Path(os.getenv("CREDENTIALS_PATH", str(BASE_DIR / "credentials.json"))),
        fsm_storage_path  = os.getenv("FSM_STORAGE_PATH", str(BASE_DIR / "fsm_storage.db")),
        sheet_url         = os.getenv(
            "SHEET_URL",
            "https://docs.google.com/spreadsheets/d/1rxds0GNVRZPF-D0RFfkdp0ZY4zEgl8TJjIyZ0Apl6rk/edit",
        ),
        required_channel  = os.getenv("REQUIRED_CHANNEL", ""),  
    )


config = load_config()

# ── Удобный прямой доступ ─────────────────────────────────────────────────────

BOT_TOKEN         = config.bot_token
ADMIN_CHAT_ID     = config.admin_chat_id
ADMIN_IDS         = config.admin_ids
GOOGLE_SHEET_NAME = config.google_sheet_name
CREDENTIALS_PATH  = config.credentials_path
FSM_STORAGE_PATH  = config.fsm_storage_path
SHEET_URL         = config.sheet_url
REQUIRED_CHANNEL  = config.required_channel  # ✅ экспортируем
