# bot/db/models/user.py

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class User(Base):
    __tablename__ = "users"

    user_id:    Mapped[int]       = mapped_column(BigInteger, primary_key=True)
    username:   Mapped[str | None]
    first_name: Mapped[str | None]
    lang:       Mapped[str]       = mapped_column(default="ru")
    created_at: Mapped[str]
