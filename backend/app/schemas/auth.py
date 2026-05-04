from app.domain.constants import UserRole
from app.schemas.common import ApiModel


class LoginRequest(ApiModel):
    identifier: str
    password: str


class AuthUserRead(ApiModel):
    id: str
    role: UserRole
    name: str
    email: str | None = None
    phone: str | None = None
    partner_id: str | None = None


class LoginResponse(ApiModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: AuthUserRead


class RefreshRequest(ApiModel):
    refresh_token: str


class LogoutRequest(ApiModel):
    refresh_token: str


class ChangePasswordRequest(ApiModel):
    current_password: str
    new_password: str
