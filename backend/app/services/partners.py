from dataclasses import dataclass, field
from decimal import Decimal
from secrets import token_urlsafe
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.domain.constants import AuditEventType, AuditSeverity, OrderStatus, UserRole
from app.domain.payment_status import PARTNER_SETTLEMENT_PENDING_STATUSES
from app.domain.phone import normalize_phone
from app.models.order import Order
from app.models.partner import Partner, PartnerCategory
from app.models.user import User
from app.repositories.partners import PartnerCategoryRepository, PartnerRepository
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.schemas.partner import (
    PartnerAdminRead,
    PartnerAssignedOrderRead,
    PartnerCategoryCreate,
    PartnerCategoryRead,
    PartnerCategoryUpdate,
    PartnerCreate,
    PartnerDetailRead,
    PartnerPasswordResetRead,
    PartnerUpdate,
)
from app.services.audit import AuditService


@dataclass(frozen=True)
class PartnerAdminContext:
    categories: dict[str, PartnerCategory] = field(default_factory=dict)
    users: dict[str, User] = field(default_factory=dict)
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    settlements: dict[str, dict[str, float | int]] = field(default_factory=dict)


ACTIVE_JOB_STATUSES = (
    OrderStatus.PARTNER_CONFIRMING,
    OrderStatus.SCHEDULE_CONFIRMED,
    OrderStatus.DAY_BEFORE_NOTICE_NEEDED,
    OrderStatus.DAY_BEFORE_NOTICE_DONE,
    OrderStatus.SCHEDULED,
    OrderStatus.IN_PROGRESS,
    OrderStatus.PHOTO_REVIEW_PENDING,
    OrderStatus.CUSTOMER_DELIVERY_NEEDED,
)

COMPLETED_JOB_STATUSES = (
    OrderStatus.CUSTOMER_DELIVERY_DONE,
    OrderStatus.COMPLETED,
)


class PartnerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.partners = PartnerRepository(db)
        self.categories = PartnerCategoryRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)
        self.audit = AuditService(db)

    def list_categories(self, *, include_inactive: bool = False) -> list[PartnerCategoryRead]:
        categories = self.categories.list_categories(include_inactive=include_inactive)
        return [self.to_category_dto(category) for category in categories]

    def create_category(self, payload: PartnerCategoryCreate) -> PartnerCategoryRead:
        category = PartnerCategory(id=str(uuid4()), **payload.model_dump())
        self.categories.add(category)
        self.db.commit()
        self.db.refresh(category)
        return self.to_category_dto(category)

    def update_category(
        self,
        category_id: str,
        payload: PartnerCategoryUpdate,
    ) -> PartnerCategoryRead:
        category = self.categories.get(category_id)
        if category is None:
            raise ValueError("partner_category_not_found")

        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(category, key, value)

        self.db.commit()
        self.db.refresh(category)
        return self.to_category_dto(category)

    def delete_category(self, category_id: str) -> None:
        category = self.categories.get(category_id)
        if category is None:
            raise ValueError("partner_category_not_found")

        for partner in self._list_partners_by_category(category_id):
            partner.partner_category_id = None

        self.db.delete(category)
        self.db.commit()

    def list_partners(self, *, include_inactive: bool = False) -> list[PartnerAdminRead]:
        partners = self.partners.list_all() if include_inactive else self.partners.list_active()
        context = self._build_admin_context(partners)
        return [self.to_admin_dto(partner, context=context) for partner in partners]

    def get_detail(self, partner_id: str) -> PartnerDetailRead:
        partner = self.partners.get(partner_id)
        if partner is None:
            raise ValueError("partner_not_found")

        base = self.to_admin_dto(partner)
        return PartnerDetailRead(
            **base.model_dump(),
            jobs=[to_assigned_order_dto(order) for order in self._list_recent_jobs(partner_id)],
        )

    def create(self, payload: PartnerCreate) -> PartnerDetailRead:
        self._require_category(payload.partner_category_id)
        partner = Partner(
            id=str(uuid4()),
            partner_category_id=payload.partner_category_id,
            name=payload.name,
            manager_name=payload.manager_name,
            phone=normalize_phone(payload.phone),
            service_areas=payload.service_areas,
            available_services=payload.available_services,
            memo=payload.memo,
            is_active=payload.is_active,
        )
        self.partners.add(partner)

        temporary_password: str | None = None
        if payload.login_phone or payload.login_password:
            # 관리자가 비밀번호를 직접 입력하지 않으면 임시 비밀번호를 자동 생성하고,
            # 자동 생성한 경우에만 응답으로 1회 노출한다.
            if payload.login_password:
                password = payload.login_password
            else:
                password = generate_temporary_password()
                temporary_password = password
            user = self._upsert_partner_user(
                partner,
                login_phone=payload.login_phone or payload.phone,
                password=password,
            )
            self.audit.record(
                event_type=AuditEventType.PARTNER_ACCOUNT_CREATED,
                severity=AuditSeverity.WARNING,
                user_id=user.id,
                details={
                    "partner_id": partner.id,
                    "auto_generated_password": temporary_password is not None,
                },
            )

        self.db.commit()
        detail = self.get_detail(partner.id)
        if temporary_password is not None:
            detail = detail.model_copy(update={"temporary_password": temporary_password})
        return detail

    def update(self, partner_id: str, payload: PartnerUpdate) -> PartnerDetailRead:
        partner = self.partners.get(partner_id)
        if partner is None:
            raise ValueError("partner_not_found")

        changes = payload.model_dump(exclude_unset=True)
        if "partner_category_id" in changes:
            self._require_category(changes["partner_category_id"])
        for key, value in changes.items():
            if key == "phone" and value is not None:
                value = normalize_phone(value)
            setattr(partner, key, value)

        partner_users = self._list_partner_users(partner_id)
        if "is_active" in changes and changes["is_active"] is False:
            for user in partner_users:
                user.is_active = False
                self.refresh_tokens.revoke_active_for_user(user.id)
            self._record_account_status_audit(
                partner_id,
                partner_users,
                AuditEventType.PARTNER_ACCOUNT_DEACTIVATED,
            )
        elif "is_active" in changes and changes["is_active"] is True:
            for user in partner_users:
                user.is_active = True
            self._record_account_status_audit(
                partner_id,
                partner_users,
                AuditEventType.PARTNER_ACCOUNT_ACTIVATED,
            )

        self.db.commit()
        return self.get_detail(partner_id)

    def _record_account_status_audit(
        self,
        partner_id: str,
        users: list[User],
        event_type: AuditEventType,
    ) -> None:
        if not users:
            return
        for user in users:
            self.audit.record(
                event_type=event_type,
                severity=AuditSeverity.WARNING,
                user_id=user.id,
                details={"partner_id": partner_id},
            )

    def delete(self, partner_id: str) -> None:
        partner = self.partners.get(partner_id)
        if partner is None:
            raise ValueError("partner_not_found")
        if scalar_count(self.db, Order.partner_id == partner_id) > 0:
            raise ValueError("partner_in_use")

        for user in self._list_partner_users(partner_id):
            user.is_active = False
            user.partner_id = None
            self.refresh_tokens.revoke_active_for_user(user.id)

        self.db.delete(partner)
        self.db.commit()

    def reset_password(
        self,
        partner_id: str,
        *,
        login_phone: str | None = None,
        password: str | None = None,
    ) -> PartnerPasswordResetRead:
        partner = self.partners.get(partner_id)
        if partner is None:
            raise ValueError("partner_not_found")

        temporary_password = password or generate_temporary_password()
        user = self._upsert_partner_user(
            partner,
            login_phone=login_phone or partner.phone,
            password=temporary_password,
        )
        user.is_active = partner.is_active
        self.refresh_tokens.revoke_active_for_user(user.id)
        self.audit.record(
            event_type=AuditEventType.PARTNER_PASSWORD_RESET,
            severity=AuditSeverity.WARNING,
            user_id=user.id,
            details={
                "partner_id": partner.id,
                "auto_generated_password": password is None,
            },
        )
        self.db.commit()
        return PartnerPasswordResetRead(
            partner_id=partner.id,
            user_id=user.id,
            login_phone=user.phone or "",
            temporary_password=temporary_password,
        )

    def to_admin_dto(
        self,
        partner: Partner,
        *,
        context: PartnerAdminContext | None = None,
    ) -> PartnerAdminRead:
        user = (
            context.users.get(partner.id)
            if context is not None
            else self._first_partner_user(partner.id)
        )
        category = None
        if partner.partner_category_id:
            category = (
                context.categories.get(partner.partner_category_id)
                if context is not None
                else self.categories.get(partner.partner_category_id)
            )
        counts = (
            context.counts.get(partner.id, empty_job_counts())
            if context is not None
            else self._job_counts(partner.id)
        )
        settlement = (
            context.settlements.get(partner.id, empty_settlement_summary())
            if context is not None
            else self._unpaid_settlement_summary(partner.id)
        )
        return PartnerAdminRead(
            id=partner.id,
            partner_category_id=partner.partner_category_id,
            partner_category_name=category.name if category else None,
            name=partner.name,
            manager_name=partner.manager_name,
            phone=partner.phone,
            service_areas=partner.service_areas,
            available_services=partner.available_services,
            memo=partner.memo,
            is_active=partner.is_active,
            created_at=partner.created_at,
            updated_at=partner.updated_at,
            scheduled_job_count=counts["scheduled"],
            active_job_count=counts["active"],
            completed_job_count=counts["completed"],
            unpaid_partner_amount_total=settlement["amount"],
            unpaid_partner_order_count=settlement["count"],
            user_id=user.id if user else None,
            login_phone=user.phone if user else None,
            user_is_active=user.is_active if user else None,
            last_login_at=user.last_login_at if user else None,
        )

    def to_category_dto(self, category: PartnerCategory) -> PartnerCategoryRead:
        return PartnerCategoryRead(
            id=category.id,
            name=category.name,
            description=category.description,
            is_active=category.is_active,
            sort_order=category.sort_order,
            partner_count=scalar_count(
                self.db,
                Partner.partner_category_id == category.id,
                model=Partner,
            ),
            created_at=category.created_at,
            updated_at=category.updated_at,
        )

    def _build_admin_context(self, partners: list[Partner]) -> PartnerAdminContext:
        partner_ids = [partner.id for partner in partners]
        if not partner_ids:
            return PartnerAdminContext()

        category_ids = {
            partner.partner_category_id
            for partner in partners
            if partner.partner_category_id
        }
        categories = (
            {
                category.id: category
                for category in self.db.scalars(
                    select(PartnerCategory).where(PartnerCategory.id.in_(category_ids))
                )
            }
            if category_ids
            else {}
        )

        users: dict[str, User] = {}
        user_stmt = (
            select(User)
            .where(User.partner_id.in_(partner_ids), User.role == UserRole.PARTNER)
            .order_by(User.partner_id.asc(), User.created_at.asc(), User.id.asc())
        )
        for user in self.db.scalars(user_stmt):
            if user.partner_id and user.partner_id not in users:
                users[user.partner_id] = user

        counts = {partner_id: empty_job_counts() for partner_id in partner_ids}
        count_stmt = (
            select(Order.partner_id, Order.status, func.count(Order.id))
            .where(Order.deleted_at.is_(None), Order.partner_id.in_(partner_ids))
            .group_by(Order.partner_id, Order.status)
        )
        for partner_id, status, count in self.db.execute(count_stmt):
            if partner_id is None:
                continue
            bucket = counts.setdefault(partner_id, empty_job_counts())
            value = int(count or 0)
            if status != OrderStatus.CANCELLED:
                bucket["scheduled"] += value
            if status in ACTIVE_JOB_STATUSES:
                bucket["active"] += value
            if status in COMPLETED_JOB_STATUSES:
                bucket["completed"] += value

        settlements = {
            partner_id: empty_settlement_summary()
            for partner_id in partner_ids
        }
        unpaid_condition = Order.partner_payment_status.is_(None) | Order.partner_payment_status.in_(
            PARTNER_SETTLEMENT_PENDING_STATUSES
        )
        settlement_stmt = (
            select(
                Order.partner_id,
                func.count(Order.id),
                func.coalesce(func.sum(Order.partner_payment_amount), 0),
            )
            .where(
                Order.deleted_at.is_(None),
                Order.partner_id.in_(partner_ids),
                Order.status == OrderStatus.COMPLETED,
                unpaid_condition,
            )
            .group_by(Order.partner_id)
        )
        for partner_id, count, amount in self.db.execute(settlement_stmt):
            if partner_id is None:
                continue
            settlements[partner_id] = {
                "amount": float(Decimal(str(amount or 0))),
                "count": int(count or 0),
            }

        return PartnerAdminContext(
            categories=categories,
            users=users,
            counts=counts,
            settlements=settlements,
        )

    def _upsert_partner_user(self, partner: Partner, *, login_phone: str, password: str) -> User:
        normalized_phone = normalize_phone(login_phone)
        user = self._first_partner_user(partner.id)
        # login_phone(=users.phone)은 유니크(migration 0012)다. 다른 사용자가 이미 쓰는 번호면
        # IntegrityError(500) 대신 명확한 400으로 막는다.
        self._ensure_login_phone_available(
            normalized_phone, exclude_user_id=user.id if user is not None else None
        )
        if user is None:
            user = User(
                id=str(uuid4()),
                role=UserRole.PARTNER,
                name=partner.manager_name or partner.name,
                email=None,
                phone=normalized_phone,
                password_hash=hash_password(password),
                partner_id=partner.id,
                is_active=partner.is_active,
            )
            self.db.add(user)
        else:
            user.name = partner.manager_name or partner.name
            user.phone = normalized_phone
            user.password_hash = hash_password(password)
        return user

    def _ensure_login_phone_available(
        self, phone: str | None, *, exclude_user_id: str | None = None
    ) -> None:
        if not phone:
            return
        stmt = select(User).where(User.phone == phone)
        if exclude_user_id is not None:
            stmt = stmt.where(User.id != exclude_user_id)
        if self.db.scalar(stmt.limit(1)) is not None:
            raise ValueError("login_phone_already_in_use")

    def _job_counts(self, partner_id: str) -> dict[str, int]:
        scheduled = scalar_count(
            self.db,
            Order.partner_id == partner_id,
            Order.status != OrderStatus.CANCELLED,
        )
        active = scalar_count(
            self.db,
            Order.partner_id == partner_id,
            Order.status.in_(ACTIVE_JOB_STATUSES),
        )
        completed = scalar_count(
            self.db,
            Order.partner_id == partner_id,
            Order.status.in_(COMPLETED_JOB_STATUSES),
        )
        return {"scheduled": scheduled, "active": active, "completed": completed}

    def _first_partner_user(self, partner_id: str) -> User | None:
        stmt = (
            select(User)
            .where(User.partner_id == partner_id, User.role == UserRole.PARTNER)
            .order_by(User.created_at.asc(), User.id.asc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def _list_partner_users(self, partner_id: str) -> list[User]:
        stmt = select(User).where(User.partner_id == partner_id, User.role == UserRole.PARTNER)
        return list(self.db.scalars(stmt))

    def _list_recent_jobs(self, partner_id: str) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.partner_id == partner_id, Order.deleted_at.is_(None))
            .order_by(Order.scheduled_date.desc().nulls_last(), Order.id.desc())
            .limit(20)
        )
        return list(self.db.scalars(stmt))

    def _unpaid_settlement_summary(self, partner_id: str) -> dict[str, float | int]:
        unpaid_condition = Order.partner_payment_status.is_(None) | Order.partner_payment_status.in_(
            PARTNER_SETTLEMENT_PENDING_STATUSES
        )
        stmt = select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.partner_payment_amount), 0),
        ).where(
            Order.partner_id == partner_id,
            Order.deleted_at.is_(None),
            Order.status == OrderStatus.COMPLETED,
            unpaid_condition,
        )
        count, amount = self.db.execute(stmt).one()
        return {
            "amount": float(Decimal(str(amount or 0))),
            "count": int(count or 0),
        }

    def _list_partners_by_category(self, category_id: str) -> list[Partner]:
        stmt = select(Partner).where(Partner.partner_category_id == category_id)
        return list(self.db.scalars(stmt))

    def _require_category(self, category_id: str | None) -> PartnerCategory | None:
        if not category_id:
            return None
        category = self.categories.get(category_id)
        if category is None:
            raise ValueError("partner_category_not_found")
        return category


def scalar_count(db: Session, *conditions, model=Order) -> int:
    stmt = select(func.count()).select_from(model)
    if model is Order:
        stmt = stmt.where(Order.deleted_at.is_(None))
    stmt = stmt.where(*conditions)
    return int(db.scalar(stmt) or 0)


def empty_job_counts() -> dict[str, int]:
    return {"scheduled": 0, "active": 0, "completed": 0}


def empty_settlement_summary() -> dict[str, float | int]:
    return {"amount": 0.0, "count": 0}


def to_assigned_order_dto(order: Order) -> PartnerAssignedOrderRead:
    return PartnerAssignedOrderRead(
        id=order.id,
        status=order.status,
        scheduled_date=order.scheduled_date,
        requested_time=order.requested_time,
        service_name=order.service_name,
        size_or_quantity=order.size_or_quantity,
        customer_name=order.customer_name,
        customer_address=order.customer_address,
        consumer_price=float(order.total_amount or 0),
        partner_price=float(order.partner_payment_amount or 0),
        partner_payment_status=order.partner_payment_status,
        settled_at=order.partner_settled_at,
    )


def generate_temporary_password() -> str:
    return f"Partner-{token_urlsafe(8)}1!"
