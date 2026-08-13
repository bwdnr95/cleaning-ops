from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.constants import RecurringContractStatus
from app.models.base import Base, TimestampMixin


class RecurringContract(TimestampMixin, Base):
    __tablename__ = "recurring_contracts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    label: Mapped[str] = mapped_column(String(160))
    order_group_id: Mapped[str] = mapped_column(ForeignKey("order_groups.id"), index=True)
    # 스케줄
    recurrence_mode: Mapped[str] = mapped_column(String(20))
    day_of_month: Mapped[int | None] = mapped_column(Integer)
    interval_weeks: Mapped[int | None] = mapped_column(Integer)
    weekday: Mapped[int | None] = mapped_column(Integer)
    weekdays: Mapped[str | None] = mapped_column(String(20))  # CSV "0,2,4" (다중요일). 레거시 weekday와 병행.
    start_date: Mapped[date] = mapped_column(Date, index=True)
    # 라이프사이클
    status: Mapped[str] = mapped_column(String(20), default=RecurringContractStatus.ACTIVE, index=True)
    end_date: Mapped[date | None] = mapped_column(Date)
    active_segment_start_date: Mapped[date | None] = mapped_column(Date)
    max_occurrences: Mapped[int | None] = mapped_column(Integer)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    # 회차 템플릿
    default_partner_id: Mapped[str | None] = mapped_column(ForeignKey("partners.id"))
    team_name: Mapped[str | None] = mapped_column(String(120))
    # 청소 담당자 연락처(계약 참조용). 협력사 배정과 별개의 자유 입력값.
    team_phone: Mapped[str | None] = mapped_column(String(30))
    service_category_id: Mapped[str | None] = mapped_column(ForeignKey("service_categories.id"))
    service_item_id: Mapped[str | None] = mapped_column(ForeignKey("service_items.id"))
    service_name: Mapped[str] = mapped_column(String(160))
    size_or_quantity: Mapped[str | None] = mapped_column(String(80))
    service_detail: Mapped[str | None] = mapped_column(Text)
    special_request: Mapped[str | None] = mapped_column(Text)
    requested_time: Mapped[str | None] = mapped_column(String(80))
    # 청구방식: per_visit(회당 금액×방문횟수 합산) / monthly(월 고정). total_amount 해석이 달라진다.
    billing_mode: Mapped[str] = mapped_column(String(20), default="per_visit", server_default="per_visit")
    partner_billing_mode: Mapped[str] = mapped_column(String(20), default="per_visit", server_default="per_visit")
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    deposit_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    balance_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    vat_type: Mapped[str | None] = mapped_column(String(20))
    partner_payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
