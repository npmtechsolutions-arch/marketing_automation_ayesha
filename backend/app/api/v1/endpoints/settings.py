"""Account settings and usage endpoints."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from app.services import dashboard
from app.services import entitlement_service as ent
from app.services.entitlements import get_organization_for_account

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
    # Resolved from the organization's plan; None is unlimited. These were read
    # off denormalised columns that no longer exist.
    monthly_post_limit: int | None = None
    max_team_members: int | None = None
    max_platforms: int | None = None
    settings: dict | None = None


class AccountSettingsUpdate(BaseModel):
    name: str | None = None
    settings: dict | None = None


class UsageResponse(BaseModel):
    posts_this_month: int
    # None is unlimited, in which case nothing is "remaining" in a countable
    # sense either.
    posts_limit: int | None = None
    posts_remaining: int | None = None
    team_members: int
    team_members_limit: int | None = None
    connected_platforms: int
    platforms_limit: int | None = None


async def _settings_response(
    db: AsyncSession, account: Account, organization
) -> "AccountSettingsResponse":
    """Build the settings payload for a workspace.

    Shared by the GET and the PUT. They each had their own copy, and the PUT's
    still read ``account.subscription_tier`` and the three limit columns --
    fields that moved to Organization in the 1.1 migration -- so renaming a
    workspace returned a 500. One builder is how that stops happening.
    """
    return AccountSettingsResponse(
        id=account.id,
        name=account.name,
        slug=account.slug,
        # Subscription fields belong to the organization; the workspace only
        # carries its own name, slug and settings blob.
        subscription_tier=organization.subscription_tier.value,
        subscription_status=organization.subscription_status.value,
        monthly_post_limit=await ent.get_limit(db, organization, ent.POSTS_PER_MONTH),
        max_team_members=await ent.get_limit(db, organization, ent.TEAM_MEMBERS),
        max_platforms=await ent.get_limit(db, organization, ent.SOCIAL_ACCOUNTS),
        settings=account.settings,
    )



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

    return await _settings_response(db, account, organization)


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

    organization = await get_organization_for_account(db, account_id)
    return await _settings_response(db, account, organization)


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

    posts_this_month = await ent.current_usage(db, organization, ent.POSTS_PER_MONTH)
    posts_limit = await ent.get_limit(db, organization, ent.POSTS_PER_MONTH)

    return UsageResponse(
        posts_this_month=posts_this_month,
        posts_limit=posts_limit,
        posts_remaining=(
            None if posts_limit is None else max(0, posts_limit - posts_this_month)
        ),
        team_members=await ent.current_usage(db, organization, ent.TEAM_MEMBERS),
        team_members_limit=await ent.get_limit(db, organization, ent.TEAM_MEMBERS),
        connected_platforms=await ent.current_usage(
            db, organization, ent.SOCIAL_ACCOUNTS
        ),
        platforms_limit=await ent.get_limit(db, organization, ent.SOCIAL_ACCOUNTS),
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard")
async def get_dashboard(
    account_id: uuid.UUID,
    range: str = Query("7d", description="today|yesterday|7d|30d|90d|custom"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Every dashboard widget in one payload.

    One call rather than six, so the widgets cannot disagree about what the
    selected range means -- and so the page costs a fixed number of queries
    regardless of how much content the workspace holds.

    Ranges resolve in the workspace's timezone: "today" for a team in Sydney is
    not the same fourteen hours as "today" in UTC.
    """
    await _verify_account_access(account_id, current_user, db)
    account = await _get_account_or_404(account_id, db)
    return await dashboard.build(
        db, account, range_key=range, date_from=date_from, date_to=date_to
    )
