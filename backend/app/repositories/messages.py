from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import MessageLog
from app.repositories.base import Repository


class MessageRepository(Repository[MessageLog]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, MessageLog)

    def list_messages(self, *, limit: int = 100, offset: int = 0) -> list[MessageLog]:
        stmt = (
            select(MessageLog)
            .order_by(MessageLog.created_at.desc(), MessageLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt))

    def list_for_order(self, order_id: str) -> list[MessageLog]:
        stmt = (
            select(MessageLog)
            .where(MessageLog.order_id == order_id)
            .order_by(MessageLog.created_at.asc(), MessageLog.id.asc())
        )
        return list(self.db.scalars(stmt))

    def get_by_provider_message_id(self, provider: str, provider_message_id: str) -> MessageLog | None:
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

    def list_by_provider_group_id(self, provider: str, provider_group_id: str) -> list[MessageLog]:
        stmt = (
            select(MessageLog)
            .where(
                MessageLog.provider == provider,
                MessageLog.provider_group_id == provider_group_id,
            )
            .order_by(MessageLog.created_at.desc(), MessageLog.id.desc())
        )
        return list(self.db.scalars(stmt))
