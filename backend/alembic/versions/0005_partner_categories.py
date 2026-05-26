"""add partner categories

Revision ID: 0005_partner_categories
Revises: 0004_message_delivery_status
Create Date: 2026-05-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_partner_categories"
down_revision: str | None = "0004_message_delivery_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "partner_categories",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *timestamp_columns(),
    )
    op.create_index("ix_partner_categories_name", "partner_categories", ["name"])

    with op.batch_alter_table("partners") as batch_op:
        batch_op.add_column(sa.Column("partner_category_id", sa.String(length=80)))
        batch_op.create_foreign_key(
            "fk_partners_partner_category_id_partner_categories",
            "partner_categories",
            ["partner_category_id"],
            ["id"],
        )
        batch_op.create_index("ix_partners_partner_category_id", ["partner_category_id"])


def downgrade() -> None:
    with op.batch_alter_table("partners") as batch_op:
        batch_op.drop_index("ix_partners_partner_category_id")
        batch_op.drop_constraint("fk_partners_partner_category_id_partner_categories", type_="foreignkey")
        batch_op.drop_column("partner_category_id")

    op.drop_index("ix_partner_categories_name", table_name="partner_categories")
    op.drop_table("partner_categories")
