"""message_logs.recipient_partner_id — 협력사 메시지 테넌트 식별자

협력사용 메시지 조회를 전화번호가 아니라 '발송 시점 배정 협력사' 식별자로
스코프하기 위한 컬럼. 공유 전화번호/재배정 시 타 협력사 정보 누출을 막는다.

Revision ID: 0016_message_recipient_partner_id
Revises: 0015_recurring_contracts
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_message_recipient_partner_id"
down_revision = "0015_recurring_contracts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "message_logs",
        sa.Column("recipient_partner_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_message_logs_recipient_partner_id",
        "message_logs",
        ["recipient_partner_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_message_logs_recipient_partner_id", table_name="message_logs")
    op.drop_column("message_logs", "recipient_partner_id")
