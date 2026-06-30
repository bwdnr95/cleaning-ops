"""정기청소 월 트래커 — recurring_monthly_status

Revision ID: 0018_recurring_monthly_status
Revises: 0017_recurring_weekdays
Create Date: 2026-07-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_recurring_monthly_status"
down_revision = "0017_recurring_weekdays"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recurring_monthly_status",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("contract_id", sa.String(length=36), nullable=False),
        sa.Column("billing_month", sa.String(length=7), nullable=False),
        sa.Column("tax_invoice_issued", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("balance_paid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["contract_id"], ["recurring_contracts.id"], name="fk_recurring_monthly_status_contract_id_recurring_contracts"),
        sa.PrimaryKeyConstraint("id", name="pk_recurring_monthly_status"),
        sa.UniqueConstraint("contract_id", "billing_month", name="uq_recurring_monthly_contract_month"),
    )
    op.create_index("ix_recurring_monthly_status_contract_id", "recurring_monthly_status", ["contract_id"])
    op.create_index("ix_recurring_monthly_status_billing_month", "recurring_monthly_status", ["billing_month"])


def downgrade() -> None:
    op.drop_table("recurring_monthly_status")
