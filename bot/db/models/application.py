# bot/db/models/application.py

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class Application(Base):
    __tablename__ = "applications"

    id:               Mapped[int]       = mapped_column(primary_key=True, autoincrement=True)
    user_id:          Mapped[int]       = mapped_column(BigInteger)
    name:             Mapped[str | None]
    birthday:         Mapped[str | None]
    phone:            Mapped[str | None]
    position:         Mapped[str | None]
    status:           Mapped[str]       = mapped_column(default="pending")
    interview_time:   Mapped[str | None]
    reminder_sent:    Mapped[int]       = mapped_column(default=0)
    view_count:       Mapped[int]       = mapped_column(default=0)
    notified_pending: Mapped[int]       = mapped_column(default=0)
    hr_score:         Mapped[int | None]
    hr_comment:       Mapped[str | None]
    hr_video_msg_id:  Mapped[int | None]
    experience:       Mapped[str | None]
    created_at:       Mapped[str]
