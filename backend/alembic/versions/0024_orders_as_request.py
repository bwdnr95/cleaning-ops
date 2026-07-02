"""AS 요청 — orders.as_requested / as_memo

Revision ID: 0024_orders_as_request
Revises: 0023_recurring_billing_mode
Create Date: 2026-07-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0024_orders_as_request"
down_revision = "0023_recurring_billing_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("as_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("orders", sa.Column("as_memo", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "as_memo")
    op.drop_column("orders", "as_requested")
