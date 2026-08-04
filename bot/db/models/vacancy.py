# bot/db/models/vacancy.py

from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class Vacancy(Base):
    __tablename__ = "vacancies"

    id:         Mapped[int]       = mapped_column(primary_key=True, autoincrement=True)
    name_ru:    Mapped[str]
    name_uz:    Mapped[str]
    emoji:      Mapped[str]       = mapped_column(default="")
    is_active:  Mapped[int]       = mapped_column(default=1)
    sort_order: Mapped[int]       = mapped_column(default=0)
    created_at: Mapped[str | None]
