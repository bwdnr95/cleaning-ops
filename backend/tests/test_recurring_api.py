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


def test_requires_admin(client):
    r = client.get("/api/admin/recurring/contracts")
    assert r.status_code == 401
