from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.seed import DEV_PARTNER_ID
from app.domain.constants import OrderStatus, RecurrenceMode, RecurringContractStatus
from app.domain.payment_status import PartnerPaymentStatus
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.models.partner import Partner
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
from app.models.recurring_partner_billing_period import RecurringPartnerBillingPeriod
from app.services.partner_settlements import PartnerSettlementService
from app.services.partners import PartnerService
from app.services.reports import ReportService
from app.services.source_channels import SourceChannelReportService


def _add_monthly_partner_contract(
    db_session,
    *,
    label="정기 월정산",
    start_date=date(2026, 1, 10),
    partner_id=DEV_PARTNER_ID,
    partner_amount=Decimal("250000"),
):
    group = OrderGroup(
        id=str(uuid4()),
        customer_token=f"token-{uuid4()}",
        customer_name="정기 고객",
        customer_phone="01011112222",
        customer_address="서울",
        customer_visible_payment=False,
    )
    db_session.add(group)
    contract = RecurringContract(
        id=str(uuid4()),
        label=label,
        order_group_id=group.id,
        recurrence_mode=RecurrenceMode.MONTHLY,
        day_of_month=10,
        start_date=start_date,
        status=RecurringContractStatus.ACTIVE,
        default_partner_id=partner_id,
        service_name="사무실 정기청소",
        billing_mode="monthly",
        total_amount=Decimal("600000"),
        partner_billing_mode="monthly",
        partner_payment_amount=partner_amount,
    )
    db_session.add(contract)
    db_session.flush()
    return contract


def test_revenue_endpoint_requires_admin(client):
    res = client.get("/api/admin/reports/revenue")
    assert res.status_code in {401, 403}


def test_revenue_endpoint_returns_buckets(client, seed_admin_token):
    res = client.get(
        "/api/admin/reports/revenue",
        params={
            "granularity": "month",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["granularity"] == "month"
    assert body["start_date"] == "2026-01-01"
    assert isinstance(body["buckets"], list)
    bucket_sum = sum(float(b["revenue"]) for b in body["buckets"])
    assert abs(bucket_sum - float(body["total_revenue"])) < 0.01


def test_revenue_excludes_soft_deleted_orders(db_session, seed_order):
    seed_order.status = OrderStatus.COMPLETED
    seed_order.scheduled_date = date(2026, 5, 15)
    seed_order.total_amount = Decimal("123000")
    db_session.flush()

    before = ReportService(db_session).revenue(
        granularity="month",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    assert before.total_revenue == Decimal("123000")

    seed_order.deleted_at = datetime.now(UTC)
    db_session.flush()

    after = ReportService(db_session).revenue(
        granularity="month",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    assert after.total_revenue == Decimal("0")
    assert after.total_completed == 0


def test_revenue_includes_only_delivery_done_and_completed(db_session, seed_order):
    service = ReportService(db_session)
    report = service.revenue(
        granularity="month",
        start_date=date(2020, 1, 1),
        end_date=date(2030, 12, 31),
    )
    assert report.total_completed == 0
    assert report.total_revenue == Decimal("0")

    seed_order.status = OrderStatus.COMPLETED
    seed_order.scheduled_date = date(2026, 5, 15)
    seed_order.total_amount = Decimal("100000")
    db_session.flush()

    report2 = service.revenue(
        granularity="month",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    assert report2.total_completed == 1
    assert report2.total_revenue == Decimal("100000")


def test_revenue_excludes_cancelled(db_session, seed_order):
    seed_order.status = OrderStatus.CANCELLED
    seed_order.scheduled_date = date(2026, 5, 15)
    seed_order.total_amount = Decimal("999999")
    db_session.flush()

    report = ReportService(db_session).revenue(
        granularity="month",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    assert report.total_completed == 0
    assert report.total_revenue == Decimal("0")


def test_revenue_groups_by_month(db_session, seed_order, make_extra_line):
    seed_order.status = OrderStatus.COMPLETED
    seed_order.scheduled_date = date(2026, 3, 10)
    seed_order.total_amount = Decimal("50000")

    extra = make_extra_line(seed_order.group_id)
    extra.status = OrderStatus.COMPLETED
    extra.scheduled_date = date(2026, 5, 20)
    extra.total_amount = Decimal("70000")
    db_session.flush()

    report = ReportService(db_session).revenue(
        granularity="month",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    periods = {bucket.period.isoformat(): bucket.revenue for bucket in report.buckets}
    assert periods == {"2026-03-01": Decimal("50000"), "2026-05-01": Decimal("70000")}


def test_settlement_backlog_only_lists_completed_unsettled(db_session, seed_order):
    # 1-1: 백로그는 '도급가>0 + 미지급'(취소 아님) 기준. 완료 여부는 요건이 아니다.
    seed_order.status = OrderStatus.COMPLETED
    seed_order.partner_payment_status = PartnerPaymentStatus.UNPAID
    seed_order.partner_payment_amount = Decimal("100000")
    db_session.flush()

    rows = ReportService(db_session).settlements().rows
    assert any(row.order_id == seed_order.id for row in rows)

    seed_order.partner_payment_status = PartnerPaymentStatus.PAID
    db_session.flush()
    rows2 = ReportService(db_session).settlements().rows
    assert not any(row.order_id == seed_order.id for row in rows2)


def test_settlement_backlog_includes_unpaid_recurring_monthly_partner_amount(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr("app.services.reports.business_today", lambda: date(2026, 7, 6))
    contract = _add_monthly_partner_contract(db_session)

    rows = ReportService(db_session).settlements().rows
    row = next(item for item in rows if item.order_id.startswith(f"recurring-monthly:{contract.id}:"))
    assert row.source == "recurring_monthly"
    assert row.expected_settlement_amount == Decimal("250000")
    assert row.status == "월정산대기"

    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=contract.id,
            billing_month="2026-07",
            partner_payment_paid=True,
        )
    )
    db_session.flush()

    rows_after_paid = ReportService(db_session).settlements().rows
    assert not any(
        item.order_id == f"recurring-monthly:{contract.id}:2026-07"
        for item in rows_after_paid
    )
    assert any(
        item.order_id == f"recurring-monthly:{contract.id}:2026-06"
        for item in rows_after_paid
    )


def test_partner_admin_summary_includes_unpaid_recurring_monthly_amount(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr("app.services.partners.business_today", lambda: date(2026, 7, 20))
    service = PartnerService(db_session)
    before = service.get_detail(DEV_PARTNER_ID)
    _add_monthly_partner_contract(
        db_session,
        start_date=date(2026, 7, 1),
    )
    db_session.flush()

    detail = service.get_detail(DEV_PARTNER_ID)
    listed = next(
        partner
        for partner in service.list_partners(include_inactive=True)
        if partner.id == DEV_PARTNER_ID
    )

    assert detail.unpaid_partner_amount_total == (
        before.unpaid_partner_amount_total + 250000
    )
    assert detail.unpaid_partner_order_count == before.unpaid_partner_order_count + 1
    assert listed.unpaid_partner_amount_total == detail.unpaid_partner_amount_total
    assert listed.unpaid_partner_order_count == detail.unpaid_partner_order_count


def test_partner_summary_does_not_assign_retained_unassigned_debt_to_new_payee(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr("app.services.partners.business_today", lambda: date(2026, 7, 20))
    service = PartnerService(db_session)
    before = service.get_detail(DEV_PARTNER_ID)
    contract = _add_monthly_partner_contract(
        db_session,
        start_date=date(2026, 7, 1),
    )
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=contract.id,
            billing_month="2026-07",
            partner_payment_paid=False,
            retained_partner_id=None,
            retained_partner_payment_amount=Decimal("300000"),
        )
    )
    db_session.flush()

    detail = service.get_detail(DEV_PARTNER_ID)

    assert detail.unpaid_partner_amount_total == before.unpaid_partner_amount_total
    assert detail.unpaid_partner_order_count == before.unpaid_partner_order_count


def test_settlement_backlog_carries_unpaid_recurring_month_across_month_boundary(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr("app.services.reports.business_today", lambda: date(2026, 8, 1))
    contract = _add_monthly_partner_contract(db_session)
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=contract.id,
            billing_month="2026-07",
            partner_payment_paid=False,
        )
    )
    db_session.flush()

    rows = ReportService(db_session).settlements().rows

    assert any(item.order_id == f"recurring-monthly:{contract.id}:2026-07" for item in rows)


def test_settlement_backlog_preserves_past_month_after_partner_billing_mode_change(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr("app.services.reports.business_today", lambda: date(2026, 8, 11))
    contract = _add_monthly_partner_contract(db_session)
    db_session.add_all(
        [
            RecurringPartnerBillingPeriod(
                contract_id=contract.id,
                effective_month="0001-01",
                partner_id=contract.default_partner_id,
                billing_mode="monthly",
                partner_payment_amount=Decimal("250000"),
            ),
            RecurringPartnerBillingPeriod(
                contract_id=contract.id,
                effective_month="2026-08",
                partner_id=contract.default_partner_id,
                billing_mode="per_visit",
                partner_payment_amount=Decimal("70000"),
            ),
            RecurringMonthlyStatus(
                id=str(uuid4()),
                contract_id=contract.id,
                billing_month="2026-07",
                partner_payment_paid=False,
            ),
            RecurringMonthlyStatus(
                id=str(uuid4()),
                contract_id=contract.id,
                billing_month="2026-08",
                partner_payment_paid=False,
            ),
        ]
    )
    contract.partner_billing_mode = "per_visit"
    contract.partner_payment_amount = Decimal("70000")
    db_session.flush()

    rows = ReportService(db_session).settlements().rows

    july = next(
        item
        for item in rows
        if item.order_id == f"recurring-monthly:{contract.id}:2026-07"
    )
    assert july.expected_settlement_amount == Decimal("250000")
    assert not any(
        item.order_id == f"recurring-monthly:{contract.id}:2026-08"
        for item in rows
    )


def test_settlement_backlog_keeps_unpaid_recurring_month_after_contract_ended(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr("app.services.reports.business_today", lambda: date(2026, 8, 1))
    contract = _add_monthly_partner_contract(db_session)
    contract.status = RecurringContractStatus.ENDED
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=contract.id,
            billing_month="2026-07",
            partner_payment_paid=False,
        )
    )
    db_session.flush()

    rows = ReportService(db_session).settlements().rows

    assert any(item.order_id == f"recurring-monthly:{contract.id}:2026-07" for item in rows)


def test_monthly_recurring_order_is_not_exposed_as_per_order_settlement(db_session):
    contract = _add_monthly_partner_contract(db_session)
    db_session.add(
        RecurringPartnerBillingPeriod(
            contract_id=contract.id,
            effective_month="0001-01",
            partner_id=contract.default_partner_id,
            billing_mode="monthly",
            partner_payment_amount=Decimal("250000"),
        )
    )
    order = Order(
        id=str(uuid4()),
        group_id=contract.order_group_id,
        status=OrderStatus.COMPLETED,
        received_date=date(2026, 8, 1),
        scheduled_date=date(2026, 8, 15),
        partner_id=contract.default_partner_id,
        service_name="레거시 월정산 주문",
        partner_payment_amount=Decimal("70000"),
        partner_payment_status=PartnerPaymentStatus.UNPAID,
        recurring_contract_id=contract.id,
        recurring_planned_date=None,
    )
    db_session.add(order)
    db_session.flush()

    backlog = ReportService(db_session).settlements().rows
    settlements = PartnerSettlementService(db_session).list_settlements(
        partner_id=contract.default_partner_id,
        status="unpaid",
    )

    assert all(row.order_id != order.id for row in backlog)
    assert all(item.order_id != order.id for item in settlements.items)
    with pytest.raises(ValueError, match="invalid_settlement_order"):
        PartnerSettlementService(db_session).settle(
            partner_id=contract.default_partner_id,
            order_ids=[order.id],
            actor_user_id=None,
        )


def test_historical_monthly_settlement_keeps_original_partner_after_reassignment(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr("app.services.reports.business_today", lambda: date(2026, 8, 11))
    original = Partner(id="historical-partner-a", name="7월 협력사", phone="01010001000")
    replacement = Partner(id="historical-partner-b", name="8월 협력사", phone="01020002000")
    db_session.add_all([original, replacement])
    db_session.flush()
    contract = _add_monthly_partner_contract(db_session, partner_id=original.id)
    db_session.add_all(
        [
            RecurringPartnerBillingPeriod(
                contract_id=contract.id,
                effective_month="0001-01",
                partner_id=original.id,
                billing_mode="monthly",
                partner_payment_amount=Decimal("250000"),
            ),
            RecurringPartnerBillingPeriod(
                contract_id=contract.id,
                effective_month="2026-08",
                partner_id=replacement.id,
                billing_mode="monthly",
                partner_payment_amount=Decimal("250000"),
            ),
            RecurringMonthlyStatus(
                id=str(uuid4()),
                contract_id=contract.id,
                billing_month="2026-07",
                partner_payment_paid=False,
            ),
        ]
    )
    contract.default_partner_id = replacement.id
    db_session.flush()

    july = next(
        row
        for row in ReportService(db_session).settlements().rows
        if row.order_id == f"recurring-monthly:{contract.id}:2026-07"
    )

    assert july.partner_id == original.id
    assert july.partner_name == original.name
    with pytest.raises(ValueError, match="partner_has_unpaid_settlements"):
        PartnerService(db_session).delete(original.id)


def test_settlement_backlog_keeps_deleted_contract_historical_status(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr("app.services.reports.business_today", lambda: date(2026, 8, 11))
    contract = _add_monthly_partner_contract(db_session)
    contract.deleted_at = datetime.now(UTC)
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=contract.id,
            billing_month="2026-07",
            partner_payment_paid=False,
        )
    )
    db_session.flush()

    rows = ReportService(db_session).settlements().rows

    assert any(
        row.order_id == f"recurring-monthly:{contract.id}:2026-07"
        for row in rows
    )


def test_settlement_backlog_excludes_recurring_month_before_contract_start(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr("app.services.reports.business_today", lambda: date(2026, 7, 6))
    contract = _add_monthly_partner_contract(db_session, start_date=date(2026, 8, 10))

    rows = ReportService(db_session).settlements().rows

    assert not any(item.order_id.startswith(f"recurring-monthly:{contract.id}:") for item in rows)


def test_partner_performance_includes_recurring_monthly_pending_settlement(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr("app.services.reports.business_today", lambda: date(2026, 7, 6))
    contract = _add_monthly_partner_contract(db_session)

    report = ReportService(db_session).partners(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
    )

    row = next(item for item in report.rows if item.partner_id == contract.default_partner_id)
    assert row.pending_settlement_count == 1
    assert row.expected_settlement_amount == Decimal("250000")


def test_partner_performance_excludes_cancelled(db_session, seed_order_assigned_to_partner):
    order = seed_order_assigned_to_partner
    order.status = OrderStatus.CANCELLED
    order.scheduled_date = date(2030, 5, 15)
    db_session.flush()

    report = ReportService(db_session).partners(
        start_date=date(2030, 1, 1),
        end_date=date(2030, 12, 31),
    )
    rows_for_partner = [row for row in report.rows if row.partner_id == order.partner_id]
    if rows_for_partner:
        assert rows_for_partner[0].job_count == 0


def test_partner_performance_pending_settlement_uses_backlog_policy(
    db_session,
    seed_order_assigned_to_partner,
    make_extra_line,
):
    completed_order = seed_order_assigned_to_partner
    completed_order.status = OrderStatus.COMPLETED
    completed_order.scheduled_date = date(2031, 5, 15)
    completed_order.total_amount = Decimal("120000")
    completed_order.partner_payment_status = PartnerPaymentStatus.UNPAID
    completed_order.partner_payment_amount = Decimal("120000")

    not_completed_order = make_extra_line(completed_order.group_id)
    not_completed_order.partner_id = completed_order.partner_id
    not_completed_order.status = OrderStatus.NEW
    not_completed_order.scheduled_date = date(2031, 5, 16)
    not_completed_order.total_amount = Decimal("990000")
    not_completed_order.partner_payment_status = None
    not_completed_order.partner_payment_amount = Decimal("990000")

    paid_order = make_extra_line(completed_order.group_id)
    paid_order.partner_id = completed_order.partner_id
    paid_order.status = OrderStatus.COMPLETED
    paid_order.scheduled_date = date(2031, 5, 17)
    paid_order.total_amount = Decimal("240000")
    paid_order.partner_payment_status = PartnerPaymentStatus.PAID
    paid_order.partner_payment_amount = Decimal("240000")
    db_session.flush()

    report = ReportService(db_session).partners(
        start_date=date(2031, 1, 1),
        end_date=date(2031, 12, 31),
    )
    row = next(item for item in report.rows if item.partner_id == completed_order.partner_id)
    assert row.job_count == 3
    assert row.avg_unit_price == Decimal("180000")
    assert row.pending_settlement_count == 2
    assert row.expected_settlement_amount == Decimal("1110000")


def test_services_includes_null_service_item_id_fallback(db_session, seed_order):
    seed_order.status = OrderStatus.COMPLETED
    seed_order.scheduled_date = date(2026, 5, 15)
    seed_order.total_amount = Decimal("55000")
    seed_order.service_item_id = None
    seed_order.service_name = "window cleaning"
    db_session.flush()

    report = ReportService(db_session).services(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    matched = [row for row in report.rows if row.service_name == "window cleaning"]
    assert len(matched) == 1
    assert matched[0].service_item_id is None
    assert matched[0].revenue == Decimal("55000")


def test_services_empty_data(db_session):
    report = ReportService(db_session).services(
        start_date=date(2020, 1, 1),
        end_date=date(2020, 12, 31),
    )
    assert report.rows == []


def test_source_channels_counts_orders_and_revenue_by_group_source(
    db_session,
    seed_order,
    make_extra_line,
):
    group = db_session.get(OrderGroup, seed_order.group_id)
    assert group is not None
    group.source_channel = "네이버"
    seed_order.source_channel = "전화"
    seed_order.status = OrderStatus.COMPLETED
    seed_order.scheduled_date = date(2026, 6, 10)
    seed_order.total_amount = Decimal("100000")

    extra = make_extra_line(seed_order.group_id)
    extra.status = OrderStatus.NEW
    extra.scheduled_date = date(2026, 6, 11)
    extra.total_amount = Decimal("700000")
    db_session.flush()

    report = SourceChannelReportService(db_session).source_channels(
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )

    assert report.total_orders == 2
    assert report.total_completed == 1
    assert report.total_revenue == Decimal("100000")
    row = next(item for item in report.rows if item.source_channel == "네이버톡톡")
    assert row.order_count == 2
    assert row.completed_count == 1
    assert row.revenue == Decimal("100000")


def test_source_channel_endpoint_returns_rows(client, seed_admin_token):
    res = client.get(
        "/api/admin/reports/source-channels",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["start_date"] == "2026-01-01"
    assert isinstance(body["rows"], list)


def test_revenue_filters_by_partner_id(db_session, seed_order_assigned_to_partner):
    order = seed_order_assigned_to_partner
    order.status = OrderStatus.COMPLETED
    order.scheduled_date = date(2026, 5, 15)
    order.total_amount = Decimal("80000")
    db_session.flush()

    report_match = ReportService(db_session).revenue(
        granularity="month",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        partner_id=order.partner_id,
    )
    assert report_match.total_revenue == Decimal("80000")

    report_other = ReportService(db_session).revenue(
        granularity="month",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        partner_id="non-existent",
    )
    assert report_other.total_revenue == Decimal("0")
