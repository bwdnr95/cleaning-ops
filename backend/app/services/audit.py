from uuid import uuid4

from sqlalchemy.orm import Session

from app.domain.constants import AuditEventType, AuditSeverity
from app.models.audit_log import AuditLog
from app.repositories.audit_logs import AuditLogRepository


class AuditService:
    def __init__(self, db: Session) -> None:
        self.repo = AuditLogRepository(db)

    def record(
        self,
        *,
        event_type: AuditEventType,
        severity: AuditSeverity = AuditSeverity.INFO,
        user_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict | None = None,
    ) -> AuditLog:
        log = AuditLog(
            id=str(uuid4()),
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )
        return self.repo.add(log)
