from datetime import UTC, date, datetime
from decimal import Decimal

from app.domain.constants import OrderStatus
from app.domain.payment_status import PartnerPaymentStatus
from app.services.reports import ReportService


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
    seed_order.status = OrderStatus.COMPLETED
    seed_order.partner_payment_status = PartnerPaymentStatus.UNPAID
    db_session.flush()

    rows = ReportService(db_session).settlements().rows
    assert any(row.order_id == seed_order.id for row in rows)

    seed_order.partner_payment_status = PartnerPaymentStatus.PAID
    db_session.flush()
    rows2 = ReportService(db_session).settlements().rows
    assert not any(row.order_id == seed_order.id for row in rows2)


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
