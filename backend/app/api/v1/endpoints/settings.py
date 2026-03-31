"""Account settings and usage endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.account import Account
from app.models.platform import SocialPlatform
from app.models.post import Post
from app.models.team_member import TeamMember, TeamRole
from app.schemas.account import AccountResponse, AccountUpdate
from app.schemas.common import MessageResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _verify_account_access(
    account_id: uuid.UUID, user, db: AsyncSession, *, min_role: TeamRole | None = None
) -> TeamMember:
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.account_id == account_id,
            TeamMember.user_id == user.id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this account")
    role_hierarchy = [TeamRole.VIEWER, TeamRole.EDITOR, TeamRole.MANAGER, TeamRole.ADMIN, TeamRole.OWNER]
    if min_role and role_hierarchy.index(member.role) < role_hierarchy.index(min_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires at least {min_role.value} role")
    return member


async def _get_account_or_404(account_id: uuid.UUID, db: AsyncSession) -> Account:
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AccountSettingsResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    subscription_tier: str
    subscription_status: str
    monthly_post_limit: int
    max_team_members: int
    max_platforms: int
    settings: dict | None = None


class AccountSettingsUpdate(BaseModel):
    name: str | None = None
    settings: dict | None = None


class UsageResponse(BaseModel):
    posts_this_month: int
    posts_limit: int
    posts_remaining: int
    team_members: int
    team_members_limit: int
    connected_platforms: int
    platforms_limit: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=AccountSettingsResponse)
async def get_account_settings(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Get account settings."""
    await _verify_account_access(account_id, current_user, db)
    account = await _get_account_or_404(account_id, db)

    return AccountSettingsResponse(
        id=account.id,
        name=account.name,
        slug=account.slug,
        subscription_tier=account.subscription_tier.value,
        subscription_status=account.subscription_status.value,
        monthly_post_limit=account.monthly_post_limit,
        max_team_members=account.max_team_members,
        max_platforms=account.max_platforms,
        settings=account.settings,
    )


@router.put("/", response_model=AccountSettingsResponse)
async def update_account_settings(
    account_id: uuid.UUID,
    body: AccountSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Update account settings. Requires admin role or above."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.ADMIN)
    account = await _get_account_or_404(account_id, db)

    if body.name is not None:
        account.name = body.name
    if body.settings is not None:
        # Merge with existing settings rather than replacing
        existing = account.settings or {}
        existing.update(body.settings)
        account.settings = existing

    await db.flush()
    await db.refresh(account)

    return AccountSettingsResponse(
        id=account.id,
        name=account.name,
        slug=account.slug,
        subscription_tier=account.subscription_tier.value,
        subscription_status=account.subscription_status.value,
        monthly_post_limit=account.monthly_post_limit,
        max_team_members=account.max_team_members,
        max_platforms=account.max_platforms,
        settings=account.settings,
    )


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Get current usage stats for the account."""
    await _verify_account_access(account_id, current_user, db)
    account = await _get_account_or_404(account_id, db)

    now = datetime.now(timezone.utc)

    # Posts created this month
    posts_count_result = await db.execute(
        select(func.count(Post.id)).where(
            Post.account_id == account_id,
            Post.deleted_at.is_(None),
            extract("year", Post.created_at) == now.year,
            extract("month", Post.created_at) == now.month,
        )
    )
    posts_this_month = posts_count_result.scalar() or 0

    # Team members
    members_count_result = await db.execute(
        select(func.count(TeamMember.id)).where(TeamMember.account_id == account_id)
    )
    team_members = members_count_result.scalar() or 0

    # Connected platforms
    platforms_count_result = await db.execute(
        select(func.count(SocialPlatform.id)).where(
            SocialPlatform.account_id == account_id,
            SocialPlatform.is_active.is_(True),
        )
    )
    connected_platforms = platforms_count_result.scalar() or 0

    return UsageResponse(
        posts_this_month=posts_this_month,
        posts_limit=account.monthly_post_limit,
        posts_remaining=max(0, account.monthly_post_limit - posts_this_month),
        team_members=team_members,
        team_members_limit=account.max_team_members,
        connected_platforms=connected_platforms,
        platforms_limit=account.max_platforms,
    )
