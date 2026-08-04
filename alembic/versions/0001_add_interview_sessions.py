"""add interview_sessions table

Revision ID: 0001
Revises:
Create Date: 2026-08-04

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_sessions",
        sa.Column("id",                 sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column("user_id",            sa.BigInteger(), nullable=False, index=True),
        sa.Column("qa_log",             sa.Text(),       nullable=False, server_default="[]"),
        sa.Column("q_count",            sa.Integer(),    nullable=False, server_default="0"),
        sa.Column("status",             sa.String(),     nullable=False, server_default="active"),
        sa.Column("report_resume",      sa.Text(),       nullable=True),
        sa.Column("report_skills",      sa.Text(),       nullable=True),
        sa.Column("report_personality", sa.Text(),       nullable=True),
        sa.Column("report_job_match",   sa.Text(),       nullable=True),
        sa.Column("report_summary",     sa.Text(),       nullable=True),
        sa.Column("created_at",         sa.String(),     nullable=False),
        sa.Column("finished_at",        sa.String(),     nullable=True),
    )
    op.create_index("ix_interview_sessions_user_id", "interview_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_interview_sessions_user_id", table_name="interview_sessions")
    op.drop_table("interview_sessions")
