"""add message provider metadata

Revision ID: 0003_message_provider_metadata
Revises: 0002_photo_storage_metadata
Create Date: 2026-05-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_message_provider_metadata"
down_revision: str | None = "0002_photo_storage_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("message_logs", sa.Column("provider", sa.String(length=40), server_default="mock"))
    op.add_column("message_logs", sa.Column("provider_message_id", sa.String(length=160)))
    op.add_column("message_logs", sa.Column("provider_group_id", sa.String(length=160)))
    op.add_column("message_logs", sa.Column("provider_error_code", sa.String(length=80)))
    op.add_column("message_logs", sa.Column("provider_response", sa.JSON()))
    op.add_column("message_logs", sa.Column("requested_at", sa.DateTime(timezone=True)))
    op.add_column("message_logs", sa.Column("delivered_at", sa.DateTime(timezone=True)))
    op.create_index("ix_message_logs_provider", "message_logs", ["provider"])
    op.create_index("ix_message_logs_provider_group_id", "message_logs", ["provider_group_id"])


def downgrade() -> None:
    op.drop_index("ix_message_logs_provider_group_id", table_name="message_logs")
    op.drop_index("ix_message_logs_provider", table_name="message_logs")
    op.drop_column("message_logs", "delivered_at")
    op.drop_column("message_logs", "requested_at")
    op.drop_column("message_logs", "provider_response")
    op.drop_column("message_logs", "provider_error_code")
    op.drop_column("message_logs", "provider_group_id")
    op.drop_column("message_logs", "provider_message_id")
    op.drop_column("message_logs", "provider")
