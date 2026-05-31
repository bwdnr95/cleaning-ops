"""R14 pricing partner base, discount, and settlement timestamp

Revision ID: 0010_pricing_partner_base_and_discount
Revises: 0009_address_detail_and_soft_delete
Create Date: 2026-05-26
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_pricing_partner_base_and_discount"
down_revision = "0009_address_detail_and_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "service_items",
        sa.Column(
            "partner_base_price",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "discount_amount",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "orders",
        sa.Column("partner_settled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_orders_partner_settled_at",
        "orders",
        ["partner_settled_at"],
    )
    op.create_index(
        "ix_orders_partner_settlement_lookup",
        "orders",
        ["partner_id", "partner_payment_status", "scheduled_date"],
    )
    op.execute(
        """
        UPDATE orders
        SET vat_type = CASE
            WHEN vat_type IN ('포함', 'included') THEN 'included'
            WHEN vat_type IN ('별도', 'excluded') THEN 'excluded'
            ELSE 'included'
        END
        """
    )


def downgrade() -> None:
    op.drop_index("ix_orders_partner_settlement_lookup", table_name="orders")
    op.drop_index("ix_orders_partner_settled_at", table_name="orders")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_column("partner_settled_at")
        batch_op.drop_column("discount_amount")
    with op.batch_alter_table("service_items") as batch_op:
        batch_op.drop_column("partner_base_price")
