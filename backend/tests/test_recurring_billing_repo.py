from datetime import date
from uuid import uuid4

from app.domain.constants import OrderStatus
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.repositories.orders import OrderRepository


def _order(db, *, contract_id, scheduled, status=OrderStatus.COMPLETED, deleted=False):
    group = OrderGroup(
        id=str(uuid4()), customer_token=f"t-{uuid4()}", customer_name="C",
        customer_phone="01000000000", customer_address="A", customer_visible_payment=False,
    )
    db.add(group)
    db.flush()
    o = Order(
        id=str(uuid4()), group_id=group.id, status=status, received_date=date(2026, 6, 1),
        scheduled_date=scheduled, service_name="S", recurring_contract_id=contract_id,
        customer_token=group.customer_token, customer_name="C", customer_phone="01000000000",
        customer_address="A",
    )
    if deleted:
        from app.core.time import utc_now
        o.deleted_at = utc_now()
    db.add(o)
    db.flush()
    return o


def test_list_billing_orders_filters_month_contract_and_excludes_cancelled_deleted(db_session):
    repo = OrderRepository(db_session)
    keep = _order(db_session, contract_id="c1", scheduled=date(2026, 6, 10))
    _order(db_session, contract_id="c1", scheduled=date(2026, 7, 10))  # 다른 달
    _order(db_session, contract_id="c2", scheduled=date(2026, 6, 10))  # 다른 계약
    _order(db_session, contract_id="c1", scheduled=date(2026, 6, 11), status=OrderStatus.CANCELLED)  # 취소
    _order(db_session, contract_id="c1", scheduled=date(2026, 6, 12), deleted=True)  # 삭제

    rows = repo.list_recurring_billing_orders(month="2026-06", contract_id="c1")
    assert [o.id for o in rows] == [keep.id]


def test_list_billing_orders_all_contracts(db_session):
    repo = OrderRepository(db_session)
    a = _order(db_session, contract_id="c1", scheduled=date(2026, 6, 10))
    b = _order(db_session, contract_id="c2", scheduled=date(2026, 6, 10))
    rows = repo.list_recurring_billing_orders(month="2026-06", contract_id=None)
    assert {o.id for o in rows} == {a.id, b.id}
