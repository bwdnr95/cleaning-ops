from collections import defaultdict
from datetime import UTC, datetime, timedelta
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
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository
from app.schemas.auth import AuthUserRead, LoginResponse
from app.services.audit import AuditService


class AuthError(ValueError):
    pass


_login_attempts: dict[str, dict] = defaultdict(lambda: {"count": 0, "locked_until": None})


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
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
        login_key = f"{expected_role.value}:{identifier.strip().lower()}"
        self._check_lockout(login_key)
        user = self.users.get_by_identifier(identifier)
        if (
            user is None
            or not user.is_active
            or self._role(user) != expected_role
            or not verify_password(password, user.password_hash)
        ):
            self._record_failure(login_key)
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
            self._record_failure(login_key)
            raise AuthError("partner_scope_required")

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

        token_record.revoked_at = utc_now()
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
            user=to_auth_user_dto(user),
        )

    def _decode_refresh_payload(self, token: str) -> dict:
        try:
            payload = decode_token(token, expected_type="refresh")
        except TokenError as exc:
            raise AuthError("invalid_refresh_token") from exc
        if not payload.get("sub") or not payload.get("jti"):
            raise AuthError("invalid_refresh_token")
        return payload

    def _check_lockout(self, login_key: str) -> None:
        attempt = _login_attempts.get(login_key)
        if not attempt or not attempt["locked_until"]:
            return
        if utc_now() < attempt["locked_until"]:
            raise AuthError("login_locked")
        _login_attempts[login_key] = {"count": 0, "locked_until": None}

    def _record_failure(self, login_key: str) -> None:
        attempt = _login_attempts[login_key]
        attempt["count"] += 1
        if attempt["count"] >= settings.login_max_attempts:
            attempt["locked_until"] = utc_now() + timedelta(minutes=settings.login_lockout_minutes)

    def _reset_failures(self, login_key: str) -> None:
        _login_attempts.pop(login_key, None)

    def _role(self, user: User) -> UserRole:
        return user.role if isinstance(user.role, UserRole) else UserRole(str(user.role))


def to_auth_user_dto(user: User) -> AuthUserRead:
    role = user.role if isinstance(user.role, UserRole) else UserRole(str(user.role))
    return AuthUserRead(
        id=user.id,
        role=role,
        name=user.name,
        email=user.email,
        phone=user.phone,
        partner_id=user.partner_id,
    )


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
