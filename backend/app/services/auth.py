from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import TypedDict
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token_jti,
    verify_password,
)
from app.core.time import utc_now
from app.domain.constants import AuditEventType, AuditSeverity, UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.partners import PartnerRepository
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository
from app.schemas.auth import AuthUserRead, LoginResponse
from app.services.audit import AuditService


class AuthError(ValueError):
    pass


LOGIN_ATTEMPT_CACHE_MAX_ENTRIES = 10_000


class LoginAttempt(TypedDict):
    count: int
    locked_until: datetime | None


_login_attempts: OrderedDict[str, LoginAttempt] = OrderedDict()
_login_attempts_lock = Lock()
_dummy_password_hash = hash_password("not-a-real-cleaning-ops-password")


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.partners = PartnerRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)
        self.audit = AuditService(db)

    def login(
        self,
        *,
        identifier: str,
        password: str,
        expected_role: UserRole,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LoginResponse:
        user = self.users.get_by_identifier(identifier)
        login_key = (
            f"{expected_role.value}:user:{user.id}"
            if user is not None
            else f"{expected_role.value}:unknown"
        )
        password_hash = user.password_hash if user is not None else _dummy_password_hash
        try:
            self._consume_login_attempt(login_key)
        except AuthError:
            verify_password(password, password_hash)
            raise
        is_password_valid = verify_password(password, password_hash)
        if (
            user is None
            or not user.is_active
            or self._role(user) != expected_role
            or not is_password_valid
        ):
            self.audit.record(
                event_type=AuditEventType.LOGIN_FAILURE,
                severity=AuditSeverity.WARNING,
                user_id=user.id if user is not None else None,
                ip_address=ip_address,
                user_agent=user_agent,
                details={"identifier": identifier, "expected_role": expected_role.value},
            )
            self.db.commit()
            raise AuthError("invalid_credentials")

        if expected_role == UserRole.PARTNER and user.partner_id is None:
            raise AuthError("partner_scope_required")
        if expected_role == UserRole.PARTNER and not self._partner_is_active(user.partner_id):
            raise AuthError("invalid_credentials")

        self._reset_failures(login_key)
        response = self._issue_token_pair(user)
        user.last_login_at = utc_now()
        self.audit.record(
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"role": expected_role.value},
        )
        self.db.commit()
        return response

    def refresh(self, refresh_token: str) -> LoginResponse:
        payload = self._decode_refresh_payload(refresh_token)
        user_id = str(payload["sub"])
        jti = str(payload["jti"])
        token_hash = hash_token_jti(jti)
        token_record = self.refresh_tokens.get_by_hash(token_hash)
        if token_record is None or token_record.user_id != user_id:
            raise AuthError("invalid_refresh_token")
        if token_record.revoked_at is not None:
            raise AuthError("refresh_token_reused")
        if _as_aware_utc(token_record.expires_at) < utc_now():
            raise AuthError("refresh_token_expired")

        user = self.users.get(user_id)
        if user is None or not user.is_active:
            raise AuthError("invalid_refresh_token")
        if self._role(user) == UserRole.PARTNER and not self._partner_is_active(user.partner_id):
            raise AuthError("invalid_refresh_token")

        if not self.refresh_tokens.consume_active(token_hash, utc_now()):
            raise AuthError("refresh_token_reused")
        response = self._issue_token_pair(user)
        self.audit.record(
            event_type=AuditEventType.TOKEN_REFRESH,
            user_id=user.id,
            details={"rotated": True},
        )
        self.db.commit()
        return response

    def logout(self, refresh_token: str) -> None:
        try:
            payload = self._decode_refresh_payload(refresh_token)
        except AuthError:
            return

        token_record = self.refresh_tokens.get_by_hash(hash_token_jti(str(payload["jti"])))
        if token_record is not None and token_record.revoked_at is None:
            token_record.revoked_at = utc_now()
            self.audit.record(
                event_type=AuditEventType.LOGOUT,
                user_id=token_record.user_id,
            )
            self.db.commit()

    def change_password(
        self,
        *,
        user: User,
        current_password: str,
        new_password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LoginResponse:
        if not verify_password(current_password, user.password_hash):
            raise AuthError("invalid_current_password")
        if current_password == new_password:
            raise AuthError("password_reuse")
        if len(new_password) < 10:
            raise AuthError("weak_password")

        user.password_hash = hash_password(new_password)
        self.refresh_tokens.revoke_active_for_user(user.id)
        response = self._issue_token_pair(user)
        self.audit.record(
            event_type=AuditEventType.PASSWORD_CHANGE,
            severity=AuditSeverity.WARNING,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.commit()
        return response

    def _issue_token_pair(self, user: User) -> LoginResponse:
        role = self._role(user)
        refresh_token, jti, expires_at = create_refresh_token(user_id=user.id, role=role)
        self.refresh_tokens.add(
            RefreshToken(
                id=str(uuid4()),
                user_id=user.id,
                token_hash=hash_token_jti(jti),
                expires_at=expires_at,
                revoked_at=None,
            )
        )
        return LoginResponse(
            access_token=create_access_token(
                user_id=user.id,
                role=role,
                partner_id=user.partner_id,
            ),
            refresh_token=refresh_token,
            user=to_auth_user_dto(user, partner_name=self._partner_name_for(user)),
        )

    def _partner_name_for(self, user: User) -> str | None:
        if not user.partner_id:
            return None
        partner = PartnerRepository(self.db).get(user.partner_id)
        return partner.name if partner else None

    def _decode_refresh_payload(self, token: str) -> dict[str, object]:
        try:
            payload = decode_token(token, expected_type="refresh")
        except TokenError as exc:
            raise AuthError("invalid_refresh_token") from exc
        if not payload.get("sub") or not payload.get("jti"):
            raise AuthError("invalid_refresh_token")
        return payload

    def _consume_login_attempt(self, login_key: str) -> None:
        now = utc_now()
        max_attempts = max(settings.login_max_attempts, 1)
        with _login_attempts_lock:
            attempt = _login_attempts.get(login_key)
            if attempt is not None and attempt["locked_until"] is not None:
                if now < attempt["locked_until"]:
                    _login_attempts.move_to_end(login_key)
                    raise AuthError("login_locked")
                del _login_attempts[login_key]
                attempt = None

            if attempt is None:
                self._make_room_for_login_attempt(now)
                attempt = LoginAttempt(count=0, locked_until=None)
                _login_attempts[login_key] = attempt

            if attempt["count"] >= max_attempts:
                attempt["locked_until"] = now + timedelta(minutes=settings.login_lockout_minutes)
                _login_attempts.move_to_end(login_key)
                raise AuthError("login_locked")

            attempt["count"] += 1
            if attempt["count"] >= max_attempts:
                attempt["locked_until"] = now + timedelta(minutes=settings.login_lockout_minutes)
            _login_attempts.move_to_end(login_key)

    def _make_room_for_login_attempt(self, now: datetime) -> None:
        if len(_login_attempts) < LOGIN_ATTEMPT_CACHE_MAX_ENTRIES:
            return
        for key, attempt in _login_attempts.items():
            locked_until = attempt["locked_until"]
            if locked_until is None or locked_until <= now:
                del _login_attempts[key]
                return
        # Preserve every active lockout. Saturation fails closed instead of
        # silently releasing a protected account for another password guess.
        raise AuthError("login_locked")

    def _reset_failures(self, login_key: str) -> None:
        with _login_attempts_lock:
            _login_attempts.pop(login_key, None)

    def _role(self, user: User) -> UserRole:
        return user.role if isinstance(user.role, UserRole) else UserRole(str(user.role))

    def _partner_is_active(self, partner_id: str | None) -> bool:
        if partner_id is None:
            return False
        partner = self.partners.get(partner_id)
        return bool(partner and partner.is_active)


def to_auth_user_dto(user: User, *, partner_name: str | None = None) -> AuthUserRead:
    role = user.role if isinstance(user.role, UserRole) else UserRole(str(user.role))
    return AuthUserRead(
        id=user.id,
        role=role,
        name=user.name,
        email=user.email,
        phone=user.phone,
        partner_id=user.partner_id,
        partner_name=partner_name,
    )


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
