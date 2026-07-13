"""고객 AS 사진 업로더 nullable 허용

Revision ID: 0027_nullable_customer_photo_uploader
Revises: 0026_recurring_partner_billing
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa

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
