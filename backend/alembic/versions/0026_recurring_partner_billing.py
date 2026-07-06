"""정기청소 협력사 정산방식

Revision ID: 0026_recurring_partner_billing
Revises: 0025_order_work_evidence
Create Date: 2026-07-06
"""

from alembic import op
import sqlalchemy as sa

revision = "0026_recurring_partner_billing"
down_revision = "0025_order_work_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recurring_contracts",
        sa.Column("partner_billing_mode", sa.String(length=20), nullable=False, server_default="per_visit"),
    )
    op.add_column(
        "recurring_monthly_status",
        sa.Column("partner_payment_paid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("recurring_monthly_status", "partner_payment_paid")
    op.drop_column("recurring_contracts", "partner_billing_mode")
