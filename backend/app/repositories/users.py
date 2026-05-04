from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.domain.phone import normalize_phone
from app.models.user import User
from app.repositories.base import Repository


class UserRepository(Repository[User]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, User)

    def get_by_identifier(self, identifier: str) -> User | None:
        email = identifier.strip().lower()
        phone = normalize_phone(identifier)
        stmt = select(User).where(
            or_(
                func.lower(User.email) == email if email else False,
                User.phone == phone if phone else False,
            )
        )
        return self.db.scalar(stmt)
