import base64
import binascii
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import to_utc
from app.domain.constants import (
    CustomerAftercareStatus,
    MessageType,
    OrderStatus,
    PhotoType,
    ReceiptStatus,
    ReceiptType,
    RecipientType,
    TimelineEventType,
    VatType,
)
from app.domain.customer_token import generate_customer_token
from app.domain.order_pricing import order_consumer_total
from app.domain.payment_status import PAYMENT_TRACKED_FIELDS, PaymentStatus
from app.domain.phone import normalize_phone
from app.models.message import MessageLog
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.models.photo import OrderPhoto
from app.models.timeline import OrderTimeline
from app.repositories.messages import MessageRepository
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.orders import OrderRepository
from app.repositories.partners import PartnerRepository
from app.repositories.photos import PhotoRepository
from app.repositories.timeline import TimelineRepository
from app.schemas.common import TimelineEventRead
from app.schemas.message import MessageLogRead, MessageSendRequest
from app.schemas.order import (
    AdminOrderDetailRead,
    AdminOrderGroupRead,
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
from app.services.messages import (
    PARTNER_ASSIGNMENT_RECOVERY_STATUSES,
    SCHEDULE_CONFIRMATION_RECOVERY_STATUSES,
    MessageService,
    has_customer_balance_due,
)
from app.services.service_catalog import ServiceCatalogService
from app.services.storage import get_storage_provider
from app.services.timeline import TimelineService


def _normalize_receipt_fields(values: dict[str, object]) -> None:
    """증빙 유형이 발급X(NONE)면 발급 상태를 '해당없음'으로 강제한다."""
    if values.get("receipt_type") == ReceiptType.NONE:
        values["receipt_status"] = ReceiptStatus.NOT_APPLICABLE


PARTNER_JOB_STARTABLE_STATUSES = {
    OrderStatus.SCHEDULE_CONFIRMED.value,
    OrderStatus.DAY_BEFORE_NOTICE_NEEDED.value,
    OrderStatus.DAY_BEFORE_NOTICE_DONE.value,
    OrderStatus.SCHEDULED.value,
    OrderStatus.CUSTOMER_CHECK_NEEDED.value,
}

PARTNER_JOB_CONFIRMABLE_STATUSES = {
    OrderStatus.PARTNER_CONFIRMING.value,
}

PARTNER_JOB_COMPLETABLE_STATUSES = {
    OrderStatus.IN_PROGRESS.value,
}

AS_REQUEST_ALLOWED_STATUSES = {
    OrderStatus.CUSTOMER_DELIVERY_NEEDED.value,
    OrderStatus.CUSTOMER_DELIVERY_DONE.value,
    OrderStatus.CUSTOMER_CHECK_NEEDED.value,
    OrderStatus.COMPLETED.value,
}

CUSTOMER_AS_INTAKE_ALLOWED_STATUSES = {
    OrderStatus.CUSTOMER_DELIVERY_NEEDED.value,
    OrderStatus.CUSTOMER_DELIVERY_DONE.value,
    OrderStatus.COMPLETED.value,
}

CONFIRMATION_INVALIDATABLE_STATUSES = {
    OrderStatus.SCHEDULE_CONFIRMED.value,
    OrderStatus.DAY_BEFORE_NOTICE_NEEDED.value,
    OrderStatus.DAY_BEFORE_NOTICE_DONE.value,
    OrderStatus.SCHEDULED.value,
}

# 협력사 사진 업로드 허용 상태 집합.
# 시작 가능(STARTABLE) 상태 + 작업진행(IN_PROGRESS)을 합친 "활성 작업 구간"으로 정의한다.
# - STARTABLE 포함: 협력사가 '작업 시작'을 누르기 전에도 사진 업로드를 허용.
# - IN_PROGRESS 포함: 멀티 배치 업로드를 허용하는 invariant 보장(작업진행 중 여러 번 나눠 업로드).
# - 제외: 사전/상담 상태(신규접수·상담중·협력사확인중), 검수/전달 단계(사진검수대기·고객전달필요),
#   종료/봉인 상태(고객전달완료·서비스완료·취소)에는 자동 공개 사진이 새로 올라오지 못하게 막는다.
PARTNER_PHOTO_UPLOADABLE_STATUSES = (
    PARTNER_JOB_STARTABLE_STATUSES | PARTNER_JOB_COMPLETABLE_STATUSES
)


def is_partner_job_startable(order: Order) -> bool:
    if order.as_intake_pending:
        return False
    if order.status not in PARTNER_JOB_STARTABLE_STATUSES:
        return False
    if order.status == OrderStatus.CUSTOMER_CHECK_NEEDED.value:
        return bool(order.as_requested)
    return True


def is_partner_photo_uploadable(order: Order) -> bool:
    if order.as_intake_pending:
        return False
    return order.status in PARTNER_JOB_COMPLETABLE_STATUSES or is_partner_job_startable(order)


def is_customer_as_intake_pending(order: Order) -> bool:
    return bool(order.as_intake_pending)


def is_partner_confirmation_required(
    order: Order,
    timeline: TimelineService,
) -> bool:
    if order.status not in (PARTNER_JOB_CONFIRMABLE_STATUSES | CONFIRMATION_INVALIDATABLE_STATUSES):
        return False
    return (
        timeline.latest_current_partner_confirmation(
            order_id=order.id,
            partner_id=order.partner_id,
        )
        is None
    )


SIGNATURE_DATA_URL_PREFIX = "data:image/png;base64,"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


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
        self.messages = MessageRepository(db)
        self.photos = PhotoRepository(db)
        self.partners = PartnerRepository(db)
        self.timelines = TimelineRepository(db)
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
            customer_token=generate_customer_token(),
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
        created_orders = [
            self._create_line_internal(group, line_payload, actor_user_id=actor_user_id)
            for line_payload in payload.lines
        ]
        self.db.commit()
        for order in created_orders:
            self.db.refresh(order)
            self._send_partner_assignment_if_needed(order, actor_user_id=actor_user_id)
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
        self._send_partner_assignment_if_needed(order, actor_user_id=actor_user_id)
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
            customer_token=generate_customer_token(),
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
        self._require_active_partner(values.get("partner_id"))
        if values.get("partner_id") and values.get("status") in CONFIRMATION_INVALIDATABLE_STATUSES:
            values["status"] = OrderStatus.PARTNER_CONFIRMING
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
            if order.status == OrderStatus.PARTNER_CONFIRMING:
                self.timeline.record(
                    order_id=order.id,
                    actor_user_id=actor_user_id,
                    event_type=TimelineEventType.PARTNER_CONFIRMATION_REQUIRED,
                    title="협력사 작업 확인 요청",
                    metadata={"partner_id": order.partner_id, "initial_assignment": True},
                )
        return order

    def update(
        self, order_id: str, payload: OrderUpdate, *, actor_user_id: str | None = None
    ) -> Order:
        order = self.db.execute(
            select(Order)
            .where(
                Order.id == order_id,
                Order.deleted_at.is_(None),
            )
            .with_for_update()
        ).scalar_one_or_none()
        if order is None:
            raise ValueError("order_not_found")

        changes = payload.model_dump(exclude_unset=True)
        has_effective_change = any(getattr(order, key) != value for key, value in changes.items())
        if has_effective_change and self.messages.has_pending_dispatch_for_order(order.id):
            raise ValueError("message_dispatch_in_progress")
        if (
            order.as_intake_pending
            and "status" in changes
            and changes["status"] not in {order.status, OrderStatus.CANCELLED}
        ):
            raise ValueError("as_intake_approval_required")
        if "partner_id" in changes and changes["partner_id"] != order.partner_id:
            self._require_active_partner(changes["partner_id"])
        self._apply_service_catalog(changes)
        _normalize_receipt_fields(changes)
        old_status = order.status
        old_partner_id = order.partner_id
        payment_changes = collect_payment_changes(order, changes)
        schedule_changes = collect_schedule_changes(order, changes)
        for key, value in changes.items():
            if key == "customer_phone" and value is not None:
                value = normalize_phone(value)
            setattr(order, key, value)

        partner_changed = "partner_id" in changes and order.partner_id != old_partner_id
        requested_status = changes.get("status")
        explicit_confirmation_reset = (
            requested_status == OrderStatus.PARTNER_CONFIRMING
            and old_status != OrderStatus.PARTNER_CONFIRMING
        )
        current_confirmation = self.timeline.latest_current_partner_confirmation(
            order_id=order.id,
            partner_id=order.partner_id,
        )
        status_preserves_confirmation_flow = (
            "status" not in changes
            or requested_status == OrderStatus.PARTNER_CONFIRMING
            or requested_status in CONFIRMATION_INVALIDATABLE_STATUSES
        )
        should_invalidate_confirmation = (
            explicit_confirmation_reset
            or (
                old_status
                in (CONFIRMATION_INVALIDATABLE_STATUSES | PARTNER_JOB_CONFIRMABLE_STATUSES)
                and bool(partner_changed or schedule_changes)
                and status_preserves_confirmation_flow
            )
            or (
                order.partner_id is not None
                and requested_status in CONFIRMATION_INVALIDATABLE_STATUSES
                and current_confirmation is None
            )
        )

        # #2: 완납(paid) 처리 시 자동 최종결제완료(서비스완료). 운영자가 같은 요청에서 상태를
        # 직접 지정했으면 그 값을 존중하고, 취소/이미 완료 건은 건드리지 않는다.
        if (
            changes.get("payment_status") == PaymentStatus.PAID
            and "status" not in changes
            and order.status not in (OrderStatus.CANCELLED, OrderStatus.COMPLETED)
            and not order.as_intake_pending
            and not order.as_requested
        ):
            from_status = order.status
            order.status = OrderStatus.COMPLETED
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.STATUS_CHANGED,
                title="상태 변경",
                description="완납 처리로 자동 최종결제완료(서비스완료) 전환되었습니다.",
                metadata={"from": from_status, "to": OrderStatus.COMPLETED.value, "auto": True},
            )

        # #3: 최종결제완료(서비스완료) 전환 시 자동 완납(paid). 운영자가 같은 요청에서 결제를
        # 직접 지정했으면 존중하고, 이미 완납/환불 건은 덮어쓰지 않는다.
        if (
            changes.get("status") == OrderStatus.COMPLETED
            and "payment_status" not in changes
            and order.payment_status not in (PaymentStatus.PAID, PaymentStatus.REFUNDED)
        ):
            from_payment = order.payment_status
            order.payment_status = PaymentStatus.PAID
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.MEMO_ADDED,
                title="결제/정산 변경",
                description="최종결제완료(서비스완료) 전환으로 자동 완납 처리되었습니다.",
                metadata={
                    "changes": {
                        "payment_status": {"from": from_payment, "to": PaymentStatus.PAID.value}
                    },
                    "auto": True,
                },
            )

        will_invalidate_confirmation = should_invalidate_confirmation and order.status not in {
            OrderStatus.CANCELLED,
            OrderStatus.COMPLETED,
        }
        if will_invalidate_confirmation:
            order.status = old_status
            self._change_status(
                order,
                OrderStatus.PARTNER_CONFIRMING,
                actor_user_id=actor_user_id,
                title="협력사 재확인 필요",
                description="협력사 또는 방문 일정이 변경되어 작업 확인을 다시 요청합니다.",
            )
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.PARTNER_CONFIRMATION_REQUIRED,
                title="협력사 재확인 요청",
                metadata={
                    "partner_changed": partner_changed,
                    "schedule_changed": bool(schedule_changes),
                    "explicit_status_reset": explicit_confirmation_reset,
                    "confirmation_missing": current_confirmation is None,
                },
            )

        if order.status == OrderStatus.CANCELLED and (
            order.as_requested or order.as_intake_pending
        ):
            order.as_requested = False
            order.as_intake_pending = False
            order.as_memo = None

        if (
            "status" in changes
            and changes["status"] != old_status
            and not will_invalidate_confirmation
        ):
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.STATUS_CHANGED,
                title="상태 변경",
                metadata={"from": old_status, "to": changes["status"]},
            )

        if partner_changed:
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

        should_send_partner_assignment = (
            settings.automation_send_partner_assignment
            and "partner_id" in changes
            and order.partner_id
            and order.partner_id != old_partner_id
            and not order.as_intake_pending
            and not order.as_requested
            and order.status in PARTNER_ASSIGNMENT_RECOVERY_STATUSES
        )
        should_send_active_as_request = (
            partner_changed and bool(order.partner_id) and order.as_requested
        )
        if should_send_active_as_request:
            self._send_automation_message(
                order,
                MessageSendRequest(
                    order_id=order.id,
                    message_type=MessageType.PARTNER_AS_REQUEST,
                    recipient_type=RecipientType.PARTNER,
                    memo=order.as_memo,
                ),
                actor_user_id=actor_user_id,
                should_send_once=True,
                successful_since=self.timelines.latest_created_at(
                    order_id=order.id,
                    event_type=TimelineEventType.PARTNER_ASSIGNED,
                ),
            )
        elif should_send_partner_assignment:
            self._send_partner_assignment_if_needed(order, actor_user_id=actor_user_id)
        else:
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
        has_effective_change = any(getattr(group, key) != value for key, value in changes.items())

        lines: list[Order] = []
        if has_effective_change:
            # MessageService.send acquires the same Order row lock before rendering and
            # committing its PENDING claim. Lock every active line in a stable order,
            # then re-check the claim, so a group edit cannot race a send that rendered
            # the previous customer details.
            lines = list(
                self.db.scalars(
                    select(Order)
                    .where(
                        Order.group_id == group_id,
                        Order.deleted_at.is_(None),
                    )
                    .order_by(Order.id.asc())
                    .execution_options(populate_existing=True)
                    .with_for_update()
                )
            )
            if self.messages.has_pending_dispatch_for_group(group.id):
                raise ValueError("message_dispatch_in_progress")

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

    def _apply_service_catalog(self, values: dict[str, object]) -> None:
        service_item_id = values.get("service_item_id")
        if isinstance(service_item_id, str) and service_item_id:
            item, _category = self.service_catalog.get_available_item(service_item_id)
            values["service_category_id"] = item.category_id
            values["service_name"] = item.name
            if values.get("total_amount") is None:
                values["total_amount"] = float(item.base_price or 0)
            if values.get("partner_payment_amount") is None:
                values["partner_payment_amount"] = float(item.partner_base_price or 0)
            return

        service_category_id = values.get("service_category_id")
        if isinstance(service_category_id, str) and service_category_id:
            self.service_catalog.require_available_category(service_category_id)

    def get_for_partner(self, order_id: str, *, partner_id: str) -> Order:
        order = self.orders.get(order_id)
        if order is None or order.partner_id != partner_id:
            raise ValueError("order_not_found")
        return order

    def confirm_partner_job(
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
        if order.as_intake_pending:
            raise ValueError("as_intake_approval_required")
        if order.status not in (
            PARTNER_JOB_CONFIRMABLE_STATUSES | CONFIRMATION_INVALIDATABLE_STATUSES
        ):
            raise ValueError("invalid_status_transition")
        if order.scheduled_date is None:
            raise ValueError("schedule_required_for_confirmation")

        partner_confirmed_at = self.timeline.latest_current_partner_confirmation(
            order_id=order.id,
            partner_id=partner_id,
        )
        has_current_confirmation = partner_confirmed_at is not None
        if order.status in PARTNER_JOB_CONFIRMABLE_STATUSES:
            self._change_status(
                order,
                OrderStatus.SCHEDULED,
                actor_user_id=actor_user_id,
                title="작업 일정 확인",
                description="협력사가 배정된 작업 일정을 확인했습니다.",
            )
        if not has_current_confirmation:
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.PARTNER_CONFIRMED,
                title="협력사 작업 확인",
                description="협력사가 작업 일정과 배정 내용을 확인했습니다.",
                metadata={"partner_id": partner_id},
            )
        if (
            settings.automation_send_schedule_confirmed
            and order.status in SCHEDULE_CONFIRMATION_RECOVERY_STATUSES
        ):
            self._send_schedule_confirmed_once(order, actor_user_id=actor_user_id)
        else:
            self.db.commit()
        self.db.refresh(order)
        return order

    def start_partner_job(
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
        if order.as_intake_pending:
            raise ValueError("as_intake_approval_required")
        if not is_partner_job_startable(order):
            raise ValueError("invalid_status_transition")
        if is_partner_confirmation_required(order, self.timeline):
            raise ValueError("partner_confirmation_required")
        if not self.photos.has_visible_type(
            order.id,
            PhotoType.BEFORE.value,
            created_after=self._completion_evidence_created_after(order),
        ):
            raise ValueError("before_photo_required_for_start")

        order.work_started_at = datetime.now(UTC)
        self._change_status(
            order,
            OrderStatus.IN_PROGRESS,
            actor_user_id=actor_user_id,
            title="작업 시작",
        )
        self.db.commit()
        self.db.refresh(order)
        return order

    def _send_partner_assignment_if_needed(
        self,
        order: Order,
        *,
        actor_user_id: str | None,
    ) -> None:
        if (
            not settings.automation_send_partner_assignment
            or not order.partner_id
            or order.as_intake_pending
            or order.as_requested
            or order.status not in PARTNER_ASSIGNMENT_RECOVERY_STATUSES
        ):
            return
        self.db.flush()
        self._send_automation_message(
            order,
            MessageSendRequest(
                order_id=order.id,
                message_type=MessageType.PARTNER_ASSIGNMENT,
                recipient_type=RecipientType.PARTNER,
            ),
            actor_user_id=actor_user_id,
            should_send_once=True,
            successful_since=self.timelines.latest_created_at(
                order_id=order.id,
                event_type=TimelineEventType.PARTNER_ASSIGNED,
            ),
        )

    def _send_schedule_confirmed_once(
        self,
        order: Order,
        *,
        actor_user_id: str | None,
    ) -> None:
        if not settings.automation_send_schedule_confirmed or order.scheduled_date is None:
            return
        self.db.flush()
        self._send_automation_message(
            order,
            MessageSendRequest(
                order_id=order.id,
                message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
                recipient_type=RecipientType.CUSTOMER,
            ),
            actor_user_id=actor_user_id,
            should_send_once=True,
            successful_since=self.timeline.latest_current_partner_confirmation(
                order_id=order.id,
                partner_id=order.partner_id,
            ),
        )

    def _send_automation_message(
        self,
        order: Order,
        payload: MessageSendRequest,
        *,
        actor_user_id: str | None,
        should_send_once: bool = False,
        successful_since: datetime | None = None,
    ) -> None:
        try:
            self.db.flush()
            message_service = MessageService(self.db)
            if should_send_once:
                message_service.send_automation_once(
                    payload,
                    actor_user_id=actor_user_id,
                    successful_since=successful_since,
                )
            else:
                message_service.send(payload, actor_user_id=actor_user_id)
        except ValueError as exc:
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.MESSAGE_SENT,
                title="자동 메시지 발송 실패",
                description=str(exc),
                metadata={
                    "message_type": payload.message_type,
                    "recipient_type": payload.recipient_type,
                    "automation": True,
                },
            )
            self.db.commit()

    def complete_partner_job(
        self,
        order_id: str,
        *,
        actor_user_id: str,
        partner_id: str,
        customer_signature_data_url: str,
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
        if order.as_intake_pending:
            raise ValueError("as_intake_approval_required")
        if order.status not in PARTNER_JOB_COMPLETABLE_STATUSES:
            raise ValueError("invalid_status_transition")

        evidence_created_after = self._completion_evidence_created_after(order)
        has_before = self.photos.has_visible_type(
            order.id,
            PhotoType.BEFORE.value,
            created_after=evidence_created_after,
        )
        has_after = self.photos.has_visible_type(
            order.id,
            PhotoType.AFTER.value,
            created_after=evidence_created_after,
        )
        signature_data = decode_signature_data_url(customer_signature_data_url)
        if not has_before or not has_after or signature_data is None:
            raise ValueError("completion_evidence_required")

        storage = get_storage_provider()
        stored_signature = storage.save(
            data=signature_data,
            file_name=f"{order.id}-customer-signature.png",
            content_type="image/png",
        )
        try:
            order.work_completed_at = datetime.now(UTC)
            order.customer_signature_storage_key = stored_signature.storage_key
            order.customer_signature_file_url = stored_signature.file_url

            was_as_requested = bool(order.as_requested)
            order.as_requested = False
            order.as_intake_pending = False

            self._change_status(
                order,
                OrderStatus.CUSTOMER_DELIVERY_NEEDED,
                actor_user_id=actor_user_id,
                title="AS 작업 완료" if was_as_requested else "작업 완료",
                description=(
                    "협력사가 AS 작업 완료를 처리했습니다."
                    if was_as_requested
                    else (
                        "협력사가 작업 완료를 처리했습니다. "
                        "자동 공개된 사진으로 고객 전달이 가능합니다."
                    )
                ),
            )
            self.db.commit()
            self.db.refresh(order)
        except Exception:
            self.db.rollback()
            with suppress(Exception):
                storage.delete(stored_signature.storage_key)
            raise
        if settings.automation_send_customer_balance_due and should_send_customer_balance_due(
            order
        ):
            self._send_automation_message(
                order,
                MessageSendRequest(
                    order_id=order.id,
                    message_type=MessageType.CUSTOMER_BALANCE_DUE,
                    recipient_type=RecipientType.CUSTOMER,
                ),
                actor_user_id=actor_user_id,
                should_send_once=True,
                successful_since=order.work_completed_at,
            )
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

    def submit_customer_as_intake(
        self,
        order_id: str,
        *,
        group_id: str,
        memo: str,
    ) -> Order:
        normalized_memo = (memo or "").strip()
        if not normalized_memo:
            raise ValueError("as_memo_required")
        order = self.db.execute(
            select(Order)
            .where(
                Order.id == order_id,
                Order.group_id == group_id,
                Order.deleted_at.is_(None),
            )
            .with_for_update()
        ).scalar_one_or_none()
        if order is None:
            raise ValueError("order_not_found")
        if order.as_requested:
            raise ValueError("as_request_already_requested")

        is_pending = is_customer_as_intake_pending(order)
        if is_pending:
            if order.as_memo == normalized_memo:
                self.db.commit()
                self.db.refresh(order)
                return order
            raise ValueError("as_request_already_pending")
        if order.status not in CUSTOMER_AS_INTAKE_ALLOWED_STATUSES:
            raise ValueError("invalid_as_request_status")

        order.as_memo = normalized_memo
        order.as_intake_pending = True
        self.timeline.record(
            order_id=order.id,
            actor_user_id=None,
            event_type=TimelineEventType.AS_INTAKE_REQUESTED,
            title="고객 AS 접수 알림",
            description=normalized_memo,
            metadata={"source": "customer_portal", "admin_attention_required": True},
        )
        self.db.commit()
        self.db.refresh(order)
        return order

    def request_as(
        self,
        order_id: str,
        *,
        memo: str,
        actor_user_id: str | None,
    ) -> Order:
        requested_memo = (memo or "").strip()
        order = self.db.execute(
            select(Order)
            .where(
                Order.id == order_id,
                Order.deleted_at.is_(None),
            )
            .with_for_update()
        ).scalar_one_or_none()
        if order is None:
            raise ValueError("order_not_found")
        if not order.partner_id:
            raise ValueError("partner_not_assigned")
        self._require_active_partner(order.partner_id)
        if order.as_requested:
            raise ValueError("as_request_already_requested")
        if order.status not in AS_REQUEST_ALLOWED_STATUSES:
            raise ValueError("invalid_as_request_status")

        is_customer_intake = is_customer_as_intake_pending(order)
        effective_memo = requested_memo or (
            (order.as_memo or "").strip() if is_customer_intake else ""
        )
        if not effective_memo:
            raise ValueError("as_memo_required")

        order.as_requested = True
        order.as_intake_pending = False
        order.as_memo = effective_memo
        self._change_status(
            order,
            OrderStatus.CUSTOMER_CHECK_NEEDED,
            actor_user_id=actor_user_id,
            title="AS 확인 필요",
            description=(
                "운영자가 고객 AS 접수를 확인하고 처리 요청을 승인했습니다."
                if is_customer_intake
                else "운영자가 AS 요청 상태로 변경했습니다."
            ),
        )
        as_event = self.timeline.record(
            order_id=order.id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.AS_REQUESTED,
            title="AS 처리 승인" if is_customer_intake else "AS 요청",
            description=effective_memo,
            metadata={"customer_intake": is_customer_intake},
        )
        self.db.flush()

        if order.partner_id:
            self._send_automation_message(
                order,
                MessageSendRequest(
                    order_id=order.id,
                    message_type=MessageType.PARTNER_AS_REQUEST,
                    recipient_type=RecipientType.PARTNER,
                    memo=effective_memo,
                ),
                actor_user_id=actor_user_id,
                should_send_once=True,
                successful_since=as_event.created_at,
            )
        self._send_automation_message(
            order,
            MessageSendRequest(
                order_id=order.id,
                message_type=MessageType.CUSTOMER_AS_NOTICE,
                recipient_type=RecipientType.CUSTOMER,
                memo=effective_memo,
            ),
            actor_user_id=actor_user_id,
            should_send_once=True,
            successful_since=as_event.created_at,
        )

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

    def _require_active_partner(self, partner_id: object) -> None:
        if partner_id is None or partner_id == "":
            return
        if not isinstance(partner_id, str):
            raise ValueError("partner_not_found")
        partner = self.partners.get(partner_id)
        if partner is None or not partner.is_active:
            raise ValueError("partner_not_found")

    def _completion_evidence_created_after(self, order: Order) -> datetime | None:
        return self.timeline.latest_partner_work_epoch(
            order_id=order.id,
            partner_id=order.partner_id,
            work_completed_at=order.work_completed_at,
            work_is_active=True,
        )


def to_admin_group_dto(
    group: OrderGroup, *, lines: list[Order] | None = None
) -> AdminOrderGroupRead:
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
    timeline: list[OrderTimeline] | None = None,
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
        broker_id=order.broker_id,
        service_category_id=order.service_category_id,
        service_item_id=order.service_item_id,
        service_name=order.service_name,
        size_or_quantity=order.size_or_quantity,
        service_detail=order.service_detail,
        special_request=order.special_request,
        as_requested=bool(order.as_requested),
        as_intake_pending=bool(order.as_intake_pending),
        as_memo=order.as_memo,
        work_started_at=order.work_started_at,
        work_completed_at=order.work_completed_at,
        customer_signature_file_url=order.customer_signature_file_url,
        source_channel=source_channel,
        customer_name=customer_name or "",
        customer_phone=customer_phone or "",
        customer_address=customer_address or "",
        customer_address_detail=customer_address_detail,
        total_amount=to_float_or_none(order.total_amount),
        discount_amount=float(order.discount_amount),
        deposit_amount=to_float_or_none(order.deposit_amount),
        balance_amount=to_float_or_none(order.balance_amount),
        onsite_extra_amount=to_float_or_none(order.onsite_extra_amount),
        vat_type=VatType(order.vat_type) if order.vat_type else None,
        payment_status=order.payment_status,
        payment_memo=order.payment_memo,
        evidence_memo=order.evidence_memo,
        receipt_type=ReceiptType(order.receipt_type) if order.receipt_type else None,
        receipt_status=ReceiptStatus(order.receipt_status) if order.receipt_status else None,
        partner_payment_amount=to_float_or_none(order.partner_payment_amount),
        partner_payment_status=order.partner_payment_status,
        broker_payment_amount=to_float_or_none(order.broker_payment_amount),
        broker_payment_status=order.broker_payment_status,
        consumer_price=to_float_or_none(order.total_amount),
        partner_price=to_float_or_none(order.partner_payment_amount),
        broker_price=to_float_or_none(order.broker_payment_amount),
        partner_settled_at=order.partner_settled_at,
        broker_settled_at=order.broker_settled_at,
        customer_visible_payment=customer_visible_payment,
        group_notes=group_notes,
        customer_token=customer_token or "",
        created_at=order.created_at,
        updated_at=order.updated_at,
        timeline=[TimelineEventRead.model_validate(event) for event in timeline or []],
    )


def to_admin_order_detail_dto(
    order: Order,
    *,
    group: OrderGroup | None = None,
    timeline: list[OrderTimeline] | None = None,
    photos: list[OrderPhoto] | None = None,
    message_logs: list[MessageLog] | None = None,
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
    as_requested_at: datetime | None = None,
    evidence_required_after: datetime | None = None,
    partner_confirmation_required: bool = False,
) -> PartnerJobRead:
    customer_name = group.customer_name if group else order.customer_name
    customer_phone = group.customer_phone if group else order.customer_phone
    customer_address = group.customer_address if group else order.customer_address
    customer_address_detail = group.customer_address_detail if group else None
    has_approved_as_request = bool(order.as_requested)
    return PartnerJobRead(
        id=order.id,
        status=order.status,
        scheduled_date=order.scheduled_date,
        requested_time=order.requested_time,
        service_name=order.service_name,
        size_or_quantity=order.size_or_quantity,
        service_detail=order.service_detail,
        special_request=order.special_request,
        as_requested=has_approved_as_request,
        as_memo=order.as_memo if has_approved_as_request else None,
        as_requested_at=as_requested_at if has_approved_as_request else None,
        evidence_required_after=evidence_required_after,
        partner_confirmation_required=partner_confirmation_required,
        work_started_at=order.work_started_at,
        work_completed_at=order.work_completed_at,
        has_recorded_customer_signature=bool(order.customer_signature_file_url),
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
        created_at=to_utc(photo.created_at) if photo.created_at is not None else None,
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
        total_amount=float(order_consumer_total(line)) if payment_visible else None,
        deposit_amount=to_float_or_none(line.deposit_amount) if payment_visible else None,
        balance_amount=to_float_or_none(line.balance_amount) if payment_visible else None,
        payment_status=line.payment_status if payment_visible else None,
        aftercare_status=_customer_aftercare_status(line),
        photos=[to_customer_photo_dto(photo) for photo in photos if photo.is_customer_visible],
    )


def _customer_aftercare_status(order: Order) -> CustomerAftercareStatus | None:
    if order.status == OrderStatus.CANCELLED:
        return None
    if order.as_requested:
        return CustomerAftercareStatus.IN_PROGRESS
    if is_customer_as_intake_pending(order):
        return CustomerAftercareStatus.PENDING
    if order.status in CUSTOMER_AS_INTAKE_ALLOWED_STATUSES:
        return CustomerAftercareStatus.AVAILABLE
    return None


def to_customer_order_dto(
    order: Order, *, photos: list[OrderPhoto] | None = None
) -> CustomerOrderRead:
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


def collect_payment_changes(
    order: Order,
    changes: dict[str, object],
) -> dict[str, dict[str, object | None]]:
    payment_changes: dict[str, dict[str, object | None]] = {}
    for field in PAYMENT_TRACKED_FIELDS:
        if field not in changes:
            continue
        before = to_timeline_value(getattr(order, field))
        after = to_timeline_value(changes[field])
        if before != after:
            payment_changes[field] = {"from": before, "to": after}
    return payment_changes


def collect_schedule_changes(
    order: Order,
    changes: dict[str, object],
) -> dict[str, dict[str, object | None]]:
    schedule_changes: dict[str, dict[str, object | None]] = {}
    for field in ("scheduled_date", "requested_time"):
        if field not in changes:
            continue
        before = to_timeline_value(getattr(order, field))
        after = to_timeline_value(changes[field])
        if before != after:
            schedule_changes[field] = {"from": before, "to": after}
    return schedule_changes


def to_float_or_none(value: object | None) -> float | None:
    return float(str(value)) if value is not None else None


def decode_signature_data_url(data_url: str) -> bytes | None:
    text = (data_url or "").strip()
    if not text.startswith(SIGNATURE_DATA_URL_PREFIX):
        return None
    try:
        data = base64.b64decode(text.removeprefix(SIGNATURE_DATA_URL_PREFIX), validate=True)
    except binascii.Error:
        return None
    if (
        not data
        or len(data) > settings.photo_max_upload_bytes
        or not data.startswith(PNG_SIGNATURE)
    ):
        return None
    return data


def should_send_customer_balance_due(order: Order) -> bool:
    return (
        not order.as_intake_pending and not order.as_requested and has_customer_balance_due(order)
    )


def to_timeline_value(value) -> object | None:
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return value.isoformat()
    if hasattr(value, "as_integer_ratio") and not isinstance(value, (int, float)):
        return float(value)
    return value
