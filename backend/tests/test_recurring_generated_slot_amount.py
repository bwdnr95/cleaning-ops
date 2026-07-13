from calendar import monthrange
from datetime import date

from app.core.time import business_today
from app.domain.recurrence import ScheduleSpec, iter_due_dates


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _cur_month() -> str:
    today = business_today()
    return f"{today.year:04d}-{today.month:02d}"


def _cur_month_start() -> str:
    today = business_today()
    return date(today.year, today.month, 1).isoformat()


def test_recurring_monthly_amount_keeps_generated_slots_after_visit_date_changes(
    client,
    seed_admin_token,
) -> None:
    month = _cur_month()
    today = business_today()
    next_month_year = today.year + (1 if today.month == 12 else 0)
    next_month = 1 if today.month == 12 else today.month + 1
    next_month_key = f"{next_month_year:04d}-{next_month:02d}"
    moved_date = date(next_month_year, next_month, 1).isoformat()
    cid = client.post(
        "/api/admin/recurring/contracts",
        json={
            "label": "월금액 슬롯 고정 정기청소",
            "customer_name": "월금액 고객",
            "customer_phone": "01011112222",
            "customer_address": "서울 강남구 1",
            "recurrence_mode": "weekly",
            "day_of_month": None,
            "interval_weeks": 1,
            "weekdays": [0],
            "start_date": _cur_month_start(),
            "service_name": "사무실 정기청소",
            "total_amount": 100000,
            "partner_payment_amount": 50000,
            "partner_billing_mode": "per_visit",
        },
        headers=_auth(seed_admin_token),
    ).json()["id"]
    generated = client.get(f"/api/admin/recurring/orders?month={month}", headers=_auth(seed_admin_token))
    assert generated.status_code == 200, generated.text
    mine = [order for order in generated.json() if order["recurring_contract_id"] == cid]
    assert len(mine) >= 2

    for order in mine[1:]:
        patched = client.patch(
            f"/api/admin/orders/{order['id']}",
            json={"scheduled_date": moved_date},
            headers=_auth(seed_admin_token),
        )
        assert patched.status_code == 200, patched.text

    monthly = client.get(f"/api/admin/recurring/monthly?month={month}", headers=_auth(seed_admin_token))
    assert monthly.status_code == 200, monthly.text
    row = next(item for item in monthly.json() if item["contract_id"] == cid)
    assert row["amount"] == 100000 * len(mine)
    assert row["partner_amount"] == 50000 * len(mine)

    next_monthly = client.get(
        f"/api/admin/recurring/monthly?month={next_month_key}",
        headers=_auth(seed_admin_token),
    )
    assert next_monthly.status_code == 200, next_monthly.text
    next_row = next(item for item in next_monthly.json() if item["contract_id"] == cid)
    next_month_first = date(next_month_year, next_month, 1)
    next_month_last = date(next_month_year, next_month, monthrange(next_month_year, next_month)[1])
    expected_next_month_slots = sum(
        1
        for _seq, due in iter_due_dates(
            ScheduleSpec(
                mode="weekly",
                start_date=date.fromisoformat(_cur_month_start()),
                interval_weeks=1,
                weekdays=(0,),
            ),
            until=next_month_last,
        )
        if next_month_first <= due <= next_month_last
    )
    assert next_row["amount"] == 100000 * expected_next_month_slots
    assert next_row["partner_amount"] == 50000 * expected_next_month_slots
