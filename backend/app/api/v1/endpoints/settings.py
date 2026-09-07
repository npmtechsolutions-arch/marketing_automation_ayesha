"""Account settings and usage endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.account import Account
from app.core.authz import verify_account_access as _verify_account_access
from app.core.permissions import (
    SETTINGS_MANAGE,
)
from app.services.entitlements import (
    count_connected_platforms,
    count_posts_this_month,
    count_team_members,
    get_organization_for_account,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    organization = await get_organization_for_account(db, account_id)

    return AccountSettingsResponse(
        id=account.id,
        name=account.name,
        slug=account.slug,
        # Subscription fields belong to the organization; the workspace only
        # carries its own name, slug and settings blob.
        subscription_tier=organization.subscription_tier.value,
        subscription_status=organization.subscription_status.value,
        monthly_post_limit=organization.monthly_post_limit,
        max_team_members=organization.max_team_members,
        max_platforms=organization.max_platforms,
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
    await _verify_account_access(account_id, current_user, db, permission=SETTINGS_MANAGE)
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
    """Current usage for the workspace's organization.

    Delegates to app.services.entitlements rather than counting here. This
    endpoint used to reimplement all three counters and disagreed with the
    enforcement code -- it bucketed posts by calendar year/month instead of the
    month-start cutoff, and counted SocialPlatform rows where enforcement counts
    distinct connected SocialAccount platforms. Users saw one number and hit a
    limit computed from another. Now that allowances are organization-wide the
    two would have diverged further still.
    """
    await _verify_account_access(account_id, current_user, db)
    organization = await get_organization_for_account(db, account_id)

    posts_this_month = await count_posts_this_month(db, organization.id)
    team_members = await count_team_members(db, organization.id)
    connected_platforms = await count_connected_platforms(db, organization.id)

    return UsageResponse(
        posts_this_month=posts_this_month,
        posts_limit=organization.monthly_post_limit,
        posts_remaining=max(0, organization.monthly_post_limit - posts_this_month),
        team_members=team_members,
        team_members_limit=organization.max_team_members,
        connected_platforms=connected_platforms,
        platforms_limit=organization.max_platforms,
    )
