from secrets import token_urlsafe
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus, TimelineEventType
from app.domain.payment_status import PAYMENT_TRACKED_FIELDS
from app.domain.phone import normalize_phone
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.models.photo import OrderPhoto
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.orders import OrderRepository
from app.repositories.photos import PhotoRepository
from app.schemas.message import MessageLogRead
from app.schemas.order import (
    AdminOrderDetailRead,
    AdminOrderRead,
    CustomerOrderRead,
    CustomerPhotoRead,
    OrderCreate,
    OrderGroupCreate,
    OrderLineCreate,
    OrderUpdate,
    PartnerJobRead,
)
from app.schemas.photo import PartnerPhotoRead, PhotoRead
from app.services.service_catalog import ServiceCatalogService
from app.services.timeline import TimelineService

PARTNER_JOB_STARTABLE_STATUSES = {
    OrderStatus.SCHEDULE_CONFIRMED.value,
    OrderStatus.DAY_BEFORE_NOTICE_NEEDED.value,
    OrderStatus.DAY_BEFORE_NOTICE_DONE.value,
    OrderStatus.SCHEDULED.value,
}

PARTNER_JOB_COMPLETABLE_STATUSES = {
    OrderStatus.IN_PROGRESS.value,
}


class OrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.orders = OrderRepository(db)
        self.photos = PhotoRepository(db)
        self.service_catalog = ServiceCatalogService(db)
        self.timeline = TimelineService(db)

    def create(self, payload: OrderCreate, *, actor_user_id: str | None = None) -> Order:
        group = self.create_group(
            OrderGroupCreate(
                customer_name=payload.customer_name,
                customer_phone=payload.customer_phone,
                customer_address=payload.customer_address,
                source_channel=payload.source_channel,
                customer_visible_payment=payload.customer_visible_payment,
                notes=None,
                lines=[
                    OrderLineCreate(
                        status=payload.status,
                        received_date=payload.received_date,
                        scheduled_date=payload.scheduled_date,
                        requested_time=payload.requested_time,
                        partner_id=payload.partner_id,
                        team_name=payload.team_name,
                        service_category_id=payload.service_category_id,
                        service_item_id=payload.service_item_id,
                        service_name=payload.service_name,
                        size_or_quantity=payload.size_or_quantity,
                        service_detail=payload.service_detail,
                        special_request=payload.special_request,
                        total_amount=payload.total_amount,
                        deposit_amount=payload.deposit_amount,
                        balance_amount=payload.balance_amount,
                        onsite_extra_amount=payload.onsite_extra_amount,
                        vat_type=payload.vat_type,
                        payment_status=payload.payment_status,
                        payment_memo=payload.payment_memo,
                        evidence_memo=payload.evidence_memo,
                        partner_payment_amount=payload.partner_payment_amount,
                        partner_payment_status=payload.partner_payment_status,
                    )
                ],
            ),
            actor_user_id=actor_user_id,
        )
        lines = OrderGroupRepository(self.db).list_lines(group.id)
        return lines[0]

    def create_group(
        self,
        payload: OrderGroupCreate,
        *,
        actor_user_id: str | None = None,
    ) -> OrderGroup:
        if not payload.lines:
            raise ValueError("at_least_one_line_required")
        group = OrderGroup(
            id=str(uuid4()),
            customer_token=token_urlsafe(24),
            customer_name=payload.customer_name,
            customer_phone=normalize_phone(payload.customer_phone),
            customer_address=payload.customer_address,
            source_channel=payload.source_channel,
            customer_visible_payment=payload.customer_visible_payment,
            notes=payload.notes,
        )
        self.db.add(group)
        self.db.flush()
        for line_payload in payload.lines:
            self._create_line_internal(group, line_payload, actor_user_id=actor_user_id)
        self.db.commit()
        self.db.refresh(group)
        return group

    def add_line_to_group(
        self,
        group_id: str,
        payload: OrderLineCreate,
        *,
        actor_user_id: str | None = None,
    ) -> Order:
        group = self.db.get(OrderGroup, group_id)
        if group is None:
            raise ValueError("group_not_found")
        order = self._create_line_internal(group, payload, actor_user_id=actor_user_id)
        self.db.commit()
        self.db.refresh(order)
        return order

    def _create_line_internal(
        self,
        group: OrderGroup,
        payload: OrderLineCreate,
        *,
        actor_user_id: str | None,
    ) -> Order:
        values = payload.model_dump()
        self._apply_service_catalog(values)
        order = Order(
            id=str(uuid4()),
            group_id=group.id,
            customer_token=group.customer_token,
            customer_name=group.customer_name,
            customer_phone=group.customer_phone,
            customer_address=group.customer_address,
            source_channel=group.source_channel,
            customer_visible_payment=group.customer_visible_payment,
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
        return order

    def update(self, order_id: str, payload: OrderUpdate, *, actor_user_id: str | None = None) -> Order:
        order = self.orders.get(order_id)
        if order is None:
            raise ValueError("order_not_found")

        changes = payload.model_dump(exclude_unset=True)
        self._apply_service_catalog(changes)
        old_status = order.status
        payment_changes = collect_payment_changes(order, changes)
        schedule_changes = collect_schedule_changes(order, changes)
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

        if schedule_changes:
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.MEMO_ADDED,
                title="방문 일정 변경",
                description="관리자가 방문 예정일 또는 요청 시간을 변경했습니다.",
                metadata={"changes": schedule_changes},
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
        if order.status not in PARTNER_JOB_STARTABLE_STATUSES:
            raise ValueError("invalid_status_transition")

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
        order = self.db.execute(
            select(Order)
            .where(Order.id == order_id, Order.partner_id == partner_id)
            .with_for_update()
        ).scalar_one_or_none()
        if order is None:
            raise ValueError("order_not_found")
        if order.status not in PARTNER_JOB_COMPLETABLE_STATUSES:
            raise ValueError("invalid_status_transition")

        photo_count = self.photos.count_visible_for_order(order.id)
        if photo_count == 0:
            raise ValueError("photo_required_for_completion")

        self._change_status(
            order,
            OrderStatus.CUSTOMER_DELIVERY_NEEDED,
            actor_user_id=actor_user_id,
            title="작업 완료",
            description="협력사가 작업 완료를 처리했습니다. 자동 공개된 사진으로 고객 전달이 가능합니다.",
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


def to_partner_job_dto(order: Order, *, photos: list[OrderPhoto] | None = None) -> PartnerJobRead:
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
        photos=[to_partner_photo_dto(photo) for photo in photos or []],
    )


def to_partner_photo_dto(photo: OrderPhoto) -> PartnerPhotoRead:
    return PartnerPhotoRead(
        id=photo.id,
        order_id=photo.order_id,
        photo_type=photo.photo_type,
        file_url=photo.file_url,
        file_name=photo.file_name,
        file_size=photo.file_size,
        content_type=photo.content_type,
        is_customer_visible=photo.is_customer_visible,
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
        customer_phone=order.customer_phone,
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


def collect_schedule_changes(order: Order, changes: dict) -> dict[str, dict[str, object | None]]:
    schedule_changes: dict[str, dict[str, object | None]] = {}
    for field in ("scheduled_date", "requested_time"):
        if field not in changes:
            continue
        before = to_timeline_value(getattr(order, field))
        after = to_timeline_value(changes[field])
        if before != after:
            schedule_changes[field] = {"from": before, "to": after}
    return schedule_changes


def to_timeline_value(value) -> object | None:
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return value.isoformat()
    if hasattr(value, "as_integer_ratio") and not isinstance(value, (int, float)):
        return float(value)
    return value
