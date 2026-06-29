"""정기청소 다중요일 — recurring_contracts.weekdays

주간 정기계약이 한 주에 여러 요일(예: 매주 월·수·금)을 가질 수 있도록
선택 요일 집합을 CSV("0,2,4")로 보관하는 컬럼. 레거시 단일 weekday는 보존·폴백.

Revision ID: 0017_recurring_weekdays
Revises: 0016_message_recipient_partner_id
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_recurring_weekdays"
down_revision = "0016_message_recipient_partner_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recurring_contracts", sa.Column("weekdays", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("recurring_contracts", "weekdays")
