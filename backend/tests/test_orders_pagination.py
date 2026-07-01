"""관리자 주문 목록 서버 페이지네이션 엔드포인트(`GET /api/admin/orders/page`) 테스트.

브라우저(OrdersPage.tsx)가 클라이언트에서 하던 필터/정렬/탭 카운트/집계를
서버가 동일하게 재현하는지 검증한다. 결정적 비교를 위해 시드 데모 주문을
soft-delete 하고, 테스트가 만든 주문만 유니버스로 남긴다.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import business_today
from app.db.seed import DEV_ORDER_ID, DEV_PARTNER_ID, seed_dev_data
from app.domain.constants import OrderStatus
from app.models import Order, OrderGroup
from tests.test_auth_integration import (
    DEV_ADMIN_EMAIL,
    DEV_ADMIN_PASSWORD,
    login,
    make_test_client,
)

CUSTOMER_TAG = "페이지검증고객"  # q 검색으로 본 테스트 주문만 격리할 때 사용.


def _add_order(
    db: Session,
    *,
    order_id: str,
    status: str,
    scheduled_date: date | None,
    received_date: date,
    payment_status: str | None = None,
    partner_id: str | None = None,
    total_amount: float | None = None,
    onsite_extra_amount: float | None = None,
    partner_payment_amount: float | None = None,
    customer_name: str = CUSTOMER_TAG,
    customer_phone: str = "01055556666",
    customer_address: str = "서울특별시 마포구 검증로 7",
    customer_address_detail: str | None = None,
    service_name: str = "입주청소",
) -> None:
    group = OrderGroup(
        id=f"grp-{order_id}",
        customer_token=f"tok-{order_id}",
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_address=customer_address,
        customer_address_detail=customer_address_detail,
        customer_visible_payment=False,
    )
    db.add(group)
    db.flush()
    db.add(
        Order(
            id=order_id,
            group_id=group.id,
            status=status,
            received_date=received_date,
            scheduled_date=scheduled_date,
            partner_id=partner_id,
            team_name="검증팀" if partner_id else None,
            service_name=service_name,
            customer_token=group.customer_token,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_address=customer_address,
            payment_status=payment_status,
            total_amount=total_amount,
            onsite_extra_amount=onsite_extra_amount,
            partner_payment_amount=partner_payment_amount,
        )
    )


def _seed_universe(db: Session) -> None:
    """시드 데모 주문을 soft-delete 하고 결정적 테스트 유니버스를 구성한다."""
    seeded = db.get(Order, DEV_ORDER_ID)
    if seeded is not None:
        seeded.deleted_at = datetime.now(UTC)

    today = business_today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    future = today + timedelta(days=10)

    # 작업예정(미래) — schedule_work_confirmed 탭, upcoming 에 포함.
    _add_order(
        db,
        order_id="ord-future-scheduled",
        status=OrderStatus.SCHEDULED.value,
        scheduled_date=future,
        received_date=today,
        payment_status="deposit_paid",
        partner_id=DEV_PARTNER_ID,
        total_amount=100_000,
        onsite_extra_amount=10_000,
        partner_payment_amount=60_000,
    )
    # 작업예정(오늘) — today 프리셋, upcoming 포함.
    _add_order(
        db,
        order_id="ord-today-scheduled",
        status=OrderStatus.SCHEDULED.value,
        scheduled_date=today,
        received_date=today,
        payment_status="paid",
        total_amount=200_000,
        onsite_extra_amount=0,
        partner_payment_amount=120_000,
    )
    # 상담중(미정) — consulting_unassigned 탭, upcoming 포함(미정).
    _add_order(
        db,
        order_id="ord-consulting",
        status=OrderStatus.CONSULTING.value,
        scheduled_date=None,
        received_date=yesterday,
        payment_status="pending",
        total_amount=0,
    )
    # 협력사확인중(내일) — schedule_partner_checking 탭, tomorrow 프리셋.
    _add_order(
        db,
        order_id="ord-partner-checking",
        status=OrderStatus.PARTNER_CONFIRMING.value,
        scheduled_date=tomorrow,
        received_date=today,
        payment_status="pending",
        total_amount=50_000,
    )
    # 고객전달필요(미래) — work_done 탭.
    _add_order(
        db,
        order_id="ord-delivery-needed",
        status=OrderStatus.CUSTOMER_DELIVERY_NEEDED.value,
        scheduled_date=future,
        received_date=today,
        payment_status="balance_pending",
        total_amount=300_000,
        partner_payment_amount=180_000,
    )
    # 서비스완료 + 완납 → final_payment_complete 탭 유지.
    _add_order(
        db,
        order_id="ord-completed-paid",
        status=OrderStatus.COMPLETED.value,
        scheduled_date=future,
        received_date=today,
        payment_status="paid",
        total_amount=150_000,
        partner_payment_amount=90_000,
    )
    # 서비스완료 + 미완납 → orderWorkflowStatusValue 로 work_done 으로 끌려감.
    _add_order(
        db,
        order_id="ord-completed-unpaid",
        status=OrderStatus.COMPLETED.value,
        scheduled_date=future,
        received_date=today,
        payment_status="unpaid",
        total_amount=170_000,
        partner_payment_amount=100_000,
    )
    # 취소 — cancel 탭.
    _add_order(
        db,
        order_id="ord-cancelled",
        status=OrderStatus.CANCELLED.value,
        scheduled_date=future,
        received_date=today,
        payment_status=None,
        total_amount=0,
    )
    # 과거 방문 + 완납 → upcoming 에서 제외, all 에서만 노출.
    _add_order(
        db,
        order_id="ord-past-paid",
        status=OrderStatus.COMPLETED.value,
        scheduled_date=yesterday,
        received_date=yesterday,
        payment_status="paid",
        total_amount=400_000,
        partner_payment_amount=250_000,
    )
    # 과거 방문 + 잔금 미완납 → upcoming 에서도 노출(is_overdue_unpaid).
    _add_order(
        db,
        order_id="ord-past-unpaid",
        status=OrderStatus.SCHEDULED.value,
        scheduled_date=yesterday,
        received_date=yesterday,
        payment_status="unpaid",
        total_amount=80_000,
        partner_payment_amount=50_000,
    )


# 유니버스 전체(10건)와 upcoming(과거 완납 1건 제외 → 9건) 카운트.
TOTAL_ORDERS = 10
UPCOMING_ORDERS = 9


def _make_client() -> TestClient:
    return make_test_client(_seed_universe)


def _auth(client: TestClient) -> dict[str, str]:
    session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    return {"Authorization": f"Bearer {session['access_token']}"}


def _get_page(client: TestClient, headers: dict[str, str], **params) -> dict:
    response = client.get("/api/admin/orders/page", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_page_default_returns_upcoming_universe() -> None:
    client = _make_client()
    headers = _auth(client)

    body = _get_page(client, headers, visit_preset="upcoming", page=1, page_size=50)

    # 기본(오늘부터) 화면은 과거 완납을 제외하고, '전체' 보기라 취소도 건수에서 뺀다.
    assert body["total"] == UPCOMING_ORDERS - 1
    assert len(body["items"]) == UPCOMING_ORDERS - 1
    assert body["status_counts"]["all"] == UPCOMING_ORDERS - 1
    ids = {item["id"] for item in body["items"]}
    assert "ord-past-paid" not in ids
    assert "ord-cancelled" not in ids  # 취소는 '전체'에서 제외(기록은 '취소' 탭).
    assert "ord-past-unpaid" in ids  # 과거 잔금 미완납은 노출.


def test_pagination_slices_pages() -> None:
    client = _make_client()
    headers = _auth(client)

    page1 = _get_page(client, headers, visit_preset="all", page=1, page_size=4)
    page2 = _get_page(client, headers, visit_preset="all", page=2, page_size=4)
    page3 = _get_page(client, headers, visit_preset="all", page=3, page_size=4)

    assert page1["total"] == TOTAL_ORDERS - 1  # '전체'는 취소 제외
    assert len(page1["items"]) == 4
    assert len(page2["items"]) == 4
    assert len(page3["items"]) == 1  # 9 = 4 + 4 + 1

    ids1 = [item["id"] for item in page1["items"]]
    ids2 = [item["id"] for item in page2["items"]]
    ids3 = [item["id"] for item in page3["items"]]
    # 페이지 간 중복 없음.
    assert len(set(ids1 + ids2 + ids3)) == TOTAL_ORDERS - 1


def test_status_tab_counts_match_universe() -> None:
    client = _make_client()
    headers = _auth(client)

    body = _get_page(client, headers, visit_preset="all", page=1, page_size=50)
    counts = body["status_counts"]

    assert counts["all"] == TOTAL_ORDERS - 1  # '전체' 카운트는 취소 제외(취소는 cancel 탭)
    assert counts["consulting_unassigned"] == 1
    assert counts["schedule_partner_checking"] == 1
    # 4-1: '일정 및 작업 확정' = 작업예정 3건(future/today/past-unpaid) + 상담중/미배정 1건 합산 = 4.
    assert counts["schedule_work_confirmed"] == 4
    # 고객전달필요: delivery-needed + completed-unpaid(워크플로 끌어내림) = 2
    assert counts["work_done"] == 2
    # 서비스완료 + 완납: completed-paid + past-paid = 2 (visit_preset=all 이라 과거 완납 포함).
    assert counts["final_payment_complete"] == 2
    assert counts["cancel"] == 1


def test_status_tab_filter_applies() -> None:
    client = _make_client()
    headers = _auth(client)

    body = _get_page(
        client,
        headers,
        visit_preset="all",
        status="work_done",
        page=1,
        page_size=50,
    )
    ids = {item["id"] for item in body["items"]}
    assert body["total"] == 2
    assert ids == {"ord-delivery-needed", "ord-completed-unpaid"}


def test_schedule_tab_includes_consulting_unassigned() -> None:
    # 4-1: '일정 및 작업 확정' 탭은 작업예정 워크플로 + 상담중/미배정을 함께 노출한다(카운트=목록 일치).
    client = _make_client()
    headers = _auth(client)

    body = _get_page(
        client,
        headers,
        visit_preset="all",
        status="schedule_work_confirmed",
        page=1,
        page_size=50,
    )
    ids = {item["id"] for item in body["items"]}
    assert ids == {
        "ord-future-scheduled",
        "ord-today-scheduled",
        "ord-past-unpaid",
        "ord-consulting",
    }
    assert body["total"] == 4

    # 상담중/미배정 탭은 그대로 유지된다(두 탭에 중복 노출되는 것은 의도된 동작).
    consulting = _get_page(
        client,
        headers,
        visit_preset="all",
        status="consulting_unassigned",
        page=1,
        page_size=50,
    )
    assert {item["id"] for item in consulting["items"]} == {"ord-consulting"}


def test_summary_sums_include_onsite_extra() -> None:
    client = _make_client()
    headers = _auth(client)

    # work_done 탭: delivery-needed(300000, partner 180000) + completed-unpaid(170000, partner 100000)
    body = _get_page(
        client,
        headers,
        visit_preset="all",
        status="work_done",
        page=1,
        page_size=50,
    )
    summary = body["summary"]
    assert summary["count"] == 2
    assert summary["consumer_total"] == 470_000  # 300000 + 170000 (현장추가 0)
    assert summary["partner_total"] == 280_000  # 180000 + 100000
    assert summary["profit"] == 190_000

    # 작업예정 탭: future-scheduled 의 onsite_extra(10000)가 consumer_total 에 포함되는지.
    body2 = _get_page(
        client,
        headers,
        visit_preset="all",
        status="schedule_work_confirmed",
        page=1,
        page_size=50,
    )
    summary2 = body2["summary"]
    # consumer = (100000+10000) + (200000+0) + (80000+0) = 390000
    assert summary2["consumer_total"] == 390_000
    assert summary2["partner_total"] == 60_000 + 120_000 + 50_000


def test_visit_asc_orders_by_group_key() -> None:
    client = _make_client()
    headers = _auth(client)

    body = _get_page(client, headers, visit_preset="all", sort="visit_asc", page=1, page_size=50)
    ids = [item["id"] for item in body["items"]]

    def pos(order_id: str) -> int:
        return ids.index(order_id)

    # group 0 (오늘·미래) 는 group 1 (미정) 보다 앞.
    assert pos("ord-today-scheduled") < pos("ord-consulting")
    # group 1 (미정) 은 group 2 (과거 잔금 미완납) 보다 앞.
    assert pos("ord-consulting") < pos("ord-past-unpaid")
    # group 2 (과거 잔금 미완납) 은 group 3 (과거 완납) 보다 앞.
    assert pos("ord-past-unpaid") < pos("ord-past-paid")
    # group 0 내부는 날짜 오름차순: 오늘 < 미래.
    assert pos("ord-today-scheduled") < pos("ord-future-scheduled")


def test_partner_filter() -> None:
    client = _make_client()
    headers = _auth(client)

    body = _get_page(
        client,
        headers,
        visit_preset="all",
        partner_id=DEV_PARTNER_ID,
        page=1,
        page_size=50,
    )
    ids = {item["id"] for item in body["items"]}
    assert ids == {"ord-future-scheduled"}
    assert body["total"] == 1


def test_received_today_preset() -> None:
    client = _make_client()
    headers = _auth(client)

    # 접수일이 오늘인 주문만.
    body = _get_page(
        client,
        headers,
        visit_preset="all",
        received_preset="today",
        page=1,
        page_size=50,
    )
    ids = {item["id"] for item in body["items"]}
    # received_date == today 로 만든 주문들.
    assert "ord-consulting" not in ids  # 어제 접수.
    assert "ord-past-paid" not in ids  # 어제 접수.
    assert "ord-future-scheduled" in ids
    assert "ord-today-scheduled" in ids


def test_visit_today_preset() -> None:
    client = _make_client()
    headers = _auth(client)

    body = _get_page(client, headers, visit_preset="today", page=1, page_size=50)
    ids = {item["id"] for item in body["items"]}
    assert ids == {"ord-today-scheduled"}


def test_search_query_matches_and_includes_past_paid() -> None:
    client = _make_client()
    headers = _auth(client)

    # 검색어가 있으면 과거 완납도 노출(shouldIncludePastPaid) → 전체 유니버스가 매칭.
    body = _get_page(client, headers, visit_preset="upcoming", q=CUSTOMER_TAG, page=1, page_size=50)
    assert body["total"] == TOTAL_ORDERS
    ids = {item["id"] for item in body["items"]}
    assert "ord-past-paid" in ids


def test_search_query_no_match() -> None:
    client = _make_client()
    headers = _auth(client)

    body = _get_page(client, headers, visit_preset="all", q="존재하지않는검색어zzz", page=1, page_size=50)
    assert body["total"] == 0
    assert body["items"] == []


def test_search_matches_address_detail() -> None:
    """주소 검색이 상세주소(customer_address_detail)도 매칭한다."""

    def seed(db: Session) -> None:
        _add_order(
            db,
            order_id="ord-detail-addr",
            status=OrderStatus.SCHEDULED.value,
            scheduled_date=business_today(),
            received_date=business_today(),
            customer_name="상세주소검증고객",
            customer_address="서울특별시 송파구 올림픽로 300",
            customer_address_detail="롯데월드타워 101동 4501호",
        )

    client = make_test_client(seed)
    headers = _auth(client)

    body = _get_page(client, headers, visit_preset="all", q="4501호", page=1, page_size=50)
    ids = {item["id"] for item in body["items"]}
    assert "ord-detail-addr" in ids


def test_search_by_phone_digits() -> None:
    client = _make_client()
    headers = _auth(client)

    # 전화번호 숫자 일부로 검색(digitsOnly 폴백).
    body = _get_page(client, headers, visit_preset="all", q="5556666", page=1, page_size=50)
    assert body["total"] == TOTAL_ORDERS


def test_old_list_endpoint_still_works() -> None:
    client = _make_client()
    headers = _auth(client)

    response = client.get("/api/admin/orders", headers=headers)
    assert response.status_code == 200
    # 기존 엔드포인트는 그대로 동작(기본 include_past_paid=false → upcoming 유니버스).
    ids = {item["id"] for item in response.json()}
    assert "ord-past-paid" not in ids
    assert "ord-today-scheduled" in ids


def test_seed_universe_isolation(db_session: Session) -> None:
    """헬퍼가 결정적 유니버스를 만드는지 직접 확인(시드 주문 제외)."""
    _seed_universe(db_session)
    db_session.commit()
    rows = db_session.scalars(
        select(Order).where(Order.deleted_at.is_(None))
    ).all()
    ids = {row.id for row in rows}
    assert DEV_ORDER_ID not in ids
    assert len(ids) == TOTAL_ORDERS
    assert str(uuid4()) not in ids
