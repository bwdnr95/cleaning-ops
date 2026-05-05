from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.constants import MessageStatus, MessageType, OrderStatus, RecipientType, TimelineEventType
from app.models.message import MessageLog
from app.models.order import Order
from app.models.partner import Partner
from app.repositories.messages import MessageRepository
from app.repositories.orders import OrderRepository
from app.repositories.partners import PartnerRepository
from app.repositories.photos import PhotoRepository
from app.schemas.message import MessageSendRequest
from app.services.timeline import TimelineService


@dataclass(frozen=True)
class MessageSendResult:
    status: MessageStatus
    error_message: str | None = None


class MessageProvider:
    def send(self, content: str, recipient_phone: str) -> MessageSendResult:
        raise NotImplementedError


class MockMessageProvider(MessageProvider):
    def send(self, content: str, recipient_phone: str) -> MessageSendResult:
        if not content or not recipient_phone:
            return MessageSendResult(status=MessageStatus.FAILED, error_message="missing_recipient")
        return MessageSendResult(status=MessageStatus.SENT)


class MessageService:
    def __init__(self, db: Session, provider: MessageProvider | None = None) -> None:
        self.db = db
        self.orders = OrderRepository(db)
        self.messages = MessageRepository(db)
        self.partners = PartnerRepository(db)
        self.photos = PhotoRepository(db)
        self.timeline = TimelineService(db)
        self.provider = provider or MockMessageProvider()

    def list_logs(self) -> list[MessageLog]:
        return self.messages.list_messages()

    def send(self, payload: MessageSendRequest, *, actor_user_id: str | None = None) -> MessageLog:
        order = self.orders.get(payload.order_id)
        if order is None:
            raise ValueError("order_not_found")
        if payload.message_type == MessageType.CUSTOMER_PHOTO_READY:
            visible_photos = self.photos.list_for_order(order.id, customer_visible_only=True)
            if not visible_photos:
                raise ValueError("no_customer_visible_photos")

        recipient_type, recipient_name, recipient_phone = self._resolve_recipient(order, payload)
        content = self._render_content(
            payload,
            order=order,
            partner=self.partners.get(order.partner_id) if order.partner_id else None,
            customer_link=self._build_customer_link(order.customer_token),
        )
        result = self.provider.send(content, recipient_phone)

        log = MessageLog(
            id=str(uuid4()),
            order_id=payload.order_id,
            recipient_type=recipient_type,
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            message_type=payload.message_type,
            channel=payload.channel,
            content=content,
            status=result.status,
            error_message=result.error_message,
            sent_at=datetime.now() if result.status == MessageStatus.SENT else None,
        )
        self.messages.add(log)
        self.timeline.record(
            order_id=payload.order_id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.MESSAGE_SENT,
            title="메시지 발송",
            description=self._message_sent_description(payload.message_type, result.status),
            metadata={
                "message_log_id": log.id,
                "message_type": payload.message_type,
                "recipient_type": recipient_type,
                "status": result.status,
            },
        )
        if result.status == MessageStatus.SENT:
            self._apply_sent_side_effects(order, payload, log, actor_user_id=actor_user_id)

        self.db.commit()
        self.db.refresh(log)
        return log

    def _resolve_recipient(self, order: Order, payload: MessageSendRequest) -> tuple[RecipientType, str, str]:
        if payload.message_type == MessageType.PARTNER_ASSIGNMENT:
            if not order.partner_id:
                raise ValueError("partner_not_assigned")
            partner = self.partners.get(order.partner_id)
            if partner is None:
                raise ValueError("partner_not_found")
            return RecipientType.PARTNER, partner.manager_name or partner.name, partner.phone

        if payload.recipient_type != RecipientType.CUSTOMER:
            raise ValueError("invalid_recipient_type")
        return RecipientType.CUSTOMER, order.customer_name, order.customer_phone

    def _apply_sent_side_effects(
        self,
        order: Order,
        payload: MessageSendRequest,
        log: MessageLog,
        *,
        actor_user_id: str | None,
    ) -> None:
        if payload.message_type == MessageType.CUSTOMER_SCHEDULE_CONFIRMED:
            self._advance_status(
                order,
                OrderStatus.SCHEDULE_CONFIRMED,
                actor_user_id=actor_user_id,
                title="일정확정 안내 완료",
                description="고객에게 일정확정 안내를 발송했습니다.",
            )
            self._record_customer_link_sent(order, payload, log, actor_user_id=actor_user_id)
            return

        if payload.message_type == MessageType.CUSTOMER_DAY_BEFORE:
            self._advance_status(
                order,
                OrderStatus.DAY_BEFORE_NOTICE_DONE,
                actor_user_id=actor_user_id,
                title="전날 안내 완료",
                description="고객에게 방문 전날 안내를 발송했습니다.",
            )
            self._record_customer_link_sent(order, payload, log, actor_user_id=actor_user_id)
            return

        if payload.message_type == MessageType.PARTNER_ASSIGNMENT:
            self._advance_status(
                order,
                OrderStatus.PARTNER_CONFIRMING,
                actor_user_id=actor_user_id,
                title="협력사 배정 안내 완료",
                description="협력사에게 작업 배정 안내를 발송했습니다.",
            )
            return

        if payload.message_type == MessageType.CUSTOMER_PHOTO_READY:
            self._advance_status(
                order,
                OrderStatus.CUSTOMER_DELIVERY_DONE,
                actor_user_id=actor_user_id,
                title="고객 전달 완료",
                description="고객에게 작업 사진 확인 링크를 발송했습니다.",
            )
            self._record_customer_link_sent(order, payload, log, actor_user_id=actor_user_id)

    def _advance_status(
        self,
        order: Order,
        next_status: OrderStatus,
        *,
        actor_user_id: str | None,
        title: str,
        description: str,
    ) -> None:
        old_status = order.status
        if not should_advance_status(old_status, next_status):
            return
        order.status = next_status
        self.timeline.record(
            order_id=order.id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.STATUS_CHANGED,
            title=title,
            description=description,
            metadata={"from": old_status, "to": order.status},
        )

    def _record_customer_link_sent(
        self,
        order: Order,
        payload: MessageSendRequest,
        log: MessageLog,
        *,
        actor_user_id: str | None,
    ) -> None:
        self.timeline.record(
            order_id=order.id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.CUSTOMER_LINK_SENT,
            title="고객 링크 발송",
            metadata={"message_log_id": log.id, "channel": payload.channel},
        )

    def _render_content(
        self,
        payload: MessageSendRequest,
        *,
        order: Order,
        partner: Partner | None,
        customer_link: str,
    ) -> str:
        schedule = format_schedule(order)
        if payload.message_type == MessageType.CUSTOMER_PHOTO_READY:
            return (
                f"[Cleaning Ops] {order.customer_name}님, {order.service_name} 작업 사진 확인이 준비되었습니다.\n"
                f"아래 링크에서 연락처 뒷자리 인증 후 확인해주세요.\n{customer_link}"
            )
        if payload.message_type == MessageType.CUSTOMER_SCHEDULE_CONFIRMED:
            return (
                f"[Cleaning Ops] {order.customer_name}님, 예약 일정이 확정되었습니다.\n"
                f"서비스: {format_service_name(order)}\n"
                f"방문: {schedule}\n"
                f"주소: {order.customer_address}\n"
                f"예약 확인: {customer_link}"
            )
        if payload.message_type == MessageType.CUSTOMER_DAY_BEFORE:
            return (
                "[Cleaning Ops] 내일 방문 예정 안내드립니다.\n"
                f"서비스: {format_service_name(order)}\n"
                f"방문: {schedule}\n"
                f"요청사항과 안내는 아래 링크에서 확인해주세요.\n{customer_link}"
            )
        if payload.message_type == MessageType.PARTNER_ASSIGNMENT:
            partner_name = partner.name if partner else "협력사"
            return (
                f"[Cleaning Ops] {partner_name}에 신규 작업이 배정되었습니다.\n"
                f"방문: {schedule}\n"
                f"서비스: {format_service_name(order)}\n"
                f"고객: {order.customer_name}\n"
                f"주소: {order.customer_address}\n"
                f"요청사항: {order.special_request or '-'}"
            )
        return f"[Cleaning Ops] {payload.message_type.value}: {format_service_name(order)}"

    def _build_customer_link(self, customer_token: str) -> str:
        return f"{settings.frontend_url.rstrip('/')}/c/{customer_token}"

    def _message_sent_description(self, message_type: MessageType, status: MessageStatus) -> str:
        label = {
            MessageType.CUSTOMER_SCHEDULE_CONFIRMED: "고객 일정확정 안내",
            MessageType.CUSTOMER_DAY_BEFORE: "고객 전날 안내",
            MessageType.PARTNER_ASSIGNMENT: "협력사 배정 안내",
            MessageType.CUSTOMER_PHOTO_READY: "고객 사진 확인 안내",
        }.get(message_type, message_type.value)
        return f"{label} 발송 결과: {status.value}"


STATUS_ORDER: dict[OrderStatus, int] = {
    OrderStatus.NEW: 10,
    OrderStatus.CONSULTING: 20,
    OrderStatus.PARTNER_CONFIRMING: 30,
    OrderStatus.SCHEDULE_CONFIRMED: 40,
    OrderStatus.DAY_BEFORE_NOTICE_NEEDED: 50,
    OrderStatus.DAY_BEFORE_NOTICE_DONE: 60,
    OrderStatus.SCHEDULED: 70,
    OrderStatus.IN_PROGRESS: 80,
    OrderStatus.PHOTO_REVIEW_PENDING: 90,
    OrderStatus.CUSTOMER_DELIVERY_NEEDED: 100,
    OrderStatus.CUSTOMER_DELIVERY_DONE: 110,
    OrderStatus.COMPLETED: 120,
    OrderStatus.CANCELLED: 999,
}


def should_advance_status(current: OrderStatus, next_status: OrderStatus) -> bool:
    if current == next_status or current == OrderStatus.CANCELLED:
        return False
    return STATUS_ORDER[current] < STATUS_ORDER[next_status]


def format_service_name(order: Order) -> str:
    if order.size_or_quantity:
        return f"{order.service_name} ({order.size_or_quantity})"
    return order.service_name


def format_schedule(order: Order) -> str:
    date_text = order.scheduled_date.isoformat() if order.scheduled_date else "일정 미정"
    if order.requested_time:
        return f"{date_text} {order.requested_time}"
    return date_text
