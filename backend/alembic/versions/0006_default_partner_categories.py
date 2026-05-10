"""seed default partner categories

Revision ID: 0006_default_partner_categories
Revises: 0005_partner_categories
Create Date: 2026-05-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0006_default_partner_categories"
down_revision: str | None = "0005_partner_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEFAULT_PARTNER_CATEGORIES = (
    {
        "id": "seed-partner-category-residential",
        "name": "주거 청소",
        "description": "입주/이사/거주/정기 청소 협력사",
        "sort_order": 10,
        "keywords": ("입주", "이사", "거주", "주거", "정기"),
    },
    {
        "id": "seed-partner-category-aircon",
        "name": "에어컨 청소",
        "description": "에어컨/냉난방 청소 협력사",
        "sort_order": 20,
        "keywords": ("에어컨", "냉난방"),
    },
    {
        "id": "seed-partner-category-grout",
        "name": "줄눈",
        "description": "줄눈 시공 협력사",
        "sort_order": 30,
        "keywords": ("줄눈",),
    },
    {
        "id": "seed-partner-category-new-house-syndrome",
        "name": "새집증후군",
        "description": "새집증후군 케어 협력사",
        "sort_order": 40,
        "keywords": ("새집증후군", "새집"),
    },
    {
        "id": "seed-partner-category-elastic-coating",
        "name": "탄성코트",
        "description": "탄성코트 시공 협력사",
        "sort_order": 50,
        "keywords": ("탄성코트", "탄성코드", "탄성"),
    },
)


def upgrade() -> None:
    connection = op.get_bind()
    for category in DEFAULT_PARTNER_CATEGORIES:
        exists = connection.execute(
            sa.text("SELECT id FROM partner_categories WHERE id = :id"),
            {"id": category["id"]},
        ).first()
        if exists is None:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO partner_categories (
                        id, name, description, is_active, sort_order, created_at, updated_at
                    )
                    VALUES (
                        :id, :name, :description, :is_active, :sort_order,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": category["id"],
                    "name": category["name"],
                    "description": category["description"],
                    "is_active": True,
                    "sort_order": category["sort_order"],
                },
            )

        for keyword in category["keywords"]:
            connection.execute(
                sa.text(
                    """
                    UPDATE partners
                    SET partner_category_id = :category_id,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE partner_category_id IS NULL
                      AND available_services LIKE :keyword
                    """
                ),
                {
                    "category_id": category["id"],
                    "keyword": f"%{keyword}%",
                },
            )


def downgrade() -> None:
    connection = op.get_bind()
    category_ids = [category["id"] for category in DEFAULT_PARTNER_CATEGORIES]
    for category_id in category_ids:
        connection.execute(
            sa.text(
                """
                UPDATE partners
                SET partner_category_id = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE partner_category_id = :category_id
                """
            ),
            {"category_id": category_id},
        )
        connection.execute(
            sa.text("DELETE FROM partner_categories WHERE id = :category_id"),
            {"category_id": category_id},
        )
