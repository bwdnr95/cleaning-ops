"""정기청소 계약 담당자 연락처 — recurring_contracts.team_phone

Revision ID: 0020_recurring_team_phone
Revises: 0019_brokers
Create Date: 2026-07-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0020_recurring_team_phone"
down_revision = "0019_brokers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recurring_contracts",
        sa.Column("team_phone", sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recurring_contracts", "team_phone")
