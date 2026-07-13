from calendar import monthrange
from datetime import date

import pytest
from sqlalchemy import select

from app.core.time import business_today
from app.db.seed import DEV_PARTNER_ID
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract
from app.schemas.recurring import RecurringContractCreate
from app.services.recurring import RecurringService
from app.services.recurring_generation import RecurringOrderGenerationService


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_contract_auto_generates_current_month_orders(client, seed_admin_token) -> None:
    today = business_today()
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
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text
    contract_id = created.json()["id"]

    orders = client.get("/api/admin/orders", headers=_auth(seed_admin_token))
    assert orders.status_code == 200, orders.text
    mine = [order for order in orders.json() if order["recurring_contract_id"] == contract_id]
    last_day = monthrange(today.year, today.month)[1]
    expected_dates = [
        date(today.year, today.month, day)
        for day in range(today.day, last_day + 1)
        if date(today.year, today.month, day).weekday() == today.weekday()
    ]
    assert len(mine) == len(expected_dates)
    assert all(order["status"] == "협력사확인중" for order in mine)


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
