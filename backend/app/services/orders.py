from dataclasses import dataclass
from datetime import UTC, datetime
from secrets import token_urlsafe
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus, ReceiptStatus, ReceiptType, TimelineEventType
from app.domain.order_pricing import order_consumer_total
from app.domain.payment_status import PAYMENT_TRACKED_FIELDS
from app.domain.phone import normalize_phone
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.models.photo import OrderPhoto
from app.models.timeline import OrderTimeline
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.orders import OrderRepository
from app.repositories.photos import PhotoRepository
from app.schemas.message import MessageLogRead
from app.schemas.order import (
    AdminOrderGroupRead,
    AdminOrderDetailRead,
    AdminOrderRead,
    AdminOrderSiblingRead,
    CustomerOrderGroupRead,
    CustomerOrderLineRead,
    CustomerOrderRead,
    CustomerPhotoRead,
    OrderCreate,
    OrderGroupCreate,
    OrderGroupUpdate,
    OrderLineCreate,
    OrderUpdate,
    PartnerJobRead,
    PartnerMemoRead,
)
from app.schemas.photo import PartnerPhotoRead, PhotoRead
from app.services.service_catalog import ServiceCatalogService
from app.services.timeline import TimelineService


def _normalize_receipt_fields(values: dict) -> None:
    """증빙 유형이 발급X(NONE)면 발급 상태를 '해당없음'으로 강제한다."""
    if values.get("receipt_type") == ReceiptType.NONE:
        values["receipt_status"] = ReceiptStatus.NOT_APPLICABLE

PARTNER_JOB_STARTABLE_STATUSES = {
    OrderStatus.SCHEDULE_CONFIRMED.value,
    OrderStatus.DAY_BEFORE_NOTICE_NEEDED.value,
    OrderStatus.DAY_BEFORE_NOTICE_DONE.value,
    OrderStatus.SCHEDULED.value,
}

# 방문일이 없던(미배정) 주문에 방문일을 새로 지정하면 자동으로 '일정확정'으로 올릴 수 있는 상태들.
AUTO_CONFIRM_ON_SCHEDULE_STATUSES = (
    OrderStatus.NEW,
    OrderStatus.CONSULTING,
    OrderStatus.PARTNER_CONFIRMING,
)

PARTNER_JOB_COMPLETABLE_STATUSES = {
    OrderStatus.IN_PROGRESS.value,
}

# 협력사 사진 업로드 허용 상태 집합.
# 시작 가능(STARTABLE) 상태 + 작업진행(IN_PROGRESS)을 합친 "활성 작업 구간"으로 정의한다.
# - STARTABLE 포함: 현재 플로우에서 협력사가 '작업 시작'을 누르기 전(작업예정 등)에도 사진을 올릴 수 있도록 허용.
# - IN_PROGRESS 포함: 멀티 배치 업로드를 허용하는 invariant 보장(작업진행 중 여러 번 나눠 업로드).
# - 제외: 사전/상담 상태(신규접수·상담중·협력사확인중), 검수/전달 단계(사진검수대기·고객전달필요),
#   종료/봉인 상태(고객전달완료·서비스완료·취소)에는 자동 공개 사진이 새로 올라오지 못하게 막는다.
PARTNER_PHOTO_UPLOADABLE_STATUSES = (
    PARTNER_JOB_STARTABLE_STATUSES | PARTNER_JOB_COMPLETABLE_STATUSES
)


@dataclass(frozen=True)
class BulkDeleteFailure:
    order_id: str
    reason: str


@dataclass(frozen=True)
class BulkDeleteResult:
    succeeded: list[str]
    failed: list[BulkDeleteFailure]


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
                customer_address_detail=payload.customer_address_detail,
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
                        discount_amount=payload.discount_amount,
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
            customer_address_detail=payload.customer_address_detail,
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
        group = OrderGroupRepository(self.db).get(group_id)
        if group is None:
            raise ValueError("group_not_found")
        order = self._create_line_internal(group, payload, actor_user_id=actor_user_id)
        self.db.commit()
        self.db.refresh(order)
        return order

    def create_empty_group(
        self,
        payload: OrderGroupCreate,
        *,
        actor_user_id: str | None = None,
    ) -> OrderGroup:
        """라인 0개 그룹 생성(정기계약 전용). payload.lines는 무시한다."""
        group = OrderGroup(
            id=str(uuid4()),
            customer_token=token_urlsafe(24),
            customer_name=payload.customer_name,
            customer_phone=normalize_phone(payload.customer_phone),
            customer_address=payload.customer_address,
            customer_address_detail=payload.customer_address_detail,
            source_channel=payload.source_channel,
            customer_visible_payment=payload.customer_visible_payment,
            notes=payload.notes,
        )
        self.db.add(group)
        self.db.commit()
        self.db.refresh(group)
        return group

    def add_recurring_line(
        self,
        group: OrderGroup,
        payload: OrderLineCreate,
        *,
        recurring_contract_id: str,
        actor_user_id: str | None = None,
    ) -> Order:
        """정기 회차 라인 생성. commit하지 않는다 — caller(RecurringService)가 트랜잭션 소유."""
        order = self._create_line_internal(group, payload, actor_user_id=actor_user_id)
        order.recurring_contract_id = recurring_contract_id
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
        _normalize_receipt_fields(values)
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
        _normalize_receipt_fields(changes)
        old_status = order.status
        old_scheduled_date = order.scheduled_date
        payment_changes = collect_payment_changes(order, changes)
        schedule_changes = collect_schedule_changes(order, changes)
        for key, value in changes.items():
            if key == "customer_phone" and value is not None:
                value = normalize_phone(value)
            setattr(order, key, value)

        # 방문일 미배정(미정) 주문에 방문일을 새로 지정하면 자동으로 '일정확정'으로 전환한다.
        # (운영자가 같은 요청에서 상태를 직접 지정했으면 그 값을 존중하여 건드리지 않음)
        if (
            "scheduled_date" in changes
            and order.scheduled_date is not None
            and old_scheduled_date is None
            and "status" not in changes
            and order.status in AUTO_CONFIRM_ON_SCHEDULE_STATUSES
        ):
            order.status = OrderStatus.SCHEDULE_CONFIRMED
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.STATUS_CHANGED,
                title="상태 변경",
                description="방문일 지정으로 자동 일정확정 처리되었습니다.",
                metadata={"from": old_status, "to": OrderStatus.SCHEDULE_CONFIRMED.value, "auto": True},
            )

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

    def update_group(
        self,
        group_id: str,
        payload: OrderGroupUpdate,
        *,
        actor_user_id: str | None = None,
    ) -> OrderGroup:
        group = OrderGroupRepository(self.db).get(group_id)
        if group is None:
            raise ValueError("group_not_found")

        changes = payload.model_dump(exclude_unset=True)
        if "customer_phone" in changes and changes["customer_phone"] is not None:
            changes["customer_phone"] = normalize_phone(changes["customer_phone"])

        group_only_changes: dict[str, dict[str, object | None]] = {}
        if "customer_address_detail" in changes:
            before = to_timeline_value(group.customer_address_detail)
            after = to_timeline_value(changes["customer_address_detail"])
            if before != after:
                group_only_changes["customer_address_detail"] = {"from": before, "to": after}

        for key, value in changes.items():
            setattr(group, key, value)

        mirror_fields = {
            "customer_name",
            "customer_phone",
            "customer_address",
            "source_channel",
            "customer_visible_payment",
        }
        mirror_changes = {key: changes[key] for key in mirror_fields if key in changes}
        if mirror_changes or group_only_changes:
            lines = self.db.scalars(
                select(Order).where(
                    Order.group_id == group_id,
                    Order.deleted_at.is_(None),
                )
            ).all()
            for line in lines:
                line_mirror_changes: dict[str, dict[str, object | None]] = dict(group_only_changes)
                for key, value in mirror_changes.items():
                    before = to_timeline_value(getattr(line, key))
                    after = to_timeline_value(value)
                    if before != after:
                        line_mirror_changes[key] = {"from": before, "to": after}
                    setattr(line, key, value)
                if line_mirror_changes:
                    self.timeline.record(
                        order_id=line.id,
                        actor_user_id=actor_user_id,
                        event_type=TimelineEventType.MEMO_ADDED,
                        title="고객 정보 변경",
                        description="관리자가 그룹 고객 정보를 변경했습니다.",
                        metadata={
                            "group_id": group_id,
                            "source": "order_group_update",
                            "changes": line_mirror_changes,
                        },
                    )

        self.db.commit()
        self.db.refresh(group)
        return group

    def _apply_service_catalog(self, values: dict) -> None:
        service_item_id = values.get("service_item_id")
        if service_item_id:
            item, _category = self.service_catalog.get_available_item(service_item_id)
            values["service_category_id"] = item.category_id
            values["service_name"] = item.name
            if values.get("total_amount") is None:
                values["total_amount"] = float(item.base_price or 0)
            if values.get("partner_payment_amount") is None:
                values["partner_payment_amount"] = float(item.partner_base_price or 0)
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
            .where(
                Order.id == order_id,
                Order.partner_id == partner_id,
                Order.deleted_at.is_(None),
            )
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

    def add_partner_memo(
        self,
        order_id: str,
        *,
        text: str,
        actor_user_id: str,
        partner_id: str,
    ) -> Order:
        """협력사 현장 메모 추가. 본인 배정 주문만 허용하고 memo_added 타임라인을 남긴다."""
        order = self.get_for_partner(order_id, partner_id=partner_id)
        self.timeline.record(
            order_id=order.id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.MEMO_ADDED,
            title="협력사 메모",
            description=text,
            metadata={"author_role": "partner", "author_partner_id": partner_id},
        )
        self.db.commit()
        self.db.refresh(order)
        return order

    def delete_order(self, *, order_id: str, actor_user_id: str) -> None:
        """주문 1건 soft-delete. 마지막 살아있는 line이면 그룹도 soft-delete한다."""
        order = self.db.execute(
            select(Order).where(
                Order.id == order_id,
                Order.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if order is None:
            raise LookupError(f"order not found or already deleted: {order_id}")

        now = datetime.now(UTC)
        order.deleted_at = now
        self.db.flush()

        self.timeline.record(
            order_id=order.id,
            event_type=TimelineEventType.ORDER_DELETED,
            actor_user_id=actor_user_id,
            title="주문 삭제",
            description="관리자가 주문 내역을 삭제했습니다.",
        )

        remaining = self.db.execute(
            select(func.count(Order.id)).where(
                Order.group_id == order.group_id,
                Order.deleted_at.is_(None),
            )
        ).scalar_one()
        if remaining == 0:
            group = self.db.get(OrderGroup, order.group_id)
            if group is not None and group.deleted_at is None:
                group.deleted_at = now

        self.db.flush()

    def bulk_delete_orders(
        self,
        *,
        order_ids: list[str],
        actor_user_id: str,
    ) -> BulkDeleteResult:
        succeeded: list[str] = []
        failed: list[BulkDeleteFailure] = []

        for order_id in order_ids:
            try:
                self.delete_order(order_id=order_id, actor_user_id=actor_user_id)
            except LookupError:
                failed.append(BulkDeleteFailure(order_id=order_id, reason="not_found"))
            else:
                succeeded.append(order_id)

        return BulkDeleteResult(succeeded=succeeded, failed=failed)

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


def to_admin_group_dto(group: OrderGroup, *, lines: list[Order] | None = None) -> AdminOrderGroupRead:
    return AdminOrderGroupRead(
        id=group.id,
        customer_token=group.customer_token,
        customer_name=group.customer_name,
        customer_phone=group.customer_phone,
        customer_address=group.customer_address,
        customer_address_detail=group.customer_address_detail,
        source_channel=group.source_channel,
        customer_visible_payment=group.customer_visible_payment,
        notes=group.notes,
        created_at=group.created_at,
        updated_at=group.updated_at,
        lines=[to_admin_order_dto(line, group=group) for line in lines or []],
    )


def to_admin_order_dto(
    order: Order,
    *,
    group: OrderGroup | None = None,
    timeline: list | None = None,
) -> AdminOrderRead:
    customer_name = group.customer_name if group else order.customer_name
    customer_phone = group.customer_phone if group else order.customer_phone
    customer_address = group.customer_address if group else order.customer_address
    customer_address_detail = group.customer_address_detail if group else None
    source_channel = group.source_channel if group else order.source_channel
    customer_visible_payment = (
        group.customer_visible_payment if group else bool(order.customer_visible_payment)
    )
    customer_token = group.customer_token if group else order.customer_token
    group_notes = group.notes if group else None
    return AdminOrderRead(
        id=order.id,
        group_id=order.group_id or "",
        recurring_contract_id=order.recurring_contract_id,
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
        source_channel=source_channel,
        customer_name=customer_name or "",
        customer_phone=customer_phone or "",
        customer_address=customer_address or "",
        customer_address_detail=customer_address_detail,
        total_amount=order.total_amount,
        discount_amount=order.discount_amount,
        deposit_amount=order.deposit_amount,
        balance_amount=order.balance_amount,
        onsite_extra_amount=order.onsite_extra_amount,
        vat_type=order.vat_type,
        payment_status=order.payment_status,
        payment_memo=order.payment_memo,
        evidence_memo=order.evidence_memo,
        receipt_type=order.receipt_type,
        receipt_status=order.receipt_status,
        partner_payment_amount=order.partner_payment_amount,
        partner_payment_status=order.partner_payment_status,
        consumer_price=order.total_amount,
        partner_price=order.partner_payment_amount,
        partner_settled_at=order.partner_settled_at,
        customer_visible_payment=customer_visible_payment,
        group_notes=group_notes,
        customer_token=customer_token or "",
        created_at=order.created_at,
        updated_at=order.updated_at,
        timeline=timeline or [],
    )


def to_admin_order_detail_dto(
    order: Order,
    *,
    group: OrderGroup | None = None,
    timeline: list | None = None,
    photos: list[OrderPhoto] | None = None,
    message_logs: list | None = None,
    sibling_lines: list[AdminOrderSiblingRead] | None = None,
) -> AdminOrderDetailRead:
    base = to_admin_order_dto(order, group=group, timeline=timeline)
    return AdminOrderDetailRead(
        **base.model_dump(),
        photos=[to_admin_photo_dto(photo) for photo in photos or []],
        message_logs=[MessageLogRead.model_validate(log) for log in message_logs or []],
        sibling_lines=sibling_lines or [],
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


def partner_memo_events(events: list[OrderTimeline], partner_id: str) -> list[OrderTimeline]:
    """이 협력사가 직접 작성한 메모만 추린다.

    - author_role 으로 관리자 결제/일정 변경의 memo_added 를 제외(민감정보 보호).
    - author_partner_id 로 작성자를 한정해 재배정(A→B) 시 B 가 이전 협력사 A 의
      현장 메모를 보지 못하게 한다. author_partner_id 가 없는 과거 메모는 노출하지 않는다.
    """
    return [
        event
        for event in events
        if event.event_type == TimelineEventType.MEMO_ADDED
        and (event.event_metadata or {}).get("author_role") == "partner"
        and (event.event_metadata or {}).get("author_partner_id") == partner_id
    ]


def to_partner_job_dto(
    order: Order,
    *,
    group: OrderGroup | None = None,
    photos: list[OrderPhoto] | None = None,
    memos: list[OrderTimeline] | None = None,
) -> PartnerJobRead:
    customer_name = group.customer_name if group else order.customer_name
    customer_phone = group.customer_phone if group else order.customer_phone
    customer_address = group.customer_address if group else order.customer_address
    customer_address_detail = group.customer_address_detail if group else None
    return PartnerJobRead(
        id=order.id,
        status=order.status,
        scheduled_date=order.scheduled_date,
        requested_time=order.requested_time,
        service_name=order.service_name,
        size_or_quantity=order.size_or_quantity,
        service_detail=order.service_detail,
        special_request=order.special_request,
        customer_name=customer_name or "",
        customer_phone=customer_phone or "",
        customer_address=customer_address or "",
        customer_address_detail=customer_address_detail,
        is_recurring=order.recurring_contract_id is not None,
        photos=[to_partner_photo_dto(photo) for photo in photos or []],
        memos=[
            PartnerMemoRead(id=m.id, text=m.description or "", created_at=m.created_at)
            for m in memos or []
        ],
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


def to_customer_group_dto(
    group: OrderGroup,
    *,
    lines_with_photos: list[tuple[Order, list[OrderPhoto]]],
) -> CustomerOrderGroupRead:
    return CustomerOrderGroupRead(
        id=group.id,
        customer_name=group.customer_name,
        customer_phone=group.customer_phone,
        customer_address=group.customer_address,
        customer_address_detail=group.customer_address_detail,
        customer_visible_payment=group.customer_visible_payment,
        lines=[
            _to_customer_line_dto(
                line,
                photos,
                payment_visible=group.customer_visible_payment,
            )
            for line, photos in lines_with_photos
        ],
    )


def _to_customer_line_dto(
    line: Order,
    photos: list[OrderPhoto],
    *,
    payment_visible: bool,
) -> CustomerOrderLineRead:
    return CustomerOrderLineRead(
        id=line.id,
        status=line.status,
        scheduled_date=line.scheduled_date,
        requested_time=line.requested_time,
        service_name=line.service_name,
        size_or_quantity=line.size_or_quantity,
        service_detail=line.service_detail,
        special_request=line.special_request,
        total_amount=order_consumer_total(line) if payment_visible else None,
        deposit_amount=line.deposit_amount if payment_visible else None,
        balance_amount=line.balance_amount if payment_visible else None,
        payment_status=line.payment_status if payment_visible else None,
        photos=[to_customer_photo_dto(photo) for photo in photos if photo.is_customer_visible],
    )


def to_customer_order_dto(order: Order, *, photos: list[OrderPhoto] | None = None) -> CustomerOrderRead:
    payment_visible = bool(order.customer_visible_payment)
    return CustomerOrderRead(
        id=order.id,
        customer_name=order.customer_name or "",
        customer_phone=order.customer_phone or "",
        customer_address=order.customer_address or "",
        customer_address_detail=None,
        customer_visible_payment=payment_visible,
        lines=[_to_customer_line_dto(order, photos or [], payment_visible=payment_visible)],
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
