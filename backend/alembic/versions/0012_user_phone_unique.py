"""Enforce unique login phone on users

같은 login_phone(=users.phone)이 둘 이상 존재하면 협력사 로그인이 엉뚱한 계정으로
인증될 수 있어, 실제 번호가 있는 행에 한해 유니크 제약을 건다.
NULL/빈 문자열은 부분 인덱스 조건으로 제외한다(미연결 계정 다수 허용).

Revision ID: 0012_user_phone_unique
Revises: 0011_partner_vat_inclusive_amounts
Create Date: 2026-06-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_user_phone_unique"
down_revision = "0011_partner_vat_inclusive_amounts"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_users_phone"
INDEX_PREDICATE = "phone IS NOT NULL AND phone <> ''"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        "users",
        ["phone"],
        unique=True,
        postgresql_where=sa.text(INDEX_PREDICATE),
        sqlite_where=sa.text(INDEX_PREDICATE),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="users")
