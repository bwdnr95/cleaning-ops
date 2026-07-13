from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import cast

import pytest
from sqlalchemy.orm import Session

import app.services.auth as auth_module
from app.core.config import settings
from app.core.security import create_refresh_token, hash_password, hash_token_jti
from app.domain.constants import UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository
from app.services.audit import AuditService
from app.services.auth import AuthError, AuthService


class FakeUserRepository:
    def __init__(self, user: User | None) -> None:
        self.user = user

    def get_by_identifier(self, identifier: str) -> User | None:
        if self.user is None:
            return None
        normalized = identifier.strip().lower()
        candidates = {
            value.strip().lower()
            for value in (self.user.email, self.user.phone)
            if value
        }
        return self.user if normalized in candidates else None

    def get(self, id_: str) -> User | None:
        if self.user and self.user.id == id_:
            return self.user
        return None


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self.added = []
        self.by_hash = {}
        self.revoked_user_ids = []
        self.consume_lock = Lock()
        self.consume_calls = 0

    def add(self, token):
        self.added.append(token)
        self.by_hash[token.token_hash] = token
        return token

    def get_by_hash(self, token_hash: str):
        return self.by_hash.get(token_hash)

    def consume_active(self, token_hash: str, revoked_at) -> bool:
        with self.consume_lock:
            self.consume_calls += 1
            token = self.by_hash.get(token_hash)
            if token is None or token.revoked_at is not None:
                return False
            token.revoked_at = revoked_at
            return True

    def revoke_active_for_user(self, user_id: str) -> None:
        self.revoked_user_ids.append(user_id)


class FakeAuditService:
    def __init__(self) -> None:
        self.records = []

    def record(self, **kwargs):
        self.records.append(kwargs)
        return kwargs


class FakeDb:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


def make_user(*, role: UserRole, partner_id: str | None = None, active: bool = True) -> User:
    return User(
        id="user-1",
        role=role,
        name="테스트",
        email="test@example.com",
        phone="01012345678",
        password_hash=hash_password("password"),
        partner_id=partner_id,
        is_active=active,
    )


def make_service(user: User | None) -> AuthService:
    service = AuthService.__new__(AuthService)
    service.db = cast(Session, cast(object, FakeDb()))
    service.users = cast(UserRepository, cast(object, FakeUserRepository(user)))
    service.refresh_tokens = cast(
        RefreshTokenRepository,
        cast(object, FakeRefreshTokenRepository()),
    )
    service.audit = cast(AuditService, cast(object, FakeAuditService()))
    return service


@pytest.fixture(autouse=True)
def reset_login_attempt_cache():
    with auth_module._login_attempts_lock:
        auth_module._login_attempts.clear()
    yield
    with auth_module._login_attempts_lock:
        auth_module._login_attempts.clear()


def test_admin_login_returns_token_and_user() -> None:
    service = make_service(make_user(role=UserRole.ADMIN))

    response = service.login(
        identifier="test@example.com",
        password="password",
        expected_role=UserRole.ADMIN,
    )

    assert response.token_type == "bearer"
    assert response.user.role == UserRole.ADMIN
    assert response.user.partner_id is None


def test_partner_login_requires_partner_scope() -> None:
    service = make_service(make_user(role=UserRole.PARTNER, partner_id=None))

    try:
        service.login(
            identifier="01012345678",
            password="password",
            expected_role=UserRole.PARTNER,
        )
    except AuthError as exc:
        assert str(exc) == "partner_scope_required"
    else:
        raise AssertionError("expected AuthError")


def test_login_rejects_wrong_role() -> None:
    service = make_service(make_user(role=UserRole.PARTNER, partner_id="partner-1"))

    try:
        service.login(
            identifier="test@example.com",
            password="password",
            expected_role=UserRole.ADMIN,
        )
    except AuthError as exc:
        assert str(exc) == "invalid_credentials"
    else:
        raise AssertionError("expected AuthError")


def test_login_attempt_reservation_is_atomic(monkeypatch) -> None:
    service = make_service(make_user(role=UserRole.ADMIN))
    login_key = "admin:user:user-1"
    monkeypatch.setattr(settings, "login_max_attempts", 2)

    def consume() -> str:
        try:
            service._consume_login_attempt(login_key)
        except AuthError as exc:
            return str(exc)
        return "allowed"

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: consume(), range(8)))

    assert results.count("allowed") == 2
    assert results.count("login_locked") == 6


def test_unknown_identifier_churn_cannot_evict_locked_account(monkeypatch) -> None:
    service = make_service(make_user(role=UserRole.ADMIN))
    monkeypatch.setattr(settings, "login_max_attempts", 2)
    monkeypatch.setattr(auth_module, "LOGIN_ATTEMPT_CACHE_MAX_ENTRIES", 2)

    for _ in range(2):
        with pytest.raises(AuthError, match="invalid_credentials"):
            service.login(
                identifier="test@example.com",
                password="wrong-password",
                expected_role=UserRole.ADMIN,
            )

    for index in range(20):
        try:
            service.login(
                identifier=f"unknown-{index}@example.com",
                password="wrong-password",
                expected_role=UserRole.ADMIN,
            )
        except AuthError:
            pass

    with pytest.raises(AuthError, match="login_locked"):
        service.login(
            identifier="test@example.com",
            password="password",
            expected_role=UserRole.ADMIN,
        )
    assert len(auth_module._login_attempts) <= 2


def test_login_failure_audit_records_supplied_peer_ip() -> None:
    service = make_service(make_user(role=UserRole.ADMIN))

    with pytest.raises(AuthError, match="invalid_credentials"):
        service.login(
            identifier="test@example.com",
            password="wrong-password",
            expected_role=UserRole.ADMIN,
            ip_address="127.0.0.1",
        )

    audit = cast(FakeAuditService, cast(object, service.audit))
    assert audit.records[-1]["ip_address"] == "127.0.0.1"


def test_refresh_rotates_refresh_token() -> None:
    user = make_user(role=UserRole.ADMIN)
    service = make_service(user)
    old_token, old_jti, old_expires_at = create_refresh_token(user_id=user.id, role=UserRole.ADMIN)
    old_record = RefreshToken(
        id="refresh-1",
        user_id=user.id,
        token_hash=hash_token_jti(old_jti),
        expires_at=old_expires_at,
        revoked_at=None,
    )
    service.refresh_tokens.add(old_record)

    response = service.refresh(old_token)

    assert response.refresh_token != old_token
    assert old_record.revoked_at is not None
    refresh_tokens = cast(FakeRefreshTokenRepository, cast(object, service.refresh_tokens))
    assert len(refresh_tokens.added) == 2


def test_refresh_rejects_reused_refresh_token() -> None:
    user = make_user(role=UserRole.ADMIN)
    service = make_service(user)
    old_token, old_jti, old_expires_at = create_refresh_token(user_id=user.id, role=UserRole.ADMIN)
    old_record = RefreshToken(
        id="refresh-1",
        user_id=user.id,
        token_hash=hash_token_jti(old_jti),
        expires_at=old_expires_at,
        revoked_at=old_expires_at,
    )
    service.refresh_tokens.add(old_record)

    try:
        service.refresh(old_token)
    except AuthError as exc:
        assert str(exc) == "refresh_token_reused"
    else:
        raise AssertionError("expected AuthError")


def test_parallel_refresh_consumes_token_only_once() -> None:
    user = make_user(role=UserRole.ADMIN)
    first = make_service(user)
    second = make_service(user)
    shared_tokens = cast(FakeRefreshTokenRepository, cast(object, first.refresh_tokens))
    second.refresh_tokens = cast(RefreshTokenRepository, cast(object, shared_tokens))
    old_token, old_jti, old_expires_at = create_refresh_token(
        user_id=user.id,
        role=UserRole.ADMIN,
    )
    shared_tokens.add(
        RefreshToken(
            id="refresh-parallel",
            user_id=user.id,
            token_hash=hash_token_jti(old_jti),
            expires_at=old_expires_at,
            revoked_at=None,
        )
    )

    def refresh(service: AuthService) -> str:
        try:
            service.refresh(old_token)
        except AuthError as exc:
            return str(exc)
        return "rotated"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(refresh, (first, second)))

    assert sorted(results) == ["refresh_token_reused", "rotated"]
    assert shared_tokens.consume_calls == 1


def test_change_password_revokes_existing_sessions() -> None:
    user = make_user(role=UserRole.ADMIN)
    service = make_service(user)

    response = service.change_password(
        user=user,
        current_password="password",
        new_password="new-password-123",
    )

    assert response.refresh_token
    refresh_tokens = cast(FakeRefreshTokenRepository, cast(object, service.refresh_tokens))
    db = cast(FakeDb, cast(object, service.db))
    assert refresh_tokens.revoked_user_ids == [user.id]
    assert db.commits == 1
