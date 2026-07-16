"""Authentication endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
    create_password_reset_token,
    verify_password_reset_token,
)
from app.models.account import Account, SubscriptionStatus, SubscriptionTier
from app.models.team_member import InvitationStatus, TeamMember, TeamRole
from app.models.user import User
from app.services.email_service import EmailService
from app.schemas.common import MessageResponse
from app.schemas.user import (
    PasswordReset,
    PasswordResetConfirm,
    TokenRefresh,
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


@router.post(
    "/register",
    response_model=UserWithToken,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: UserCreate,
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
        password_hash=get_password_hash(payload.password),
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

    # Generate tokens
    token_data = {"sub": str(user.id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return UserWithToken(
        user=UserResponse.model_validate(user),
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=UserWithToken)
async def login(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate a user and return access/refresh tokens."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
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

    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    token_data = {"sub": str(user.id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return UserWithToken(
        user=UserResponse.model_validate(user),
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=UserWithToken)
async def refresh_token(
    payload: TokenRefresh,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a valid refresh token for new access and refresh tokens."""
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

    token_data = {"sub": str(user.id)}
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    return UserWithToken(
        user=UserResponse.model_validate(user),
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )


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

    user.password_hash = get_password_hash(payload.new_password)
    db.add(user)

    return MessageResponse(message="Password has been reset successfully")

