from datetime import datetime

from sqlalchemy import and_, func, or_, select, true, update
from sqlalchemy.orm import Session

from app.domain.constants import (
    MESSAGE_PROVIDER_OUTCOME_UNKNOWN_ERROR_CODES,
    MessageStatus,
    MessageType,
)
from app.models.message import MessageLog
from app.models.order import Order
from app.repositories.base import Repository


class MessageRepository(Repository[MessageLog]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, MessageLog)

    def list_messages(self, *, limit: int | None = None, offset: int = 0) -> list[MessageLog]:
        stmt = (
            select(MessageLog)
            .join(Order, MessageLog.order_id == Order.id)
            .where(Order.deleted_at.is_(None))
            .order_by(MessageLog.created_at.desc(), MessageLog.id.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def list_messages_with_customer(
        self, *, limit: int | None = None, offset: int = 0
    ) -> list[tuple[MessageLog, str | None]]:
        # 발송이력 화면에서 원시 주문 ID 대신 주문 고객명을 보여주기 위해 함께 조회한다.
        stmt = (
            select(MessageLog, Order.customer_name)
            .join(Order, MessageLog.order_id == Order.id)
            .where(Order.deleted_at.is_(None))
            .order_by(MessageLog.created_at.desc(), MessageLog.id.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        return [(row[0], row[1]) for row in self.db.execute(stmt).all()]

    def list_for_order(self, order_id: str) -> list[MessageLog]:
        stmt = (
            select(MessageLog)
            .where(MessageLog.order_id == order_id)
            .order_by(MessageLog.created_at.asc(), MessageLog.id.asc())
        )
        return list(self.db.scalars(stmt))

    def last_sent_at(
        self,
        *,
        order_id: str,
        message_type: MessageType,
        sent_since: datetime | None = None,
    ) -> datetime | None:
        conditions = [
            MessageLog.order_id == order_id,
            MessageLog.message_type == message_type,
            MessageLog.status.in_([MessageStatus.SENT, MessageStatus.DELIVERED]),
        ]
        if sent_since is not None:
            conditions.append(MessageLog.sent_at >= sent_since)
        return self.db.execute(
            select(MessageLog.sent_at)
            .where(*conditions)
            .order_by(MessageLog.sent_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def has_blocking_delivery_attempt(
        self,
        *,
        order_id: str,
        message_type: MessageType,
        retry_since: datetime,
        successful_since: datetime | None = None,
        recipient_partner_id: str | None = None,
    ) -> bool:
        attempted_at = func.coalesce(MessageLog.requested_at, MessageLog.created_at)
        successful_attempt = MessageLog.status.in_([MessageStatus.SENT, MessageStatus.DELIVERED])

        epoch_filter = attempted_at >= successful_since if successful_since is not None else true()
        recipient_filter = (
            MessageLog.recipient_partner_id == recipient_partner_id
            if recipient_partner_id is not None
            else true()
        )
        return (
            self.db.execute(
                select(MessageLog.id)
                .where(
                    MessageLog.order_id == order_id,
                    MessageLog.message_type == message_type,
                    recipient_filter,
                    epoch_filter,
                    or_(
                        successful_attempt,
                        and_(
                            MessageLog.status == MessageStatus.PENDING,
                            MessageLog.provider_error_code.in_(
                                MESSAGE_PROVIDER_OUTCOME_UNKNOWN_ERROR_CODES
                            ),
                        ),
                        and_(
                            MessageLog.status == MessageStatus.PENDING,
                            attempted_at > retry_since,
                        ),
                        and_(
                            MessageLog.status.in_(
                                [MessageStatus.FAILED, MessageStatus.DELIVERY_FAILED]
                            ),
                            attempted_at > retry_since,
                        ),
                    ),
                )
                .limit(1)
            ).scalar_one_or_none()
            is not None
        )

    def has_unknown_delivery_outcome(
        self,
        *,
        order_id: str,
        message_type: MessageType,
        attempted_since: datetime | None = None,
        recipient_partner_id: str | None = None,
    ) -> bool:
        attempted_at = func.coalesce(MessageLog.requested_at, MessageLog.created_at)
        conditions = [
            MessageLog.order_id == order_id,
            MessageLog.message_type == message_type,
            MessageLog.status == MessageStatus.PENDING,
            MessageLog.provider_error_code.in_(MESSAGE_PROVIDER_OUTCOME_UNKNOWN_ERROR_CODES),
        ]
        if attempted_since is not None:
            conditions.append(attempted_at >= attempted_since)
        if recipient_partner_id is not None:
            conditions.append(MessageLog.recipient_partner_id == recipient_partner_id)
        return (
            self.db.execute(select(MessageLog.id).where(*conditions).limit(1)).scalar_one_or_none()
            is not None
        )

    def has_pending_delivery_attempt(
        self,
        *,
        order_id: str,
        message_type: MessageType,
        attempted_since: datetime | None = None,
        recipient_partner_id: str | None = None,
    ) -> bool:
        attempted_at = func.coalesce(MessageLog.requested_at, MessageLog.created_at)
        conditions = [
            MessageLog.order_id == order_id,
            MessageLog.message_type == message_type,
            MessageLog.status == MessageStatus.PENDING,
        ]
        if attempted_since is not None:
            conditions.append(attempted_at >= attempted_since)
        if recipient_partner_id is not None:
            conditions.append(MessageLog.recipient_partner_id == recipient_partner_id)
        return (
            self.db.execute(select(MessageLog.id).where(*conditions).limit(1)).scalar_one_or_none()
            is not None
        )

    def has_pending_dispatch_for_order(self, order_id: str) -> bool:
        return (
            self.db.execute(
                select(MessageLog.id)
                .where(
                    MessageLog.order_id == order_id,
                    MessageLog.status == MessageStatus.PENDING,
                )
                .limit(1)
            ).scalar_one_or_none()
            is not None
        )

    def has_pending_dispatch_for_group(self, group_id: str) -> bool:
        return (
            self.db.execute(
                select(MessageLog.id)
                .join(Order, MessageLog.order_id == Order.id)
                .where(
                    Order.group_id == group_id,
                    Order.deleted_at.is_(None),
                    MessageLog.status == MessageStatus.PENDING,
                )
                .limit(1)
            ).scalar_one_or_none()
            is not None
        )

    def expire_stale_pending_attempts(
        self,
        *,
        order_id: str,
        message_type: MessageType,
        pending_before: datetime,
        recipient_partner_id: str | None = None,
    ) -> int:
        attempted_at = func.coalesce(MessageLog.requested_at, MessageLog.created_at)
        recipient_filter = (
            MessageLog.recipient_partner_id == recipient_partner_id
            if recipient_partner_id is not None
            else true()
        )
        result = self.db.execute(
            update(MessageLog)
            .where(
                MessageLog.order_id == order_id,
                MessageLog.message_type == message_type,
                recipient_filter,
                MessageLog.status == MessageStatus.PENDING,
                MessageLog.provider != "solapi",
                attempted_at <= pending_before,
                or_(
                    MessageLog.provider_error_code.is_(None),
                    MessageLog.provider_error_code.not_in(
                        MESSAGE_PROVIDER_OUTCOME_UNKNOWN_ERROR_CODES
                    ),
                ),
            )
            .values(
                status=MessageStatus.FAILED,
                error_message="자동 발송 응답이 장시간 확인되지 않아 재시도 대상으로 전환했습니다.",
                provider_error_code="stale_pending_attempt",
                provider_status_message="stale pending attempt expired before retry",
            )
        )
        return int(getattr(result, "rowcount", 0) or 0)

    def mark_stale_solapi_pending_unknown(
        self,
        *,
        order_id: str,
        message_type: MessageType,
        pending_before: datetime,
        recipient_partner_id: str | None = None,
    ) -> int:
        attempted_at = func.coalesce(MessageLog.requested_at, MessageLog.created_at)
        recipient_filter = (
            MessageLog.recipient_partner_id == recipient_partner_id
            if recipient_partner_id is not None
            else true()
        )
        result = self.db.execute(
            update(MessageLog)
            .where(
                MessageLog.order_id == order_id,
                MessageLog.message_type == message_type,
                recipient_filter,
                MessageLog.status == MessageStatus.PENDING,
                MessageLog.provider == "solapi",
                attempted_at <= pending_before,
                or_(
                    MessageLog.provider_error_code.is_(None),
                    MessageLog.provider_error_code.not_in(
                        MESSAGE_PROVIDER_OUTCOME_UNKNOWN_ERROR_CODES
                    ),
                ),
            )
            .values(
                error_message=(
                    "프로세스 중단 구간의 SOLAPI 수락 여부를 "
                    "자동으로 확정할 수 없습니다."
                ),
                provider_error_code="solapi_outcome_unknown",
                provider_status_message="operator confirmation required for stale SOLAPI attempt",
            )
        )
        return int(getattr(result, "rowcount", 0) or 0)

    def find_by_provider_message_id(
        self, provider: str, provider_message_id: str
    ) -> MessageLog | None:
        stmt = (
            select(MessageLog)
            .where(
                MessageLog.provider == provider,
                MessageLog.provider_message_id == provider_message_id,
            )
            .order_by(MessageLog.created_at.desc(), MessageLog.id.desc())
            .limit(1)
        )
        return self.db.scalars(stmt).first()

    def find_by_provider_group_id(self, provider: str, provider_group_id: str) -> list[MessageLog]:
        stmt = (
            select(MessageLog)
            .where(
                MessageLog.provider == provider,
                MessageLog.provider_group_id == provider_group_id,
            )
            .order_by(MessageLog.created_at.desc(), MessageLog.id.desc())
        )
        return list(self.db.scalars(stmt))
