"""User profile, preferences, two-factor auth, and session endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.security import (
    get_password_hash_async,
    oauth2_scheme,
    verify_password_async,
)
from app.models.user import User
from app.models.user_session import UserSession
from app.schemas.common import MessageResponse
from app.schemas.user import (
    AccountDeletion,
    PasswordChange,
    RecoveryCodesResponse,
    SessionResponse,
    TwoFactorDisable,
    TwoFactorEnable,
    TwoFactorEnableResponse,
    TwoFactorSetupResponse,
    UserResponse,
    UserUpdate,
)
from app.services import totp_service
from app.services.activity_service import log_activity

router = APIRouter(prefix="/users", tags=["Users"])


async def _primary_account_id(db: AsyncSession, user_id: uuid.UUID):
    """Resolve the user's primary account (for attaching user-level activity
    log entries so they show up in the account's Activity page). Prefers an
    owned membership, falling back to the earliest accepted membership.
    """
    from app.models.team_member import InvitationStatus, TeamMember, TeamRole

    result = await db.execute(
        select(TeamMember.account_id)
        .where(
            TeamMember.user_id == user_id,
            TeamMember.invitation_status == InvitationStatus.ACCEPTED,
        )
        .order_by((TeamMember.role == TeamRole.OWNER).desc(), TeamMember.created_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
):
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update the currently authenticated user's profile.

    full_name and avatar_url are set directly; preferences (a free-form JSON
    blob of notification/appearance settings) is *merged* into any existing
    preferences so partial updates don't clobber unrelated keys.
    """
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    preferences = update_data.pop("preferences", None)
    if preferences is not None:
        merged = dict(current_user.preferences or {})
        for k, v in preferences.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                sub = dict(merged[k])
                sub.update(v)
                merged[k] = sub
            else:
                merged[k] = v
        current_user.preferences = merged

    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.flush()
    await db.refresh(current_user)

    account_id = await _primary_account_id(db, current_user.id)
    changed = ", ".join(sorted({*update_data.keys(), *(["preferences"] if preferences else [])}))
    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="settings.profile_updated",
        category="settings",
        description=f"Updated account settings ({changed})" if changed else "Updated account settings",
        resource_type="user",
        resource_id=str(current_user.id),
    )

    return UserResponse.model_validate(current_user)


@router.post("/me/change-password", response_model=MessageResponse)
async def change_password(
    payload: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Change the current user's password.

    Requires the current password for verification.
    """
    if not await verify_password_async(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )

    current_user.password_hash = await get_password_hash_async(payload.new_password)
    await db.flush()

    account_id = await _primary_account_id(db, current_user.id)
    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="settings.password_changed",
        category="settings",
        description="Changed account password",
        resource_type="user",
        resource_id=str(current_user.id),
    )

    return MessageResponse(message="Password updated successfully")


@router.delete("/me", response_model=MessageResponse)
async def delete_current_user(
    payload: AccountDeletion,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Soft-delete the current user account.

    Requires the current password for verification. Sets the deleted_at
    timestamp, deactivates the user, and deactivates any accounts the user
    owns. Records are retained (soft delete) for data integrity and any
    legally required retention period.
    """
    if not await verify_password_async(payload.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect",
        )

    now = datetime.now(timezone.utc)

    current_user.deleted_at = now
    current_user.is_active = False

    # Deactivate any accounts (workspaces) this user owns.
    from sqlalchemy import select

    from app.models.account import Account

    result = await db.execute(
        select(Account).where(Account.owner_id == current_user.id)
    )
    for account in result.scalars().all():
        if hasattr(account, "deleted_at"):
            account.deleted_at = now

    await db.flush()

    return MessageResponse(message="Account has been deleted")


# ---------------------------------------------------------------------------
# Two-factor authentication (TOTP)
# ---------------------------------------------------------------------------

@router.post("/me/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_two_factor(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Begin 2FA enrollment: generate a pending secret + QR code.

    The secret is stored as ``totp_pending_secret`` and is not active until the
    user confirms a valid code via ``/me/2fa/enable``.
    """
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is already enabled.",
        )

    secret = totp_service.generate_secret()
    current_user.totp_pending_secret = secret
    await db.flush()

    return TwoFactorSetupResponse(
        secret=secret,
        otpauth_uri=totp_service.provisioning_uri(secret, current_user.email),
        qr_code=totp_service.qr_data_url(secret, current_user.email),
    )


@router.post("/me/2fa/enable", response_model=TwoFactorEnableResponse)
async def enable_two_factor(
    payload: TwoFactorEnable,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Confirm a code against the pending secret and turn 2FA on.

    Returns one-time recovery codes (shown to the user once).
    """
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is already enabled.",
        )
    if not current_user.totp_pending_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start 2FA setup first.",
        )
    if not totp_service.verify_code(current_user.totp_pending_secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. Try again.",
        )

    plaintext, hashed = totp_service.generate_recovery_codes()
    current_user.totp_secret = current_user.totp_pending_secret
    current_user.totp_pending_secret = None
    current_user.two_factor_enabled = True
    current_user.totp_recovery_codes = hashed
    await db.flush()

    account_id = await _primary_account_id(db, current_user.id)
    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="settings.2fa_enabled",
        category="settings",
        description="Enabled two-factor authentication",
        resource_type="user",
        resource_id=str(current_user.id),
    )

    return TwoFactorEnableResponse(recovery_codes=plaintext)


@router.post("/me/2fa/disable", response_model=MessageResponse)
async def disable_two_factor(
    payload: TwoFactorDisable,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Disable 2FA. Requires the account password to confirm."""
    if not await verify_password_async(payload.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect",
        )

    current_user.two_factor_enabled = False
    current_user.totp_secret = None
    current_user.totp_pending_secret = None
    current_user.totp_recovery_codes = None
    await db.flush()

    account_id = await _primary_account_id(db, current_user.id)
    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="settings.2fa_disabled",
        category="settings",
        description="Disabled two-factor authentication",
        resource_type="user",
        resource_id=str(current_user.id),
        status="warning",
    )

    return MessageResponse(message="Two-factor authentication disabled")


@router.post("/me/2fa/recovery-codes", response_model=RecoveryCodesResponse)
async def regenerate_recovery_codes(
    payload: TwoFactorDisable,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Regenerate recovery codes (invalidates old ones). Requires password."""
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not enabled.",
        )
    if not await verify_password_async(payload.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect",
        )

    plaintext, hashed = totp_service.generate_recovery_codes()
    current_user.totp_recovery_codes = hashed
    await db.flush()

    return RecoveryCodesResponse(recovery_codes=plaintext)


# ---------------------------------------------------------------------------
# Active sessions
# ---------------------------------------------------------------------------

@router.get("/me/sessions", response_model=list[SessionResponse])
async def list_sessions(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List active (non-revoked) login sessions for the current user."""
    from app.core.security import decode_token

    current_sid = None
    try:
        current_sid = decode_token(token).get("sid")
    except Exception:
        current_sid = None

    result = await db.execute(
        select(UserSession)
        .where(
            UserSession.user_id == current_user.id,
            UserSession.revoked.is_(False),
        )
        .order_by(UserSession.last_active_at.desc())
    )
    sessions = result.scalars().all()

    return [
        SessionResponse(
            id=s.id,
            device=s.device,
            user_agent=s.user_agent,
            ip_address=s.ip_address,
            created_at=s.created_at,
            last_active_at=s.last_active_at,
            current=(current_sid is not None and str(s.refresh_jti) == str(current_sid)),
        )
        for s in sessions
    ]


@router.delete("/me/sessions/{session_id}", response_model=MessageResponse)
async def revoke_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Revoke a session so its refresh token can no longer be used."""
    result = await db.execute(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    session.revoked = True
    await db.flush()

    account_id = await _primary_account_id(db, current_user.id)
    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="settings.session_revoked",
        category="settings",
        description="Revoked an active login session",
        resource_type="session",
        resource_id=str(session_id),
        status="warning",
    )

    return MessageResponse(message="Session revoked")
