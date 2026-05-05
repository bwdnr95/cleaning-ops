from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TokenError, decode_access_token
from app.db.session import get_db
from app.domain.constants import UserRole
from app.repositories.partners import PartnerRepository
from app.repositories.users import UserRepository


@dataclass(frozen=True)
class CurrentUser:
    id: str
    role: UserRole
    partner_id: str | None = None


bearer_scheme = HTTPBearer(auto_error=False)


def get_session(db: Session = Depends(get_db)) -> Session:
    return db


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_session),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = UserRepository(db).get(str(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found")
    if user.role == UserRole.PARTNER:
        partner = PartnerRepository(db).get(user.partner_id or "")
        if partner is None or not partner.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found")

    return CurrentUser(id=user.id, role=user.role, partner_id=user.partner_id)


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_required")
    return user


def require_partner(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != UserRole.PARTNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="partner_required")
    return user


def ensure_partner_scope(user: CurrentUser) -> str:
    if user.partner_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="partner_scope_required")
    return user.partner_id
