from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.partner import Partner, PartnerCategory
from app.repositories.base import Repository


class PartnerCategoryRepository(Repository[PartnerCategory]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, PartnerCategory)

    def list_categories(self, *, include_inactive: bool = False) -> list[PartnerCategory]:
        stmt = select(PartnerCategory).order_by(
            PartnerCategory.sort_order.asc(),
            PartnerCategory.name.asc(),
        )
        if not include_inactive:
            stmt = stmt.where(PartnerCategory.is_active.is_(True))
        return list(self.db.scalars(stmt))


class PartnerRepository(Repository[Partner]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Partner)

    def list_all(self) -> list[Partner]:
        stmt = select(Partner).order_by(Partner.is_active.desc(), Partner.name.asc())
        return list(self.db.scalars(stmt))

    def list_active(self) -> list[Partner]:
        stmt = select(Partner).where(Partner.is_active.is_(True)).order_by(Partner.name.asc())
        return list(self.db.scalars(stmt))
