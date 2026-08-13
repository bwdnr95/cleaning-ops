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

    def get(self, id_: str, *, include_deleted: bool = False) -> Partner | None:
        partner = self.db.get(Partner, id_)
        if partner is None:
            return None
        if partner.deleted_at is not None and not include_deleted:
            return None
        return partner

    def get_for_update(
        self,
        id_: str,
        *,
        include_deleted: bool = False,
    ) -> Partner | None:
        stmt = (
            select(Partner)
            .where(Partner.id == id_)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        partner = self.db.scalar(stmt)
        if partner is None:
            return None
        if partner.deleted_at is not None and not include_deleted:
            return None
        return partner

    def lock_ids(self, partner_ids: list[str]) -> list[Partner]:
        ids = sorted(set(partner_ids))
        if not ids:
            return []
        stmt = (
            select(Partner)
            .where(Partner.id.in_(ids))
            .order_by(Partner.id.asc())
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return list(self.db.scalars(stmt))

    def list_all(self) -> list[Partner]:
        stmt = (
            select(Partner)
            .where(Partner.deleted_at.is_(None))
            .order_by(Partner.is_active.desc(), Partner.name.asc())
        )
        return list(self.db.scalars(stmt))

    def list_active(self) -> list[Partner]:
        stmt = (
            select(Partner)
            .where(Partner.deleted_at.is_(None), Partner.is_active.is_(True))
            .order_by(Partner.name.asc())
        )
        return list(self.db.scalars(stmt))
