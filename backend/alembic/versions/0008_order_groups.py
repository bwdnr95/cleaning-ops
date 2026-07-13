"""Add order_groups + backfill 1:1 groups from existing orders.

Revision ID: 0008_order_groups
Revises: 0007_auto_publish_legacy_photos
Create Date: 2026-05-18
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "0008_order_groups"
down_revision: str | None = "0007_auto_publish_legacy_photos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "order_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer_token", sa.String(80), nullable=False),
        sa.Column("customer_name", sa.String(80), nullable=False),
        sa.Column("customer_phone", sa.String(30), nullable=False),
        sa.Column("customer_address", sa.Text(), nullable=False),
        sa.Column("source_channel", sa.String(120), nullable=True),
        sa.Column(
            "customer_visible_payment", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_order_groups_customer_token", "order_groups", ["customer_token"], unique=True
    )
    op.create_index("ix_order_groups_customer_name", "order_groups", ["customer_name"])
    op.create_index("ix_order_groups_customer_phone", "order_groups", ["customer_phone"])

    op.add_column("orders", sa.Column("group_id", sa.String(36), nullable=True))

    bind = op.get_bind()
    if context.is_offline_mode():
        op.execute("-- Online data backfill creates one order_group per existing order.")
    else:
        existing_orders = bind.execute(
            sa.text(
                """
                SELECT id, customer_token, customer_name, customer_phone, customer_address,
                       source_channel, customer_visible_payment, created_at, updated_at
                FROM orders
                WHERE customer_token IS NOT NULL
                """
            )
        ).fetchall()

        for row in existing_orders:
            group_id = str(uuid.uuid4())
            bind.execute(
                sa.text(
                    """
                    INSERT INTO order_groups (
                        id, customer_token, customer_name, customer_phone, customer_address,
                        source_channel, customer_visible_payment, created_at, updated_at
                    )
                    VALUES (
                        :id, :token, :name, :phone, :address,
                        :source, :visible, :created, :updated
                    )
                    """
                ),
                {
                    "id": group_id,
                    "token": row.customer_token,
                    "name": row.customer_name,
                    "phone": row.customer_phone,
                    "address": row.customer_address,
                    "source": row.source_channel,
                    "visible": bool(row.customer_visible_payment)
                    if row.customer_visible_payment is not None
                    else False,
                    "created": row.created_at,
                    "updated": row.updated_at,
                },
            )
            bind.execute(
                sa.text("UPDATE orders SET group_id = :group_id WHERE id = :order_id"),
                {"group_id": group_id, "order_id": row.id},
            )

    orders_target = sa.Table(
        "orders",
        sa.MetaData(),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default=sa.literal("신규접수")),
        sa.Column("received_date", sa.Date(), nullable=False),
        sa.Column("scheduled_date", sa.Date()),
        sa.Column("requested_time", sa.String(80)),
        sa.Column("partner_id", sa.String(36), sa.ForeignKey("partners.id")),
        sa.Column("team_name", sa.String(120)),
        sa.Column("service_category_id", sa.String(36), sa.ForeignKey("service_categories.id")),
        sa.Column("service_item_id", sa.String(36), sa.ForeignKey("service_items.id")),
        sa.Column("service_name", sa.String(160), nullable=False),
        sa.Column("size_or_quantity", sa.String(80)),
        sa.Column("service_detail", sa.Text()),
        sa.Column("special_request", sa.Text()),
        sa.Column("source_channel", sa.String(120)),
        sa.Column("customer_name", sa.String(80)),
        sa.Column("customer_phone", sa.String(30)),
        sa.Column("customer_address", sa.Text()),
        sa.Column("total_amount", sa.Numeric(12, 2)),
        sa.Column("deposit_amount", sa.Numeric(12, 2)),
        sa.Column("balance_amount", sa.Numeric(12, 2)),
        sa.Column("onsite_extra_amount", sa.Numeric(12, 2)),
        sa.Column("vat_type", sa.String(20)),
        sa.Column("payment_status", sa.String(40)),
        sa.Column("payment_memo", sa.Text()),
        sa.Column("evidence_memo", sa.Text()),
        sa.Column("partner_payment_amount", sa.Numeric(12, 2)),
        sa.Column("partner_payment_status", sa.String(40)),
        sa.Column("customer_token", sa.String(80)),
        sa.Column("customer_visible_payment", sa.Boolean(), server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Index("ix_orders_status", "status"),
        sa.Index("ix_orders_received_date", "received_date"),
        sa.Index("ix_orders_scheduled_date", "scheduled_date"),
        sa.Index("ix_orders_partner_id", "partner_id"),
        sa.Index("ix_orders_customer_name", "customer_name"),
        sa.Index("ix_orders_customer_phone", "customer_phone"),
        sa.Index("ix_orders_customer_token", "customer_token"),
        sa.Index("ix_orders_payment_status", "payment_status"),
    )

    with op.batch_alter_table("orders", copy_from=orders_target) as batch_op:
        batch_op.alter_column("group_id", existing_type=sa.String(36), nullable=False)
        batch_op.create_index("ix_orders_group_id", ["group_id"])
        batch_op.create_foreign_key(
            "fk_orders_group_id_order_groups",
            "order_groups",
            ["group_id"],
            ["id"],
        )
        batch_op.alter_column("customer_token", existing_type=sa.String(80), nullable=True)
        batch_op.alter_column("customer_name", existing_type=sa.String(80), nullable=True)
        batch_op.alter_column("customer_phone", existing_type=sa.String(30), nullable=True)
        batch_op.alter_column("customer_address", existing_type=sa.Text(), nullable=True)
        batch_op.alter_column(
            "customer_visible_payment",
            existing_type=sa.Boolean(),
            nullable=True,
            existing_server_default=sa.false(),
        )

    dialect = bind.dialect.name
    if dialect == "postgresql":
        bind.execute(
            sa.text("ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_customer_token_key")
        )
        bind.execute(
            sa.text("ALTER TABLE orders DROP CONSTRAINT IF EXISTS uq_orders_customer_token")
        )


def downgrade() -> None:
    # Intentional no-op: restore from a DB backup if this structural migration must roll back.
    pass
