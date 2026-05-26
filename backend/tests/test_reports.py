from datetime import UTC, date, datetime
from decimal import Decimal

from app.domain.constants import OrderStatus
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
