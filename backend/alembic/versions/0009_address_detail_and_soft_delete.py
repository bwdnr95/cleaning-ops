"""R8 address detail + soft delete

Revision ID: 0009_address_detail_and_soft_delete
Revises: 0008_order_groups
Create Date: 2026-05-20
"""

import sqlalchemy as sa

from alembic import op

revision = "0009_address_detail_and_soft_delete"
down_revision = "0008_order_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column(
            "alembic_version",
            "version_num",
            existing_type=sa.String(length=32),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
    op.add_column(
        "order_groups",
        sa.Column("customer_address_detail", sa.Text(), nullable=True),
    )
    op.add_column(
        "order_groups",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_orders_deleted_at", "orders", ["deleted_at"])
    op.create_index("ix_order_groups_deleted_at", "order_groups", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_order_groups_deleted_at", table_name="order_groups")
    op.drop_index("ix_orders_deleted_at", table_name="orders")
    op.drop_column("orders", "deleted_at")
    op.drop_column("order_groups", "deleted_at")
    op.drop_column("order_groups", "customer_address_detail")
