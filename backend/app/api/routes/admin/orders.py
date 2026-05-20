from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.repositories.messages import MessageRepository
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.orders import OrderRepository
from app.repositories.photos import PhotoRepository
from app.repositories.timeline import TimelineRepository
from app.schemas.order import (
    AdminOrderDetailRead,
    AdminOrderGroupRead,
    AdminOrderRead,
    AdminOrderSiblingRead,
    OrderCreate,
    OrderGroupCreate,
    OrderGroupUpdate,
    OrderLineCreate,
    OrderUpdate,
)
from app.services.orders import (
    OrderService,
    to_admin_group_dto,
    to_admin_order_detail_dto,
    to_admin_order_dto,
)

router = APIRouter()


class BulkDeleteRequest(BaseModel):
    order_ids: list[str]


class BulkDeleteFailureItem(BaseModel):
    order_id: str
    reason: str


class BulkDeleteResponse(BaseModel):
    succeeded: list[str]
    failed: list[BulkDeleteFailureItem]


@router.get("", response_model=list[AdminOrderRead])
def list_orders(
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> list:
    group_repo = OrderGroupRepository(db)
    return [
        to_admin_order_dto(order, group=group_repo.get(order.group_id))
        for order in OrderRepository(db).list_orders()
    ]


@router.post("", response_model=AdminOrderRead, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    try:
        order = OrderService(db).create(payload, actor_user_id=user.id)
        return to_admin_order_dto(order, group=OrderGroupRepository(db).get(order.group_id))
    except ValueError as exc:
        raise order_http_error(exc) from exc


@router.post("/groups", response_model=AdminOrderGroupRead, status_code=status.HTTP_201_CREATED)
def create_order_group(
    payload: OrderGroupCreate,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    try:
        group = OrderService(db).create_group(payload, actor_user_id=user.id)
    except ValueError as exc:
        raise order_http_error(exc) from exc
    return to_admin_group_dto(group, lines=OrderGroupRepository(db).list_lines(group.id))


@router.get("/groups/{group_id}", response_model=AdminOrderGroupRead)
def get_order_group(
    group_id: str,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
):
    group_repo = OrderGroupRepository(db)
    group = group_repo.get(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="group_not_found")
    return to_admin_group_dto(group, lines=group_repo.list_lines(group_id))


@router.patch("/groups/{group_id}", response_model=AdminOrderGroupRead)
def update_order_group(
    group_id: str,
    payload: OrderGroupUpdate,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    try:
        group = OrderService(db).update_group(group_id, payload, actor_user_id=user.id)
    except ValueError as exc:
        raise order_http_error(exc) from exc
    return to_admin_group_dto(group, lines=OrderGroupRepository(db).list_lines(group.id))


@router.post("/groups/{group_id}/lines", response_model=AdminOrderRead, status_code=status.HTTP_201_CREATED)
def add_line(
    group_id: str,
    payload: OrderLineCreate,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    try:
        order = OrderService(db).add_line_to_group(group_id, payload, actor_user_id=user.id)
    except ValueError as exc:
        raise order_http_error(exc) from exc
    return to_admin_order_dto(order, group=OrderGroupRepository(db).get(group_id))


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
def bulk_delete_admin_orders(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
) -> BulkDeleteResponse:
    try:
        result = OrderService(db).bulk_delete_orders(
            order_ids=payload.order_ids,
            actor_user_id=user.id,
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="bulk_delete_failed") from exc

    return BulkDeleteResponse(
        succeeded=result.succeeded,
        failed=[
            BulkDeleteFailureItem(order_id=failure.order_id, reason=failure.reason)
            for failure in result.failed
        ],
    )


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_order(
    order_id: str,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
) -> Response:
    try:
        OrderService(db).delete_order(order_id=order_id, actor_user_id=user.id)
        db.commit()
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail="order_not_found") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="order_delete_failed") from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{order_id}", response_model=AdminOrderDetailRead)
def get_order(
    order_id: str,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
):
    order = OrderRepository(db).get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order_not_found")
    group_repo = OrderGroupRepository(db)
    group = group_repo.get(order.group_id)
    sibling_lines = [
        AdminOrderSiblingRead(
            id=line.id,
            status=line.status,
            service_name=line.service_name,
            partner_id=line.partner_id,
            team_name=line.team_name,
            total_amount=line.total_amount,
        )
        for line in group_repo.list_lines(order.group_id)
        if line.id != order.id
    ]
    return to_admin_order_detail_dto(
        order,
        group=group,
        timeline=TimelineRepository(db).list_for_order(order_id),
        photos=PhotoRepository(db).list_for_order(order_id),
        message_logs=MessageRepository(db).list_for_order(order_id),
        sibling_lines=sibling_lines,
    )


@router.patch("/{order_id}", response_model=AdminOrderRead)
def update_order(
    order_id: str,
    payload: OrderUpdate,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    try:
        order = OrderService(db).update(order_id, payload, actor_user_id=user.id)
        return to_admin_order_dto(order, group=OrderGroupRepository(db).get(order.group_id))
    except ValueError as exc:
        raise order_http_error(exc) from exc


def order_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    status_code = 404 if detail in {"order_not_found", "group_not_found"} else 400
    return HTTPException(status_code=status_code, detail=detail)
