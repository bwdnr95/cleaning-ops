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
