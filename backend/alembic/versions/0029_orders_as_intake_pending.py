"""Add the explicit customer AS intake-pending marker."""

import sqlalchemy as sa

from alembic import op

revision = "0029_orders_as_intake_pending"
down_revision = "0028_orders_active_as_request_id"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "as_intake_pending",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS customer_token_ct2_or_null")
        op.execute("ALTER TABLE order_groups DROP CONSTRAINT IF EXISTS customer_token_ct2")
    op.drop_column("orders", "as_intake_pending")
