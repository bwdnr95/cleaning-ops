"""테스트 전역 환경 격리.

backend/.env 가 시연 배포용 값(`FRONTEND_URL=https://...`)을 가질 수 있어
테스트가 dev 환경 메시지 본문을 검증할 때 회귀가 발생한다. 테스트는
어떤 워킹 디렉토리에서 실행되든 결정적인 값을 봐야 하므로, app.* 가
import 되기 전에 os.environ 으로 핵심 설정을 고정한다.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Generator
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_TEST_ENV: dict[str, str] = {
    "ENVIRONMENT": "test",
    "FRONTEND_URL": "http://localhost:5173",
    "CORS_ORIGINS": '["http://localhost:5173"]',
    "MESSAGE_PROVIDER": "mock",
    "STORAGE_PROVIDER": "local",
    "STORAGE_ROOT": "test_storage",
    "DATABASE_URL": "sqlite:///./test_cleaning_ops.db",
    "AUTOMATION_SEND_PARTNER_ASSIGNMENT": "false",
    "AUTOMATION_SEND_SCHEDULE_CONFIRMED": "false",
    "AUTOMATION_DAY_BEFORE_NOTICE_SCHEDULER_ENABLED": "false",
    "AUTOMATION_RECURRING_ORDER_SCHEDULER_ENABLED": "false",
    "SENTRY_DSN": "",
}

for key, value in _TEST_ENV.items():
    os.environ[key] = value

from app.db.seed import (  # noqa: E402
    DEV_ADMIN_EMAIL,
    DEV_ADMIN_PASSWORD,
    DEV_ORDER_ID,
    DEV_PARTNER_ID,
    DEV_PARTNER_PASSWORD,
    DEV_PARTNER_PHONE,
    DEV_PARTNER_USER_ID,
    seed_dev_data,
)
from app.domain.constants import OrderStatus  # noqa: E402
from app.models import Base, Order, OrderGroup, User  # noqa: E402
from tests.test_auth_integration import make_test_client  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """In-memory SQLite seed DB + FastAPI app을 한 묶음으로 제공한다."""
    return make_test_client()


@pytest.fixture
def seed_admin_token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/admin/login",
        json={"identifier": DEV_ADMIN_EMAIL, "password": DEV_ADMIN_PASSWORD},
    )
    return response.json()["access_token"]


@pytest.fixture
def seed_partner_token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/partner/login",
        json={"identifier": DEV_PARTNER_PHONE, "password": DEV_PARTNER_PASSWORD},
    )
    return response.json()["access_token"]


@pytest.fixture
def seed_order_id() -> str:
    return DEV_ORDER_ID


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        seed_dev_data(db)
        db.commit()

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture
def seed_admin_user(db_session: Session) -> User:
    user = db_session.scalar(select(User).where(User.email == DEV_ADMIN_EMAIL))
    assert user is not None
    return user


@pytest.fixture
def seed_partner_user(db_session: Session) -> User:
    user = db_session.get(User, DEV_PARTNER_USER_ID)
    assert user is not None
    return user


@pytest.fixture
def seed_order(db_session: Session) -> Order:
    group = OrderGroup(
        id=str(uuid4()),
        customer_token=f"test-token-{uuid4()}",
        customer_name="테스트",
        customer_phone="01012345678",
        customer_address="서울특별시 강남구 테스트로 1",
        customer_address_detail=None,
        source_channel="테스트",
        customer_visible_payment=False,
    )
    db_session.add(group)
    db_session.flush()

    order = Order(
        id=str(uuid4()),
        group_id=group.id,
        status=OrderStatus.NEW,
        received_date=date.today(),
        service_name="테스트 청소",
        customer_token=group.customer_token,
        customer_name=group.customer_name,
        customer_phone=group.customer_phone,
        customer_address=group.customer_address,
        source_channel=group.source_channel,
        customer_visible_payment=group.customer_visible_payment,
    )
    db_session.add(order)
    db_session.flush()
    return order


@pytest.fixture
def make_extra_line(db_session: Session) -> Callable[[str], Order]:
    def factory(group_id: str) -> Order:
        group = db_session.get(OrderGroup, group_id)
        assert group is not None
        order = Order(
            id=str(uuid4()),
            group_id=group.id,
            status=OrderStatus.NEW,
            received_date=date.today(),
            service_name="추가 청소",
            customer_token=group.customer_token,
            customer_name=group.customer_name,
            customer_phone=group.customer_phone,
            customer_address=group.customer_address,
            source_channel=group.source_channel,
            customer_visible_payment=group.customer_visible_payment,
        )
        db_session.add(order)
        db_session.flush()
        return order

    return factory


@pytest.fixture
def seed_order_assigned_to_partner(seed_order: Order) -> Order:
    seed_order.partner_id = DEV_PARTNER_ID
    return seed_order


@pytest.fixture
def seed_order_with_customer_token(seed_order: Order, db_session: Session) -> tuple[Order, OrderGroup]:
    group = db_session.get(OrderGroup, seed_order.group_id)
    assert group is not None
    return seed_order, group
