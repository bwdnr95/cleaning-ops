"""협력사 담당자 연락처(manager_phone)

Revision ID: 0014_partner_manager_phone
Revises: 0013_receipt_fields
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_partner_manager_phone"
down_revision = "0013_receipt_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("partners", sa.Column("manager_phone", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("partners", "manager_phone")
