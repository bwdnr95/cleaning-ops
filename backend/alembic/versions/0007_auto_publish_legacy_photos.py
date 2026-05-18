"""Auto-publish legacy partner photos and clear photo_review_pending status.

Revision ID: 0007_auto_publish_legacy_photos
Revises: 0006_default_partner_categories
Create Date: 2026-05-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_auto_publish_legacy_photos"
down_revision: str | None = "0006_default_partner_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) 모든 비공개 사진을 일괄 공개한다.
    op.execute(
        "UPDATE order_photos SET is_customer_visible = TRUE WHERE is_customer_visible = FALSE"
    )
    # 2) 사진이 1장 이상인 '사진검수대기' 주문은 '고객전달필요'로 이동한다.
    op.execute(
        """
        UPDATE orders
        SET status = '고객전달필요'
        WHERE status = '사진검수대기'
          AND id IN (
              SELECT DISTINCT order_id FROM order_photos
          )
        """
    )
    # 3) 사진이 0장인 '사진검수대기' 주문은 작업 완료 전 상태로 되돌린다.
    op.execute(
        """
        UPDATE orders
        SET status = '작업진행'
        WHERE status = '사진검수대기'
          AND id NOT IN (
              SELECT DISTINCT order_id FROM order_photos
          )
        """
    )


def downgrade() -> None:
    # 의도적으로 no-op: 자동 공개는 의도된 정책 변경이며 되돌리지 않는다.
    pass
