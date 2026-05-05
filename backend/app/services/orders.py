from secrets import token_urlsafe
from uuid import uuid4

from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus, TimelineEventType
from app.domain.payment_status import PAYMENT_TRACKED_FIELDS
from app.domain.phone import normalize_phone
from app.models.order import Order
from app.models.photo import OrderPhoto
from app.repositories.orders import OrderRepository
from app.schemas.message import MessageLogRead
from app.schemas.order import (
    AdminOrderDetailRead,
    AdminOrderRead,
    CustomerOrderRead,
    CustomerPhotoRead,
    OrderCreate,
    OrderUpdate,
    PartnerJobRead,
)
from app.schemas.photo import PhotoRead
from app.services.service_catalog import ServiceCatalogService
from app.services.timeline import TimelineService


class OrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.orders = OrderRepository(db)
        self.service_catalog = ServiceCatalogService(db)
        self.timeline = TimelineService(db)

    def create(self, payload: OrderCreate, *, actor_user_id: str | None = None) -> Order:
        values = payload.model_dump(exclude={"customer_phone"})
        self._apply_service_catalog(values)
        order = Order(
            id=str(uuid4()),
            customer_token=token_urlsafe(24),
            customer_phone=normalize_phone(payload.customer_phone),
            **values,
        )
        self.orders.add(order)
        self.timeline.record(
            order_id=order.id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.CREATED,
            title="주문 생성",
        )
        if order.partner_id:
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.PARTNER_ASSIGNED,
                title="협력사 배정",
                metadata={"partner_id": order.partner_id},
            )
        self.db.commit()
        self.db.refresh(order)
        return order

    def update(self, order_id: str, payload: OrderUpdate, *, actor_user_id: str | None = None) -> Order:
        order = self.orders.get(order_id)
        if order is None:
            raise ValueError("order_not_found")

        changes = payload.model_dump(exclude_unset=True)
        self._apply_service_catalog(changes)
        old_status = order.status
        payment_changes = collect_payment_changes(order, changes)
        for key, value in changes.items():
            if key == "customer_phone" and value is not None:
                value = normalize_phone(value)
            setattr(order, key, value)

        if "status" in changes and changes["status"] != old_status:
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.STATUS_CHANGED,
                title="상태 변경",
                metadata={"from": old_status, "to": changes["status"]},
            )

        if "partner_id" in changes:
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.PARTNER_ASSIGNED,
                title="협력사 배정",
                metadata={"partner_id": changes["partner_id"]},
            )

        if payment_changes:
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.MEMO_ADDED,
                title="결제/정산 변경",
                description="관리자가 결제 또는 협력사 정산 정보를 변경했습니다.",
                metadata={"changes": payment_changes},
            )

        self.db.commit()
        self.db.refresh(order)
        return order

    def _apply_service_catalog(self, values: dict) -> None:
        service_item_id = values.get("service_item_id")
        if service_item_id:
            item, _category = self.service_catalog.get_available_item(service_item_id)
            values["service_category_id"] = item.category_id
            values["service_name"] = item.name
            if values.get("total_amount") is None:
                values["total_amount"] = float(item.base_price or 0)
            return

        service_category_id = values.get("service_category_id")
        if service_category_id:
            self.service_catalog.require_available_category(service_category_id)

    def get_for_partner(self, order_id: str, *, partner_id: str) -> Order:
        order = self.orders.get(order_id)
        if order is None or order.partner_id != partner_id:
            raise ValueError("order_not_found")
        return order

    def start_partner_job(
        self,
        order_id: str,
        *,
        actor_user_id: str,
        partner_id: str,
    ) -> Order:
        order = self.get_for_partner(order_id, partner_id=partner_id)
        self._change_status(
            order,
            OrderStatus.IN_PROGRESS,
            actor_user_id=actor_user_id,
            title="작업 시작",
        )
        self.db.commit()
        self.db.refresh(order)
        return order

    def complete_partner_job(
        self,
        order_id: str,
        *,
        actor_user_id: str,
        partner_id: str,
    ) -> Order:
        order = self.get_for_partner(order_id, partner_id=partner_id)
        self._change_status(
            order,
            OrderStatus.PHOTO_REVIEW_PENDING,
            actor_user_id=actor_user_id,
            title="작업 완료",
            description="협력사가 작업 완료를 처리했습니다. 관리자 사진 검수가 필요합니다.",
        )
        self.db.commit()
        self.db.refresh(order)
        return order

    def _change_status(
        self,
        order: Order,
        next_status: OrderStatus,
        *,
        actor_user_id: str | None,
        title: str,
        description: str | None = None,
    ) -> None:
        old_status = order.status
        if old_status == next_status:
            return

        order.status = next_status
        self.timeline.record(
            order_id=order.id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.STATUS_CHANGED,
            title=title,
            description=description,
            metadata={"from": old_status, "to": next_status},
        )


def to_admin_order_dto(order: Order, *, timeline: list | None = None) -> AdminOrderRead:
    return AdminOrderRead(
        id=order.id,
        status=order.status,
        received_date=order.received_date,
        scheduled_date=order.scheduled_date,
        requested_time=order.requested_time,
        partner_id=order.partner_id,
        team_name=order.team_name,
        service_category_id=order.service_category_id,
        service_item_id=order.service_item_id,
        service_name=order.service_name,
        size_or_quantity=order.size_or_quantity,
        service_detail=order.service_detail,
        special_request=order.special_request,
        source_channel=order.source_channel,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        customer_address=order.customer_address,
        total_amount=order.total_amount,
        deposit_amount=order.deposit_amount,
        balance_amount=order.balance_amount,
        onsite_extra_amount=order.onsite_extra_amount,
        vat_type=order.vat_type,
        payment_status=order.payment_status,
        payment_memo=order.payment_memo,
        evidence_memo=order.evidence_memo,
        partner_payment_amount=order.partner_payment_amount,
        partner_payment_status=order.partner_payment_status,
        customer_visible_payment=order.customer_visible_payment,
        customer_token=order.customer_token,
        created_at=order.created_at,
        updated_at=order.updated_at,
        timeline=timeline or [],
    )


def to_admin_order_detail_dto(
    order: Order,
    *,
    timeline: list | None = None,
    photos: list[OrderPhoto] | None = None,
    message_logs: list | None = None,
) -> AdminOrderDetailRead:
    base = to_admin_order_dto(order, timeline=timeline)
    return AdminOrderDetailRead(
        **base.model_dump(),
        photos=[to_admin_photo_dto(photo) for photo in photos or []],
        message_logs=[MessageLogRead.model_validate(log) for log in message_logs or []],
    )


def to_admin_photo_dto(photo: OrderPhoto) -> PhotoRead:
    return PhotoRead(
        id=photo.id,
        order_id=photo.order_id,
        uploaded_by_user_id=photo.uploaded_by_user_id,
        photo_type=photo.photo_type,
        file_url=photo.file_url,
        file_name=photo.file_name,
        file_size=photo.file_size,
        content_type=photo.content_type,
        is_customer_visible=photo.is_customer_visible,
    )


def to_partner_job_dto(order: Order) -> PartnerJobRead:
    return PartnerJobRead(
        id=order.id,
        status=order.status,
        scheduled_date=order.scheduled_date,
        requested_time=order.requested_time,
        service_name=order.service_name,
        size_or_quantity=order.size_or_quantity,
        service_detail=order.service_detail,
        special_request=order.special_request,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        customer_address=order.customer_address,
    )


def to_customer_order_dto(order: Order, *, photos: list[OrderPhoto] | None = None) -> CustomerOrderRead:
    return CustomerOrderRead(
        id=order.id,
        status=order.status,
        scheduled_date=order.scheduled_date,
        requested_time=order.requested_time,
        service_name=order.service_name,
        size_or_quantity=order.size_or_quantity,
        service_detail=order.service_detail,
        special_request=order.special_request,
        customer_name=order.customer_name,
        customer_address=order.customer_address,
        total_amount=order.total_amount if order.customer_visible_payment else None,
        deposit_amount=order.deposit_amount if order.customer_visible_payment else None,
        balance_amount=order.balance_amount if order.customer_visible_payment else None,
        payment_status=order.payment_status if order.customer_visible_payment else None,
        photos=[to_customer_photo_dto(photo) for photo in photos or [] if photo.is_customer_visible],
    )


def to_customer_photo_dto(photo: OrderPhoto) -> CustomerPhotoRead:
    return CustomerPhotoRead(
        id=photo.id,
        photo_type=photo.photo_type,
        file_url=photo.file_url,
        file_name=photo.file_name,
    )


def collect_payment_changes(order: Order, changes: dict) -> dict[str, dict[str, object | None]]:
    payment_changes: dict[str, dict[str, object | None]] = {}
    for field in PAYMENT_TRACKED_FIELDS:
        if field not in changes:
            continue
        before = to_timeline_value(getattr(order, field))
        after = to_timeline_value(changes[field])
        if before != after:
            payment_changes[field] = {"from": before, "to": after}
    return payment_changes


def to_timeline_value(value) -> object | None:
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "as_integer_ratio") and not isinstance(value, (int, float)):
        return float(value)
    return value
