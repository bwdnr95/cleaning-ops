from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.time import business_today
from app.domain.constants import MessageChannel, MessageType, RecipientType
from app.models.message import MessageLog
from app.models.order import Order
from app.models.order_visit import OrderVisit
from app.repositories.orders import order_visit_sort_key
from app.schemas.message import MessageSendRequest
from app.services.messages import MessageService


def _admin_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_multi_visit_order(
    client: TestClient,
    admin_token: str,
) -> tuple[dict, dict]:
    response = client.post(
        "/api/admin/orders/groups",
        headers=_admin_headers(admin_token),
        json={
            "customer_name": "여러날 고객",
            "customer_phone": "010-5555-9876",
            "customer_address": "서울시 중구 다중방문로 2",
            "lines": [
                {
                    "status": "일정확정",
                    "received_date": "2026-08-16",
                    "visit_dates": ["2026-09-07", "2026-09-02", "2026-09-03"],
                    "requested_time": "09:30",
                    "service_name": "3일 입주청소",
                    "partner_id": "seed-partner-01",
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    group = response.json()
    return group, group["lines"][0]


def test_create_and_read_multi_visit_order(
    client: TestClient,
    seed_admin_token: str,
    seed_partner_token: str,
) -> None:
    group, line = _create_multi_visit_order(client, seed_admin_token)

    assert line["scheduled_date"] == "2026-09-02"
    assert line["visit_dates"] == ["2026-09-02", "2026-09-03", "2026-09-07"]

    partner_response = client.get(
        f"/api/partner/jobs/{line['id']}",
        headers=_admin_headers(seed_partner_token),
    )
    assert partner_response.status_code == 200, partner_response.text
    assert partner_response.json()["visit_dates"] == line["visit_dates"]

    customer_response = client.post(
        "/api/customer/orders/verify",
        headers={"X-Customer-Token": group["customer_token"]},
        json={"phone_suffix": "9876"},
    )
    assert customer_response.status_code == 200, customer_response.text
    assert customer_response.json()["lines"][0]["visit_dates"] == line["visit_dates"]


def test_update_visit_dates_records_timeline_and_calendar_occurrences(
    client: TestClient,
    seed_admin_token: str,
) -> None:
    _, line = _create_multi_visit_order(client, seed_admin_token)
    replacement = ["2026-09-12", "2026-09-05", "2026-09-09"]

    update_response = client.patch(
        f"/api/admin/orders/{line['id']}",
        headers=_admin_headers(seed_admin_token),
        json={"visit_dates": replacement},
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["scheduled_date"] == "2026-09-05"
    assert updated["visit_dates"] == sorted(replacement)

    detail_response = client.get(
        f"/api/admin/orders/{line['id']}",
        headers=_admin_headers(seed_admin_token),
    )
    assert detail_response.status_code == 200, detail_response.text
    schedule_events = [
        event
        for event in detail_response.json()["timeline"]
        if event["event_type"] == "memo_added" and event["title"] == "방문 일정 변경"
    ]
    assert schedule_events
    assert schedule_events[-1]["event_metadata"]["changes"]["visit_dates"] == {
        "from": ["2026-09-02", "2026-09-03", "2026-09-07"],
        "to": sorted(replacement),
    }

    calendar_response = client.get(
        "/api/admin/calendar?year=2026&month=9",
        headers=_admin_headers(seed_admin_token),
    )
    assert calendar_response.status_code == 200, calendar_response.text
    occurrences = [
        row for row in calendar_response.json() if row["id"] == line["id"]
    ]
    assert [row["scheduled_date"] for row in occurrences] == sorted(replacement)
    assert len({row["visit_id"] for row in occurrences}) == 3


def test_legacy_scheduled_date_input_remains_supported(
    client: TestClient,
    seed_admin_token: str,
) -> None:
    response = client.post(
        "/api/admin/orders/groups",
        headers=_admin_headers(seed_admin_token),
        json={
            "customer_name": "기존 연동 고객",
            "customer_phone": "010-1111-2222",
            "customer_address": "서울시 강서구",
            "lines": [
                {
                    "received_date": "2026-08-16",
                    "scheduled_date": "2026-09-20",
                    "service_name": "기존 단일 방문 주문",
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    line = response.json()["lines"][0]
    assert line["scheduled_date"] == "2026-09-20"
    assert line["visit_dates"] == ["2026-09-20"]


def test_dashboard_counts_secondary_visit_date(
    client: TestClient,
    seed_admin_token: str,
) -> None:
    headers = _admin_headers(seed_admin_token)
    before = client.get("/api/admin/dashboard/summary", headers=headers)
    assert before.status_code == 200, before.text
    tomorrow = business_today() + timedelta(days=1)
    yesterday = business_today() - timedelta(days=1)

    create_response = client.post(
        "/api/admin/orders/groups",
        headers=headers,
        json={
            "customer_name": "대시보드 다중방문",
            "customer_phone": "010-3333-4444",
            "customer_address": "서울시 종로구",
            "lines": [
                {
                    "status": "일정확정",
                    "received_date": business_today().isoformat(),
                    "visit_dates": [yesterday.isoformat(), tomorrow.isoformat()],
                    "service_name": "이틀 작업",
                }
            ],
        },
    )
    assert create_response.status_code == 201, create_response.text

    after = client.get("/api/admin/dashboard/summary", headers=headers)
    assert after.status_code == 200, after.text
    assert (
        after.json()["tomorrow_notice_targets"]
        == before.json()["tomorrow_notice_targets"] + 1
    )


def test_legacy_scheduled_date_patch_rejects_multi_visit_collapse(
    client: TestClient,
    seed_admin_token: str,
) -> None:
    _, line = _create_multi_visit_order(client, seed_admin_token)

    response = client.patch(
        f"/api/admin/orders/{line['id']}",
        headers=_admin_headers(seed_admin_token),
        json={"scheduled_date": "2026-09-05"},
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "visit_dates_required_for_multi_visit_order"
    detail = client.get(
        f"/api/admin/orders/{line['id']}",
        headers=_admin_headers(seed_admin_token),
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["visit_dates"] == ["2026-09-02", "2026-09-03", "2026-09-07"]


def test_visit_sort_directions_reverse_the_same_next_visit_axis() -> None:
    today = date(2026, 8, 17)
    first = Order(id="first", scheduled_date=date(2026, 8, 18))
    first.visits = [
        OrderVisit(id="first-1", order_id=first.id, visit_date=date(2026, 8, 18)),
        OrderVisit(id="first-2", order_id=first.id, visit_date=date(2026, 12, 31)),
    ]
    second = Order(id="second", scheduled_date=date(2026, 8, 19))
    second.visits = [
        OrderVisit(id="second-1", order_id=second.id, visit_date=date(2026, 8, 19)),
    ]

    ascending = sorted(
        [first, second],
        key=lambda order: order_visit_sort_key(order, today, reverse_visit=False),
    )
    descending = sorted(
        [first, second],
        key=lambda order: order_visit_sort_key(order, today, reverse_visit=True),
    )

    assert [order.id for order in ascending] == ["first", "second"]
    assert [order.id for order in descending] == ["second", "first"]


def test_monthly_dashboard_and_drilldowns_use_matching_visit_date_basis(
    client: TestClient,
    seed_admin_token: str,
) -> None:
    headers = _admin_headers(seed_admin_token)
    today = business_today()
    month_start = today.replace(day=1)
    previous_month_date = month_start - timedelta(days=1)
    next_month_date = (
        date(today.year + 1, 1, 1)
        if today.month == 12
        else date(today.year, today.month + 1, 1)
    )
    before = client.get("/api/admin/dashboard/summary", headers=headers)
    assert before.status_code == 200, before.text

    previous_to_current = client.post(
        "/api/admin/orders/groups",
        headers=headers,
        json={
            "customer_name": "월경계 완료기준",
            "customer_phone": "010-1000-1000",
            "customer_address": "서울시 월경계로 1",
            "lines": [
                {
                    "status": "서비스완료",
                    "received_date": today.isoformat(),
                    "visit_dates": [previous_month_date.isoformat(), month_start.isoformat()],
                    "service_name": "월경계 완료 테스트",
                    "total_amount": 123456,
                }
            ],
        },
    )
    assert previous_to_current.status_code == 201, previous_to_current.text

    current_to_next = client.post(
        "/api/admin/orders/groups",
        headers=headers,
        json={
            "customer_name": "월경계 금액기준",
            "customer_phone": "010-2000-2000",
            "customer_address": "서울시 월경계로 2",
            "lines": [
                {
                    "status": "서비스완료",
                    "received_date": today.isoformat(),
                    "visit_dates": [month_start.isoformat(), next_month_date.isoformat()],
                    "service_name": "월경계 금액 테스트",
                    "total_amount": 654321,
                }
            ],
        },
    )
    assert current_to_next.status_code == 201, current_to_next.text

    after = client.get("/api/admin/dashboard/summary", headers=headers)
    assert after.status_code == 200, after.text
    assert after.json()["monthly_completed"] == before.json()["monthly_completed"] + 1
    assert after.json()["monthly_contract_amount"] == pytest.approx(
        before.json()["monthly_contract_amount"] + 654321
    )
    assert after.json()["monthly_revenue"] == pytest.approx(
        before.json()["monthly_revenue"] + 654321
    )

    completed_page = client.get(
        "/api/admin/orders/page",
        headers=headers,
        params={
            "status": "monthly_done",
            "visit_preset": "month",
            "scope": "regular",
            "q": "월경계 완료기준",
        },
    )
    contract_page = client.get(
        "/api/admin/orders/page",
        headers=headers,
        params={
            "status": "monthly_contract",
            "visit_preset": "month",
            "scope": "regular",
            "q": "월경계 금액기준",
        },
    )
    assert completed_page.status_code == 200, completed_page.text
    assert completed_page.json()["total"] == 1
    assert contract_page.status_code == 200, contract_page.text
    assert contract_page.json()["total"] == 1

    mismatched_completion = client.get(
        "/api/admin/orders/page",
        headers=headers,
        params={
            "status": "monthly_done",
            "visit_preset": "month",
            "scope": "regular",
            "q": "월경계 금액기준",
        },
    )
    mismatched_contract = client.get(
        "/api/admin/orders/page",
        headers=headers,
        params={
            "status": "monthly_contract",
            "visit_preset": "month",
            "scope": "regular",
            "q": "월경계 완료기준",
        },
    )
    assert mismatched_completion.status_code == 200, mismatched_completion.text
    assert mismatched_completion.json()["total"] == 0
    assert mismatched_contract.status_code == 200, mismatched_contract.text
    assert mismatched_contract.json()["total"] == 0


def test_calendar_batches_order_group_lookup(
    client: TestClient,
    seed_admin_token: str,
) -> None:
    _create_multi_visit_order(client, seed_admin_token)
    _create_multi_visit_order(client, seed_admin_token)
    group_selects: list[str] = []

    def capture_group_selects(
        _connection,
        _cursor,
        statement: str,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        if "FROM order_groups" in statement:
            group_selects.append(statement)

    event.listen(Engine, "before_cursor_execute", capture_group_selects)
    try:
        response = client.get(
            "/api/admin/calendar?year=2026&month=9",
            headers=_admin_headers(seed_admin_token),
        )
    finally:
        event.remove(Engine, "before_cursor_execute", capture_group_selects)

    assert response.status_code == 200, response.text
    assert len(group_selects) == 1


def test_message_dispatch_snapshot_detects_secondary_visit_change(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_dates = (date(2026, 9, 2), date(2026, 9, 3), date(2026, 9, 7))
    seed_order.scheduled_date = original_dates[0]
    seed_order.visits = [
        OrderVisit(id=str(uuid4()), order_id=seed_order.id, visit_date=visit_date)
        for visit_date in original_dates
    ]
    service = MessageService(db_session)
    confirmed_at = datetime(2026, 8, 17, tzinfo=UTC)
    monkeypatch.setattr(
        service,
        "_validate_message_preconditions",
        lambda _order, _payload, expected_scheduled_date=None: None,
    )
    monkeypatch.setattr(
        service.timeline,
        "latest_current_partner_confirmation",
        lambda *, order_id, partner_id: confirmed_at,
    )
    payload = MessageSendRequest(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        recipient_type=RecipientType.CUSTOMER,
        channel=MessageChannel.SMS,
    )
    log = MessageLog(
        id=str(uuid4()),
        order_id=seed_order.id,
        recipient_type=RecipientType.CUSTOMER,
        recipient_name="고객",
        recipient_phone="01010001000",
        message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        channel=MessageChannel.SMS,
        content="test",
        status="sent",
    )

    assert service._dispatch_snapshot_is_current(
        seed_order,
        payload,
        log,
        dispatch_scheduled_date=original_dates[0],
        dispatch_visit_dates=original_dates,
        dispatch_requested_time=seed_order.requested_time,
        dispatch_partner_confirmed_at=confirmed_at,
    )

    changed_dates = (date(2026, 9, 2), date(2026, 9, 3), date(2026, 9, 8))
    seed_order.visits = [
        OrderVisit(id=str(uuid4()), order_id=seed_order.id, visit_date=visit_date)
        for visit_date in changed_dates
    ]

    assert not service._dispatch_snapshot_is_current(
        seed_order,
        payload,
        log,
        dispatch_scheduled_date=original_dates[0],
        dispatch_visit_dates=original_dates,
        dispatch_requested_time=seed_order.requested_time,
        dispatch_partner_confirmed_at=confirmed_at,
    )
