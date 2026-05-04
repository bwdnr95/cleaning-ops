from datetime import timedelta

import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.domain.constants import UserRole


def test_password_hash_roundtrip_and_wrong_password_rejected() -> None:
    password_hash = hash_password("correct-password")

    assert password_hash != "correct-password"
    assert verify_password("correct-password", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_access_token_roundtrip() -> None:
    token = create_access_token(
        user_id="user-1",
        role=UserRole.PARTNER,
        partner_id="partner-1",
    )

    payload = decode_access_token(token)

    assert payload["sub"] == "user-1"
    assert payload["role"] == "partner"
    assert payload["partner_id"] == "partner-1"


def test_access_token_rejects_tampering() -> None:
    token = create_access_token(user_id="user-1", role=UserRole.ADMIN)
    tampered = token[:-2] + "xx"

    with pytest.raises(TokenError):
        decode_access_token(tampered)


def test_access_token_rejects_expired_token() -> None:
    token = create_access_token(
        user_id="user-1",
        role=UserRole.ADMIN,
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(TokenError, match="token_expired"):
        decode_access_token(token)
