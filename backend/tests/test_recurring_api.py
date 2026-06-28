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


def test_sync_and_approve_flow(client, seed_admin_token):
    client.post("/api/admin/recurring/contracts", json=_contract_body(start_date="2026-06-10"), headers=_auth(seed_admin_token))
    # sync는 '오늘' 기준이라 미래 start_date면 도래분이 없을 수 있음 → 과거 start_date로 보장
    client.post("/api/admin/recurring/contracts", json=_contract_body(label="과거건", start_date="2020-01-10"), headers=_auth(seed_admin_token))
    synced = client.post("/api/admin/recurring/occurrences/sync", headers=_auth(seed_admin_token))
    assert synced.status_code == 200
    pending = client.get("/api/admin/recurring/occurrences/pending", headers=_auth(seed_admin_token))
    assert pending.status_code == 200


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


def test_contract_occurrences_returns_contract_rows(client, seed_admin_token):
    # 과거 start_date면 sync 윈도([오늘-30, 오늘+14], 44일)에 월간 회차가 최소 1건 도래한다.
    created = client.post(
        "/api/admin/recurring/contracts",
        json=_contract_body(start_date="2020-01-10"),
        headers=_auth(seed_admin_token),
    )
    cid = created.json()["id"]
    client.post("/api/admin/recurring/occurrences/sync", headers=_auth(seed_admin_token))
    r = client.get(f"/api/admin/recurring/contracts/{cid}/occurrences", headers=_auth(seed_admin_token))
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) >= 1
    assert all(row["contract_id"] == cid for row in rows)
    first = rows[0]
    assert {"id", "sequence_no", "due_date", "billing_month", "status"} <= set(first.keys())


def test_contract_occurrences_unknown_contract_returns_404(client, seed_admin_token):
    r = client.get("/api/admin/recurring/contracts/no-such-id/occurrences", headers=_auth(seed_admin_token))
    assert r.status_code == 404, r.text


def test_contract_detail_includes_this_month_summary(client, seed_admin_token):
    created = client.post(
        "/api/admin/recurring/contracts", json=_contract_body(), headers=_auth(seed_admin_token)
    )
    cid = created.json()["id"]
    r = client.get(f"/api/admin/recurring/contracts/{cid}", headers=_auth(seed_admin_token))
    assert r.status_code == 200, r.text
    body = r.json()
    # 아직 승인된 회차가 없으므로 이번달 요약은 0이지만 필드 자체는 항상 존재해야 한다.
    assert body["this_month_count"] == 0
    assert body["this_month_amount"] == 0


def test_requires_admin(client):
    r = client.get("/api/admin/recurring/contracts")
    assert r.status_code == 401
