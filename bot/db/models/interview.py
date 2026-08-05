# bot/db/models/interview.py

from sqlalchemy import BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class InterviewSession(Base):
    """AI-интервью кандидата. Одна запись = одна сессия интервью."""
    __tablename__ = "interview_sessions"

    id:           Mapped[int]       = mapped_column(primary_key=True, autoincrement=True)
    user_id:      Mapped[int]       = mapped_column(BigInteger, index=True)
    # JSON-список {"q": "...", "a": "..."} — хранится как текст
    qa_log:       Mapped[str]       = mapped_column(Text, default="[]")
    # Количество заданных вопросов
    q_count:      Mapped[int]       = mapped_column(default=0)
    # Статус: "active" | "done" | "skipped"
    status:       Mapped[str]       = mapped_column(default="active")
    # Итоговые AI-отчёты (каждый — текст)
    report_resume:      Mapped[str | None] = mapped_column(Text)
    report_skills:      Mapped[str | None] = mapped_column(Text)
    report_personality: Mapped[str | None] = mapped_column(Text)
    report_job_match:   Mapped[str | None] = mapped_column(Text)
    report_summary:     Mapped[str | None] = mapped_column(Text)
    created_at:   Mapped[str]
    finished_at:  Mapped[str | None]
