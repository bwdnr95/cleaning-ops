from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.time import business_today, utc_now
from app.db.seed import DEV_PARTNER_ID, DEV_SERVICE_ITEM_ID
from app.domain.constants import OrderStatus
from app.models.order import Order
from app.models.recurring_partner_billing_period import RecurringPartnerBillingPeriod
from app.schemas.order import OrderUpdate
from app.schemas.recurring import RecurringContractCreate, RecurringContractUpdate
from app.services.orders import OrderService
from app.services.recurring import RecurringService


def _cur_month() -> str:
    t = business_today()
    return f"{t.year:04d}-{t.month:02d}"


def _cur_month_start() -> str:
    t = business_today()
    return date(t.year, t.month, 1).isoformat()


def _previous_month() -> str:
    first = date.fromisoformat(_cur_month_start())
    previous = first - timedelta(days=1)
    return f"{previous.year:04d}-{previous.month:02d}"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_partner(client, token, *, name: str, phone: str) -> str:
    response = client.post(
        "/api/admin/partners",
        headers=_auth(token),
        json={"name": name, "phone": phone, "is_active": True},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


def _contract_body(**over):
    body = {
        "label": "강남빌딩 정기청소", "customer_name": "강남빌딩", "customer_phone": "01011112222",
        "customer_address": "서울 강남구 1", "recurrence_mode": "monthly", "day_of_month": 10,
        "start_date": "2026-06-10", "service_name": "사무실 정기청소", "total_amount": 150000,
    }
    body.update(over)
    return body


def test_create_list_contract(client, seed_admin_token):
    r = client.post("/api/admin/recurring/contracts", json=_contract_body(), headers=_auth(seed_admin_token))
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    lst = client.get("/api/admin/recurring/contracts", headers=_auth(seed_admin_token))
    assert lst.status_code == 200
    assert any(c["id"] == cid for c in lst.json())


def test_create_contract_invalid_schedule_returns_422(client, seed_admin_token):
    body = _contract_body()
    body.pop("day_of_month")  # monthly인데 day_of_month 누락
    r = client.post("/api/admin/recurring/contracts", json=body, headers=_auth(seed_admin_token))
    assert r.status_code == 422, r.text


def test_patch_contract_invalid_mode_switch_returns_400(client, seed_admin_token):
    created = client.post(
        "/api/admin/recurring/contracts", json=_contract_body(), headers=_auth(seed_admin_token)
    )
    cid = created.json()["id"]
    # weekly 전환인데 interval_weeks 미동반 → 400
    r = client.patch(
        f"/api/admin/recurring/contracts/{cid}",
        json={"recurrence_mode": "weekly"},
        headers=_auth(seed_admin_token),
    )
    assert r.status_code == 400, r.text


def test_create_contract_unknown_partner_returns_404(client, seed_admin_token):
    body = _contract_body(default_partner_id="no-such-partner")
    r = client.post("/api/admin/recurring/contracts", json=body, headers=_auth(seed_admin_token))
    assert r.status_code == 404, r.text


def test_future_contract_start_date_edit_realigns_initial_active_segment(
    client,
    seed_admin_token,
):
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(start_date="2099-09-01", day_of_month=1),
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text

    patched = client.patch(
        f"/api/admin/recurring/contracts/{created.json()['id']}",
        json={"start_date": "2099-08-01"},
        headers=_auth(seed_admin_token),
    )

    assert patched.status_code == 200, patched.text
    assert patched.json()["start_date"] == "2099-08-01"


def test_contract_start_date_edit_is_locked_after_orders_exist(client, seed_admin_token):
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(start_date=_cur_month_start(), day_of_month=15),
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text

    patched = client.patch(
        f"/api/admin/recurring/contracts/{created.json()['id']}",
        json={"start_date": "2099-08-01"},
        headers=_auth(seed_admin_token),
    )

    assert patched.status_code == 400, patched.text
    assert patched.json()["detail"] == "recurring_start_date_locked"


def test_requires_admin(client):
    r = client.get("/api/admin/recurring/contracts")
    assert r.status_code == 401


def test_contract_stores_team_phone(client, seed_admin_token):
    # 2-1: 청소 담당자 연락처(team_phone) 기입란이 저장/응답된다.
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(team_phone="01099998888"),
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text
    assert created.json()["team_phone"] == "01099998888"


def test_recurring_orders_generated_for_current_month(client, seed_admin_token):
    # 2-4: 현재 달 조회 시 예정일(15일)에 주문이 1건 생성되고, 재조회는 멱등하다.
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID, start_date=_cur_month_start(), day_of_month=15
        ),
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]

    month = _cur_month()
    first = client.get(f"/api/admin/recurring/orders?month={month}", headers=_auth(seed_admin_token))
    assert first.status_code == 200, first.text
    mine = [o for o in first.json() if o["recurring_contract_id"] == cid]
    assert len(mine) == 1
    assert mine[0]["status"] == "협력사확인중"
    assert mine[0]["partner_id"] == DEV_PARTNER_ID

    again = client.get(f"/api/admin/recurring/orders?month={month}", headers=_auth(seed_admin_token))
    assert len([o for o in again.json() if o["recurring_contract_id"] == cid]) == 1


def test_recurring_per_visit_partner_payment_flows_to_generated_order(client, seed_admin_token):
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=_cur_month_start(),
            day_of_month=15,
            partner_payment_amount=70000,
            partner_billing_mode="per_visit",
        ),
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]

    month = _cur_month()
    generated = client.get(f"/api/admin/recurring/orders?month={month}", headers=_auth(seed_admin_token))
    assert generated.status_code == 200, generated.text
    mine = [o for o in generated.json() if o["recurring_contract_id"] == cid]
    assert len(mine) == 1
    assert mine[0]["partner_payment_amount"] == 70000

    monthly = client.get(f"/api/admin/recurring/monthly?month={month}", headers=_auth(seed_admin_token))
    assert monthly.status_code == 200, monthly.text
    row = next(r for r in monthly.json() if r["contract_id"] == cid)
    assert row["partner_billing_mode"] == "per_visit"
    assert row["partner_amount"] == 70000


def test_recurring_monthly_partner_payment_uses_monthly_tracker(client, seed_admin_token):
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=_cur_month_start(),
            day_of_month=15,
            partner_payment_amount=300000,
            partner_billing_mode="monthly",
        ),
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]

    month = _cur_month()
    generated = client.get(f"/api/admin/recurring/orders?month={month}", headers=_auth(seed_admin_token))
    assert generated.status_code == 200, generated.text
    mine = [o for o in generated.json() if o["recurring_contract_id"] == cid]
    assert len(mine) == 1
    assert mine[0]["partner_payment_amount"] is None

    monthly = client.get(f"/api/admin/recurring/monthly?month={month}", headers=_auth(seed_admin_token))
    assert monthly.status_code == 200, monthly.text
    row = next(r for r in monthly.json() if r["contract_id"] == cid)
    assert row["partner_billing_mode"] == "monthly"
    assert row["partner_amount"] == 300000
    assert row["partner_payment_paid"] is False

    patched = client.post(
        "/api/admin/recurring/monthly/set",
        json={"contract_id": cid, "month": month, "partner_payment_paid": True},
        headers=_auth(seed_admin_token),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["partner_payment_paid"] is True


def test_monthly_recurring_order_rejects_per_order_partner_payment_edit(
    client,
    seed_admin_token,
):
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=_cur_month_start(),
            day_of_month=15,
            partner_payment_amount=300000,
            partner_billing_mode="monthly",
        ),
        headers=_auth(seed_admin_token),
    )
    contract_id = created.json()["id"]
    generated = client.get(
        f"/api/admin/recurring/orders?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    ).json()
    order = next(
        item for item in generated if item["recurring_contract_id"] == contract_id
    )

    patched = client.patch(
        f"/api/admin/orders/{order['id']}",
        json={"partner_payment_status": "paid"},
        headers=_auth(seed_admin_token),
    )

    assert patched.status_code == 400, patched.text
    assert patched.json()["detail"] == "recurring_partner_payment_not_per_visit"


def test_monthly_recurring_order_catalog_change_does_not_restore_per_visit_amount(
    client,
    seed_admin_token,
):
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=_cur_month_start(),
            day_of_month=15,
            billing_mode="monthly",
            partner_payment_amount=300000,
            partner_billing_mode="monthly",
        ),
        headers=_auth(seed_admin_token),
    )
    contract_id = created.json()["id"]
    order = next(
        item
        for item in client.get(
            f"/api/admin/recurring/orders?month={_cur_month()}",
            headers=_auth(seed_admin_token),
        ).json()
        if item["recurring_contract_id"] == contract_id
    )

    patched = client.patch(
        f"/api/admin/orders/{order['id']}",
        json={"service_item_id": DEV_SERVICE_ITEM_ID},
        headers=_auth(seed_admin_token),
    )

    assert patched.status_code == 200, patched.text
    assert patched.json()["total_amount"] is None
    assert patched.json()["partner_payment_amount"] is None
    assert patched.json()["partner_payment_status"] is None


def _monthly_contract_order(client, token, **over):
    """월 청구 정기계약 1건 + 이번 달 생성 주문 1건."""
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=_cur_month_start(),
            day_of_month=15,
            billing_mode="monthly",
            **over,
        ),
        headers=_auth(token),
    )
    assert created.status_code == 201, created.text
    contract_id = created.json()["id"]
    generated = client.get(
        f"/api/admin/recurring/orders?month={_cur_month()}",
        headers=_auth(token),
    )
    assert generated.status_code == 200, generated.text
    order = next(
        item
        for item in generated.json()
        if item["recurring_contract_id"] == contract_id
    )
    return contract_id, order


def test_monthly_recurring_order_edit_allows_untouched_amount_fields(
    client,
    seed_admin_token,
):
    """월 청구 주문 수정: 금액 필드가 빈 값(no-op)으로 실려와도 나머지 수정은 저장돼야 한다.

    주문 수정 화면은 라인 전체를 보내므로 금액을 건드리지 않아도 null 이 payload 에 실린다.
    이걸 거부하면 주소/특이사항/일정 같은 무관한 수정까지 통째로 막힌다.
    """
    _contract_id, order = _monthly_contract_order(
        client,
        seed_admin_token,
        partner_payment_amount=300000,
        partner_billing_mode="monthly",
    )

    patched = client.patch(
        f"/api/admin/orders/{order['id']}/edit",
        json={
            "line": {
                "special_request": "출입 카드 수령 필요",
                "total_amount": None,
                "partner_payment_amount": None,
                "partner_payment_status": None,
            },
            "group": {},
        },
        headers=_auth(seed_admin_token),
    )

    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["special_request"] == "출입 카드 수령 필요"
    assert body["total_amount"] is None
    assert body["partner_payment_amount"] is None


def test_monthly_recurring_order_rejects_explicit_customer_amount(
    client,
    seed_admin_token,
):
    """실제 금액 입력은 계속 거부한다(계약 월 청구액이 진실이므로 조용히 삼키면 안 된다)."""
    _contract_id, order = _monthly_contract_order(client, seed_admin_token)

    patched = client.patch(
        f"/api/admin/orders/{order['id']}/edit",
        json={"line": {"total_amount": 250000}, "group": {}},
        headers=_auth(seed_admin_token),
    )

    assert patched.status_code == 400, patched.text
    assert patched.json()["detail"] == "recurring_customer_payment_not_per_visit"


def test_recurring_order_detail_exposes_billing_modes(client, seed_admin_token):
    """주문 상세는 계약의 청구방식을 노출한다 — 수정 화면이 금액 입력을 잠글 근거."""
    _contract_id, order = _monthly_contract_order(
        client,
        seed_admin_token,
        partner_payment_amount=300000,
        partner_billing_mode="monthly",
    )

    detail = client.get(
        f"/api/admin/orders/{order['id']}",
        headers=_auth(seed_admin_token),
    )

    assert detail.status_code == 200, detail.text
    assert detail.json()["recurring_billing_mode"] == "monthly"
    assert detail.json()["recurring_partner_billing_mode"] == "monthly"


def test_non_recurring_order_detail_has_no_billing_modes(client, seed_order_id, seed_admin_token):
    detail = client.get(
        f"/api/admin/orders/{seed_order_id}",
        headers=_auth(seed_admin_token),
    )

    assert detail.status_code == 200, detail.text
    assert detail.json()["recurring_billing_mode"] is None
    assert detail.json()["recurring_partner_billing_mode"] is None


def test_dateless_recurring_order_keeps_settlement_on_noop_partner_fields(db_session):
    """방문일 없는 정기주문: 빈/동일 값 요청은 무시하고, 실제 정산 변경은 계속 막는다.

    도급비는 정산 월이 있어야 확정할 수 있어 날짜 없는 주문에서는 변경을 거부한다.
    다만 no-op 까지 거부하면 주소 수정이 막히고, 반대로 그냥 통과시키면 payload 의
    null 이 기존 '지급완료'와 정산일을 지운다 — 둘 다 안 된다.
    """
    recurring = RecurringService(db_session)
    contract = recurring.create_contract(
        RecurringContractCreate(**_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=_cur_month_start(),
            day_of_month=15,
            partner_payment_amount=70000,
            partner_billing_mode="per_visit",
        )),
        actor_user_id=None,
    )
    order = db_session.scalar(
        select(Order).where(Order.recurring_contract_id == contract.id)
    )
    assert order is not None
    order.recurring_planned_date = None
    order.scheduled_date = None
    order.partner_payment_amount = 70000
    order.partner_payment_status = "paid"
    order.partner_settled_at = utc_now()
    db_session.commit()
    settled_at = order.partner_settled_at

    OrderService(db_session).update(
        order.id,
        OrderUpdate(
            special_request="출입 카드 수령 필요",
            partner_payment_amount=70000,
            partner_payment_status="paid",
        ),
    )
    db_session.refresh(order)
    assert order.special_request == "출입 카드 수령 필요"
    assert order.partner_payment_status == "paid"
    assert order.partner_settled_at == settled_at

    with pytest.raises(ValueError, match="recurring_partner_payment_date_required"):
        OrderService(db_session).update(
            order.id,
            OrderUpdate(partner_payment_status=None),
        )
    db_session.rollback()
    db_session.refresh(order)
    assert order.partner_payment_status == "paid"
    assert order.partner_settled_at == settled_at


def test_legacy_order_month_move_normalizes_destination_monthly_terms(
    db_session,
):
    recurring = RecurringService(db_session)
    contract = recurring.create_contract(
        RecurringContractCreate(**_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=f"{_previous_month()}-01",
            day_of_month=15,
            partner_payment_amount=70000,
            partner_billing_mode="per_visit",
        )),
        actor_user_id=None,
    )
    recurring.update_contract(
        contract.id,
        RecurringContractUpdate(
            partner_billing_mode="monthly",
            partner_payment_amount=300000,
        ),
        actor_user_id=None,
    )
    order = db_session.scalar(
        select(Order).where(Order.recurring_contract_id == contract.id)
    )
    assert order is not None
    order.recurring_planned_date = None
    order.scheduled_date = date.fromisoformat(f"{_previous_month()}-15")
    order.partner_payment_amount = 70000
    order.partner_payment_status = "unpaid"
    db_session.commit()

    with pytest.raises(
        ValueError,
        match="recurring_partner_payment_not_per_visit",
    ):
        OrderService(db_session).update(
            order.id,
            OrderUpdate(
                scheduled_date=date.fromisoformat(f"{_cur_month()}-20"),
                partner_payment_status="paid",
            ),
        )
    db_session.rollback()
    db_session.refresh(order)
    assert order.scheduled_date == date.fromisoformat(f"{_previous_month()}-15")
    assert order.partner_payment_status == "unpaid"

    moved = OrderService(db_session).update(
        order.id,
        OrderUpdate(scheduled_date=date.fromisoformat(f"{_cur_month()}-20")),
    )

    assert moved.partner_payment_amount is None
    assert moved.partner_payment_status is None


def test_recurring_contract_rejects_negative_partner_payment_without_mutation(
    client,
    seed_admin_token,
):
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=_cur_month_start(),
            partner_payment_amount=70000,
        ),
        headers=_auth(seed_admin_token),
    )
    contract_id = created.json()["id"]

    rejected = client.patch(
        f"/api/admin/recurring/contracts/{contract_id}",
        json={"partner_payment_amount": -1},
        headers=_auth(seed_admin_token),
    )
    fetched = client.get(
        f"/api/admin/recurring/contracts/{contract_id}",
        headers=_auth(seed_admin_token),
    )

    assert rejected.status_code == 422, rejected.text
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["partner_payment_amount"] == 70000


def test_delete_contract_waits_for_monthly_partner_settlement(client, seed_admin_token):
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=_cur_month_start(),
            day_of_month=15,
            partner_payment_amount=300000,
            partner_billing_mode="monthly",
        ),
        headers=_auth(seed_admin_token),
    )
    contract_id = created.json()["id"]
    client.get(
        f"/api/admin/recurring/monthly?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    )

    blocked = client.delete(
        f"/api/admin/recurring/contracts/{contract_id}",
        headers=_auth(seed_admin_token),
    )
    paid = client.post(
        "/api/admin/recurring/monthly/set",
        json={
            "contract_id": contract_id,
            "month": _cur_month(),
            "partner_payment_paid": True,
        },
        headers=_auth(seed_admin_token),
    )
    deleted = client.delete(
        f"/api/admin/recurring/contracts/{contract_id}",
        headers=_auth(seed_admin_token),
    )
    tracker = client.get(
        f"/api/admin/recurring/monthly?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    )

    assert blocked.status_code == 400, blocked.text
    assert blocked.json()["detail"] == "recurring_contract_has_unpaid_settlements"
    assert paid.status_code == 200, paid.text
    assert deleted.status_code == 204, deleted.text
    row = next(item for item in tracker.json() if item["contract_id"] == contract_id)
    assert row["partner_payment_paid"] is True


def test_pause_materializes_monthly_obligation_without_tracker_read(
    client,
    seed_admin_token,
):
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=_cur_month_start(),
            partner_payment_amount=300000,
            partner_billing_mode="monthly",
        ),
        headers=_auth(seed_admin_token),
    )
    contract_id = created.json()["id"]

    paused = client.post(
        f"/api/admin/recurring/contracts/{contract_id}/pause",
        headers=_auth(seed_admin_token),
    )
    blocked = client.delete(
        f"/api/admin/recurring/contracts/{contract_id}",
        headers=_auth(seed_admin_token),
    )
    backlog = client.get(
        "/api/admin/reports/settlements",
        headers=_auth(seed_admin_token),
    )

    assert paused.status_code == 200, paused.text
    assert blocked.status_code == 400, blocked.text
    assert blocked.json()["detail"] == "recurring_contract_has_unpaid_settlements"
    assert any(
        row["order_id"] == f"recurring-monthly:{contract_id}:{_cur_month()}"
        for row in backlog.json()["rows"]
    )


def test_recurring_partner_billing_change_applies_from_current_month_without_deleting_orders(
    client,
    seed_admin_token,
):
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=f"{_previous_month()}-01",
            day_of_month=15,
            partner_payment_amount=70000,
            partner_billing_mode="per_visit",
        ),
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]

    generated = client.get(
        f"/api/admin/recurring/orders?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    )
    assert generated.status_code == 200, generated.text
    order = next(o for o in generated.json() if o["recurring_contract_id"] == cid)
    assert order["partner_payment_amount"] == 70000

    previous = client.get(
        f"/api/admin/recurring/monthly?month={_previous_month()}",
        headers=_auth(seed_admin_token),
    )
    assert previous.status_code == 200, previous.text
    previous_row = next(row for row in previous.json() if row["contract_id"] == cid)
    assert previous_row["partner_billing_mode"] == "per_visit"
    assert previous_row["partner_amount"] == 70000

    patched = client.patch(
        f"/api/admin/recurring/contracts/{cid}",
        json={"partner_billing_mode": "monthly", "partner_payment_amount": 300000},
        headers=_auth(seed_admin_token),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["partner_billing_mode"] == "monthly"
    assert patched.json()["partner_payment_amount"] == 300000

    current_orders = client.get(
        f"/api/admin/recurring/orders?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    )
    current_order = next(
        item for item in current_orders.json() if item["recurring_contract_id"] == cid
    )
    assert current_order["id"] == order["id"]
    assert current_order["status"] == order["status"]
    assert current_order["partner_payment_amount"] is None
    order_detail = client.get(
        f"/api/admin/orders/{order['id']}",
        headers=_auth(seed_admin_token),
    )
    assert any(
        event["event_type"] == "memo_added"
        and event["event_metadata"].get("effective_month") == _cur_month()
        for event in order_detail.json()["timeline"]
        if event["event_metadata"]
    )

    current = client.get(
        f"/api/admin/recurring/monthly?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    )
    current_row = next(row for row in current.json() if row["contract_id"] == cid)
    assert current_row["partner_billing_mode"] == "monthly"
    assert current_row["partner_amount"] == 300000

    previous_after_change = client.get(
        f"/api/admin/recurring/monthly?month={_previous_month()}",
        headers=_auth(seed_admin_token),
    )
    previous_after_row = next(
        row for row in previous_after_change.json() if row["contract_id"] == cid
    )
    assert previous_after_row["partner_billing_mode"] == "per_visit"
    assert previous_after_row["partner_amount"] == 70000


def test_recurring_partner_change_reassigns_current_unpaid_orders_and_settlement(
    client,
    seed_admin_token,
):
    replacement_partner_id = _create_partner(
        client,
        seed_admin_token,
        name="8월 대체 협력사",
        phone="01088000001",
    )
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=_cur_month_start(),
            day_of_month=15,
            partner_payment_amount=70000,
            partner_billing_mode="per_visit",
        ),
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text
    contract_id = created.json()["id"]
    generated = client.get(
        f"/api/admin/recurring/orders?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    ).json()
    order = next(item for item in generated if item["recurring_contract_id"] == contract_id)
    assert order["partner_id"] == DEV_PARTNER_ID

    patched = client.patch(
        f"/api/admin/recurring/contracts/{contract_id}",
        json={"default_partner_id": replacement_partner_id},
        headers=_auth(seed_admin_token),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["default_partner_id"] == replacement_partner_id

    current_orders = client.get(
        f"/api/admin/recurring/orders?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    ).json()
    current_order = next(item for item in current_orders if item["id"] == order["id"])
    assert current_order["partner_id"] == replacement_partner_id

    backlog = client.get(
        "/api/admin/reports/settlements",
        headers=_auth(seed_admin_token),
    )
    assert backlog.status_code == 200, backlog.text
    settlement = next(row for row in backlog.json()["rows"] if row["order_id"] == order["id"])
    assert settlement["partner_id"] == replacement_partner_id

    detail = client.get(
        f"/api/admin/orders/{order['id']}",
        headers=_auth(seed_admin_token),
    ).json()
    reassignment = next(
        event
        for event in detail["timeline"]
        if event["event_type"] == "partner_assigned"
        and event["event_metadata"].get("effective_month") == _cur_month()
    )
    assert reassignment["event_metadata"]["from_partner_id"] == DEV_PARTNER_ID
    assert reassignment["event_metadata"]["partner_id"] == replacement_partner_id


def test_recurring_partner_change_preserves_completed_photo_order(
    client,
    seed_admin_token,
    seed_partner_token,
):
    replacement_partner_id = _create_partner(
        client,
        seed_admin_token,
        name="이력 보존 대체 협력사",
        phone="01088000002",
    )
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            recurrence_mode="weekly",
            day_of_month=None,
            interval_weeks=1,
            weekdays=[0, 1, 2, 3, 4, 5, 6],
            start_date=_cur_month_start(),
            partner_payment_amount=70000,
            partner_billing_mode="per_visit",
        ),
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text
    contract_id = created.json()["id"]
    generated = client.get(
        f"/api/admin/recurring/orders?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    ).json()
    contract_orders = [
        item for item in generated if item["recurring_contract_id"] == contract_id
    ]
    assert len(contract_orders) >= 2
    order, mutable_order = contract_orders[:2]

    started = client.patch(
        f"/api/admin/orders/{order['id']}",
        json={"status": OrderStatus.IN_PROGRESS.value},
        headers=_auth(seed_admin_token),
    )
    assert started.status_code == 200, started.text
    uploaded = client.post(
        f"/api/partner/jobs/{order['id']}/photos",
        headers=_auth(seed_partner_token),
        files={"file": ("history.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"photo_type": "after"},
    )
    assert uploaded.status_code == 200, uploaded.text
    completed = client.patch(
        f"/api/admin/orders/{order['id']}",
        json={"status": OrderStatus.COMPLETED.value},
        headers=_auth(seed_admin_token),
    )
    assert completed.status_code == 200, completed.text

    patched = client.patch(
        f"/api/admin/recurring/contracts/{contract_id}",
        json={"default_partner_id": replacement_partner_id},
        headers=_auth(seed_admin_token),
    )
    assert patched.status_code == 200, patched.text

    contract = client.get(
        f"/api/admin/recurring/contracts/{contract_id}",
        headers=_auth(seed_admin_token),
    ).json()
    detail = client.get(
        f"/api/admin/orders/{order['id']}",
        headers=_auth(seed_admin_token),
    ).json()
    mutable_detail = client.get(
        f"/api/admin/orders/{mutable_order['id']}",
        headers=_auth(seed_admin_token),
    ).json()
    assert contract["default_partner_id"] == replacement_partner_id
    assert detail["partner_id"] == DEV_PARTNER_ID
    assert detail["status"] == OrderStatus.COMPLETED.value
    assert any(photo["file_name"] == "history.jpg" for photo in detail["photos"])
    assert mutable_detail["partner_id"] == replacement_partner_id
    settlements = client.get(
        f"/api/admin/partners/{DEV_PARTNER_ID}/settlements?status=unpaid",
        headers=_auth(seed_admin_token),
    )
    assert settlements.status_code == 200, settlements.text
    preserved = next(
        item for item in settlements.json()["items"] if item["order_id"] == order["id"]
    )
    assert preserved["partner_price"] == 70000


def test_recurring_billing_change_preserves_delivery_done_history(
    client,
    seed_admin_token,
):
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            recurrence_mode="weekly",
            day_of_month=None,
            interval_weeks=1,
            weekdays=[0, 1, 2, 3, 4, 5, 6],
            start_date=_cur_month_start(),
            partner_payment_amount=70000,
            partner_billing_mode="per_visit",
        ),
        headers=_auth(seed_admin_token),
    )
    contract_id = created.json()["id"]
    orders = [
        item
        for item in client.get(
            f"/api/admin/recurring/orders?month={_cur_month()}",
            headers=_auth(seed_admin_token),
        ).json()
        if item["recurring_contract_id"] == contract_id
    ]
    assert len(orders) >= 2
    order, mutable_order = orders[:2]
    completed = client.patch(
        f"/api/admin/orders/{order['id']}",
        json={"status": OrderStatus.CUSTOMER_DELIVERY_DONE.value},
        headers=_auth(seed_admin_token),
    )

    patched = client.patch(
        f"/api/admin/recurring/contracts/{contract_id}",
        json={"partner_billing_mode": "monthly", "partner_payment_amount": 300000},
        headers=_auth(seed_admin_token),
    )
    detail = client.get(
        f"/api/admin/orders/{order['id']}",
        headers=_auth(seed_admin_token),
    )
    mutable_detail = client.get(
        f"/api/admin/orders/{mutable_order['id']}",
        headers=_auth(seed_admin_token),
    )

    assert completed.status_code == 200, completed.text
    assert patched.status_code == 200, patched.text
    assert detail.json()["partner_payment_amount"] == 70000
    assert detail.json()["partner_payment_status"] is None
    assert mutable_detail.json()["partner_payment_amount"] is None
    assert mutable_detail.json()["partner_payment_status"] is None
    settlements = client.get(
        f"/api/admin/partners/{DEV_PARTNER_ID}/settlements?status=unpaid",
        headers=_auth(seed_admin_token),
    )
    assert settlements.status_code == 200, settlements.text
    preserved = next(
        item for item in settlements.json()["items"] if item["order_id"] == order["id"]
    )
    assert preserved["partner_price"] == 70000


def test_recurring_billing_change_rejects_legacy_unscheduled_order(
    db_session,
):
    recurring = RecurringService(db_session)
    contract = recurring.create_contract(
        RecurringContractCreate(**_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=_cur_month_start(),
            day_of_month=15,
            partner_payment_amount=70000,
        )),
        actor_user_id=None,
    )
    order = db_session.scalar(
        select(Order).where(Order.recurring_contract_id == contract.id)
    )
    assert order is not None
    order.recurring_planned_date = None
    order.scheduled_date = None
    db_session.commit()

    with pytest.raises(ValueError, match="recurring_partner_billing_change_unscheduled"):
        recurring.update_contract(
            contract.id,
            RecurringContractUpdate(
                partner_billing_mode="monthly",
                partner_payment_amount=300000,
            ),
            actor_user_id=None,
        )
    with pytest.raises(ValueError, match="recurring_partner_payment_date_required"):
        OrderService(db_session).update(
            order.id,
            OrderUpdate(partner_payment_status="paid"),
            actor_user_id=None,
        )


def test_legacy_order_cross_month_uses_destination_per_visit_rate(db_session):
    recurring = RecurringService(db_session)
    contract = recurring.create_contract(
        RecurringContractCreate(
            **_contract_body(
                default_partner_id=DEV_PARTNER_ID,
                start_date=_cur_month_start(),
                day_of_month=15,
                partner_payment_amount=70000,
            )
        ),
        actor_user_id=None,
    )
    order = db_session.scalar(
        select(Order).where(Order.recurring_contract_id == contract.id)
    )
    assert order is not None
    order.recurring_planned_date = None
    order.scheduled_date = date(2026, 7, 15)
    db_session.add(
        RecurringPartnerBillingPeriod(
            contract_id=contract.id,
            effective_month="2026-08",
            partner_id=DEV_PARTNER_ID,
            billing_mode="per_visit",
            partner_payment_amount=90000,
        )
    )
    db_session.commit()

    updated = OrderService(db_session).update(
        order.id,
        OrderUpdate(scheduled_date=date(2026, 8, 15)),
        actor_user_id=None,
    )

    assert updated.partner_payment_amount == 90000
    assert updated.partner_payment_status == "unpaid"
    assert updated.partner_settled_at is None


def test_recurring_partner_billing_change_preserves_paid_current_order(client, seed_admin_token):
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=_cur_month_start(),
            day_of_month=15,
            partner_payment_amount=70000,
            partner_billing_mode="per_visit",
        ),
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    generated = client.get(
        f"/api/admin/recurring/orders?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    )
    order = next(o for o in generated.json() if o["recurring_contract_id"] == cid)
    settled = client.patch(
        f"/api/admin/orders/{order['id']}",
        json={"partner_payment_status": "paid"},
        headers=_auth(seed_admin_token),
    )
    assert settled.status_code == 200, settled.text

    patched = client.patch(
        f"/api/admin/recurring/contracts/{cid}",
        json={"partner_billing_mode": "monthly"},
        headers=_auth(seed_admin_token),
    )
    assert patched.status_code == 200, patched.text
    paid = client.get(
        f"/api/admin/partners/{DEV_PARTNER_ID}/settlements?status=paid",
        headers=_auth(seed_admin_token),
    )
    assert paid.status_code == 200, paid.text
    paid_order = next(item for item in paid.json()["items"] if item["order_id"] == order["id"])
    assert paid_order["partner_price"] == 70000
    assert paid_order["partner_payment_status"] == "paid"
    unrelated = client.patch(
        f"/api/admin/orders/{order['id']}",
        json={"special_request": "지급 이력 보존"},
        headers=_auth(seed_admin_token),
    )
    assert unrelated.status_code == 200, unrelated.text
    assert unrelated.json()["partner_payment_amount"] == 70000
    assert unrelated.json()["partner_payment_status"] == "paid"


def test_recurring_partner_billing_change_preserves_paid_and_updates_mutable_orders(
    client,
    seed_admin_token,
):
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            recurrence_mode="weekly",
            day_of_month=None,
            interval_weeks=1,
            weekdays=[0, 1, 2, 3, 4, 5, 6],
            start_date=_cur_month_start(),
            partner_payment_amount=70000,
            partner_billing_mode="per_visit",
        ),
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    generated = client.get(
        f"/api/admin/recurring/orders?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    )
    mine = [
        order for order in generated.json()
        if order["recurring_contract_id"] == cid
    ]
    assert len(mine) >= 2
    paid_order, unpaid_order = mine[:2]
    marked_paid = client.patch(
        f"/api/admin/orders/{paid_order['id']}",
        json={"partner_payment_status": "paid"},
        headers=_auth(seed_admin_token),
    )
    assert marked_paid.status_code == 200, marked_paid.text

    patched = client.patch(
        f"/api/admin/recurring/contracts/{cid}",
        json={"partner_billing_mode": "monthly", "partner_payment_amount": 300000},
        headers=_auth(seed_admin_token),
    )
    current_orders = client.get(
        f"/api/admin/recurring/orders?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    ).json()
    current_by_id = {order["id"]: order for order in current_orders}

    assert patched.status_code == 200, patched.text
    assert patched.json()["partner_billing_mode"] == "monthly"
    assert patched.json()["partner_payment_amount"] == 300000
    assert current_by_id[paid_order["id"]]["partner_payment_status"] == "paid"
    assert current_by_id[paid_order["id"]]["partner_payment_amount"] == 70000
    assert current_by_id[unpaid_order["id"]]["partner_payment_status"] is None
    assert current_by_id[unpaid_order["id"]]["partner_payment_amount"] is None
    monthly = client.get(
        f"/api/admin/recurring/monthly?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    )
    monthly_row = next(row for row in monthly.json() if row["contract_id"] == cid)
    assert monthly_row["partner_billing_mode"] == "monthly"
    assert monthly_row["partner_amount"] == 300000


def test_recurring_partner_billing_change_rejects_paid_current_month(client, seed_admin_token):
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=_cur_month_start(),
            day_of_month=15,
            partner_payment_amount=300000,
            partner_billing_mode="monthly",
        ),
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    marked_paid = client.post(
        "/api/admin/recurring/monthly/set",
        json={
            "contract_id": cid,
            "month": _cur_month(),
            "partner_payment_paid": True,
        },
        headers=_auth(seed_admin_token),
    )
    assert marked_paid.status_code == 200, marked_paid.text

    patched = client.patch(
        f"/api/admin/recurring/contracts/{cid}",
        json={"partner_billing_mode": "per_visit"},
        headers=_auth(seed_admin_token),
    )
    assert patched.status_code == 400, patched.text
    assert patched.json()["detail"] == "recurring_partner_billing_change_paid"


def test_recurring_partner_billing_change_from_monthly_to_per_visit_updates_unpaid_orders(
    client,
    seed_admin_token,
):
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID,
            start_date=_cur_month_start(),
            day_of_month=15,
            partner_payment_amount=300000,
            partner_billing_mode="monthly",
        ),
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    generated = client.get(
        f"/api/admin/recurring/orders?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    )
    order = next(o for o in generated.json() if o["recurring_contract_id"] == cid)
    assert order["partner_payment_amount"] is None

    patched = client.patch(
        f"/api/admin/recurring/contracts/{cid}",
        json={"partner_billing_mode": "per_visit", "partner_payment_amount": 70000},
        headers=_auth(seed_admin_token),
    )
    assert patched.status_code == 200, patched.text

    current_orders = client.get(
        f"/api/admin/recurring/orders?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    )
    current_order = next(
        item for item in current_orders.json() if item["recurring_contract_id"] == cid
    )
    assert current_order["id"] == order["id"]
    assert current_order["partner_payment_amount"] == 70000
    assert current_order["partner_payment_status"] == "unpaid"

    current = client.get(
        f"/api/admin/recurring/monthly?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    )
    current_row = next(row for row in current.json() if row["contract_id"] == cid)
    assert current_row["partner_billing_mode"] == "per_visit"
    assert current_row["partner_amount"] == 70000


def test_monthly_change_preserves_locked_month_amount_and_payee(
    client,
    seed_admin_token,
):
    original_partner_id = _create_partner(
        client,
        seed_admin_token,
        name="월정산 이력 협력사",
        phone="01088000031",
    )
    replacement_partner_id = _create_partner(
        client,
        seed_admin_token,
        name="변경 후 협력사",
        phone="01088000032",
    )
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=original_partner_id,
            start_date=_cur_month_start(),
            day_of_month=15,
            partner_payment_amount=300000,
            partner_billing_mode="monthly",
        ),
        headers=_auth(seed_admin_token),
    )
    assert created.status_code == 201, created.text
    contract_id = created.json()["id"]
    order = next(
        item
        for item in client.get(
            f"/api/admin/recurring/orders?month={_cur_month()}",
            headers=_auth(seed_admin_token),
        ).json()
        if item["recurring_contract_id"] == contract_id
    )
    completed = client.patch(
        f"/api/admin/orders/{order['id']}",
        json={"status": OrderStatus.COMPLETED.value},
        headers=_auth(seed_admin_token),
    )
    assert completed.status_code == 200, completed.text

    patched = client.patch(
        f"/api/admin/recurring/contracts/{contract_id}",
        json={
            "default_partner_id": replacement_partner_id,
            "partner_billing_mode": "per_visit",
            "partner_payment_amount": 70000,
        },
        headers=_auth(seed_admin_token),
    )
    assert patched.status_code == 200, patched.text
    locked_order = client.get(
        f"/api/admin/orders/{order['id']}",
        headers=_auth(seed_admin_token),
    ).json()
    assert locked_order["partner_id"] == original_partner_id
    assert locked_order["partner_payment_amount"] is None

    backlog = client.get(
        "/api/admin/reports/settlements",
        headers=_auth(seed_admin_token),
    )
    retained = next(
        row
        for row in backlog.json()["rows"]
        if row["order_id"] == f"recurring-monthly:{contract_id}:{_cur_month()}"
    )
    assert retained["partner_id"] == original_partner_id
    assert float(retained["expected_settlement_amount"]) == 300000
    tracker = client.get(
        f"/api/admin/recurring/monthly?month={_cur_month()}",
        headers=_auth(seed_admin_token),
    )
    tracker_row = next(
        row for row in tracker.json() if row["contract_id"] == contract_id
    )
    assert tracker_row["partner_billing_mode"] == "monthly"
    assert tracker_row["partner_amount"] == 300000

    paid = client.post(
        "/api/admin/recurring/monthly/set",
        json={
            "contract_id": contract_id,
            "month": _cur_month(),
            "partner_payment_paid": True,
        },
        headers=_auth(seed_admin_token),
    )
    assert paid.status_code == 200, paid.text
    backlog_after = client.get(
        "/api/admin/reports/settlements",
        headers=_auth(seed_admin_token),
    )
    assert all(
        row["order_id"] != f"recurring-monthly:{contract_id}:{_cur_month()}"
        for row in backlog_after.json()["rows"]
    )


def test_recurring_future_month_browse_does_not_generate(client, seed_admin_token):
    # 프론트 리뷰 심각2 대응: 미래 달을 넘겨봐도 주문이 생성되지 않는다(생성은 현재 달에서만).
    t = business_today()
    future = f"{t.year + 1:04d}-{t.month:02d}"
    cid = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(start_date=_cur_month_start(), day_of_month=15),
        headers=_auth(seed_admin_token),
    ).json()["id"]
    resp = client.get(f"/api/admin/recurring/orders?month={future}", headers=_auth(seed_admin_token))
    assert resp.status_code == 200, resp.text
    assert [o for o in resp.json() if o["recurring_contract_id"] == cid] == []


def test_recurring_order_visible_in_partner_link(client, seed_admin_token, seed_partner_token):
    # 2-5: 생성된 정기 주문이 협력사링크(내 작업)에 일반 주문처럼 노출된다.
    cid = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(
            default_partner_id=DEV_PARTNER_ID, start_date=_cur_month_start(), day_of_month=15
        ),
        headers=_auth(seed_admin_token),
    ).json()["id"]
    gen = client.get(f"/api/admin/recurring/orders?month={_cur_month()}", headers=_auth(seed_admin_token))
    mine = [o for o in gen.json() if o["recurring_contract_id"] == cid]
    assert len(mine) == 1
    order_id = mine[0]["id"]

    jobs = client.get("/api/partner/jobs", headers=_auth(seed_partner_token))
    assert jobs.status_code == 200, jobs.text
    job = next((j for j in jobs.json() if j["id"] == order_id), None)
    assert job is not None
    assert job["is_recurring"] is True


def test_recurring_order_not_regenerated_after_delete_or_reschedule(client, seed_admin_token):
    # 심각1 대응: 회차 삭제/방문일 수정 같은 일상 운영에서 슬롯이 되살아나거나 중복 생성되지 않는다.
    month = _cur_month()
    t = business_today()

    # (a) 삭제 후 재조회 → 되살아나지 않음.
    c1 = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(start_date=_cur_month_start(), day_of_month=15),
        headers=_auth(seed_admin_token),
    ).json()["id"]
    gen1 = client.get(f"/api/admin/recurring/orders?month={month}", headers=_auth(seed_admin_token)).json()
    o1 = [o for o in gen1 if o["recurring_contract_id"] == c1][0]["id"]
    assert client.delete(f"/api/admin/orders/{o1}", headers=_auth(seed_admin_token)).status_code == 204
    after_del = client.get(f"/api/admin/recurring/orders?month={month}", headers=_auth(seed_admin_token)).json()
    assert [o for o in after_del if o["recurring_contract_id"] == c1] == []

    # (b) 방문일 수정 후 재조회 → 원래 슬롯이 중복 생성되지 않음.
    c2 = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(start_date=_cur_month_start(), day_of_month=15),
        headers=_auth(seed_admin_token),
    ).json()["id"]
    gen2 = client.get(f"/api/admin/recurring/orders?month={month}", headers=_auth(seed_admin_token)).json()
    o2 = [o for o in gen2 if o["recurring_contract_id"] == c2][0]["id"]
    new_date = date(t.year, t.month, 20).isoformat()
    patched = client.patch(
        f"/api/admin/orders/{o2}", json={"scheduled_date": new_date}, headers=_auth(seed_admin_token)
    )
    assert patched.status_code == 200, patched.text
    after_move = [
        o
        for o in client.get(f"/api/admin/recurring/orders?month={month}", headers=_auth(seed_admin_token)).json()
        if o["recurring_contract_id"] == c2
    ]
    assert len(after_move) == 1
    assert after_move[0]["scheduled_date"] == new_date


def test_recurring_weekly_generates_multiple(client, seed_admin_token):
    # 2-3: 매주 특정 요일(월·수)이면 현재 달에 여러 건 생성된다(한 달의 월+수 ≥ 8).
    body = _contract_body(
        recurrence_mode="weekly", interval_weeks=1, weekdays=[0, 2],
        start_date=_cur_month_start(), day_of_month=None,
    )
    cid = client.post("/api/admin/recurring/contracts", json=body, headers=_auth(seed_admin_token)).json()["id"]
    gen = client.get(f"/api/admin/recurring/orders?month={_cur_month()}", headers=_auth(seed_admin_token))
    mine = [o for o in gen.json() if o["recurring_contract_id"] == cid]
    assert len(mine) >= 8
