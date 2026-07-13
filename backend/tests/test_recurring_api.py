from datetime import date

from app.core.time import business_today
from app.db.seed import DEV_PARTNER_ID


def _cur_month() -> str:
    t = business_today()
    return f"{t.year:04d}-{t.month:02d}"


def _cur_month_start() -> str:
    t = business_today()
    return date(t.year, t.month, 1).isoformat()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


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


def test_recurring_partner_billing_mode_locked_after_order_generation(client, seed_admin_token):
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
    assert generated.status_code == 200, generated.text
    assert any(o["recurring_contract_id"] == cid for o in generated.json())

    patched = client.patch(
        f"/api/admin/recurring/contracts/{cid}",
        json={"partner_billing_mode": "monthly"},
        headers=_auth(seed_admin_token),
    )
    assert patched.status_code == 400, patched.text
    assert patched.json()["detail"] == "recurring_partner_billing_mode_locked"


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
