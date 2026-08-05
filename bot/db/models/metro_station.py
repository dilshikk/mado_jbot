# bot/db/models/metro_station.py
"""Модель станций метро Ташкента.

Данные хранятся в БД — бот отображает название на языке пользователя.
Анкета хранит metro_station_id (int) вместо текстового названия.
"""

from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class MetroStation(Base):
    __tablename__ = "metro_stations"

    id:          Mapped[int]       = mapped_column(primary_key=True, autoincrement=True)
    name_ru:     Mapped[str]
    name_uz:     Mapped[str]
    name_en:     Mapped[str | None]
    line:        Mapped[str]        # red | blue | green | orange
    sort_order:  Mapped[int]        = mapped_column(default=0)
    active:      Mapped[int]        = mapped_column(default=1)
