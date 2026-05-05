from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.service_item import ServiceCategory, ServiceItem
from app.repositories.base import Repository


class ServiceCategoryRepository(Repository[ServiceCategory]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, ServiceCategory)

    def list_categories(self, *, include_inactive: bool = False) -> list[ServiceCategory]:
        stmt = select(ServiceCategory).order_by(ServiceCategory.sort_order.asc(), ServiceCategory.name.asc())
        if not include_inactive:
            stmt = stmt.where(ServiceCategory.is_active.is_(True))
        return list(self.db.scalars(stmt))


class ServiceItemRepository(Repository[ServiceItem]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, ServiceItem)

    def list_items(self, *, include_inactive: bool = False) -> list[ServiceItem]:
        stmt = select(ServiceItem).order_by(ServiceItem.sort_order.asc(), ServiceItem.name.asc())
        if not include_inactive:
            stmt = stmt.where(ServiceItem.is_active.is_(True))
        return list(self.db.scalars(stmt))

    def list_by_category(self, category_id: str, *, include_inactive: bool = False) -> list[ServiceItem]:
        stmt = (
            select(ServiceItem)
            .where(ServiceItem.category_id == category_id)
            .order_by(ServiceItem.sort_order.asc(), ServiceItem.name.asc())
        )
        if not include_inactive:
            stmt = stmt.where(ServiceItem.is_active.is_(True))
        return list(self.db.scalars(stmt))
