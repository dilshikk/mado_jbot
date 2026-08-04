# bot/db/base.py

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import func, select

from bot.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine       = create_async_engine(settings.database_url)
session_pool = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Создаёт все таблицы и сидит дефолтные вакансии."""
    from bot.db import models  # noqa: F401 — регистрация моделей в metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_vacancies()
    logger.info("БД инициализирована: %s", settings.database_url)


async def _seed_vacancies() -> None:
    from bot.db.models.vacancy import Vacancy

    async with session_pool() as session:
        count = await session.scalar(select(func.count(Vacancy.id)))
        if count:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        defaults = [
            ("Повар",         "Oshpaz",       "👨‍🍳", 0),
            ("Официант",      "Ofitsiant",    "🤵",   1),
            ("Раннер",        "Yuguruvchi",   "🏃",   2),
            ("Бариста",       "Barista",      "☕️",  3),
            ("Тех. персонал", "Texnik xodim", "🧹",   4),
        ]
        for name_ru, name_uz, emoji, order in defaults:
            session.add(Vacancy(
                name_ru=name_ru, name_uz=name_uz, emoji=emoji,
                is_active=1, sort_order=order, created_at=now,
            ))
        await session.commit()
    logger.info("Дефолтные вакансии добавлены.")
