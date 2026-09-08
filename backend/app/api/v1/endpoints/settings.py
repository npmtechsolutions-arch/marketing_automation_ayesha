"""Account settings and usage endpoints."""

import uuid
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
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


# Settings keys the application actually consumes. Anything else is stored
# untouched -- the blob is a deliberate extension point for client-side
# preferences -- but these drive real behaviour, so a bad value here has to be
# a 422 rather than something that reads back wrong later.
_KNOWN_SETTINGS: dict[str, type] = {
    "timezone": str,
    "approvals_required": bool,
    "client_approval_required": bool,
}


class AccountSettingsUpdate(BaseModel):
    """A settings write.

    ``extra="forbid"`` because the alternative is what this endpoint used to
    do: accept ``{"timezone": "Australia/Sydney"}`` at the top level, ignore
    it, and return 200. A write that reports success and changes nothing is
    indistinguishable from one that worked, and the caller has no way to find
    out. An unknown key is now a 422 naming the field.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=255)
    settings: dict | None = None

    @field_validator("settings")
    @classmethod
    def _check_known_keys(cls, value: dict | None) -> dict | None:
        """Type- and value-check the keys that drive behaviour.

        An unusable timezone is the same accept-but-drop bug one layer down:
        the dashboard falls back to UTC and logs, so the workspace is told the
        write succeeded and then quietly gets the wrong day's numbers. Better
        to refuse it at the door and keep the fallback for old rows.
        """
        if value is None:
            return value

        checked = dict(value)
        for key, expected in _KNOWN_SETTINGS.items():
            if key not in checked:
                continue
            given = checked[key]
            # isinstance, not truthiness: bool("false") is True, so a workspace
            # sending the string would have switched the workflow on while
            # believing it had switched it off.
            if not isinstance(given, expected):
                wanted = "true or false" if expected is bool else expected.__name__
                raise ValueError(f"settings.{key} must be {wanted}")

        timezone = checked.get("timezone")
        if isinstance(timezone, str):
            timezone = timezone.strip()
            try:
                ZoneInfo(timezone)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError(
                    f"settings.timezone {checked['timezone']!r} is not a known "
                    "IANA timezone"
                ) from exc
            # Store the normalised form, so the reader does not have to strip
            # and a padded value cannot round-trip looking different.
            checked["timezone"] = timezone
        return checked


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
        # Merge rather than replace -- and build a NEW dict to do it.
        #
        # This used to mutate the loaded dict in place and assign it back to
        # itself. SQLAlchemy compares the attribute's before and after values
        # to decide whether to emit an UPDATE, and here they were the same
        # object, so ``history.has_changes()`` was False and the flush wrote
        # nothing. The endpoint returned 200 with the old values, and the
        # approval workflow could not be switched on through the API at all.
        # A plain JSON column has no change tracking of its own; only a fresh
        # object is visible as a change.
        account.settings = {**(account.settings or {}), **body.settings}

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
