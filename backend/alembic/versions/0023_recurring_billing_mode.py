"""정기청소 청구방식 — recurring_contracts.billing_mode (per_visit/monthly)

Revision ID: 0023_recurring_billing_mode
Revises: 0022_orders_broker_settlement
Create Date: 2026-07-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0023_recurring_billing_mode"
down_revision = "0022_orders_broker_settlement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 기존 계약은 '1주기 금액'(회당 개념)이었으므로 per_visit 로 채운다.
    op.add_column(
        "recurring_contracts",
        sa.Column("billing_mode", sa.String(length=20), nullable=False, server_default="per_visit"),
    )


def downgrade() -> None:
    op.drop_column("recurring_contracts", "billing_mode")
