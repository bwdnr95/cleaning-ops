from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.constants import MessageType, OrderStatus
from app.domain.constants import MessageStatus, TimelineEventType
from app.models.message import MessageLog
from app.repositories.messages import MessageRepository
from app.repositories.orders import OrderRepository
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
        self.timeline = TimelineService(db)
        self.provider = provider or MockMessageProvider()

    def send(self, payload: MessageSendRequest, *, actor_user_id: str | None = None) -> MessageLog:
        order = self.orders.get(payload.order_id)
        if order is None:
            raise ValueError("order_not_found")

        recipient_name = order.customer_name
        recipient_phone = order.customer_phone
        content = self._render_content(
            payload,
            customer_name=order.customer_name,
            service_name=order.service_name,
            customer_link=self._build_customer_link(order.customer_token),
        )
        result = self.provider.send(content, recipient_phone)

        log = MessageLog(
            id=str(uuid4()),
            order_id=payload.order_id,
            recipient_type=payload.recipient_type,
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
            metadata={"message_type": payload.message_type, "status": result.status},
        )
        if payload.message_type == MessageType.CUSTOMER_PHOTO_READY and result.status == MessageStatus.SENT:
            order.status = OrderStatus.CUSTOMER_DELIVERY_DONE
            self.timeline.record(
                order_id=payload.order_id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.CUSTOMER_LINK_SENT,
                title="고객 링크 발송",
                metadata={"message_log_id": log.id, "channel": payload.channel},
            )
        self.db.commit()
        self.db.refresh(log)
        return log

    def _render_content(
        self,
        payload: MessageSendRequest,
        *,
        customer_name: str,
        service_name: str,
        customer_link: str,
    ) -> str:
        if payload.message_type == MessageType.CUSTOMER_PHOTO_READY:
            return (
                f"[Cleaning Ops] {customer_name}님, {service_name} 작업 사진 확인이 준비되었습니다.\n"
                f"아래 링크에서 연락처 뒷자리 인증 후 확인해주세요.\n{customer_link}"
            )
        return f"[Cleaning Ops] {payload.message_type.value}: {service_name}"

    def _build_customer_link(self, customer_token: str) -> str:
        return f"{settings.frontend_url.rstrip('/')}/customer?t={customer_token}"
