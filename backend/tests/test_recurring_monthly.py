from datetime import date
from uuid import uuid4

from app.domain.constants import RecurrenceMode, RecurringContractStatus
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
    row = svc.set_status(c.id, "2026-06", tax_invoice_issued=True, actor_user_id="admin")
    assert row.tax_invoice_issued is True and row.balance_paid is False
    row2 = svc.set_status(c.id, "2026-06", balance_paid=True, actor_user_id="admin")
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
