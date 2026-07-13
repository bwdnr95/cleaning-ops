"""Allow customer AS photos without an authenticated uploader."""

import sqlalchemy as sa

from alembic import op

revision = "0027_nullable_customer_photo_uploader"
down_revision = "0026_recurring_partner_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("order_photos") as batch_op:
        batch_op.alter_column(
            "uploaded_by_user_id",
            existing_type=sa.String(length=36),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("order_photos") as batch_op:
        batch_op.alter_column(
            "uploaded_by_user_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )
