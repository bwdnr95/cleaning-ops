from sqlalchemy.orm import Session

from app.services.service_catalog import ServiceCatalogService


def validate_recurring_service_catalog(
    db: Session,
    *,
    service_item_id: str | None,
    service_category_id: str | None,
) -> None:
    catalog = ServiceCatalogService(db)
    if service_item_id is not None:
        catalog.get_available_item(service_item_id)
    if service_category_id is not None:
        catalog.require_available_category(service_category_id)
