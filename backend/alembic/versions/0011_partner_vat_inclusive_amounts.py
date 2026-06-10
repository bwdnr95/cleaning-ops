"""Partner prices include VAT from June 2026

Revision ID: 0011_partner_vat_inclusive_amounts
Revises: 0010_pricing_partner_base_and_discount
Create Date: 2026-06-07
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from alembic import op
import sqlalchemy as sa

revision = "0011_partner_vat_inclusive_amounts"
down_revision = "0010_pricing_partner_base_and_discount"
branch_labels = None
depends_on = None

EFFECTIVE_DATE = date(2026, 6, 1)
VAT_MULTIPLIER = Decimal("1.10")


def upgrade() -> None:
    bind = op.get_bind()
    orders = sa.table(
        "orders",
        sa.column("id"),
        sa.column("scheduled_date"),
        sa.column("partner_payment_amount"),
        sa.column("partner_payment_status"),
        sa.column("partner_settled_at"),
        sa.column("deleted_at"),
    )
    service_items = sa.table(
        "service_items",
        sa.column("id"),
        sa.column("partner_base_price"),
    )

    service_item_rows = bind.execute(
        sa.select(service_items.c.id, service_items.c.partner_base_price).where(
            service_items.c.partner_base_price.is_not(None),
            service_items.c.partner_base_price > 0,
        )
    ).mappings()
    for row in service_item_rows:
        bind.execute(
            sa.update(service_items)
            .where(service_items.c.id == row["id"])
            .values(partner_base_price=_gross_up(row["partner_base_price"]))
        )

    order_rows = bind.execute(
        sa.select(orders.c.id, orders.c.partner_payment_amount).where(
            orders.c.deleted_at.is_(None),
            orders.c.scheduled_date >= EFFECTIVE_DATE,
            orders.c.partner_payment_amount.is_not(None),
            orders.c.partner_payment_amount > 0,
            orders.c.partner_settled_at.is_(None),
            (orders.c.partner_payment_status.is_(None) | (orders.c.partner_payment_status != "paid")),
        )
    ).mappings()
    for row in order_rows:
        bind.execute(
            sa.update(orders)
            .where(orders.c.id == row["id"])
            .values(partner_payment_amount=_gross_up(row["partner_payment_amount"]))
        )


def downgrade() -> None:
    # Irreversible data migration: dividing by 1.1 later would corrupt values edited after upgrade.
    pass


def _gross_up(amount: object) -> Decimal:
    return (Decimal(str(amount)) * VAT_MULTIPLIER).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
