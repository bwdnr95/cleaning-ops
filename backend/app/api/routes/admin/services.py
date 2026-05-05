from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.service_catalog import (
    ServiceCategoryCreate,
    ServiceCategoryDetailRead,
    ServiceCategoryUpdate,
    ServiceItemCreate,
    ServiceItemRead,
    ServiceItemUpdate,
)
from app.services.service_catalog import ServiceCatalogService

router = APIRouter()


@router.get("", response_model=list[ServiceCategoryDetailRead])
def list_service_catalog(
    include_inactive: bool = False,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> list[ServiceCategoryDetailRead]:
    return ServiceCatalogService(db).list_catalog(include_inactive=include_inactive)


@router.post("/categories", response_model=ServiceCategoryDetailRead, status_code=201)
def create_service_category(
    payload: ServiceCategoryCreate,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> ServiceCategoryDetailRead:
    return ServiceCatalogService(db).create_category(payload)


@router.patch("/categories/{category_id}", response_model=ServiceCategoryDetailRead)
def update_service_category(
    category_id: str,
    payload: ServiceCategoryUpdate,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> ServiceCategoryDetailRead:
    try:
        return ServiceCatalogService(db).update_category(category_id, payload)
    except ValueError as exc:
        raise service_catalog_http_error(exc) from exc


@router.post("/items", response_model=ServiceItemRead, status_code=201)
def create_service_item(
    payload: ServiceItemCreate,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> ServiceItemRead:
    try:
        return ServiceCatalogService(db).create_item(payload)
    except ValueError as exc:
        raise service_catalog_http_error(exc) from exc


@router.patch("/items/{item_id}", response_model=ServiceItemRead)
def update_service_item(
    item_id: str,
    payload: ServiceItemUpdate,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> ServiceItemRead:
    try:
        return ServiceCatalogService(db).update_item(item_id, payload)
    except ValueError as exc:
        raise service_catalog_http_error(exc) from exc


def service_catalog_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    status_code = 404 if detail.endswith("_not_found") else 400
    return HTTPException(status_code=status_code, detail=detail)
