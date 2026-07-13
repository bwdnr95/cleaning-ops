from datetime import date
from uuid import uuid4

from app.domain.constants import OrderStatus, RecurrenceMode, RecurringContractStatus
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
from app.repositories.recurring import RecurringMonthlyStatusRepository
from app.services.recurring_monthly import RecurringMonthlyService


def _contract(db):
    g = OrderGroup(id=str(uuid4()), customer_token=f"t-{uuid4()}", customer_name="강남",
                   customer_phone="01011112222", customer_address="A", customer_visible_payment=False)
    db.add(g); db.flush()
    c = RecurringContract(id=str(uuid4()), label="L", order_group_id=g.id,
                          recurrence_mode=RecurrenceMode.MONTHLY, day_of_month=10, start_date=date(2026, 6, 10),
                          status=RecurringContractStatus.ACTIVE, service_name="청소", total_amount=150000)
    db.add(c); db.flush()
    return c


def test_monthly_status_persists_and_lookup(db_session):
    repo = RecurringMonthlyStatusRepository(db_session)
    c = _contract(db_session)
    repo.add(RecurringMonthlyStatus(id=str(uuid4()), contract_id=c.id, billing_month="2026-06"))
    db_session.flush()
    found = repo.get_by_contract_and_month(c.id, "2026-06")
    assert found is not None and found.tax_invoice_issued is False and found.balance_paid is False
    assert repo.get_by_contract_and_month(c.id, "2026-07") is None


def test_list_month_upserts_active_contracts_idempotently(db_session):
    c = _contract(db_session)  # start 2026-06-10, ACTIVE
    db_session.commit()
    svc = RecurringMonthlyService(db_session)
    rows1 = svc.list_month("2026-06")
    assert any(r.contract_id == c.id and r.amount == 150000 for r in rows1)
    n_before = len(RecurringMonthlyStatusRepository(db_session).list_by_month("2026-06"))
    svc.list_month("2026-06")  # 멱등
    assert len(RecurringMonthlyStatusRepository(db_session).list_by_month("2026-06")) == n_before


def test_list_month_excludes_before_start(db_session):
    c = _contract(db_session)  # start 2026-06
    db_session.commit()
    rows = RecurringMonthlyService(db_session).list_month("2026-05")
    assert all(r.contract_id != c.id for r in rows)  # 시작 전 달 제외


def test_set_status_toggles(db_session):
    c = _contract(db_session)
    db_session.commit()
    svc = RecurringMonthlyService(db_session)
    row = svc.set_status(c.id, "2026-06", tax_invoice_issued=True)
    assert row.tax_invoice_issued is True and row.balance_paid is False
    row2 = svc.set_status(c.id, "2026-06", balance_paid=True)
    assert row2.tax_invoice_issued is True and row2.balance_paid is True


def test_monthly_api_requires_admin(client):
    assert client.get("/api/admin/recurring/monthly?month=2026-06").status_code == 401


def test_monthly_api_list_and_set(client, seed_admin_token):
    h = {"Authorization": f"Bearer {seed_admin_token}"}
    body = {"label": "강남", "customer_name": "강남", "customer_phone": "01011112222",
            "customer_address": "A", "recurrence_mode": "monthly", "day_of_month": 10,
            "start_date": "2020-01-10", "service_name": "청소", "total_amount": 100000}
    cid = client.post("/api/admin/recurring/contracts", json=body, headers=h).json()["id"]
    lst = client.get("/api/admin/recurring/monthly?month=2026-06", headers=h)
    assert lst.status_code == 200 and any(r["contract_id"] == cid for r in lst.json())
    res = client.post("/api/admin/recurring/monthly/set",
                      json={"contract_id": cid, "month": "2026-06", "tax_invoice_issued": True}, headers=h)
    assert res.status_code == 200 and res.json()["tax_invoice_issued"] is True


def _weekly_contract(db, *, billing_mode="per_visit", amount=50000):
    # 2026-06-01은 월요일 → 매주(간격1) 월요일은 6월에 5회(1,8,15,22,29).
    g = OrderGroup(id=str(uuid4()), customer_token=f"t-{uuid4()}", customer_name="주간",
                   customer_phone="01099998888", customer_address="B", customer_visible_payment=False)
    db.add(g); db.flush()
    c = RecurringContract(id=str(uuid4()), label="W", order_group_id=g.id,
                          recurrence_mode=RecurrenceMode.WEEKLY, interval_weeks=1,
                          start_date=date(2026, 6, 1), status=RecurringContractStatus.ACTIVE,
                          service_name="청소", total_amount=amount, billing_mode=billing_mode)
    db.add(c); db.flush()
    return c


def test_month_amount_per_visit_multiplies_by_visits(db_session):
    # per_visit(회당 합산): 회당 금액 × 그달 방문 횟수. 2026-06 매주 월요일 = 5회.
    c = _weekly_contract(db_session, billing_mode="per_visit", amount=50000)
    db_session.commit()
    row = next(r for r in RecurringMonthlyService(db_session).list_month("2026-06") if r.contract_id == c.id)
    assert row.amount == 50000 * 5


def test_month_amount_monthly_is_fixed(db_session):
    # monthly(월 고정): 방문 횟수와 무관하게 월 고정 금액.
    c = _weekly_contract(db_session, billing_mode="monthly", amount=50000)
    db_session.commit()
    row = next(r for r in RecurringMonthlyService(db_session).list_month("2026-06") if r.contract_id == c.id)
    assert row.amount == 50000


def test_month_amount_per_visit_counts_actual_live_orders(db_session):
    # per_visit: 그달 회차가 실제로 생성돼 있으면 살아있는(취소/삭제 제외) 방문만 청구한다.
    # 6월 회차 3건 생성 후 1건 취소 → 2건만 청구(스케줄상 5회여도 실제 발생 기준).
    c = _weekly_contract(db_session, billing_mode="per_visit", amount=50000)
    for day, st in zip((1, 8, 15), (OrderStatus.SCHEDULED, OrderStatus.SCHEDULED, OrderStatus.CANCELLED)):
        db_session.add(Order(
            id=str(uuid4()), group_id=c.order_group_id, status=st,
            received_date=date(2026, 6, 1), scheduled_date=date(2026, 6, day),
            service_name="청소", recurring_contract_id=c.id, recurring_planned_date=date(2026, 6, day),
        ))
    db_session.commit()
    row = next(r for r in RecurringMonthlyService(db_session).list_month("2026-06") if r.contract_id == c.id)
    assert row.amount == 50000 * 2


def test_month_amount_uses_generated_slots_without_new_weekday_projection(db_session):
    g = OrderGroup(id=str(uuid4()), customer_token=f"t-{uuid4()}", customer_name="요일변경",
                   customer_phone="01022223333", customer_address="C", customer_visible_payment=False)
    db_session.add(g); db_session.flush()
    c = RecurringContract(id=str(uuid4()), label="WG", order_group_id=g.id,
                          recurrence_mode=RecurrenceMode.WEEKLY, interval_weeks=1, weekdays="1",
                          start_date=date(2026, 6, 1), status=RecurringContractStatus.ACTIVE,
                          service_name="청소", total_amount=50000, billing_mode="per_visit",
                          partner_payment_amount=30000, partner_billing_mode="per_visit")
    db_session.add(c); db_session.flush()
    db_session.add(Order(
        id=str(uuid4()), group_id=g.id, status=OrderStatus.SCHEDULED,
        received_date=date(2026, 6, 1), scheduled_date=date(2026, 6, 1),
        service_name="청소", recurring_contract_id=c.id, recurring_planned_date=date(2026, 6, 1),
    ))
    db_session.commit()

    row = next(r for r in RecurringMonthlyService(db_session).list_month("2026-06") if r.contract_id == c.id)
    assert row.amount == 50000
    assert row.partner_amount == 30000


def test_month_amount_per_visit_future_projects_own_slots_without_moved_planned_month(db_session):
    # 월 1회(day10) per_visit 계약에서 과거 예정 회차를 미래 방문일로 옮겨도,
    # 자동 생성 회차는 원래 예정 월에 귀속해 미래 달과 중복 청구하지 않는다.
    from app.core.time import business_today

    today = business_today()
    fm = f"{today.year + 1:04d}-{today.month:02d}"  # 약 1년 뒤 → 확실히 미래 달
    g = OrderGroup(id=str(uuid4()), customer_token=f"t-{uuid4()}", customer_name="미래",
                   customer_phone="01012340000", customer_address="F", customer_visible_payment=False)
    db_session.add(g); db_session.flush()
    c = RecurringContract(id=str(uuid4()), label="F", order_group_id=g.id,
                          recurrence_mode=RecurrenceMode.MONTHLY, day_of_month=10,
                          start_date=date(2020, 1, 10), status=RecurringContractStatus.ACTIVE,
                          service_name="청소", total_amount=70000, billing_mode="per_visit")
    db_session.add(c); db_session.flush()
    # 다른(과거) 슬롯에서 이동해 온 회차 1건: 미래 달 5일 방문, planned_date는 과거로 스탬프.
    db_session.add(Order(
        id=str(uuid4()), group_id=g.id, status=OrderStatus.SCHEDULED,
        received_date=date(2020, 1, 1), scheduled_date=date(int(fm[:4]), int(fm[5:7]), 5),
        service_name="청소", recurring_contract_id=c.id, recurring_planned_date=date(2020, 1, 10),
    ))
    db_session.commit()
    original_row = next(r for r in RecurringMonthlyService(db_session).list_month("2020-01") if r.contract_id == c.id)
    assert original_row.amount == 70000

    row = next(r for r in RecurringMonthlyService(db_session).list_month(fm) if r.contract_id == c.id)
    assert row.amount == 70000


def test_monthly_api_rejects_invalid_month(client, seed_admin_token):
    # 잘못된 월은 GET 500이 아니라 422, POST는 영속화 없이 422 (검증 일원화).
    h = {"Authorization": f"Bearer {seed_admin_token}"}
    assert client.get("/api/admin/recurring/monthly?month=2026-13", headers=h).status_code == 422
    assert client.get("/api/admin/recurring/monthly?month=foo", headers=h).status_code == 422
    assert client.post("/api/admin/recurring/monthly/set",
                       json={"contract_id": "x", "month": "2026-13", "tax_invoice_issued": True},
                       headers=h).status_code == 422
