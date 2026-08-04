# bot/db/models/blacklist.py

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class Blacklist(Base):
    __tablename__ = "blacklist"

    user_id:    Mapped[int]       = mapped_column(BigInteger, primary_key=True)
    blocked_at: Mapped[str | None]
    unblock_at: Mapped[str | None]
