# bot/db/base.py

import logging
from datetime import datetime

from sqlalchemy import func, inspect, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from bot.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# pool_pre_ping — проверяет соединение перед использованием,
# защищает от ошибок при разрывах соединения с Postgres
engine       = create_async_engine(settings.database_url, pool_pre_ping=True)
session_pool = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Создаёт недостающие таблицы и сидирует дефолтные вакансии."""
    from bot.db import models  # noqa: F401 — регистрация моделей в metadata

    async with engine.begin() as conn:
        # Узнаём какие таблицы уже существуют в БД
        existing: set[str] = set(
            await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )
        )

        expected: set[str] = set(Base.metadata.tables.keys())
        missing  = expected - existing
        present  = expected & existing

        if present:
            logger.info("Таблицы уже существуют (%d): %s", len(present), ", ".join(sorted(present)))
        if missing:
            logger.warning("Отсутствующие таблицы — будут созданы (%d): %s", len(missing), ", ".join(sorted(missing)))
        else:
            logger.info("Все ожидаемые таблицы присутствуют, миграция не требуется.")

        # create_all создаёт только те таблицы, которых ещё нет (checkfirst=True по умолчанию)
        await conn.run_sync(Base.metadata.create_all)

        if missing:
            # Проверяем что таблицы действительно созданы
            now_existing: set[str] = set(
                await conn.run_sync(
                    lambda sync_conn: inspect(sync_conn).get_table_names()
                )
            )
            created   = missing & now_existing
            failed    = missing - now_existing
            if created:
                logger.info("Таблицы успешно созданы: %s", ", ".join(sorted(created)))
            if failed:
                logger.error("Не удалось создать таблицы: %s", ", ".join(sorted(failed)))

    await _seed_vacancies()
    logger.info("БД инициализирована: %s", settings.database_url)


async def _seed_vacancies() -> None:
    from bot.db.models.vacancy import Vacancy

    async with session_pool() as session:
        count = await session.scalar(select(func.count(Vacancy.id)))
        if count:
            logger.info("Вакансии уже есть в БД (%d шт.), сидирование пропущено.", count)
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
    logger.info("Дефолтные вакансии добавлены (%d шт.).", len(defaults))
