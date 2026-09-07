"""Entitlement enforcement.

The limits themselves live in the ``plans`` / ``plan_features`` tables and are
resolved by :mod:`app.services.entitlement_service`. This module keeps the
enforcement helpers the endpoints already call, so introducing the tables did
not require touching fourteen call sites.

The hard-coded ``TIER_LIMITS`` / ``TIER_PRICING`` / ``TIER_NAMES`` /
``TIER_RANK`` dictionaries that used to live here are gone. They were seeded
into plan rows by migration d5b28a71f3c6 with identical values, so behaviour is
unchanged; what changed is that a limit is now data.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, SubscriptionTier
from app.models.organization import Organization
from app.services import entitlement_service as ent
from app.services.entitlement_service import (  # re-exported for callers
    EntitlementExceeded,
    get_organization_for_account,
)

# A limit of -1 used to mean "no cap". Unlimited is now NULL in plan_features;
# this remains only for reading legacy Organization columns.
UNLIMITED = -1


def tier_name(tier: SubscriptionTier) -> str:
    return str(getattr(tier, "value", tier)).title()


async def apply_tier(
    db: AsyncSession, organization: Organization, tier: SubscriptionTier
) -> None:
    """Move an organization onto a plan.

    Only the tier is written now. The denormalised limit columns are no longer
    the source of truth -- plan_features is -- so they are left alone rather
    than being kept in a state that could disagree with it.

    Cached limits for this organization are dropped immediately, so a plan
    change takes effect on the next request rather than after the cache TTL.
    """
    organization.subscription_tier = tier
    ent.invalidate_organization(organization.id)


# ---------------------------------------------------------------------------
# Usage counters, kept for the billing page and tests.
# ---------------------------------------------------------------------------

async def count_posts_this_month(db: AsyncSession, organization_id: uuid.UUID) -> int:
    org = Organization(id=organization_id)
    return await ent.current_usage(db, org, ent.POSTS_PER_MONTH)


async def count_team_members(db: AsyncSession, organization_id: uuid.UUID) -> int:
    org = Organization(id=organization_id)
    return await ent._count_stateful(db, org, ent.TEAM_MEMBERS)


async def count_connected_platforms(db: AsyncSession, organization_id: uuid.UUID) -> int:
    org = Organization(id=organization_id)
    return await ent._count_stateful(db, org, ent.SOCIAL_ACCOUNTS)


async def count_workspaces(db: AsyncSession, organization_id: uuid.UUID) -> int:
    org = Organization(id=organization_id)
    return await ent._count_stateful(db, org, ent.WORKSPACES)


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------

async def enforce_post_limit(
    db: AsyncSession, account_id: uuid.UUID, *, adding: int = 1
) -> None:
    """Spend ``adding`` posts from the organization's monthly allowance.

    Now a metered increment rather than a count of existing rows, which makes
    the check and the write atomic. One consequence is deliberate: deleting a
    post no longer refunds the quota, because the allowance measures what was
    created during the period.
    """
    organization = await ent.get_organization_for_account(db, account_id)
    await ent.check_and_increment(db, organization, ent.POSTS_PER_MONTH, adding)


async def enforce_member_limit(db: AsyncSession, account: Account) -> None:
    organization = await ent.get_organization_for_account(db, account.id)
    await ent.enforce_stateful_limit(db, organization, ent.TEAM_MEMBERS)


async def enforce_workspace_limit(db: AsyncSession, organization: Organization) -> None:
    await ent.enforce_stateful_limit(db, organization, ent.WORKSPACES)


async def platform_slot_available(
    db: AsyncSession, account_id: uuid.UUID, platform_id: uuid.UUID
) -> bool:
    """Whether another social account may be connected.

    A platform already connected anywhere in the organization is free: extra
    profiles on a platform it already pays for are not metered.
    """
    organization = await ent.get_organization_for_account(db, account_id)
    limit = await ent.get_limit(db, organization, ent.SOCIAL_ACCOUNTS)
    if limit is None:
        return True
    connected = await ent.current_usage(db, organization, ent.SOCIAL_ACCOUNTS)
    return connected < limit


async def enforce_platform_limit(
    db: AsyncSession, account_id: uuid.UUID, platform_id: uuid.UUID
) -> None:
    organization = await ent.get_organization_for_account(db, account_id)
    await ent.enforce_stateful_limit(db, organization, ent.SOCIAL_ACCOUNTS)


__all__ = [
    "EntitlementExceeded",
    "UNLIMITED",
    "apply_tier",
    "count_connected_platforms",
    "count_posts_this_month",
    "count_team_members",
    "count_workspaces",
    "enforce_member_limit",
    "enforce_platform_limit",
    "enforce_post_limit",
    "enforce_workspace_limit",
    "get_organization_for_account",
    "platform_slot_available",
    "tier_name",
]
