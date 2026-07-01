"""정기 주문 멱등 슬롯 — orders.recurring_planned_date + uq(recurring_contract_id, recurring_planned_date)

Revision ID: 0021_orders_recurring_slot
Revises: 0020_recurring_team_phone
Create Date: 2026-07-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0021_orders_recurring_slot"
down_revision = "0020_recurring_team_phone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("recurring_planned_date", sa.Date(), nullable=True))
    op.create_index("ix_orders_recurring_planned_date", "orders", ["recurring_planned_date"])
    # 같은 계약의 같은 생성 예정일은 1건만. 일회성 주문은 (NULL, NULL)이라 제약 무관(NULL은 서로 구별).
    op.create_unique_constraint(
        "uq_orders_recurring_slot",
        "orders",
        ["recurring_contract_id", "recurring_planned_date"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_orders_recurring_slot", "orders", type_="unique")
    op.drop_index("ix_orders_recurring_planned_date", table_name="orders")
    op.drop_column("orders", "recurring_planned_date")
