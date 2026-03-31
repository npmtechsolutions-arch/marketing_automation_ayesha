"""Social account management endpoints."""

import math
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.platform import SocialAccount, SocialPlatform
from app.models.team_member import InvitationStatus, TeamMember
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.social_account import (
    SocialAccountCreate,
    SocialAccountResponse,
    SocialAccountUpdate,
    SocialAccountWithPlatform,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _verify_membership(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> TeamMember:
    """Ensure the current user is an accepted member of the account."""
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.user_id == user_id,
            TeamMember.account_id == account_id,
            TeamMember.invitation_status == InvitationStatus.ACCEPTED,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this account",
        )
    return member


async def _get_social_account_or_404(
    social_account_id: uuid.UUID,
    account_id: uuid.UUID,
    db: AsyncSession,
) -> SocialAccount:
    """Fetch a social account or raise 404."""
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == social_account_id,
            SocialAccount.account_id == account_id,
        )
    )
    social_account = result.scalar_one_or_none()
    if social_account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social account not found",
        )
    return social_account


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=PaginatedResponse[SocialAccountResponse])
async def list_social_accounts(
    account_id: uuid.UUID,
    platform_id: uuid.UUID | None = Query(None, description="Filter by platform"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all social accounts for the account, optionally filtered by platform."""
    await _verify_membership(db, current_user.id, account_id)

    conditions = [SocialAccount.account_id == account_id]
    if platform_id is not None:
        conditions.append(SocialAccount.platform_id == platform_id)
    if is_active is not None:
        conditions.append(SocialAccount.is_active == is_active)

    count_result = await db.execute(
        select(func.count()).select_from(SocialAccount).where(*conditions)
    )
    total = count_result.scalar() or 0

    stmt = (
        select(SocialAccount)
        .where(*conditions)
        .order_by(SocialAccount.account_name)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    accounts = result.scalars().all()

    return PaginatedResponse[SocialAccountResponse](
        items=[SocialAccountResponse.model_validate(a) for a in accounts],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.post("/", response_model=SocialAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_social_account(
    account_id: uuid.UUID,
    body: SocialAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new social media account linked to a platform."""
    await _verify_membership(db, current_user.id, account_id)

    # Verify the platform exists and belongs to this account
    platform_result = await db.execute(
        select(SocialPlatform).where(
            SocialPlatform.id == body.platform_id,
            SocialPlatform.account_id == account_id,
        )
    )
    platform = platform_result.scalar_one_or_none()
    if platform is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social platform not found in this account",
        )

    social_account = SocialAccount(
        user_id=current_user.id,
        account_id=account_id,
        platform_id=body.platform_id,
        account_name=body.account_name,
        account_handle=body.account_handle,
        profile_url=body.profile_url,
        profile_image_url=body.profile_image_url,
        api_key=body.api_key,
        api_secret=body.api_secret,
        access_token=body.access_token,
        refresh_token=body.refresh_token,
        config=body.config,
    )
    db.add(social_account)
    await db.flush()
    await db.refresh(social_account)

    return SocialAccountResponse.model_validate(social_account)


@router.get("/{social_account_id}", response_model=SocialAccountWithPlatform)
async def get_social_account(
    account_id: uuid.UUID,
    social_account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a single social account with platform details."""
    await _verify_membership(db, current_user.id, account_id)
    social_account = await _get_social_account_or_404(social_account_id, account_id, db)

    response = SocialAccountWithPlatform.model_validate(social_account)
    return response


@router.put("/{social_account_id}", response_model=SocialAccountResponse)
async def update_social_account(
    account_id: uuid.UUID,
    social_account_id: uuid.UUID,
    body: SocialAccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a social account's settings or credentials."""
    await _verify_membership(db, current_user.id, account_id)
    social_account = await _get_social_account_or_404(social_account_id, account_id, db)

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    for field, value in update_data.items():
        setattr(social_account, field, value)

    await db.flush()
    await db.refresh(social_account)

    return SocialAccountResponse.model_validate(social_account)


@router.delete("/{social_account_id}", response_model=MessageResponse)
async def delete_social_account(
    account_id: uuid.UUID,
    social_account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a social account."""
    await _verify_membership(db, current_user.id, account_id)
    social_account = await _get_social_account_or_404(social_account_id, account_id, db)

    await db.delete(social_account)
    await db.flush()

    return MessageResponse(message="Social account deleted successfully")


@router.post("/{social_account_id}/verify", response_model=MessageResponse)
async def verify_social_account(
    account_id: uuid.UUID,
    social_account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Test the connection / API keys for a social account.

    This is a placeholder that returns mock success. In production,
    this would make an actual API call to the platform to verify credentials.
    """
    await _verify_membership(db, current_user.id, account_id)
    social_account = await _get_social_account_or_404(social_account_id, account_id, db)

    # TODO: Implement real verification per platform type
    # For now, mark as verified with a mock success
    social_account.is_verified = True
    social_account.last_verified_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(social_account)

    return MessageResponse(message="Social account connection verified successfully")


@router.post("/{social_account_id}/refresh-token", response_model=MessageResponse)
async def refresh_social_account_token(
    account_id: uuid.UUID,
    social_account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Refresh the access token for a social account.

    This is a placeholder. In production, this would use the refresh_token
    to obtain new credentials from the platform's OAuth endpoint.
    """
    await _verify_membership(db, current_user.id, account_id)
    social_account = await _get_social_account_or_404(social_account_id, account_id, db)

    if not social_account.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token available for this account. Please reconnect.",
        )

    # TODO: Implement real token refresh per platform type
    # For now, return a mock success
    return MessageResponse(message="Token refresh initiated (placeholder)")
