"""중개사(broker) 관리 — brokers + orders.broker_id

Revision ID: 0019_brokers
Revises: 0018_recurring_monthly_status
Create Date: 2026-07-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0019_brokers"
down_revision = "0018_recurring_monthly_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brokers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("manager_name", sa.String(length=80), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("manager_phone", sa.String(length=30), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_brokers"),
    )
    op.create_index("ix_brokers_name", "brokers", ["name"])

    op.add_column(
        "orders",
        sa.Column(
            "broker_id",
            sa.String(length=36),
            sa.ForeignKey("brokers.id", name="fk_orders_broker_id_brokers"),
            nullable=True,
        ),
    )
    op.create_index("ix_orders_broker_id", "orders", ["broker_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_broker_id", table_name="orders")
    op.drop_constraint("fk_orders_broker_id_brokers", "orders", type_="foreignkey")
    op.drop_column("orders", "broker_id")
    op.drop_index("ix_brokers_name", table_name="brokers")
    op.drop_table("brokers")
