"""add message delivery status metadata

Revision ID: 0004_message_delivery_status
Revises: 0003_message_provider_metadata
Create Date: 2026-05-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_message_delivery_status"
down_revision: str | None = "0003_message_provider_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("message_logs", sa.Column("provider_status_code", sa.String(length=80)))
    op.add_column("message_logs", sa.Column("provider_status_message", sa.String(length=255)))
    op.add_column("message_logs", sa.Column("provider_reported_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("message_logs", "provider_reported_at")
    op.drop_column("message_logs", "provider_status_message")
    op.drop_column("message_logs", "provider_status_code")
