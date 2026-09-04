from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.core.time import business_today
from app.db.seed import DEV_PARTNER_ID
from app.domain.constants import OrderStatus, RecurrenceMode, RecurringContractStatus
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
from app.models.recurring_partner_billing_period import RecurringPartnerBillingPeriod
from app.repositories.recurring import RecurringMonthlyStatusRepository
from app.services.recurring import RecurringService
from app.services.recurring_generation import RecurringOrderGenerationService
from app.services.recurring_monthly import RecurringMonthlyService
from app.services.recurring_partner_billing import billing_month, incurred_billing_months
from app.services.reports import ReportService


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


def test_list_month_keeps_existing_unpaid_row_after_contract_is_paused(db_session):
    c = _contract(db_session)
    c.partner_payment_amount = 90000
    c.partner_billing_mode = "monthly"
    db_session.commit()
    service = RecurringMonthlyService(db_session)
    initial = next(row for row in service.list_month("2026-06") if row.contract_id == c.id)
    assert initial.partner_payment_paid is False
    assert RecurringMonthlyStatusRepository(db_session).get_by_contract_and_month(
        c.id,
        "2026-06",
    ) is None

    RecurringService(db_session).set_status(c.id, RecurringContractStatus.PAUSED)

    paused = next(row for row in service.list_month("2026-06") if row.contract_id == c.id)
    assert paused.partner_amount == 90000
    assert paused.partner_payment_paid is False
    assert RecurringMonthlyStatusRepository(db_session).get_by_contract_and_month(
        c.id,
        "2026-06",
    ) is not None


def test_list_month_does_not_create_future_rows_for_paused_contract(db_session):
    c = _contract(db_session)
    c.status = RecurringContractStatus.PAUSED
    db_session.commit()

    rows = RecurringMonthlyService(db_session).list_month("2026-07")

    assert all(row.contract_id != c.id for row in rows)
    assert RecurringMonthlyStatusRepository(db_session).get_by_contract_and_month(
        c.id,
        "2026-07",
    ) is None

    with pytest.raises(ValueError, match="recurring_month_not_editable"):
        RecurringMonthlyService(db_session).set_status(
            c.id,
            "2026-07",
            partner_payment_paid=True,
        )


def test_resume_does_not_make_paused_gap_billable(db_session, monkeypatch):
    contract = _contract(db_session)
    contract.start_date = date(2026, 1, 1)
    contract.active_segment_start_date = date(2026, 1, 1)
    contract.partner_payment_amount = 90000
    contract.partner_billing_mode = "monthly"
    contract.end_date = date(2026, 9, 30)
    db_session.commit()

    monkeypatch.setattr("app.services.recurring.business_today", lambda: date(2026, 1, 15))
    RecurringService(db_session).set_status(contract.id, RecurringContractStatus.PAUSED)
    monkeypatch.setattr("app.services.recurring.business_today", lambda: date(2026, 5, 2))
    resumed = RecurringService(db_session).set_status(
        contract.id,
        RecurringContractStatus.ACTIVE,
    )

    service = RecurringMonthlyService(db_session)
    assert resumed.active_segment_start_date == date(2026, 5, 2)
    assert resumed.end_date == date(2026, 9, 30)
    assert all(row.contract_id != contract.id for row in service.list_month("2026-02"))
    assert any(row.contract_id == contract.id for row in service.list_month("2026-05"))
    assert incurred_billing_months(
        resumed,
        through_date=date(2026, 6, 30),
    ) == ("2026-05", "2026-06")
    assert RecurringMonthlyStatusRepository(db_session).get_by_contract_and_month(
        contract.id,
        "2026-01",
    ) is not None


def test_deleted_active_contract_does_not_create_future_partner_debt(
    db_session,
    monkeypatch,
):
    today = business_today()
    contract = _contract(db_session)
    contract.start_date = today.replace(day=1)
    contract.active_segment_start_date = contract.start_date
    contract.partner_payment_amount = 90000
    contract.partner_billing_mode = "monthly"
    RecurringService(db_session).partner_billing.ensure_baseline(contract)
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=contract.id,
            billing_month=billing_month(today),
            partner_payment_paid=True,
        )
    )
    db_session.commit()

    RecurringService(db_session).delete_contract(contract.id, actor_user_id=None)
    db_session.refresh(contract)
    future = date(today.year + (today.month == 12), today.month % 12 + 1, 15)
    monkeypatch.setattr("app.services.reports.business_today", lambda: future)
    backlog = ReportService(db_session).settlements()

    assert contract.status == RecurringContractStatus.ENDED
    assert contract.end_date == today
    assert contract.active_segment_start_date == today.replace(day=1)
    assert incurred_billing_months(contract, through_date=future) == ()
    assert all(
        row.order_id != f"recurring-monthly:{contract.id}:{billing_month(future)}"
        for row in backlog.rows
    )


def test_generation_and_projection_start_after_same_month_resume(db_session):
    contract = _contract(db_session)
    contract.recurrence_mode = "weekly"
    contract.day_of_month = None
    contract.interval_weeks = 1
    contract.weekday = 4
    contract.start_date = date(2026, 5, 1)
    contract.active_segment_start_date = date(2026, 5, 2)
    contract.total_amount = 100000
    db_session.commit()

    created = RecurringOrderGenerationService(db_session).generate_month(
        date(2026, 5, 1),
        date(2026, 5, 31),
        actor_user_id=None,
    )
    orders = list(
        db_session.query(Order)
        .filter(Order.recurring_contract_id == contract.id)
        .order_by(Order.recurring_planned_date)
    )

    assert created == 4
    assert [order.recurring_planned_date for order in orders] == [
        date(2026, 5, 8),
        date(2026, 5, 15),
        date(2026, 5, 22),
        date(2026, 5, 29),
    ]
    row = next(
        item
        for item in RecurringMonthlyService(db_session).list_month("2026-05")
        if item.contract_id == contract.id
    )
    assert row.amount == 400000


def test_list_month_keeps_actual_order_from_before_current_active_segment(db_session):
    contract = _weekly_contract(db_session, billing_mode="per_visit", amount=50000)
    contract.start_date = date(2026, 1, 1)
    contract.active_segment_start_date = date(2026, 5, 1)
    db_session.add(
        Order(
            id=str(uuid4()),
            group_id=contract.order_group_id,
            status=OrderStatus.SCHEDULED,
            received_date=date(2026, 4, 1),
            scheduled_date=date(2026, 4, 6),
            service_name="청소",
            recurring_contract_id=contract.id,
            recurring_planned_date=date(2026, 4, 6),
        )
    )
    db_session.commit()

    row = next(
        item
        for item in RecurringMonthlyService(db_session).list_month("2026-04")
        if item.contract_id == contract.id
    )

    assert row.amount == 50000


def test_paused_contract_does_not_project_month_before_current_active_segment(db_session):
    contract = _weekly_contract(db_session, billing_mode="per_visit", amount=50000)
    contract.start_date = date(2026, 1, 1)
    contract.active_segment_start_date = date(2026, 5, 1)
    contract.status = RecurringContractStatus.PAUSED
    db_session.commit()

    rows = RecurringMonthlyService(db_session).list_month("2026-04")

    assert all(item.contract_id != contract.id for item in rows)


def test_resume_rejects_contract_with_expired_end_date(db_session, monkeypatch):
    contract = _contract(db_session)
    contract.status = RecurringContractStatus.PAUSED
    contract.end_date = date(2026, 6, 30)
    db_session.commit()
    monkeypatch.setattr("app.services.recurring.business_today", lambda: date(2026, 7, 1))

    with pytest.raises(ValueError, match="recurring_contract_end_date_passed"):
        RecurringService(db_session).set_status(
            contract.id,
            RecurringContractStatus.ACTIVE,
        )

    db_session.refresh(contract)
    assert contract.status == RecurringContractStatus.PAUSED


def test_monthly_partner_payment_requires_payee(db_session):
    contract = _contract(db_session)
    contract.default_partner_id = None
    contract.partner_billing_mode = "monthly"
    contract.partner_payment_amount = 90000
    db_session.commit()

    with pytest.raises(ValueError, match="recurring_partner_required"):
        RecurringMonthlyService(db_session).set_status(
            contract.id,
            "2026-06",
            partner_payment_paid=True,
        )


def test_retained_monthly_payment_does_not_fall_forward_to_new_payee(db_session):
    contract = _contract(db_session)
    contract.default_partner_id = DEV_PARTNER_ID
    contract.partner_billing_mode = "per_visit"
    contract.partner_payment_amount = 70000
    db_session.add(
        RecurringPartnerBillingPeriod(
            contract_id=contract.id,
            effective_month="0001-01",
            partner_id=DEV_PARTNER_ID,
            billing_mode="per_visit",
            partner_payment_amount=70000,
        )
    )
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=contract.id,
            billing_month="2026-06",
            partner_payment_paid=False,
            retained_partner_id=None,
            retained_partner_payment_amount=90000,
        )
    )
    db_session.commit()

    with pytest.raises(ValueError, match="recurring_partner_required"):
        RecurringMonthlyService(db_session).set_status(
            contract.id,
            "2026-06",
            partner_payment_paid=True,
        )


def test_list_month_projects_future_active_contract_without_persisting_status(db_session):
    c = _contract(db_session)
    future = "2099-07"
    db_session.commit()

    rows = RecurringMonthlyService(db_session).list_month(future)

    assert any(row.contract_id == c.id for row in rows)
    assert RecurringMonthlyStatusRepository(db_session).get_by_contract_and_month(
        c.id,
        future,
    ) is None
    with pytest.raises(ValueError, match="recurring_month_not_editable"):
        RecurringMonthlyService(db_session).set_status(
            c.id,
            future,
            partner_payment_paid=True,
        )


def test_list_month_keeps_existing_unpaid_row_after_contract_has_ended(db_session):
    c = _contract(db_session)
    c.partner_payment_amount = 90000
    c.partner_billing_mode = "monthly"
    c.status = RecurringContractStatus.ENDED
    c.end_date = date(2026, 5, 31)
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=c.id,
            billing_month="2026-06",
            partner_payment_paid=False,
        )
    )
    db_session.commit()

    row = next(
        item
        for item in RecurringMonthlyService(db_session).list_month("2026-06")
        if item.contract_id == c.id
    )

    assert row.partner_amount == 90000
    assert row.partner_payment_paid is False


def test_list_month_hides_empty_status_after_contract_ended(db_session):
    c = _contract(db_session)
    c.recurrence_mode = RecurrenceMode.MONTHLY
    c.billing_mode = "per_visit"
    c.status = RecurringContractStatus.ENDED
    c.end_date = date(2026, 9, 3)
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=c.id,
            billing_month="2026-09",
            tax_invoice_issued=False,
            balance_paid=False,
            partner_payment_paid=False,
            retained_partner_id=None,
            retained_partner_payment_amount=None,
        )
    )
    db_session.commit()

    rows = RecurringMonthlyService(db_session).list_month("2026-09")

    assert all(row.contract_id != c.id for row in rows)


@pytest.mark.parametrize(
    "status_values",
    [
        {"tax_invoice_issued": True},
        {
            "retained_partner_id": DEV_PARTNER_ID,
            "retained_partner_payment_amount": 90000,
        },
    ],
)
def test_list_month_keeps_meaningful_status_after_contract_ended(
    db_session,
    status_values,
):
    c = _contract(db_session)
    c.status = RecurringContractStatus.ENDED
    c.end_date = date(2026, 8, 31)
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=c.id,
            billing_month="2026-09",
            **status_values,
        )
    )
    db_session.commit()

    rows = RecurringMonthlyService(db_session).list_month("2026-09")

    assert any(row.contract_id == c.id for row in rows)


def test_list_month_keeps_active_contract_empty_status(db_session):
    c = _contract(db_session)
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=c.id,
            billing_month="2026-09",
        )
    )
    db_session.commit()

    rows = RecurringMonthlyService(db_session).list_month("2026-09")

    assert any(row.contract_id == c.id for row in rows)


def test_list_month_preserves_ended_history_but_hides_empty_end_month(db_session):
    c = _contract(db_session)
    c.default_partner_id = DEV_PARTNER_ID
    c.status = RecurringContractStatus.ENDED
    c.end_date = date(2026, 9, 3)
    db_session.add_all(
        [
            RecurringMonthlyStatus(
                id=str(uuid4()),
                contract_id=c.id,
                billing_month="2026-06",
                tax_invoice_issued=True,
            ),
            RecurringMonthlyStatus(
                id=str(uuid4()),
                contract_id=c.id,
                billing_month="2026-07",
                balance_paid=True,
            ),
            RecurringMonthlyStatus(
                id=str(uuid4()),
                contract_id=c.id,
                billing_month="2026-08",
                retained_partner_id=DEV_PARTNER_ID,
                retained_partner_payment_amount=90000,
            ),
            RecurringMonthlyStatus(
                id=str(uuid4()),
                contract_id=c.id,
                billing_month="2026-09",
            ),
        ]
    )
    db_session.commit()
    service = RecurringMonthlyService(db_session)

    visible_months = {
        month
        for month in ("2026-06", "2026-07", "2026-08", "2026-09")
        if any(row.contract_id == c.id for row in service.list_month(month))
    }

    assert visible_months == {"2026-06", "2026-07", "2026-08"}


def test_deleted_contract_existing_status_remains_visible_and_editable(db_session):
    c = _contract(db_session)
    c.default_partner_id = DEV_PARTNER_ID
    c.partner_payment_amount = 90000
    c.partner_billing_mode = "monthly"
    c.deleted_at = datetime.now(UTC)
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=c.id,
            billing_month="2026-06",
            partner_payment_paid=False,
        )
    )
    db_session.commit()
    service = RecurringMonthlyService(db_session)

    row = next(item for item in service.list_month("2026-06") if item.contract_id == c.id)
    updated = service.set_status(c.id, "2026-06", partner_payment_paid=True)

    assert row.partner_amount == 90000
    assert updated.partner_payment_paid is True


def test_set_status_toggles(db_session):
    c = _contract(db_session)
    db_session.commit()
    svc = RecurringMonthlyService(db_session)
    row = svc.set_status(c.id, "2026-06", tax_invoice_issued=True)
    assert row.tax_invoice_issued is True and row.balance_paid is False
    row2 = svc.set_status(c.id, "2026-06", balance_paid=True)
    assert row2.tax_invoice_issued is True and row2.balance_paid is True


def test_set_status_rejects_partner_payment_for_per_visit_terms(db_session):
    contract = _contract(db_session)
    contract.partner_billing_mode = "per_visit"
    contract.partner_payment_amount = 90000
    db_session.commit()

    with pytest.raises(ValueError, match="recurring_partner_payment_not_monthly"):
        RecurringMonthlyService(db_session).set_status(
            contract.id,
            "2026-06",
            partner_payment_paid=True,
        )


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


def test_legacy_cancelled_generated_visit_does_not_reappear_as_projection(db_session):
    c = _weekly_contract(db_session, billing_mode="per_visit", amount=50000)
    c.partner_payment_amount = 30000
    c.partner_billing_mode = "per_visit"
    db_session.add(Order(
        id=str(uuid4()), group_id=c.order_group_id, status=OrderStatus.CANCELLED,
        received_date=date(2026, 6, 1), scheduled_date=date(2026, 6, 1),
        service_name="청소", recurring_contract_id=c.id, recurring_planned_date=None,
    ))
    db_session.commit()

    row = next(
        item
        for item in RecurringMonthlyService(db_session).list_month("2026-06")
        if item.contract_id == c.id
    )
    assert row.amount == 0
    assert row.partner_amount == 0


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
