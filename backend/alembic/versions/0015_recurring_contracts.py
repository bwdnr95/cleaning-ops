"""정기청소 — RecurringContract/Occurrence + orders.recurring_contract_id

Revision ID: 0015_recurring_contracts
Revises: 0014_partner_manager_phone
Create Date: 2026-06-28
"""

import sqlalchemy as sa

from alembic import op

revision = "0015_recurring_contracts"
down_revision = "0014_partner_manager_phone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recurring_contracts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("order_group_id", sa.String(length=36), nullable=False),
        sa.Column("recurrence_mode", sa.String(length=20), nullable=False),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("interval_weeks", sa.Integer(), nullable=True),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("max_occurrences", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("default_partner_id", sa.String(length=36), nullable=True),
        sa.Column("team_name", sa.String(length=120), nullable=True),
        sa.Column("service_category_id", sa.String(length=36), nullable=True),
        sa.Column("service_item_id", sa.String(length=36), nullable=True),
        sa.Column("service_name", sa.String(length=160), nullable=False),
        sa.Column("size_or_quantity", sa.String(length=80), nullable=True),
        sa.Column("service_detail", sa.Text(), nullable=True),
        sa.Column("special_request", sa.Text(), nullable=True),
        sa.Column("requested_time", sa.String(length=80), nullable=True),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("deposit_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("balance_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("vat_type", sa.String(length=20), nullable=True),
        sa.Column("partner_payment_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["order_group_id"],
            ["order_groups.id"],
            name="fk_recurring_contracts_order_group_id_order_groups",
        ),
        sa.ForeignKeyConstraint(
            ["default_partner_id"],
            ["partners.id"],
            name="fk_recurring_contracts_default_partner_id_partners",
        ),
        sa.ForeignKeyConstraint(
            ["service_category_id"],
            ["service_categories.id"],
            name="fk_recurring_contracts_service_category_id_service_categories",
        ),
        sa.ForeignKeyConstraint(
            ["service_item_id"],
            ["service_items.id"],
            name="fk_recurring_contracts_service_item_id_service_items",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recurring_contracts"),
    )
    op.create_index(
        "ix_recurring_contracts_order_group_id", "recurring_contracts", ["order_group_id"]
    )
    op.create_index("ix_recurring_contracts_start_date", "recurring_contracts", ["start_date"])
    op.create_index("ix_recurring_contracts_status", "recurring_contracts", ["status"])
    op.create_index("ix_recurring_contracts_deleted_at", "recurring_contracts", ["deleted_at"])

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("orders") as batch_op:
            batch_op.add_column(
                sa.Column("recurring_contract_id", sa.String(length=36), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_orders_recurring_contract_id_recurring_contracts",
                "recurring_contracts",
                ["recurring_contract_id"],
                ["id"],
            )
            batch_op.create_index(
                "ix_orders_recurring_contract_id",
                ["recurring_contract_id"],
            )
    else:
        op.add_column(
            "orders",
            sa.Column(
                "recurring_contract_id",
                sa.String(length=36),
                sa.ForeignKey(
                    "recurring_contracts.id",
                    name="fk_orders_recurring_contract_id_recurring_contracts",
                ),
                nullable=True,
            ),
        )
        op.create_index("ix_orders_recurring_contract_id", "orders", ["recurring_contract_id"])

    op.create_table(
        "recurring_occurrences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("contract_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("billing_month", sa.String(length=7), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("generated_order_id", sa.String(length=36), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skipped_reason", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["recurring_contracts.id"],
            name="fk_recurring_occurrences_contract_id_recurring_contracts",
        ),
        sa.ForeignKeyConstraint(
            ["generated_order_id"],
            ["orders.id"],
            name="fk_recurring_occurrences_generated_order_id_orders",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recurring_occurrences"),
        sa.UniqueConstraint("contract_id", "due_date", name="uq_recurring_occurrence_contract_due"),
    )
    op.create_index(
        "ix_recurring_occurrences_contract_id", "recurring_occurrences", ["contract_id"]
    )
    op.create_index("ix_recurring_occurrences_due_date", "recurring_occurrences", ["due_date"])
    op.create_index("ix_recurring_occurrences_status", "recurring_occurrences", ["status"])


def downgrade() -> None:
    op.drop_table("recurring_occurrences")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("orders") as batch_op:
            batch_op.drop_index("ix_orders_recurring_contract_id")
            batch_op.drop_constraint(
                "fk_orders_recurring_contract_id_recurring_contracts",
                type_="foreignkey",
            )
            batch_op.drop_column("recurring_contract_id")
    else:
        op.drop_index("ix_orders_recurring_contract_id", table_name="orders")
        op.drop_constraint(
            "fk_orders_recurring_contract_id_recurring_contracts",
            "orders",
            type_="foreignkey",
        )
        op.drop_column("orders", "recurring_contract_id")
    op.drop_table("recurring_contracts")
