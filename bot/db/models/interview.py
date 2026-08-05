# bot/db/models/interview.py

from sqlalchemy import BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class InterviewSession(Base):
    """AI-интервью кандидата. Одна запись = одна сессия интервью."""
    __tablename__ = "interview_sessions"

    id:           Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id:      Mapped[int] = mapped_column(BigInteger, index=True)

    # JSON-список {"q": "...", "a": "..."} — хранится как текст
    qa_log:       Mapped[str] = mapped_column(Text, default="[]")
    # Количество заданных вопросов
    q_count:      Mapped[int] = mapped_column(default=0)
    # Статус: "active" | "done" | "skipped"
    status:       Mapped[str] = mapped_column(default="active")

    # ── Отчёты AI-агентов (JSON-строки) ──────────────────────────────────────
    # Уровень 2
    report_resume:        Mapped[str | None] = mapped_column(Text)  # Resume Extractor JSON
    report_communication: Mapped[str | None] = mapped_column(Text)  # Communication AI JSON
    report_integrity:     Mapped[str | None] = mapped_column(Text)  # Integrity AI JSON (Fraud+RedFlags)
    # Уровень 4
    report_job_match:     Mapped[str | None] = mapped_column(Text)  # Job Match AI JSON
    # Уровень 5
    report_decision:      Mapped[str | None] = mapped_column(Text)  # Hiring Decision AI JSON
    # Итоговый текст для HR-чата (рендерится в Python, не AI)
    report_summary:       Mapped[str | None] = mapped_column(Text)

    # ── Итоговый балл (денормализован для быстрой сортировки) ────────────────
    total_score:          Mapped[float | None] = mapped_column()

    # ── Обратная совместимость (старые поля, будут удалены после миграции) ───
    report_skills:        Mapped[str | None] = mapped_column(Text)
    report_personality:   Mapped[str | None] = mapped_column(Text)

    created_at:   Mapped[str]
    finished_at:  Mapped[str | None]
