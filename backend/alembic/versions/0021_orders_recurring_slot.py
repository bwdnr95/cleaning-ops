"""정기 주문 멱등 슬롯.

orders.recurring_planned_date와 계약별 예정일 unique constraint를 추가한다.

Revision ID: 0021_orders_recurring_slot
Revises: 0020_recurring_team_phone
Create Date: 2026-07-01
"""

import sqlalchemy as sa

from alembic import op

revision = "0021_orders_recurring_slot"
down_revision = "0020_recurring_team_phone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("orders") as batch_op:
            batch_op.add_column(sa.Column("recurring_planned_date", sa.Date(), nullable=True))
            batch_op.create_index(
                "ix_orders_recurring_planned_date",
                ["recurring_planned_date"],
            )
            batch_op.create_unique_constraint(
                "uq_orders_recurring_slot",
                ["recurring_contract_id", "recurring_planned_date"],
            )
    else:
        op.add_column("orders", sa.Column("recurring_planned_date", sa.Date(), nullable=True))
        op.create_index("ix_orders_recurring_planned_date", "orders", ["recurring_planned_date"])
        # 같은 계약의 같은 생성 예정일은 1건만 허용한다.
        # 일회성 주문의 (NULL, NULL)은 SQL NULL 의미상 제약 대상이 아니다.
        op.create_unique_constraint(
            "uq_orders_recurring_slot",
            "orders",
            ["recurring_contract_id", "recurring_planned_date"],
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("orders") as batch_op:
            batch_op.drop_constraint("uq_orders_recurring_slot", type_="unique")
            batch_op.drop_index("ix_orders_recurring_planned_date")
            batch_op.drop_column("recurring_planned_date")
    else:
        op.drop_constraint("uq_orders_recurring_slot", "orders", type_="unique")
        op.drop_index("ix_orders_recurring_planned_date", table_name="orders")
        op.drop_column("orders", "recurring_planned_date")
