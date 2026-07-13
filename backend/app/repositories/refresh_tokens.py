from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken
from app.repositories.base import Repository


class RefreshTokenRepository(Repository[RefreshToken]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, RefreshToken)

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return self.db.scalar(stmt)

    def consume_active(self, token_hash: str, revoked_at: datetime) -> bool:
        """Atomically revoke a token only if no other request consumed it first."""
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
            .execution_options(synchronize_session=False)
        )
        result = self.db.execute(stmt)
        return result.rowcount == 1

    def revoke_active_for_user(self, user_id: str) -> None:
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        for token in self.db.scalars(stmt):
            from app.core.time import utc_now

            token.revoked_at = utc_now()
