from app.core.security import create_refresh_token, hash_password, hash_token_jti
from app.domain.constants import UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.auth import AuthError, AuthService


class FakeUserRepository:
    def __init__(self, user: User | None) -> None:
        self.user = user

    def get_by_identifier(self, identifier: str) -> User | None:
        return self.user

    def get(self, id_: str) -> User | None:
        if self.user and self.user.id == id_:
            return self.user
        return None


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self.added = []
        self.by_hash = {}
        self.revoked_user_ids = []

    def add(self, token):
        self.added.append(token)
        self.by_hash[token.token_hash] = token
        return token

    def get_by_hash(self, token_hash: str):
        return self.by_hash.get(token_hash)

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
    service.db = FakeDb()
    service.users = FakeUserRepository(user)
    service.refresh_tokens = FakeRefreshTokenRepository()
    service.audit = FakeAuditService()
    return service


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
    assert len(service.refresh_tokens.added) == 2


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


def test_change_password_revokes_existing_sessions() -> None:
    user = make_user(role=UserRole.ADMIN)
    service = make_service(user)

    response = service.change_password(
        user=user,
        current_password="password",
        new_password="new-password-123",
    )

    assert response.refresh_token
    assert service.refresh_tokens.revoked_user_ids == [user.id]
    assert service.db.commits == 1
