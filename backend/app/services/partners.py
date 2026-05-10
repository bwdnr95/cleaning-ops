from secrets import token_urlsafe
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.domain.constants import OrderStatus, UserRole
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
        return [self.to_admin_dto(partner) for partner in partners]

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

        if payload.login_phone or payload.login_password:
            self._upsert_partner_user(
                partner,
                login_phone=payload.login_phone or payload.phone,
                password=payload.login_password or generate_temporary_password(),
            )

        self.db.commit()
        return self.get_detail(partner.id)

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

        if "is_active" in changes and changes["is_active"] is False:
            for user in self._list_partner_users(partner_id):
                user.is_active = False
                self.refresh_tokens.revoke_active_for_user(user.id)
        elif "is_active" in changes and changes["is_active"] is True:
            for user in self._list_partner_users(partner_id):
                user.is_active = True

        self.db.commit()
        return self.get_detail(partner_id)

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
        self.db.commit()
        return PartnerPasswordResetRead(
            partner_id=partner.id,
            user_id=user.id,
            login_phone=user.phone or "",
            temporary_password=temporary_password,
        )

    def to_admin_dto(self, partner: Partner) -> PartnerAdminRead:
        user = self._first_partner_user(partner.id)
        category = (
            self.categories.get(partner.partner_category_id)
            if partner.partner_category_id
            else None
        )
        counts = self._job_counts(partner.id)
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

    def _upsert_partner_user(self, partner: Partner, *, login_phone: str, password: str) -> User:
        user = self._first_partner_user(partner.id)
        if user is None:
            user = User(
                id=str(uuid4()),
                role=UserRole.PARTNER,
                name=partner.manager_name or partner.name,
                email=None,
                phone=normalize_phone(login_phone),
                password_hash=hash_password(password),
                partner_id=partner.id,
                is_active=partner.is_active,
            )
            self.db.add(user)
        else:
            user.name = partner.manager_name or partner.name
            user.phone = normalize_phone(login_phone)
            user.password_hash = hash_password(password)
        return user

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
            .where(Order.partner_id == partner_id)
            .order_by(Order.scheduled_date.desc().nulls_last(), Order.id.desc())
            .limit(20)
        )
        return list(self.db.scalars(stmt))

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
    stmt = select(func.count()).select_from(model).where(*conditions)
    return int(db.scalar(stmt) or 0)


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
    )


def generate_temporary_password() -> str:
    return f"Partner-{token_urlsafe(8)}1!"
