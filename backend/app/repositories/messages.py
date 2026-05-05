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
