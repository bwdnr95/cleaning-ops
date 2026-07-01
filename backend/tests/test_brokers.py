"""중개사(broker) 관리 — CRUD / 집계(건수·매출) / 사용중 삭제가드 / 주문 broker_id·목록 필터."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.seed import DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD
from tests.test_auth_integration import make_test_client


def admin_headers(client: TestClient) -> dict[str, str]:
    session = client.post(
        "/api/auth/admin/login",
        json={"identifier": DEV_ADMIN_EMAIL, "password": DEV_ADMIN_PASSWORD},
    )
    return {"Authorization": f"Bearer {session.json()['access_token']}"}


def _create_broker(client: TestClient, headers: dict[str, str], name: str = "우리중개") -> str:
    response = client.post(
        "/api/admin/brokers",
        headers=headers,
        json={"name": name, "manager_name": "김담당", "phone": "021234567"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_line_order(
    client: TestClient,
    headers: dict[str, str],
    *,
    broker_id: str | None,
    total_amount: float,
    status: str = "신규접수",
    customer_name: str = "고객",
) -> dict:
    payload = {
        "customer_name": customer_name,
        "customer_phone": "01011112222",
        "customer_address": "서울시 강남구 테스트로 1",
        "lines": [
            {
                "status": status,
                "received_date": "2026-07-01",
                "service_name": "입주청소",
                "broker_id": broker_id,
                "total_amount": total_amount,
            }
        ],
    }
    response = client.post("/api/admin/orders/groups", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_broker_crud_roundtrip() -> None:
    client = make_test_client()
    headers = admin_headers(client)

    broker_id = _create_broker(client, headers, name="스타중개")

    # 목록에 노출되고 초기 집계는 0.
    list_response = client.get("/api/admin/brokers", headers=headers)
    assert list_response.status_code == 200, list_response.text
    listed = {item["id"]: item for item in list_response.json()}
    assert broker_id in listed
    assert listed[broker_id]["order_count"] == 0
    assert listed[broker_id]["revenue_total"] == 0

    # 상세 조회.
    detail = client.get(f"/api/admin/brokers/{broker_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["name"] == "스타중개"
    assert detail.json()["orders"] == []

    # 수정.
    patched = client.patch(
        f"/api/admin/brokers/{broker_id}",
        headers=headers,
        json={"name": "스타공인중개", "memo": "우수 제휴처"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == "스타공인중개"
    assert patched.json()["memo"] == "우수 제휴처"


def test_broker_not_found_returns_404() -> None:
    client = make_test_client()
    headers = admin_headers(client)
    response = client.get("/api/admin/brokers/does-not-exist", headers=headers)
    assert response.status_code == 404


def test_broker_aggregation_counts_and_revenue() -> None:
    client = make_test_client()
    headers = admin_headers(client)
    broker_id = _create_broker(client, headers)

    # 매출은 앱 표준 매출 집합(서비스완료·고객전달완료)만 합산한다. 건수는 취소 제외 전체.
    _create_line_order(client, headers, broker_id=broker_id, total_amount=100000, status="서비스완료")
    _create_line_order(client, headers, broker_id=broker_id, total_amount=50000, status="신규접수")
    # 취소 건은 건수·매출 모두 제외.
    _create_line_order(client, headers, broker_id=broker_id, total_amount=300000, status="취소")
    # 다른 중개사 없이(=없음) 생성된 주문은 이 중개사 집계에 포함되지 않는다.
    _create_line_order(client, headers, broker_id=None, total_amount=999000, status="서비스완료")

    listed = {item["id"]: item for item in client.get("/api/admin/brokers", headers=headers).json()}
    assert listed[broker_id]["order_count"] == 2  # 서비스완료 + 신규접수 (취소 제외)
    assert listed[broker_id]["revenue_total"] == 100000  # 서비스완료만

    detail = client.get(f"/api/admin/brokers/{broker_id}", headers=headers).json()
    assert detail["order_count"] == 2
    assert detail["revenue_total"] == 100000
    # 드릴다운 목록은 취소 제외 소개 주문(=order_count와 동일 집합).
    assert len(detail["orders"]) == 2


def test_broker_delete_guard_when_in_use() -> None:
    client = make_test_client()
    headers = admin_headers(client)

    used_broker = _create_broker(client, headers, name="사용중중개")
    _create_line_order(client, headers, broker_id=used_broker, total_amount=100000)

    blocked = client.delete(f"/api/admin/brokers/{used_broker}", headers=headers)
    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "broker_in_use"

    # 소개 이력이 없는 중개사는 삭제 가능.
    empty_broker = _create_broker(client, headers, name="빈중개")
    removed = client.delete(f"/api/admin/brokers/{empty_broker}", headers=headers)
    assert removed.status_code == 204


def test_order_page_broker_filter() -> None:
    client = make_test_client()
    headers = admin_headers(client)

    broker_a = _create_broker(client, headers, name="A중개")
    broker_b = _create_broker(client, headers, name="B중개")

    order_a = _create_line_order(client, headers, broker_id=broker_a, total_amount=100000)
    order_b = _create_line_order(client, headers, broker_id=broker_b, total_amount=200000)
    line_a_id = order_a["lines"][0]["id"]
    line_b_id = order_b["lines"][0]["id"]

    page_a = client.get("/api/admin/orders/page", headers=headers, params={"broker_id": broker_a})
    assert page_a.status_code == 200, page_a.text
    ids_a = {item["id"] for item in page_a.json()["items"]}
    assert line_a_id in ids_a
    assert line_b_id not in ids_a

    page_b = client.get("/api/admin/orders/page", headers=headers, params={"broker_id": broker_b})
    ids_b = {item["id"] for item in page_b.json()["items"]}
    assert line_b_id in ids_b
    assert line_a_id not in ids_b


def test_order_line_persists_broker_id() -> None:
    client = make_test_client()
    headers = admin_headers(client)
    broker_id = _create_broker(client, headers)

    order = _create_line_order(client, headers, broker_id=broker_id, total_amount=100000)
    assert order["lines"][0]["broker_id"] == broker_id
