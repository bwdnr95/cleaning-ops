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
    broker_payment_amount: float | None = None,
    customer_name: str = "고객",
    scheduled_date: str | None = None,
) -> dict:
    payload = {
        "customer_name": customer_name,
        "customer_phone": "01011112222",
        "customer_address": "서울시 강남구 테스트로 1",
        "lines": [
            {
                "status": status,
                "received_date": "2026-07-01",
                "scheduled_date": scheduled_date,
                "service_name": "입주청소",
                "broker_id": broker_id,
                "total_amount": total_amount,
                "broker_payment_amount": broker_payment_amount,
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
    assert listed[broker_id]["unpaid_broker_amount_total"] == 0

    # 상세 조회.
    detail = client.get(f"/api/admin/brokers/{broker_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["name"] == "스타중개"
    assert detail.json()["unpaid_broker_amount_total"] == 0

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


def test_broker_aggregation_counts_and_unpaid_commission() -> None:
    client = make_test_client()
    headers = admin_headers(client)
    broker_id = _create_broker(client, headers)

    # 소개 건수 = 취소 제외 전체. 미정산 수수료 = 수수료가 입력됐고 미지급인 취소 아닌 건.
    _create_line_order(client, headers, broker_id=broker_id, total_amount=100000, broker_payment_amount=10000)
    _create_line_order(client, headers, broker_id=broker_id, total_amount=50000, broker_payment_amount=5000)
    # 수수료 미입력(None) → 미정산 수수료에는 안 잡히지만 소개 건수에는 포함.
    _create_line_order(client, headers, broker_id=broker_id, total_amount=70000)
    # 수수료 0원 → 정산할 것이 없으므로 미정산에서 제외(프론트 isSettleable>0과 동일 기준). 건수엔 포함.
    _create_line_order(client, headers, broker_id=broker_id, total_amount=80000, broker_payment_amount=0)
    # 취소 건은 건수·미정산 모두 제외.
    _create_line_order(client, headers, broker_id=broker_id, total_amount=300000, broker_payment_amount=30000, status="취소")
    # 다른 중개사 없이(=없음) 생성된 주문은 이 중개사 집계에 포함되지 않는다.
    _create_line_order(client, headers, broker_id=None, total_amount=999000, broker_payment_amount=99000)

    listed = {item["id"]: item for item in client.get("/api/admin/brokers", headers=headers).json()}
    assert listed[broker_id]["order_count"] == 4  # 취소 제외 (수수료 유무·0원 무관)
    assert listed[broker_id]["unpaid_broker_amount_total"] == 15000  # 10000 + 5000 (0원·None 제외)
    assert listed[broker_id]["unpaid_broker_order_count"] == 2

    detail = client.get(f"/api/admin/brokers/{broker_id}", headers=headers).json()
    assert detail["order_count"] == 4
    assert detail["unpaid_broker_amount_total"] == 15000


def test_broker_settlement_all_status_and_date_filter() -> None:
    """'전체'는 수수료 미입력 건까지 소개 건수와 동일하게 보여주고, from/to는 방문일로 거른다.

    운영 사례(260819): 목록의 소개 건수는 4건인데 정산 섹션 기본 필터(미정산)가 수수료
    미입력 건을 숨겨 2건만 보였다 → 프론트 기본을 '전체'+전체 기간으로 바꾸고 날짜
    필터 UI를 추가했다. 이 테스트는 그 화면이 쓰는 API 조합을 고정한다.
    """
    client = make_test_client()
    headers = admin_headers(client)
    broker_id = _create_broker(client, headers)

    _create_line_order(client, headers, broker_id=broker_id, total_amount=100000, scheduled_date="2026-07-30")
    _create_line_order(client, headers, broker_id=broker_id, total_amount=50000, scheduled_date="2026-08-11")
    _create_line_order(
        client, headers, broker_id=broker_id, total_amount=70000,
        broker_payment_amount=10000, scheduled_date="2026-08-25",
    )

    # 전체: 수수료 미입력(None) 건 포함 3건 — 소개 건수와 일치.
    all_response = client.get(
        f"/api/admin/brokers/{broker_id}/settlements", headers=headers, params={"status": "all"}
    )
    assert all_response.status_code == 200, all_response.text
    assert len(all_response.json()["items"]) == 3

    # 날짜 필터: 8월 범위 → 8/11·8/25 2건.
    august = client.get(
        f"/api/admin/brokers/{broker_id}/settlements",
        headers=headers,
        params={"status": "all", "from": "2026-08-01", "to": "2026-08-31"},
    )
    assert august.status_code == 200, august.text
    assert {item["scheduled_date"] for item in august.json()["items"]} == {"2026-08-11", "2026-08-25"}

    # 미정산: 수수료가 입력된 8/25 1건만.
    unpaid = client.get(
        f"/api/admin/brokers/{broker_id}/settlements", headers=headers, params={"status": "unpaid"}
    )
    assert unpaid.status_code == 200, unpaid.text
    assert [item["scheduled_date"] for item in unpaid.json()["items"]] == ["2026-08-25"]


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


def test_broker_settlement_flow() -> None:
    # 중개사 클릭 → 그 업체 주문(수수료) 정산: 미정산 → 정산완료 → 되돌리기.
    client = make_test_client()
    headers = admin_headers(client)
    broker_id = _create_broker(client, headers)
    order = _create_line_order(
        client, headers, broker_id=broker_id, total_amount=100000, broker_payment_amount=10000
    )
    order_id = order["lines"][0]["id"]

    unpaid = client.get(f"/api/admin/brokers/{broker_id}/settlements?status=unpaid", headers=headers)
    assert unpaid.status_code == 200, unpaid.text
    assert {i["order_id"] for i in unpaid.json()["items"]} == {order_id}
    assert unpaid.json()["total_broker_price"] == 10000

    settle = client.post(
        f"/api/admin/brokers/{broker_id}/settlements/settle",
        headers=headers,
        json={"order_ids": [order_id], "memo": "7월 수수료 지급"},
    )
    assert settle.status_code == 200, settle.text
    assert settle.json()["updated_order_ids"] == [order_id]

    # 정산 후: 미정산에서 사라지고 정산완료 목록에 노출.
    after_unpaid = client.get(f"/api/admin/brokers/{broker_id}/settlements?status=unpaid", headers=headers)
    assert [i["order_id"] for i in after_unpaid.json()["items"]] == []
    paid = client.get(f"/api/admin/brokers/{broker_id}/settlements?status=paid", headers=headers).json()
    assert {i["order_id"] for i in paid["items"]} == {order_id}
    assert paid["items"][0]["broker_payment_status"] == "paid"

    # 되돌리기 → 다시 미정산.
    revert = client.post(
        f"/api/admin/brokers/{broker_id}/settlements/revert",
        headers=headers,
        json={"order_ids": [order_id]},
    )
    assert revert.status_code == 200, revert.text
    back = client.get(f"/api/admin/brokers/{broker_id}/settlements?status=unpaid", headers=headers)
    assert {i["order_id"] for i in back.json()["items"]} == {order_id}


def test_broker_settlement_rejects_cross_broker_order() -> None:
    # 다른 중개사의 주문을 정산하려 하면 422로 막는다(테넌트/소유 검증).
    client = make_test_client()
    headers = admin_headers(client)
    broker_a = _create_broker(client, headers, name="A중개")
    broker_b = _create_broker(client, headers, name="B중개")
    order = _create_line_order(
        client, headers, broker_id=broker_a, total_amount=100000, broker_payment_amount=10000
    )
    order_id = order["lines"][0]["id"]
    resp = client.post(
        f"/api/admin/brokers/{broker_b}/settlements/settle",
        headers=headers,
        json={"order_ids": [order_id]},
    )
    assert resp.status_code == 422
