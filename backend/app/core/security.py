import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import settings
from app.domain.constants import UserRole


class TokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    *,
    user_id: str,
    role: UserRole,
    partner_id: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    expires_at = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_ttl_minutes)
    )
    payload = {
        "sub": user_id,
        "type": "access",
        "role": role.value,
        "partner_id": partner_id,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    *,
    user_id: str,
    role: UserRole,
    expires_delta: timedelta | None = None,
) -> tuple[str, str, datetime]:
    ttl_days = (
        settings.partner_refresh_token_ttl_days
        if role == UserRole.PARTNER
        else settings.admin_refresh_token_ttl_days
    )
    expires_at = datetime.now(UTC) + (expires_delta or timedelta(days=ttl_days))
    jti = secrets.token_urlsafe(32)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": jti,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except ExpiredSignatureError as exc:
        raise TokenError("token_expired") from exc
    except JWTError as exc:
        raise TokenError("invalid_token") from exc

    if expected_type is not None and payload.get("type") != expected_type:
        raise TokenError(f"{expected_type}_token_required")
    if not payload.get("sub"):
        raise TokenError("invalid_claims")

    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    payload = decode_token(token, expected_type="access")
    if payload.get("role") not in {role.value for role in UserRole}:
        raise TokenError("invalid_claims")
    return payload


def hash_token_jti(jti: str) -> str:
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()
