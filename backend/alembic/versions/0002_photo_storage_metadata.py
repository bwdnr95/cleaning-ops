"""add photo storage metadata

Revision ID: 0002_photo_storage_metadata
Revises: 0001_initial_schema
Create Date: 2026-05-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_photo_storage_metadata"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("order_photos", sa.Column("storage_key", sa.String(length=500)))
    op.add_column("order_photos", sa.Column("content_type", sa.String(length=120)))
    op.create_index("ix_order_photos_storage_key", "order_photos", ["storage_key"])


def downgrade() -> None:
    op.drop_index("ix_order_photos_storage_key", table_name="order_photos")
    op.drop_column("order_photos", "content_type")
    op.drop_column("order_photos", "storage_key")
