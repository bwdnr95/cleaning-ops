from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.constants import OrderStatus
from app.models.base import Base, TimestampMixin


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    # 정기 주문 멱등 슬롯: 같은 계약의 같은 '생성 예정일'은 1건만 존재한다(재생성/동시생성 방지).
    # 일회성 주문은 두 값이 모두 NULL이라 제약에 걸리지 않는다(유니크에서 NULL은 서로 구별됨).
    __table_args__ = (
        UniqueConstraint(
            "recurring_contract_id",
            "recurring_planned_date",
            name="uq_orders_recurring_slot",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("order_groups.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(String(40), default=OrderStatus.NEW, index=True)
    received_date: Mapped[date] = mapped_column(Date, index=True)
    scheduled_date: Mapped[date | None] = mapped_column(Date, index=True)
    requested_time: Mapped[str | None] = mapped_column(String(80))
    partner_id: Mapped[str | None] = mapped_column(ForeignKey("partners.id"), index=True)
    team_name: Mapped[str | None] = mapped_column(String(120))
    # 중개사(주문을 소개한 중개업체). partner_id 와 동형(라인 단위).
    broker_id: Mapped[str | None] = mapped_column(ForeignKey("brokers.id"), index=True)
    service_category_id: Mapped[str | None] = mapped_column(ForeignKey("service_categories.id"))
    service_item_id: Mapped[str | None] = mapped_column(ForeignKey("service_items.id"))
    service_name: Mapped[str] = mapped_column(String(160))
    size_or_quantity: Mapped[str | None] = mapped_column(String(80))
    service_detail: Mapped[str | None] = mapped_column(Text)
    special_request: Mapped[str | None] = mapped_column(Text)
    # AS(사후관리) 요청: 컴플레인/AS 건에 체크 + 메모. 협력사링크로 전송된다.
    as_requested: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    as_memo: Mapped[str | None] = mapped_column(Text)
    work_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    work_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    customer_signature_storage_key: Mapped[str | None] = mapped_column(String(500))
    customer_signature_file_url: Mapped[str | None] = mapped_column(String(1000))
    # R7 deprecated: see OrderGroup. Drop in R7.5.
    source_channel: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(30), index=True, nullable=True)
    customer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        server_default="0",
    )
    deposit_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    balance_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    onsite_extra_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    vat_type: Mapped[str | None] = mapped_column(String(20))
    payment_status: Mapped[str | None] = mapped_column(String(40), index=True)
    payment_memo: Mapped[str | None] = mapped_column(Text)
    evidence_memo: Mapped[str | None] = mapped_column(Text)
    # 증빙자료(현금영수증/세금계산서) 구조화 상태. evidence_memo(자유텍스트)와 병행.
    receipt_type: Mapped[str | None] = mapped_column(String(20))
    receipt_status: Mapped[str | None] = mapped_column(String(30))
    partner_payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    partner_payment_status: Mapped[str | None] = mapped_column(String(40))
    partner_settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 중개사 소개 수수료 정산(협력사 도급가 정산과 동형).
    broker_payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    broker_payment_status: Mapped[str | None] = mapped_column(String(40))
    broker_settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # R7 deprecated: see OrderGroup. Drop in R7.5.
    customer_token: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    customer_visible_payment: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)
    # 정기청소 계약에서 생성된 라인이면 계약 id가 스탬프된다. 일회성 주문은 NULL.
    recurring_contract_id: Mapped[str | None] = mapped_column(
        ForeignKey("recurring_contracts.id"),
        index=True,
        nullable=True,
    )
    # 정기청소에서 자동 생성된 회차의 '생성 당시 예정일'(불변). 멱등 생성 키.
    # scheduled_date는 운영자가 옮길 수 있어 멱등 키로 쓰지 않는다.
    recurring_planned_date: Mapped[date | None] = mapped_column(Date, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
