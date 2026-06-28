from datetime import date

from app.domain.constants import OrderStatus
from app.schemas.order import OrderGroupCreate, OrderLineCreate
from app.services.orders import OrderService


def test_create_empty_group_has_no_lines(db_session):
    svc = OrderService(db_session)
    group = svc.create_empty_group(
        OrderGroupCreate(
            customer_name="강남빌딩", customer_phone="01011112222", customer_address="서울 강남구 1",
            lines=[OrderLineCreate(service_name="placeholder", received_date=date(2026, 6, 28))],  # lines는 무시됨
        )
    )
    assert group.customer_token
    from app.repositories.order_groups import OrderGroupRepository
    assert OrderGroupRepository(db_session).list_lines(group.id) == []


def test_add_recurring_line_stamps_contract_id_without_commit(db_session):
    svc = OrderService(db_session)
    group = svc.create_empty_group(
        OrderGroupCreate(
            customer_name="강남빌딩", customer_phone="01011112222", customer_address="서울 강남구 1",
            lines=[OrderLineCreate(service_name="x", received_date=date(2026, 6, 28))],
        )
    )
    order = svc.add_recurring_line(
        group,
        OrderLineCreate(service_name="사무실 정기청소", status=OrderStatus.SCHEDULE_CONFIRMED,
                        received_date=date(2026, 6, 28), scheduled_date=date(2026, 7, 10)),
        recurring_contract_id="contract-xyz",
        actor_user_id=None,
    )
    db_session.commit()
    assert order.recurring_contract_id == "contract-xyz"
    assert order.status == OrderStatus.SCHEDULE_CONFIRMED
