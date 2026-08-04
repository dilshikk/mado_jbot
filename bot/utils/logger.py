# bot/utils/logger.py

import logging


def setup_logging(log_path: str, log_level: int) -> None:
    """Настраивает корневое логирование и подавляет шумные библиотеки."""
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),          # stdout → journald
            logging.FileHandler(log_path),    # путь из .env (LOG_PATH)
        ],
    )

    if log_level > logging.DEBUG:
        for noisy in ("aiogram", "apscheduler", "gspread", "urllib3", "httpcore", "httpx"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Логирование запущено: уровень=%s, файл=%s",
        logging.getLevelName(log_level), log_path,
    )
