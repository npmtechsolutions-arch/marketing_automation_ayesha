"""User profile endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.user import (
    AccountDeletion,
    PasswordChange,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["Users"])


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

    Only full_name and avatar_url can be changed via this endpoint.
    """
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.flush()
    await db.refresh(current_user)

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
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )

    current_user.password_hash = get_password_hash(payload.new_password)
    await db.flush()

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
    if not verify_password(payload.password, current_user.password_hash):
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
