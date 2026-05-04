from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.domain.phone import phone_suffix_matches
from app.repositories.orders import OrderRepository
from app.repositories.photos import PhotoRepository
from app.schemas.order import CustomerOrderRead, CustomerVerifyRequest
from app.services.orders import to_customer_order_dto

router = APIRouter()


@router.post("/{customer_token}/verify", response_model=CustomerOrderRead)
def verify_customer_order(
    customer_token: str,
    payload: CustomerVerifyRequest,
    db: Session = Depends(get_session),
) -> CustomerOrderRead:
    order = OrderRepository(db).get_by_customer_token(customer_token)
    if order is None or not phone_suffix_matches(order.customer_phone, payload.phone_suffix):
        raise HTTPException(status_code=404, detail="order_not_found")
    photos = PhotoRepository(db).list_for_order(order.id, customer_visible_only=True)
    return to_customer_order_dto(order, photos=photos)
