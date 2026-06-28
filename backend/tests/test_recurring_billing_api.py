from app.core.time import business_today
from app.db.seed import DEV_PARTNER_ID


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


def test_settle_inactive_partner_returns_4xx_not_500(client, seed_admin_token):
    """담당 협력사가 비활성화된 완료·미정산 정기 주문을 월 정산하면, 서비스 ValueError가
    HTTP 4xx로 변환되어야 한다(전역 핸들러 부재로 인한 500 방지). 형제 정산 라우트와 정합."""
    h = _auth(seed_admin_token)
    today = business_today()  # 백엔드 sync/생성과 동일 기준(KST)
    month = today.strftime("%Y-%m")

    r = client.post("/api/admin/recurring/contracts", headers=h, json={
        "label": "정산엣지", "customer_name": "강남", "customer_phone": "01011112222",
        "customer_address": "A", "recurrence_mode": "monthly", "day_of_month": today.day,
        "start_date": today.isoformat(), "service_name": "청소", "total_amount": 100000,
        "partner_payment_amount": 60000, "default_partner_id": DEV_PARTNER_ID,
    })
    assert r.status_code == 201, r.text
    contract_id = r.json()["id"]

    client.post("/api/admin/recurring/occurrences/sync", headers=h)
    pending = client.get("/api/admin/recurring/occurrences/pending", headers=h).json()
    occ = next(p for p in pending if p["contract_id"] == contract_id)
    appr = client.post(
        "/api/admin/recurring/occurrences/approve", headers=h,
        json={"items": [{"occurrence_id": occ["occurrence_id"]}]},
    )
    order_id = appr.json()["generated_order_ids"][0]

    # 완료 + 미정산으로 만들어 정산 가능 상태로
    client.patch(f"/api/admin/orders/{order_id}", headers=h,
                 json={"status": "서비스완료", "partner_payment_status": "unpaid"})
    # 담당 협력사 비활성화
    client.patch(f"/api/admin/partners/{DEV_PARTNER_ID}", headers=h, json={"is_active": False})

    settle = client.post("/api/admin/recurring/billing/settle", headers=h,
                         json={"contract_id": contract_id, "month": month})
    assert settle.status_code != 500, settle.text
    assert settle.status_code in (400, 404, 422), settle.text
