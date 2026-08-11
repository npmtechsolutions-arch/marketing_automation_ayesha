from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None
    preferences: dict | None = None


class UserResponse(UserBase):
    id: UUID
    avatar_url: str | None = None
    is_active: bool
    email_verified: bool
    two_factor_enabled: bool = False
    preferences: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserWithToken(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResult(BaseModel):
    """Login response. When the account has 2FA enabled, only ``requires_2fa``
    and ``challenge_token`` are populated and the caller must complete the
    challenge via /auth/login/2fa. Otherwise the token fields are populated
    exactly like :class:`UserWithToken`.
    """

    requires_2fa: bool = False
    challenge_token: str | None = None
    user: UserResponse | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"


class TwoFactorLogin(BaseModel):
    challenge_token: str
    code: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class AccountDeletion(BaseModel):
    password: str


class PasswordReset(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class TokenRefresh(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Two-factor authentication
# ---------------------------------------------------------------------------

class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_code: str  # base64 PNG data URL


class TwoFactorEnable(BaseModel):
    code: str


class TwoFactorEnableResponse(BaseModel):
    recovery_codes: list[str]


class TwoFactorDisable(BaseModel):
    password: str


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


# ---------------------------------------------------------------------------
# Active sessions
# ---------------------------------------------------------------------------

class SessionResponse(BaseModel):
    id: UUID
    device: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None
    created_at: datetime
    last_active_at: datetime
    current: bool = False

    model_config = ConfigDict(from_attributes=True)
