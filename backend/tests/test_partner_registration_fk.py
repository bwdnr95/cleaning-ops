"""협력사 등록 시 audit_log FK INSERT 순서 회귀 테스트.

실 운영 DB(Postgres)는 FK 를 강제하지만 기본 SQLite 는 강제하지 않아, 일반 테스트
픽스처(conftest.db_session)로는 이 버그를 잡지 못했다. 이 테스트는
`PRAGMA foreign_keys=ON` 으로 Postgres 의 FK 강제를 재현한다.

버그: SQLAlchemy 의 unit-of-work 는 relationship 이 없으면 테이블 FK 만으로는 같은
flush 안의 INSERT 순서를 보장하지 않는다. 신규 partner user 를 먼저 flush 하지 않으면
직후의 audit_logs(user_id FK) 가 users 보다 먼저 INSERT 되어 FK 위반(=등록 실패)이 난다.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User
from app.models.audit_log import AuditLog
from app.schemas.partner import PartnerCreate
from app.services.partners import PartnerService


@pytest.fixture
def fk_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _record) -> None:  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=True, autocommit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_partner_create_with_login_account_succeeds_under_fk_enforcement(fk_session: Session) -> None:
    detail = PartnerService(fk_session).create(
        PartnerCreate(
            name="회귀테스트협력사",
            phone="01077778888",
            partner_category_id=None,
            login_phone="01077778888",
            login_password="regress1234",
        )
    )
    assert detail.id

    # user 와 audit_log 가 실제로 함께 영속화돼야 한다(FK 위반 없이).
    user = fk_session.scalar(select(User).where(User.phone == "01077778888"))
    assert user is not None
    audit = fk_session.scalar(select(AuditLog).where(AuditLog.user_id == user.id))
    assert audit is not None
