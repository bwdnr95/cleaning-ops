"""주문 활성 AS 요청 ID 추가

Revision ID: 0028_orders_active_as_request_id
Revises: 0027_nullable_customer_photo_uploader
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0028_orders_active_as_request_id"
down_revision = "0027_nullable_customer_photo_uploader"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("active_as_request_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_orders_active_as_request_id", ["active_as_request_id"])


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_index("ix_orders_active_as_request_id")
        batch_op.drop_column("active_as_request_id")
