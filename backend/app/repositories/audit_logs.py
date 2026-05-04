from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.repositories.base import Repository


class AuditLogRepository(Repository[AuditLog]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, AuditLog)
