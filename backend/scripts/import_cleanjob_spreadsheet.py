from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from secrets import token_urlsafe
from typing import Any

from openpyxl import load_workbook

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.security import hash_password
from app.db.seed import (
    DEV_ADMIN_EMAIL,
    DEV_ADMIN_ID,
    DEV_ADMIN_PASSWORD,
    DEV_PARTNER_PASSWORD,
)
from app.db.session import SessionLocal, engine
from app.domain.constants import OrderStatus, TimelineEventType, UserRole
from app.domain.payment_status import PaymentStatus
from app.domain.partner_category import DEFAULT_PARTNER_CATEGORIES, infer_partner_category_id
from app.domain.phone import normalize_phone
from app.models import Base, Order, OrderTimeline, Partner, PartnerCategory, User


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPREADSHEET = REPO_ROOT / ".master" / "(2026.04.29) 스프레드시트 (클린잡).xlsx"
DEFAULT_START_DATE = date(2026, 5, 1)

# Sheet columns are fixed by the raw handoff file.
COL_STATUS = 1
COL_RECEIVED_DATE = 2
COL_SCHEDULED_DATE = 3
COL_REQUESTED_TIME = 4
COL_TEAM_NAME = 5
COL_SERVICE_NAME = 6
COL_ADDRESS = 7
COL_SIZE = 8
COL_DETAIL = 9
COL_SOURCE = 10
COL_CUSTOMER_NAME = 11
COL_PHONE = 12
COL_TOTAL_AMOUNT = 13
COL_DEPOSIT_AMOUNT = 14
COL_BALANCE_AMOUNT = 15
COL_ONSITE_EXTRA = 16
COL_VAT_TYPE = 17
COL_PAYMENT_STATUS = 18
COL_PAYMENT_MEMO = 19
COL_EVIDENCE_MEMO = 20
COL_COMPANY_NAME = 21
COL_PARTNER_PAYMENT_AMOUNT = 22
COL_PARTNER_PAYMENT_STATUS = 23


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CleanJob spreadsheet rows into local DB.")
    parser.add_argument("--path", type=Path, default=DEFAULT_SPREADSHEET)
    parser.add_argument("--start-date", type=parse_date_arg, default=DEFAULT_START_DATE)
    parser.add_argument("--today", type=parse_date_arg, default=date.today())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = read_rows(args.path, start_date=args.start_date, today=args.today)

    if args.dry_run:
        print_summary(rows)
        return

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_dev_admin(db)
        ensure_default_partner_categories(db)
        created = 0
        updated = 0
        partners_created = 0
        timeline_events_created = 0
        partner_cache: set[str] = set()

        for row in rows:
            partner_id, was_created = ensure_partner(db, row, partner_cache=partner_cache)
            partners_created += int(was_created)

            order = db.get(Order, row["id"])
            if order is None:
                order = Order(id=row["id"], customer_token=token_urlsafe(24))
                db.add(order)
                created += 1
            else:
                updated += 1

            apply_order_fields(order, row, partner_id=partner_id)
            timeline_events_created += int(
                add_timeline_if_missing(
                    db,
                    event_id=f"{row['id']}-created",
                    order_id=order.id,
                    event_type=TimelineEventType.CREATED,
                    title="클린잡 데이터 가져오기",
                    description=f"스프레드시트 row {row['source_row']}에서 가져왔습니다.",
                    metadata={"source": "cleanjob_spreadsheet", "source_row": row["source_row"]},
                )
            )
            if partner_id:
                timeline_events_created += int(
                    add_timeline_if_missing(
                        db,
                        event_id=f"{row['id']}-partner-assigned",
                        order_id=order.id,
                        event_type=TimelineEventType.PARTNER_ASSIGNED,
                        title="협력사 배정",
                        description=f"클린잡 원본 업체명/담당팀 기준으로 {row['company_name'] or row['team_name']}에 배정했습니다.",
                        metadata={
                            "source": "cleanjob_spreadsheet",
                            "source_row": row["source_row"],
                            "partner_id": partner_id,
                        },
                    )
                )

        db.commit()

    print(f"Imported CleanJob rows from {args.start_date.isoformat()}")
    print(
        "orders "
        f"created={created}, updated={updated}, partners_created={partners_created}, "
        f"timeline_events_created={timeline_events_created}"
    )


def add_timeline_if_missing(
    db,
    *,
    event_id: str,
    order_id: str,
    event_type: TimelineEventType,
    title: str,
    description: str,
    metadata: dict[str, Any],
) -> bool:
    if db.get(OrderTimeline, event_id) is not None:
        return False
    db.add(
        OrderTimeline(
            id=event_id,
            order_id=order_id,
            actor_user_id=DEV_ADMIN_ID,
            event_type=event_type,
            title=title,
            description=description,
            event_metadata=metadata,
        )
    )
    return True


def read_rows(path: Path, *, start_date: date, today: date) -> list[dict[str, Any]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook.worksheets[0]
    rows: list[dict[str, Any]] = []

    for row_index, values in enumerate(worksheet.iter_rows(min_row=3, values_only=True), start=3):
        scheduled_date = normalize_excel_date(values[COL_SCHEDULED_DATE])
        if scheduled_date is None or scheduled_date < start_date:
            continue

        rows.append(
            {
                "id": f"cleanjob-{row_index:04d}",
                "source_row": row_index,
                "status": map_status(values[COL_STATUS], scheduled_date=scheduled_date, today=today),
                "received_date": normalize_excel_date(values[COL_RECEIVED_DATE]) or scheduled_date,
                "scheduled_date": scheduled_date,
                "requested_time": normalize_time(values[COL_REQUESTED_TIME]),
                "team_name": clean_text(values[COL_TEAM_NAME]),
                "company_name": clean_text(values[COL_COMPANY_NAME]),
                "service_name": clean_text(values[COL_SERVICE_NAME]) or "청소",
                "size_or_quantity": clean_text(values[COL_SIZE]),
                "service_detail": clean_text(values[COL_DETAIL]),
                "special_request": clean_text(values[COL_DETAIL]),
                "source_channel": clean_text(values[COL_SOURCE]),
                "customer_name": clean_text(values[COL_CUSTOMER_NAME]) or "고객",
                "customer_phone": first_phone(values[COL_PHONE]) or "0000000000",
                "customer_address": clean_text(values[COL_ADDRESS]) or "주소 미입력",
                "total_amount": money_or_none(values[COL_TOTAL_AMOUNT]),
                "deposit_amount": money_or_none(values[COL_DEPOSIT_AMOUNT]),
                "balance_amount": money_or_none(values[COL_BALANCE_AMOUNT]),
                "onsite_extra_amount": money_or_none(values[COL_ONSITE_EXTRA]),
                "vat_type": clean_text(values[COL_VAT_TYPE]),
                "payment_status": normalize_payment_status(values[COL_PAYMENT_STATUS]),
                "payment_memo": clean_text(values[COL_PAYMENT_MEMO]),
                "evidence_memo": clean_text(values[COL_EVIDENCE_MEMO]),
                "partner_payment_amount": money_or_none(values[COL_PARTNER_PAYMENT_AMOUNT]),
                "partner_payment_status": clean_text(values[COL_PARTNER_PAYMENT_STATUS]),
            }
        )

    return rows


def ensure_dev_admin(db) -> None:
    if db.get(User, DEV_ADMIN_ID) is not None:
        return
    db.add(
        User(
            id=DEV_ADMIN_ID,
            role=UserRole.ADMIN,
            name="전소영",
            email=DEV_ADMIN_EMAIL,
            phone=None,
            password_hash=hash_password(DEV_ADMIN_PASSWORD),
            partner_id=None,
            is_active=True,
        )
    )


def ensure_default_partner_categories(db) -> None:
    for default_category in DEFAULT_PARTNER_CATEGORIES:
        category = db.get(PartnerCategory, default_category.id)
        if category is None:
            db.add(
                PartnerCategory(
                    id=default_category.id,
                    name=default_category.name,
                    description=default_category.description,
                    is_active=True,
                    sort_order=default_category.sort_order,
                )
            )


def ensure_partner(db, row: dict[str, Any], *, partner_cache: set[str]) -> tuple[str | None, bool]:
    name = row["company_name"] or row["team_name"]
    if not name:
        return None, False

    partner_id = f"cleanjob-partner-{stable_hash(name, 12)}"
    partner_category_id = infer_partner_category_id(row["service_name"])
    if partner_id in partner_cache:
        return partner_id, False
    existing = db.get(Partner, partner_id)
    if existing is not None:
        if not existing.partner_category_id:
            existing.partner_category_id = partner_category_id
        if not existing.available_services:
            existing.available_services = row["service_name"]
        partner_cache.add(partner_id)
        return partner_id, False

    partner_cache.add(partner_id)
    db.add(
        Partner(
            id=partner_id,
            partner_category_id=partner_category_id,
            name=name,
            manager_name=None,
            phone="0000000000",
            service_areas=None,
            available_services=row["service_name"],
            memo="클린잡 스프레드시트에서 자동 생성",
            is_active=True,
        )
    )
    partner_user_id = f"cleanjob-user-{stable_hash(name, 12)}"
    if db.get(User, partner_user_id) is None:
        db.add(
            User(
                id=partner_user_id,
                role=UserRole.PARTNER,
                name=name,
                email=None,
                phone=f"019{stable_number(name, 8)}",
                password_hash=hash_password(DEV_PARTNER_PASSWORD),
                partner_id=partner_id,
                is_active=True,
            )
        )
    return partner_id, True


def apply_order_fields(order: Order, row: dict[str, Any], *, partner_id: str | None) -> None:
    order.status = row["status"]
    order.received_date = row["received_date"]
    order.scheduled_date = row["scheduled_date"]
    order.requested_time = row["requested_time"]
    order.partner_id = partner_id
    order.team_name = row["team_name"] or row["company_name"]
    order.service_category_id = None
    order.service_item_id = None
    order.service_name = row["service_name"]
    order.size_or_quantity = row["size_or_quantity"]
    order.service_detail = row["service_detail"]
    order.special_request = row["special_request"]
    order.source_channel = row["source_channel"]
    order.customer_name = row["customer_name"]
    order.customer_phone = normalize_phone(row["customer_phone"])
    order.customer_address = row["customer_address"]
    order.total_amount = row["total_amount"]
    order.deposit_amount = row["deposit_amount"]
    order.balance_amount = row["balance_amount"]
    order.onsite_extra_amount = row["onsite_extra_amount"]
    order.vat_type = row["vat_type"]
    order.payment_status = row["payment_status"]
    order.payment_memo = row["payment_memo"]
    order.evidence_memo = row["evidence_memo"]
    order.partner_payment_amount = row["partner_payment_amount"]
    order.partner_payment_status = row["partner_payment_status"]
    order.customer_visible_payment = False


def map_status(raw_status: Any, *, scheduled_date: date, today: date) -> OrderStatus:
    text = clean_text(raw_status)
    if text == "서비스완료":
        return OrderStatus.COMPLETED
    if text and "취소" in text:
        return OrderStatus.CANCELLED
    if scheduled_date < today:
        return OrderStatus.COMPLETED
    if scheduled_date == today:
        return OrderStatus.SCHEDULED
    if scheduled_date == today + timedelta(days=1):
        return OrderStatus.DAY_BEFORE_NOTICE_NEEDED
    return OrderStatus.SCHEDULE_CONFIRMED


def normalize_payment_status(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if "총액" in text or "잔금" in text or "완료" in text:
        return PaymentStatus.PAID
    if "계약금" in text or "법인통장" in text:
        return PaymentStatus.DEPOSIT_PAID
    if "미" in text or "대기" in text:
        return PaymentStatus.BALANCE_PENDING
    return text


def normalize_excel_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        year = value.year - 2300 if value.year > 3000 else value.year
        return date(year, value.month, value.day)
    if isinstance(value, date):
        year = value.year - 2300 if value.year > 3000 else value.year
        return date(year, value.month, value.day)
    return None


def normalize_time(value: Any) -> str | None:
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return clean_text(value)


def money_or_none(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    text = clean_text(value)
    if not text:
        return None
    digits = re.sub(r"[^0-9.-]", "", text)
    if not digits or digits in {"-", "."}:
        return None
    try:
        return float(digits)
    except ValueError:
        return None


def first_phone(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}", text)
    if match:
        return normalize_phone(match.group(0))
    digits = normalize_phone(text)
    return digits[:11] if digits else None


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "ㅡ", "—", "None"}:
        return None
    return text


def stable_hash(value: str, length: int) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def stable_number(value: str, length: int) -> str:
    number = int(hashlib.sha1(value.encode("utf-8")).hexdigest(), 16)
    return str(number % (10**length)).zfill(length)


def parse_date_arg(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def print_summary(rows: list[dict[str, Any]]) -> None:
    print(f"rows={len(rows)}")
    if not rows:
        return
    print(f"date_range={rows[0]['scheduled_date']}..{rows[-1]['scheduled_date']}")
    for row in rows[:10]:
        print(
            row["id"],
            row["scheduled_date"],
            row["status"],
            row["team_name"],
            row["service_name"],
            row["customer_name"],
        )


if __name__ == "__main__":
    main()
