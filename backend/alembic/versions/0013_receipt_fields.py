"""주문 증빙자료(현금영수증/세금계산서) 구조화 필드

Revision ID: 0013_receipt_fields
Revises: 0012_user_phone_unique
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_receipt_fields"
down_revision = "0012_user_phone_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("receipt_type", sa.String(length=20), nullable=True))
    op.add_column("orders", sa.Column("receipt_status", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "receipt_status")
    op.drop_column("orders", "receipt_type")
