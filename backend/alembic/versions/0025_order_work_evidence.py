"""작업 시작/완료 시각과 고객 서명 증빙

Revision ID: 0025_order_work_evidence
Revises: 0024_orders_as_request
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa

revision = "0025_order_work_evidence"
down_revision = "0024_orders_as_request"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("work_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("work_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("customer_signature_storage_key", sa.String(length=500), nullable=True))
    op.add_column("orders", sa.Column("customer_signature_file_url", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "customer_signature_file_url")
    op.drop_column("orders", "customer_signature_storage_key")
    op.drop_column("orders", "work_completed_at")
    op.drop_column("orders", "work_started_at")
