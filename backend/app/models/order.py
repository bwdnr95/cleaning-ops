from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.constants import OrderStatus
from app.models.base import Base, TimestampMixin


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("order_groups.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(String(40), default=OrderStatus.NEW, index=True)
    received_date: Mapped[date] = mapped_column(Date, index=True)
    scheduled_date: Mapped[date | None] = mapped_column(Date, index=True)
    requested_time: Mapped[str | None] = mapped_column(String(80))
    partner_id: Mapped[str | None] = mapped_column(ForeignKey("partners.id"), index=True)
    team_name: Mapped[str | None] = mapped_column(String(120))
    service_category_id: Mapped[str | None] = mapped_column(ForeignKey("service_categories.id"))
    service_item_id: Mapped[str | None] = mapped_column(ForeignKey("service_items.id"))
    service_name: Mapped[str] = mapped_column(String(160))
    size_or_quantity: Mapped[str | None] = mapped_column(String(80))
    service_detail: Mapped[str | None] = mapped_column(Text)
    special_request: Mapped[str | None] = mapped_column(Text)
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
    # R7 deprecated: see OrderGroup. Drop in R7.5.
    customer_token: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    customer_visible_payment: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)
    # 정기청소 계약에서 생성된 라인이면 계약 id가 스탬프된다. 일회성 주문은 NULL.
    recurring_contract_id: Mapped[str | None] = mapped_column(
        ForeignKey("recurring_contracts.id"),
        index=True,
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
