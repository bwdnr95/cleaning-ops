from datetime import timedelta
from uuid import uuid4

from app.core.security import hash_token_jti
from app.core.time import utc_now
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_tokens import RefreshTokenRepository


def test_consume_active_refresh_token_is_single_use(db_session, seed_admin_user: User) -> None:
    repository = RefreshTokenRepository(db_session)
    token = RefreshToken(
        id=str(uuid4()),
        user_id=seed_admin_user.id,
        token_hash=hash_token_jti(str(uuid4())),
        expires_at=utc_now() + timedelta(days=1),
        revoked_at=None,
    )
    repository.add(token)
    db_session.flush()
    revoked_at = utc_now()

    assert repository.consume_active(token.token_hash, revoked_at) is True
    assert repository.consume_active(token.token_hash, utc_now()) is False

    db_session.expire(token)
    assert token.revoked_at is not None
    assert token.revoked_at.replace(tzinfo=None) == revoked_at.replace(tzinfo=None)
