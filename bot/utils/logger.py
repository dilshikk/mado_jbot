# bot/utils/logger.py

import logging
import sys


def setup_logging(log_path: str, log_level: int) -> None:
    """Настраивает корневое логирование: цветной вывод в терминал + файл."""

    # Форматы
    fmt_console = "%(asctime)s | %(levelname)-8s | %(name)s: %(message)s"
    fmt_file    = "%(asctime)s | %(levelname)-8s | %(name)s: %(message)s"
    datefmt     = "%H:%M:%S"

    # Handler: терминал (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(fmt_console, datefmt=datefmt))

    # Handler: файл
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(fmt_file, datefmt="%Y-%m-%d %H:%M:%S"))

    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # Подавляем шум внешних библиотек — они логируют на INFO/DEBUG постоянно
    for noisy in ("aiogram.event", "apscheduler", "gspread",
                  "urllib3", "httpcore", "httpx", "aiosqlite",
                  "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Логирование запущено: уровень=%s, файл=%s",
        logging.getLevelName(log_level), log_path,
    )
