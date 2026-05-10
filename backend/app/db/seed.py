from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.domain.constants import OrderStatus, TimelineEventType, UserRole
from app.domain.phone import normalize_phone
from app.models.order import Order
from app.models.partner import Partner, PartnerCategory
from app.models.service_item import ServiceCategory, ServiceItem
from app.models.timeline import OrderTimeline
from app.models.user import User

DEV_ADMIN_EMAIL = "admin@cleanops.kr"
DEV_ADMIN_PASSWORD = "AdminPass123!"
DEV_PARTNER_EMAIL = "partner@cleanops.kr"
DEV_PARTNER_PHONE = "01012345678"
DEV_PARTNER_PASSWORD = "PartnerPass123!"

DEV_ADMIN_ID = "seed-admin-user"
DEV_PARTNER_ID = "seed-partner-01"
DEV_PARTNER_CATEGORY_ID = "seed-partner-category-residential"
DEV_PARTNER_USER_ID = "seed-partner-user"
DEV_ORDER_ID = "seed-order-2450"
DEV_ORDER_TIMELINE_ID = "seed-order-2450-created"
DEV_CUSTOMER_TOKEN = "seed-customer-token-2450"
DEV_SERVICE_CATEGORY_ID = "seed-service-category-cleaning"
DEV_SERVICE_ITEM_ID = "seed-service-item-move-in"


@dataclass(frozen=True)
class SeedSummary:
    admin_email: str
    admin_password: str
    partner_email: str
    partner_phone: str
    partner_password: str
    partner_id: str
    order_id: str
    customer_token: str


def seed_dev_data(db: Session) -> SeedSummary:
    ensure_partner_category(db)
    ensure_partner(db)
    ensure_admin_user(db)
    ensure_partner_user(db)
    ensure_service_catalog(db)
    ensure_sample_order(db)
    ensure_order_created_timeline(db)
    db.commit()

    return SeedSummary(
        admin_email=DEV_ADMIN_EMAIL,
        admin_password=DEV_ADMIN_PASSWORD,
        partner_email=DEV_PARTNER_EMAIL,
        partner_phone=DEV_PARTNER_PHONE,
        partner_password=DEV_PARTNER_PASSWORD,
        partner_id=DEV_PARTNER_ID,
        order_id=DEV_ORDER_ID,
        customer_token=DEV_CUSTOMER_TOKEN,
    )


def ensure_partner_category(db: Session) -> PartnerCategory:
    category = db.get(PartnerCategory, DEV_PARTNER_CATEGORY_ID)
    if category is not None:
        return category

    category = PartnerCategory(
        id=DEV_PARTNER_CATEGORY_ID,
        name="주거 청소",
        description="입주/이사/정기 청소 협력사",
        is_active=True,
        sort_order=10,
    )
    db.add(category)
    return category


def ensure_partner(db: Session) -> Partner:
    partner = db.get(Partner, DEV_PARTNER_ID)
    if partner is not None:
        if not partner.partner_category_id:
            partner.partner_category_id = DEV_PARTNER_CATEGORY_ID
        return partner

    partner = Partner(
        id=DEV_PARTNER_ID,
        partner_category_id=DEV_PARTNER_CATEGORY_ID,
        name="클린파트너 강남",
        manager_name="김현장",
        phone=normalize_phone(DEV_PARTNER_PHONE),
        service_areas="서울 강남구, 서초구",
        available_services="입주청소, 정기청소",
        memo="개발/통합 테스트용 협력사",
        is_active=True,
    )
    db.add(partner)
    return partner


def ensure_admin_user(db: Session) -> User:
    user = db.get(User, DEV_ADMIN_ID)
    if user is not None:
        return user

    user = User(
        id=DEV_ADMIN_ID,
        role=UserRole.ADMIN,
        name="운영 관리자",
        email=DEV_ADMIN_EMAIL,
        phone=normalize_phone("01000000000"),
        password_hash=hash_password(DEV_ADMIN_PASSWORD),
        partner_id=None,
        is_active=True,
    )
    db.add(user)
    return user


def ensure_partner_user(db: Session) -> User:
    user = db.get(User, DEV_PARTNER_USER_ID)
    if user is not None:
        return user

    user = User(
        id=DEV_PARTNER_USER_ID,
        role=UserRole.PARTNER,
        name="김현장",
        email=DEV_PARTNER_EMAIL,
        phone=normalize_phone(DEV_PARTNER_PHONE),
        password_hash=hash_password(DEV_PARTNER_PASSWORD),
        partner_id=DEV_PARTNER_ID,
        is_active=True,
    )
    db.add(user)
    return user


def ensure_service_catalog(db: Session) -> tuple[ServiceCategory, ServiceItem]:
    category = db.get(ServiceCategory, DEV_SERVICE_CATEGORY_ID)
    if category is None:
        category = ServiceCategory(
            id=DEV_SERVICE_CATEGORY_ID,
            name="주거 청소",
            description="입주/이사/정기 청소 기본 상품",
            is_active=True,
            sort_order=10,
        )
        db.add(category)

    item = db.get(ServiceItem, DEV_SERVICE_ITEM_ID)
    if item is None:
        item = ServiceItem(
            id=DEV_SERVICE_ITEM_ID,
            category_id=DEV_SERVICE_CATEGORY_ID,
            name="입주청소",
            unit="평",
            base_price=280000,
            description="기본 입주청소 상품",
            is_active=True,
            sort_order=10,
        )
        db.add(item)

    return category, item


def ensure_sample_order(db: Session) -> Order:
    order = db.get(Order, DEV_ORDER_ID)
    if order is not None:
        return order

    order = Order(
        id=DEV_ORDER_ID,
        status=OrderStatus.SCHEDULE_CONFIRMED,
        received_date=date(2026, 5, 2),
        scheduled_date=date(2026, 5, 4),
        requested_time="09:00",
        partner_id=DEV_PARTNER_ID,
        team_name="강남 1팀",
        service_category_id=DEV_SERVICE_CATEGORY_ID,
        service_item_id=DEV_SERVICE_ITEM_ID,
        service_name="입주청소",
        size_or_quantity="24평",
        service_detail="방 3, 욕실 2",
        special_request="창틀 오염 확인 필요",
        source_channel="네이버 예약",
        customer_name="박고객",
        customer_phone=normalize_phone("01098765432"),
        customer_address="서울 강남구 테헤란로 100",
        total_amount=280000,
        deposit_amount=50000,
        balance_amount=230000,
        onsite_extra_amount=0,
        vat_type="included",
        payment_status="deposit_paid",
        payment_memo="잔금 현장 결제 예정",
        evidence_memo="예약 문자 확인",
        partner_payment_amount=180000,
        partner_payment_status="unpaid",
        customer_token=DEV_CUSTOMER_TOKEN,
        customer_visible_payment=False,
    )
    db.add(order)
    return order


def ensure_order_created_timeline(db: Session) -> OrderTimeline:
    event = db.get(OrderTimeline, DEV_ORDER_TIMELINE_ID)
    if event is not None:
        return event

    event = OrderTimeline(
        id=DEV_ORDER_TIMELINE_ID,
        order_id=DEV_ORDER_ID,
        actor_user_id=DEV_ADMIN_ID,
        event_type=TimelineEventType.CREATED,
        title="개발 샘플 주문 생성",
        description="Seed 데이터로 생성된 통합 테스트용 주문입니다.",
        event_metadata={"seed": True},
    )
    db.add(event)
    return event
