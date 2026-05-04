from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.repositories.messages import MessageRepository
from app.repositories.orders import OrderRepository
from app.repositories.photos import PhotoRepository
from app.repositories.timeline import TimelineRepository
from app.schemas.order import AdminOrderDetailRead, AdminOrderRead, OrderCreate, OrderUpdate
from app.services.orders import OrderService, to_admin_order_detail_dto, to_admin_order_dto

router = APIRouter()


@router.get("", response_model=list[AdminOrderRead])
def list_orders(
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> list:
    return [to_admin_order_dto(order) for order in OrderRepository(db).list_orders()]


@router.post("", response_model=AdminOrderRead, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    return to_admin_order_dto(OrderService(db).create(payload, actor_user_id=user.id))


@router.get("/{order_id}", response_model=AdminOrderDetailRead)
def get_order(
    order_id: str,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
):
    order = OrderRepository(db).get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order_not_found")
    return to_admin_order_detail_dto(
        order,
        timeline=TimelineRepository(db).list_for_order(order_id),
        photos=PhotoRepository(db).list_for_order(order_id),
        message_logs=MessageRepository(db).list_for_order(order_id),
    )


@router.patch("/{order_id}", response_model=AdminOrderRead)
def update_order(
    order_id: str,
    payload: OrderUpdate,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    try:
        return to_admin_order_dto(OrderService(db).update(order_id, payload, actor_user_id=user.id))
    except ValueError as exc:
        if str(exc) == "order_not_found":
            raise HTTPException(status_code=404, detail="order_not_found") from exc
        raise
