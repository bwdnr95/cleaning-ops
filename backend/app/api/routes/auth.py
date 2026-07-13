from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin, require_partner
from app.domain.constants import UserRole
from app.repositories.users import UserRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
)
from app.services.auth import AuthError, AuthService

router = APIRouter()


@router.post("/admin/login", response_model=LoginResponse)
def admin_login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_session),
) -> LoginResponse:
    return _login(payload, request, db, expected_role=UserRole.ADMIN)


@router.post("/partner/login", response_model=LoginResponse)
def partner_login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_session),
) -> LoginResponse:
    return _login(payload, request, db, expected_role=UserRole.PARTNER)


@router.post("/refresh", response_model=LoginResponse)
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_session)) -> LoginResponse:
    try:
        return AuthService(db).refresh(payload.refresh_token)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/logout")
def logout(payload: LogoutRequest, db: Session = Depends(get_session)) -> dict[str, str]:
    AuthService(db).logout(payload.refresh_token)
    return {"message": "logout_complete"}


@router.post("/admin/change-password", response_model=LoginResponse)
def admin_change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_session),
    current_user: CurrentUser = Depends(require_admin),
) -> LoginResponse:
    return _change_password(payload, request, db, current_user)


@router.post("/partner/change-password", response_model=LoginResponse)
def partner_change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_session),
    current_user: CurrentUser = Depends(require_partner),
) -> LoginResponse:
    return _change_password(payload, request, db, current_user)


def _login(
    payload: LoginRequest,
    request: Request,
    db: Session,
    *,
    expected_role: UserRole,
) -> LoginResponse:
    try:
        return AuthService(db).login(
            identifier=payload.identifier,
            password=payload.password,
            expected_role=expected_role,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AuthError as exc:
        detail = str(exc)
        if detail == "login_locked":
            detail = "invalid_credentials"
        status_code = (
            status.HTTP_403_FORBIDDEN
            if detail == "partner_scope_required"
            else status.HTTP_401_UNAUTHORIZED
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc


def _change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session,
    current_user: CurrentUser,
) -> LoginResponse:
    user = UserRepository(db).get(current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found")
    try:
        return AuthService(db).change_password(
            user=user,
            current_password=payload.current_password,
            new_password=payload.new_password,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
