"""add communication, integrity, decision columns + total_score to interview_sessions

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-05
"""

from alembic import op
import sqlalchemy as sa

revision    = "0002"
down_revision = "0001"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.add_column("interview_sessions",
        sa.Column("report_communication", sa.Text(), nullable=True))
    op.add_column("interview_sessions",
        sa.Column("report_integrity",     sa.Text(), nullable=True))
    op.add_column("interview_sessions",
        sa.Column("report_decision",      sa.Text(), nullable=True))
    op.add_column("interview_sessions",
        sa.Column("total_score",          sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("interview_sessions", "total_score")
    op.drop_column("interview_sessions", "report_decision")
    op.drop_column("interview_sessions", "report_integrity")
    op.drop_column("interview_sessions", "report_communication")
