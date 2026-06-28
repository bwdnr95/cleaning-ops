def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_billing_summary_requires_admin(client):
    r = client.get("/api/admin/recurring/billing?month=2026-06")
    assert r.status_code == 401


def test_billing_summary_ok(client, seed_admin_token):
    r = client.get("/api/admin/recurring/billing?month=2026-06", headers=_auth(seed_admin_token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_mark_paid_and_settle_endpoints_exist(client, seed_admin_token):
    mp = client.post(
        "/api/admin/recurring/billing/mark-paid",
        json={"contract_id": "nope", "month": "2026-06"}, headers=_auth(seed_admin_token),
    )
    assert mp.status_code == 200  # 대상 없으면 빈 결과
    st = client.post(
        "/api/admin/recurring/billing/settle",
        json={"contract_id": "nope", "month": "2026-06"}, headers=_auth(seed_admin_token),
    )
    assert st.status_code == 200


def test_export_csv_returns_csv_with_order_headers(client, seed_admin_token):
    r = client.get(
        "/api/admin/recurring/billing/export?month=2026-06", headers=_auth(seed_admin_token)
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    # 기존 주문 export 와 동일한 utf-8-sig(BOM) 직렬화 + 헤더 행
    header_line = r.content.decode("utf-8-sig").splitlines()[0]
    assert "주문ID" in header_line
