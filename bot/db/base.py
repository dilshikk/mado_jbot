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

# Маппинг SQLAlchemy-типов → SQL-тип для ALTER TABLE
# Используется при добавлении отсутствующих колонок
_SA_TYPE_TO_SQL: dict[str, str] = {
    "VARCHAR":   "VARCHAR",
    "TEXT":      "TEXT",
    "INTEGER":   "INTEGER",
    "BIGINT":    "BIGINT",
    "FLOAT":     "DOUBLE PRECISION",
    "BOOLEAN":   "BOOLEAN",
    "DATETIME":  "TIMESTAMP",
    "TIMESTAMP": "TIMESTAMP",
    "NUMERIC":   "NUMERIC",
}


def _sql_type_for_column(col) -> str:  # type: ignore[no-untyped-def]
    """Возвращает SQL-тип для ALTER TABLE ADD COLUMN."""
    type_name = type(col.type).__name__.upper()
    return _SA_TYPE_TO_SQL.get(type_name, "TEXT")


async def init_db() -> None:
    """Создаёт недостающие таблицы, добавляет недостающие колонки."""
    from bot.db import models  # noqa: F401 — регистрация моделей в metadata

    async with engine.begin() as conn:
        # ── 1. Проверяем какие таблицы существуют ────────────────────────────
        existing_tables: set[str] = set(
            await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )
        )
        expected_tables: set[str] = set(Base.metadata.tables.keys())
        missing_tables  = expected_tables - existing_tables
        present_tables  = expected_tables & existing_tables

        if present_tables:
            logger.info(
                "Таблицы уже существуют (%d): %s",
                len(present_tables), ", ".join(sorted(present_tables)),
            )
        if missing_tables:
            logger.warning(
                "Отсутствующие таблицы — будут созданы (%d): %s",
                len(missing_tables), ", ".join(sorted(missing_tables)),
            )
        else:
            logger.info("Все ожидаемые таблицы присутствуют.")

        # ── 2. Создаём отсутствующие таблицы (checkfirst=True по умолчанию) ──
        await conn.run_sync(Base.metadata.create_all)

        if missing_tables:
            now_existing: set[str] = set(
                await conn.run_sync(
                    lambda sync_conn: inspect(sync_conn).get_table_names()
                )
            )
            created = missing_tables & now_existing
            failed  = missing_tables - now_existing
            if created:
                logger.info("Таблицы созданы: %s", ", ".join(sorted(created)))
            if failed:
                logger.error("Не удалось создать таблицы: %s", ", ".join(sorted(failed)))

        # ── 3. Проверяем и добавляем отсутствующие КОЛОНКИ ───────────────────
        # create_all не добавляет колонки в уже существующие таблицы.
        # Делаем это вручную через ALTER TABLE ADD COLUMN IF NOT EXISTS.
        for table_name, table_obj in Base.metadata.tables.items():
            existing_cols: set[str] = set(
                await conn.run_sync(
                    lambda sync_conn, tn=table_name: {
                        c["name"]
                        for c in inspect(sync_conn).get_columns(tn)
                    }
                )
            )
            for col in table_obj.columns:
                if col.name in existing_cols:
                    continue
                sql_type  = _sql_type_for_column(col)
                nullable  = col.nullable
                null_part = "" if nullable else " NOT NULL"
                # DEFAULT нужен только для NOT NULL колонок без server_default
                default_part = ""
                if not nullable and col.default is not None:
                    raw = col.default.arg
                    if isinstance(raw, str):
                        default_part = f" DEFAULT '{raw}'"
                    elif isinstance(raw, (int, float)):
                        default_part = f" DEFAULT {raw}"
                try:
                    await conn.execute(
                        text(
                            f"ALTER TABLE {table_name} "
                            f"ADD COLUMN IF NOT EXISTS "
                            f"{col.name} {sql_type}{null_part}{default_part}"
                        )
                    )
                    logger.warning(
                        "Добавлена колонка: %s.%s (%s)", table_name, col.name, sql_type,
                    )
                except Exception as e:
                    logger.error(
                        "Не удалось добавить колонку %s.%s: %s", table_name, col.name, e,
                    )

    await _seed_vacancies()
    logger.info("БД инициализирована: %s", settings.database_url)


async def _seed_vacancies() -> None:
    from bot.db.models.vacancy import Vacancy

    defaults = [
        ("Повар",         "Oshpaz",       "👨‍🍳", 0),
        ("Официант",      "Ofitsiant",    "🤵",   1),
        ("Раннер",        "Yuguruvchi",   "🏃",   2),
        ("Бариста",       "Barista",      "☕️",  3),
        ("Тех. персонал", "Texnik xodim", "🧹",   4),
    ]

    async with session_pool() as session:
        count = await session.scalar(select(func.count(Vacancy.id)))
        if count:
            logger.info(
                "Вакансии уже есть в БД (%d шт.), сидирование пропущено.", count,
            )
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for name_ru, name_uz, emoji, order in defaults:
            session.add(Vacancy(
                name_ru=name_ru, name_uz=name_uz, emoji=emoji,
                is_active=1, sort_order=order, created_at=now,
            ))
        await session.commit()
    logger.info("Дефолтные вакансии добавлены (%d шт.).", len(defaults))
