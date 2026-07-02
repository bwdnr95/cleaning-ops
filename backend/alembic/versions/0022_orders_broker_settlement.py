"""중개사 수수료 정산 — orders.broker_payment_amount/status/settled_at

Revision ID: 0022_orders_broker_settlement
Revises: 0021_orders_recurring_slot
Create Date: 2026-07-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0022_orders_broker_settlement"
down_revision = "0021_orders_recurring_slot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("broker_payment_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("orders", sa.Column("broker_payment_status", sa.String(length=40), nullable=True))
    op.add_column("orders", sa.Column("broker_settled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "broker_settled_at")
    op.drop_column("orders", "broker_payment_status")
    op.drop_column("orders", "broker_payment_amount")
