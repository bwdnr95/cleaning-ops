from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.service_item import ServiceCategory, ServiceItem
from app.repositories.service_catalog import ServiceCategoryRepository, ServiceItemRepository
from app.schemas.service_catalog import (
    ServiceCategoryCreate,
    ServiceCategoryDetailRead,
    ServiceCategoryRead,
    ServiceCategoryUpdate,
    ServiceItemCreate,
    ServiceItemRead,
    ServiceItemUpdate,
)


class ServiceCatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.categories = ServiceCategoryRepository(db)
        self.items = ServiceItemRepository(db)

    def list_catalog(self, *, include_inactive: bool = False) -> list[ServiceCategoryDetailRead]:
        categories = self.categories.list_categories(include_inactive=include_inactive)
        items_by_category = {
            category.id: self.items.list_by_category(category.id, include_inactive=include_inactive)
            for category in categories
        }
        return [
            to_category_detail_dto(category, items=items_by_category.get(category.id, []))
            for category in categories
        ]

    def create_category(self, payload: ServiceCategoryCreate) -> ServiceCategoryDetailRead:
        category = ServiceCategory(id=str(uuid4()), **payload.model_dump())
        self.categories.add(category)
        self.db.commit()
        self.db.refresh(category)
        return to_category_detail_dto(category, items=[])

    def update_category(self, category_id: str, payload: ServiceCategoryUpdate) -> ServiceCategoryDetailRead:
        category = self.categories.get(category_id)
        if category is None:
            raise ValueError("service_category_not_found")

        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(category, key, value)

        self.db.commit()
        self.db.refresh(category)
        return to_category_detail_dto(
            category,
            items=self.items.list_by_category(category.id, include_inactive=True),
        )

    def create_item(self, payload: ServiceItemCreate) -> ServiceItemRead:
        category = self.categories.get(payload.category_id)
        if category is None:
            raise ValueError("service_category_not_found")
        if not category.is_active and payload.is_active:
            raise ValueError("service_category_not_available")

        item = ServiceItem(id=str(uuid4()), **payload.model_dump())
        self.items.add(item)
        self.db.commit()
        self.db.refresh(item)
        return to_item_dto(item)

    def update_item(self, item_id: str, payload: ServiceItemUpdate) -> ServiceItemRead:
        item = self.items.get(item_id)
        if item is None:
            raise ValueError("service_item_not_found")

        changes = payload.model_dump(exclude_unset=True)
        if "category_id" in changes:
            category = self.categories.get(changes["category_id"])
            if category is None:
                raise ValueError("service_category_not_found")
            if not category.is_active and changes.get("is_active", item.is_active):
                raise ValueError("service_category_not_available")

        for key, value in changes.items():
            setattr(item, key, value)

        self.db.commit()
        self.db.refresh(item)
        return to_item_dto(item)

    def get_available_item(self, item_id: str) -> tuple[ServiceItem, ServiceCategory]:
        item = self.items.get(item_id)
        if item is None:
            raise ValueError("service_item_not_found")
        category = self.categories.get(item.category_id)
        if category is None:
            raise ValueError("service_category_not_found")
        if not item.is_active or not category.is_active:
            raise ValueError("service_item_not_available")
        return item, category

    def require_available_category(self, category_id: str) -> ServiceCategory:
        category = self.categories.get(category_id)
        if category is None:
            raise ValueError("service_category_not_found")
        if not category.is_active:
            raise ValueError("service_category_not_available")
        return category


def to_category_detail_dto(category: ServiceCategory, *, items: list[ServiceItem]) -> ServiceCategoryDetailRead:
    base = to_category_dto(category)
    return ServiceCategoryDetailRead(**base.model_dump(), items=[to_item_dto(item) for item in items])


def to_category_dto(category: ServiceCategory) -> ServiceCategoryRead:
    return ServiceCategoryRead(
        id=category.id,
        name=category.name,
        description=category.description,
        is_active=category.is_active,
        sort_order=category.sort_order,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


def to_item_dto(item: ServiceItem) -> ServiceItemRead:
    return ServiceItemRead(
        id=item.id,
        category_id=item.category_id,
        name=item.name,
        unit=item.unit,
        base_price=float(item.base_price or 0),
        description=item.description,
        is_active=item.is_active,
        sort_order=item.sort_order,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )
