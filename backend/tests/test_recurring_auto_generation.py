from calendar import monthrange
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.core.time import business_today
from app.db.seed import DEV_PARTNER_ID, DEV_SERVICE_ITEM_ID
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.models.partner import Partner
from app.models.recurring_contract import RecurringContract
from app.schemas.recurring import RecurringContractCreate
from app.services.recurring import RecurringService
from app.services.recurring_generation import RecurringOrderGenerationService


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_contract_auto_generates_orders_without_inflating_regular_dashboard_amount(
    client,
    seed_admin_token,
) -> None:
    today = business_today()
    headers = _auth(seed_admin_token)
    summary_before = client.get("/api/admin/dashboard/summary", headers=headers)
    assert summary_before.status_code == 200, summary_before.text
    created = client.post(
        "/api/admin/recurring/contracts",
        json={
            "label": "자동생성 정기청소",
            "customer_name": "자동생성 고객",
            "customer_phone": "01022223333",
            "customer_address": "서울시 강남구 테스트로 7",
            "recurrence_mode": "weekly",
            "day_of_month": None,
            "interval_weeks": 1,
            "weekdays": [today.weekday()],
            "start_date": date(today.year, today.month, 1).isoformat(),
            "default_partner_id": DEV_PARTNER_ID,
            "service_name": "사무실 정기청소",
            "total_amount": 88000,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    contract_id = created.json()["id"]

    regular_orders = client.get("/api/admin/orders", headers=headers)
    assert regular_orders.status_code == 200, regular_orders.text
    assert all(order["recurring_contract_id"] is None for order in regular_orders.json())
    regular_page = client.get(
        "/api/admin/orders/page?visit_preset=all&page_size=2000",
        headers=headers,
    )
    assert regular_page.status_code == 200, regular_page.text
    assert all(
        order["recurring_contract_id"] is None
        for order in regular_page.json()["items"]
    )
    invalid_scope = client.get(
        "/api/admin/orders/page?scope=all",
        headers=headers,
    )
    assert invalid_scope.status_code == 422, invalid_scope.text

    orders = client.get(
        "/api/admin/orders/page?scope=recurring&visit_preset=upcoming&page_size=2000",
        headers=headers,
    )
    assert orders.status_code == 200, orders.text
    mine = [
        order
        for order in orders.json()["items"]
        if order["recurring_contract_id"] == contract_id
    ]
    last_day = monthrange(today.year, today.month)[1]
    expected_dates = [
        date(today.year, today.month, day)
        for day in range(today.day, last_day + 1)
        if date(today.year, today.month, day).weekday() == today.weekday()
    ]
    assert len(mine) == len(expected_dates)
    assert all(order["status"] == "협력사확인중" for order in mine)
    summary_after = client.get("/api/admin/dashboard/summary", headers=headers)
    assert summary_after.status_code == 200, summary_after.text
    count_fields = {
        "today_jobs",
        "tomorrow_notice_targets",
        "partner_pending",
        "unpaid_check_needed",
        "customer_check_needed",
        "monthly_completed",
        "photo_review_pending",
        "customer_delivery_needed",
        "payment_check_needed",
    }
    assert {
        field: summary_after.json()[field]
        for field in count_fields
    } == {
        field: summary_before.json()[field]
        for field in count_fields
    }
    assert (
        summary_after.json()["monthly_contract_amount"]
        == summary_before.json()["monthly_contract_amount"]
    )


def test_create_contract_rejects_invalid_service_item_before_auto_generation(
    client,
    seed_admin_token,
) -> None:
    today = business_today()
    created = client.post(
        "/api/admin/recurring/contracts",
        json={
            "label": "잘못된 서비스 정기청소",
            "customer_name": "자동생성 고객",
            "customer_phone": "01022223333",
            "customer_address": "서울시 강남구 테스트로 7",
            "recurrence_mode": "weekly",
            "day_of_month": None,
            "interval_weeks": 1,
            "weekdays": [today.weekday()],
            "start_date": date(today.year, today.month, 1).isoformat(),
            "service_item_id": "missing-service-item",
            "service_name": "사무실 정기청소",
            "total_amount": 88000,
        },
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 404, created.text
    assert created.json()["detail"] == "service_item_not_found"

    contracts = client.get("/api/admin/recurring/contracts", headers=_auth(seed_admin_token))
    assert contracts.status_code == 200, contracts.text
    assert all(item["label"] != "잘못된 서비스 정기청소" for item in contracts.json())


def test_monthly_partner_contract_keeps_catalog_price_out_of_generated_orders(
    client,
    seed_admin_token,
) -> None:
    today = business_today()
    created = client.post(
        "/api/admin/recurring/contracts",
        json={
            "label": "월정산 카탈로그 계약",
            "customer_name": "월정산 고객",
            "customer_phone": "01022223333",
            "customer_address": "서울시 강남구 테스트로 7",
            "recurrence_mode": "monthly",
            "day_of_month": today.day,
            "start_date": date(today.year, today.month, 1).isoformat(),
            "default_partner_id": DEV_PARTNER_ID,
            "service_item_id": DEV_SERVICE_ITEM_ID,
            "service_name": "사무실 정기청소",
            "partner_billing_mode": "monthly",
            "partner_payment_amount": 300000,
        },
        headers=_auth(seed_admin_token),
    )

    assert created.status_code == 201, created.text
    contract_id = created.json()["id"]
    generated = client.get(
        f"/api/admin/recurring/orders?month={today.year:04d}-{today.month:02d}",
        headers=_auth(seed_admin_token),
    )
    order = next(
        item
        for item in generated.json()
        if item["recurring_contract_id"] == contract_id
    )
    assert order["service_item_id"] == DEV_SERVICE_ITEM_ID
    assert order["partner_payment_amount"] is None
    assert order["partner_payment_status"] is None


def test_patch_contract_rejects_invalid_service_item_before_persistence(
    client,
    seed_admin_token,
) -> None:
    today = business_today()
    created = client.post(
        "/api/admin/recurring/contracts",
        json={
            "label": "수정검증 정기청소",
            "customer_name": "자동생성 고객",
            "customer_phone": "01022223333",
            "customer_address": "서울시 강남구 테스트로 7",
            "recurrence_mode": "weekly",
            "day_of_month": None,
            "interval_weeks": 1,
            "weekdays": [today.weekday()],
            "start_date": date(today.year, today.month, 1).isoformat(),
            "service_name": "사무실 정기청소",
            "total_amount": 88000,
        },
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text
    contract_id = created.json()["id"]

    patched = client.patch(
        f"/api/admin/recurring/contracts/{contract_id}",
        json={"service_item_id": "missing-service-item"},
        headers=_auth(seed_admin_token),
    )
    assert patched.status_code == 404, patched.text
    assert patched.json()["detail"] == "service_item_not_found"

    fetched = client.get(f"/api/admin/recurring/contracts/{contract_id}", headers=_auth(seed_admin_token))
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["service_item_id"] is None


def test_create_contract_discards_group_and_contract_when_auto_generation_fails(
    db_session,
    monkeypatch,
) -> None:
    today = business_today()

    def fail_generation(
        self: RecurringOrderGenerationService,
        contract: RecurringContract,
        *,
        actor_user_id: str | None,
    ) -> int:
        raise ValueError("service_item_not_found")

    monkeypatch.setattr(
        "app.services.recurring_generation.RecurringOrderGenerationService.generate_current_month_for_contract",
        fail_generation,
    )
    payload = RecurringContractCreate(
        label="생성실패 정기청소",
        customer_name="자동생성 고객",
        customer_phone="01022223333",
        customer_address="서울시 강남구 테스트로 7",
        recurrence_mode="weekly",
        day_of_month=None,
        interval_weeks=1,
        weekdays=[today.weekday()],
        start_date=date(today.year, today.month, 1),
        service_name="사무실 정기청소",
        total_amount=88000,
    )

    with pytest.raises(ValueError):
        RecurringService(db_session).create_contract(payload, actor_user_id=None)

    contract = db_session.scalar(
        select(RecurringContract).where(RecurringContract.label == "생성실패 정기청소")
    )
    assert contract is not None
    assert contract.deleted_at is not None
    group = db_session.get(OrderGroup, contract.order_group_id)
    assert group is not None
    assert group.deleted_at is not None


def test_generation_rejects_archived_effective_partner(db_session) -> None:
    today = business_today()
    partner = db_session.get(Partner, DEV_PARTNER_ID)
    assert partner is not None
    partner.deleted_at = datetime.now(UTC)
    partner.is_active = False
    group = OrderGroup(
        id="archived-generation-group",
        customer_token="archived-generation-token",
        customer_name="보관 협력사 고객",
        customer_phone="01033334444",
        customer_address="서울시 강남구",
        customer_visible_payment=False,
    )
    contract = RecurringContract(
        id="archived-generation-contract",
        label="보관 협력사 생성 방지",
        order_group_id=group.id,
        recurrence_mode="monthly",
        day_of_month=today.day,
        start_date=today.replace(day=1),
        status="active",
        default_partner_id=partner.id,
        service_name="정기청소",
    )
    db_session.add_all([group, contract])
    db_session.flush()

    with pytest.raises(ValueError, match="partner_not_found"):
        RecurringOrderGenerationService(db_session).generate_current_month_for_contract(
            contract,
            actor_user_id=None,
        )

    assert db_session.scalars(
        select(Order).where(Order.recurring_contract_id == contract.id)
    ).all() == []
