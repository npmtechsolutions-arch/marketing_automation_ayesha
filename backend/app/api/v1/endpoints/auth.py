"""Authentication endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.security import (
    create_2fa_challenge_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash_async,
    verify_2fa_challenge_token,
    verify_password_async,
    create_password_reset_token,
    verify_password_reset_token,
)
from app.models.account import Account, SubscriptionStatus, SubscriptionTier
from app.models.team_member import InvitationStatus, TeamMember, TeamRole
from app.models.user import User
from app.models.user_session import UserSession
from app.services import totp_service
from app.services.email_service import EmailService
from app.schemas.common import MessageResponse
from app.schemas.user import (
    LoginResult,
    PasswordReset,
    PasswordResetConfirm,
    TokenRefresh,
    TwoFactorLogin,
    UserCreate,
    UserLogin,
    UserResponse,
    UserWithToken,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a name."""
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{slug}-{uuid.uuid4().hex[:8]}"


def _device_from_user_agent(ua: str | None) -> str:
    """Derive a short, human-friendly device label from a User-Agent string."""
    if not ua:
        return "Unknown device"
    ua_l = ua.lower()
    if "iphone" in ua_l:
        os_name = "iPhone"
    elif "ipad" in ua_l:
        os_name = "iPad"
    elif "android" in ua_l:
        os_name = "Android"
    elif "windows" in ua_l:
        os_name = "Windows"
    elif "mac os" in ua_l or "macintosh" in ua_l:
        os_name = "macOS"
    elif "linux" in ua_l:
        os_name = "Linux"
    else:
        os_name = "Unknown OS"

    if "edg/" in ua_l:
        browser = "Edge"
    elif "chrome" in ua_l and "chromium" not in ua_l:
        browser = "Chrome"
    elif "firefox" in ua_l:
        browser = "Firefox"
    elif "safari" in ua_l:
        browser = "Safari"
    else:
        browser = "Browser"
    return f"{browser} on {os_name}"


async def _issue_session_tokens(
    db: AsyncSession, user: User, request: Request | None
) -> UserWithToken:
    """Create a UserSession row and return access/refresh tokens bound to it.

    Both tokens carry the session id (``sid``); the refresh token's id is used
    to revoke the session later. Called only after full authentication.
    """
    session_id = uuid.uuid4()
    sid = session_id.hex

    ua = request.headers.get("user-agent") if request else None
    ip = None
    if request is not None:
        fwd = request.headers.get("x-forwarded-for")
        ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)

    db.add(
        UserSession(
            id=session_id,
            user_id=user.id,
            refresh_jti=sid,
            device=_device_from_user_agent(ua),
            user_agent=ua,
            ip_address=ip,
        )
    )
    await db.flush()

    token_data = {"sub": str(user.id), "sid": sid}
    return UserWithToken(
        user=UserResponse.model_validate(user),
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post(
    "/register",
    response_model=UserWithToken,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account.

    Creates the user, a default account, and an owner team membership.
    """
    # Check for existing email
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    # Create user
    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        full_name=payload.full_name,
        password_hash=await get_password_hash_async(payload.password),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Create default account
    account = Account(
        id=uuid.uuid4(),
        name=f"{payload.full_name}'s Workspace",
        slug=_generate_slug(payload.full_name),
        owner_id=user.id,
        subscription_tier=SubscriptionTier.FREE,
        subscription_status=SubscriptionStatus.TRIALING,
    )
    db.add(account)
    await db.flush()

    # Create owner team membership
    team_member = TeamMember(
        id=uuid.uuid4(),
        user_id=user.id,
        account_id=account.id,
        role=TeamRole.OWNER,
        invitation_status=InvitationStatus.ACCEPTED,
        accepted_at=datetime.now(timezone.utc),
    )
    db.add(team_member)
    await db.flush()

    # Generate tokens (register never requires 2FA — it's a brand new account)
    return await _issue_session_tokens(db, user, request)


@router.post("/login", response_model=LoginResult)
async def login(
    payload: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate a user.

    If the account has 2FA enabled, returns a short-lived challenge token that
    must be completed via ``/auth/login/2fa``. Otherwise returns tokens.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not await verify_password_async(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deleted",
        )

    # Password OK. If 2FA is on, defer token issuance to the 2FA step.
    if user.two_factor_enabled:
        return LoginResult(
            requires_2fa=True,
            challenge_token=create_2fa_challenge_token(str(user.id)),
        )

    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)

    tokens = await _issue_session_tokens(db, user, request)
    return LoginResult(
        requires_2fa=False,
        user=tokens.user,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post("/login/2fa", response_model=LoginResult)
async def login_2fa(
    payload: TwoFactorLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Complete a 2FA login using a TOTP code or a recovery code."""
    user_id = verify_2fa_challenge_token(payload.challenge_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your verification session expired. Please sign in again.",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not verify your account.",
        )

    code = (payload.code or "").strip()
    verified = totp_service.verify_code(user.totp_secret, code)

    # Fall back to consuming a one-time recovery code.
    if not verified:
        remaining = totp_service.consume_recovery_code(
            code, user.totp_recovery_codes or []
        )
        if remaining is not None:
            user.totp_recovery_codes = remaining
            verified = True

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code.",
        )

    user.last_login_at = datetime.now(timezone.utc)
    tokens = await _issue_session_tokens(db, user, request)
    return LoginResult(
        requires_2fa=False,
        user=tokens.user,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post("/refresh", response_model=UserWithToken)
async def refresh_token(
    payload: TokenRefresh,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a valid refresh token for new access and refresh tokens.

    If the token is bound to a session (carries ``sid``), the session must
    still exist and not be revoked. Legacy tokens without a ``sid`` are
    accepted for backward compatibility.
    """
    token_payload = decode_token(payload.refresh_token)

    if token_payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type: expected refresh token",
        )

    user_id = token_payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Session enforcement: if this token is bound to a session, honor revocation.
    sid = token_payload.get("sid")
    session = None
    if sid:
        session_result = await db.execute(
            select(UserSession).where(UserSession.refresh_jti == sid)
        )
        session = session_result.scalar_one_or_none()
        if session is not None and session.revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This session has been revoked. Please sign in again.",
            )
        if session is not None:
            session.last_active_at = datetime.now(timezone.utc)

    token_data = {"sub": str(user.id)}
    if sid:
        token_data["sid"] = sid
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)
    await db.flush()

    return UserWithToken(
        user=UserResponse.model_validate(user),
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )


@router.get("/me", response_model=UserResponse)
async def get_auth_me(
    current_user: User = Depends(get_current_active_user),
):
    """Return current authenticated user profile."""
    return UserResponse.model_validate(current_user)


@router.post("/logout", response_model=MessageResponse)
async def logout():
    """Log out the current user.

    Note: Full token blacklisting requires a Redis-backed token store.
    This is a placeholder that acknowledges the logout request.
    """
    return MessageResponse(message="Successfully logged out")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: PasswordReset,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset email."""
    # Look up user (but always return success to prevent enumeration)
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is not None and user.is_active:
        token = create_password_reset_token(user.email)
        EmailService.send_password_reset_email(user.email, token)

    return MessageResponse(
        message="If an account with that email exists, a reset link has been sent"
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """Reset the password using a valid reset token."""
    email = verify_password_reset_token(payload.token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found or inactive",
        )

    user.password_hash = await get_password_hash_async(payload.new_password)
    db.add(user)

    return MessageResponse(message="Password has been reset successfully")

