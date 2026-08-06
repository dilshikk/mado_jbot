# bot/db/models/application.py

from sqlalchemy import BigInteger, Text
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
    metro_station_id: Mapped[int | None]
    created_at:       Mapped[str]

    # ── Расширенные поля анкеты ────────────────────────────────────────────────
    gender:           Mapped[str | None]
    branch:           Mapped[str | None]
    # Языки хранятся как JSON-строка вида '["ru","en"]'
    languages:        Mapped[str | None] = mapped_column(Text)
    readiness:        Mapped[str | None]
    exp_company:      Mapped[str | None]
    exp_position:     Mapped[str | None]
    exp_duration:     Mapped[str | None]
    exp_duties:       Mapped[str | None]
    salary:           Mapped[str | None]
    schedule:         Mapped[str | None]
    evening_shifts:   Mapped[str | None]
    weekends:         Mapped[str | None]
    smoking:          Mapped[str | None]
    med_book:         Mapped[str | None]
    photo_file_id:    Mapped[str | None]
    video_file_id:    Mapped[str | None]
    is_video_note:    Mapped[int]        = mapped_column(default=0)
    video_duration:   Mapped[int]        = mapped_column(default=0)
    username:         Mapped[str | None]
    first_name:       Mapped[str | None]
    last_name:        Mapped[str | None]
