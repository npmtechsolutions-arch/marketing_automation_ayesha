"""Subscription plan entitlements.

Single source of truth for what each tier includes, plus the checks that hold
accounts to those limits. Both the billing UI and the feature endpoints read
from here, so the numbers shown on the billing page are the numbers enforced.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, SubscriptionTier
from app.models.organization import Organization
from app.models.platform import SocialAccount
from app.models.post import Post
from app.models.team_member import TeamMember

# A limit of -1 means "no cap".
UNLIMITED = -1

# Every allowance is spent across ALL workspaces in an organization, not per
# workspace -- that is the point of the Organization tier.
TIER_LIMITS: dict[SubscriptionTier, dict[str, int]] = {
    SubscriptionTier.FREE: {"posts": 10, "members": 1, "platforms": 2, "workspaces": 1},
    SubscriptionTier.STARTER: {"posts": 50, "members": 3, "platforms": 5, "workspaces": 3},
    SubscriptionTier.GROWTH: {"posts": 200, "members": 10, "platforms": 8, "workspaces": 10},
    SubscriptionTier.PRO: {"posts": 1000, "members": 25, "platforms": 8, "workspaces": 25},
    SubscriptionTier.ENTERPRISE: {
        "posts": 99999, "members": 100, "platforms": 8, "workspaces": UNLIMITED,
    },
}

# Display order / upgrade ranking. A tier with a higher rank than the account's
# current tier is an upgrade; a lower rank is a downgrade.
TIER_RANK: dict[SubscriptionTier, int] = {
    SubscriptionTier.FREE: 0,
    SubscriptionTier.STARTER: 1,
    SubscriptionTier.GROWTH: 2,
    SubscriptionTier.PRO: 3,
    SubscriptionTier.ENTERPRISE: 4,
}

# (monthly price, effective monthly price when billed annually)
TIER_PRICING: dict[SubscriptionTier, tuple[float, float]] = {
    SubscriptionTier.FREE: (0.0, 0.0),
    SubscriptionTier.STARTER: (49.0, 39.0),
    SubscriptionTier.GROWTH: (149.0, 119.0),
    SubscriptionTier.PRO: (399.0, 319.0),
    SubscriptionTier.ENTERPRISE: (0.0, 0.0),  # quoted by sales
}

TIER_NAMES: dict[SubscriptionTier, str] = {
    SubscriptionTier.FREE: "Free",
    SubscriptionTier.STARTER: "Starter",
    SubscriptionTier.GROWTH: "Growth",
    SubscriptionTier.PRO: "Pro",
    SubscriptionTier.ENTERPRISE: "Enterprise",
}


def tier_name(tier: SubscriptionTier) -> str:
    return TIER_NAMES.get(tier, str(getattr(tier, "value", tier)).title())


def apply_tier(organization: Organization, tier: SubscriptionTier) -> None:
    """Set the organization's tier and the limits that come with it.

    The only writer of the tier and the four denormalised limit columns --
    enforcement reads those columns, never the tier itself.
    """
    limits = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])
    organization.subscription_tier = tier
    organization.monthly_post_limit = limits["posts"]
    organization.max_team_members = limits["members"]
    organization.max_platforms = limits["platforms"]
    organization.max_workspaces = limits["workspaces"]


# ---------------------------------------------------------------------------
# Usage counters — these define what "used" means on the billing page, so the
# enforcement below and the meters the user sees can never disagree.
# ---------------------------------------------------------------------------

def _month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


# Each counter joins through Account.organization_id so usage is summed over
# every workspace the organization owns. Counting one workspace would let a
# company reset its allowance by creating another one.

async def count_posts_this_month(db: AsyncSession, organization_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count(Post.id))
            .join(Account, Account.id == Post.account_id)
            .where(
                Account.organization_id == organization_id,
                Post.deleted_at.is_(None),
                Post.created_at >= _month_start(),
            )
        )
    ).scalar() or 0


async def count_team_members(db: AsyncSession, organization_id: uuid.UUID) -> int:
    """Members and pending invitations both consume a seat.

    Counts DISTINCT users: one person invited to three workspaces of the same
    organization occupies one seat, not three.
    """
    return (
        await db.execute(
            select(func.count(func.distinct(func.coalesce(
                cast(TeamMember.user_id, String), TeamMember.invitation_email
            ))))
            .join(Account, Account.id == TeamMember.account_id)
            .where(Account.organization_id == organization_id)
        )
    ).scalar() or 0


async def connected_platform_ids(
    db: AsyncSession, organization_id: uuid.UUID
) -> set[uuid.UUID]:
    """Platforms the organization has at least one live connection on.

    Two Instagram profiles still count as one platform — the seeded platform
    definitions themselves are free, only actual connections are metered.
    """
    rows = await db.execute(
        select(SocialAccount.platform_id)
        .join(Account, Account.id == SocialAccount.account_id)
        .where(
            Account.organization_id == organization_id,
            SocialAccount.is_active.is_(True),
        )
        .distinct()
    )
    return set(rows.scalars().all())


async def count_connected_platforms(db: AsyncSession, organization_id: uuid.UUID) -> int:
    return len(await connected_platform_ids(db, organization_id))


async def count_workspaces(db: AsyncSession, organization_id: uuid.UUID) -> int:
    """Live workspaces in the organization. Soft-deleted ones do not count."""
    return (
        await db.execute(
            select(func.count(Account.id)).where(
                Account.organization_id == organization_id,
                Account.deleted_at.is_(None),
            )
        )
    ).scalar() or 0


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------

async def get_account(db: AsyncSession, account_id: uuid.UUID) -> Account:
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


async def get_organization(db: AsyncSession, organization_id: uuid.UUID) -> Organization:
    organization = (
        await db.execute(
            select(Organization).where(Organization.id == organization_id)
        )
    ).scalar_one_or_none()
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    return organization


async def get_organization_for_account(
    db: AsyncSession, account_id: uuid.UUID
) -> Organization:
    """The billing entity a workspace belongs to.

    One join, used by every enforcement path: limits live on the organization
    but callers still arrive holding a workspace id.
    """
    organization = (
        await db.execute(
            select(Organization)
            .join(Account, Account.organization_id == Organization.id)
            .where(Account.id == account_id)
        )
    ).scalar_one_or_none()
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    return organization


def _limit_reached(limit: int, used: int, adding: int) -> bool:
    return limit >= 0 and used + adding > limit


def _plan_error(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


async def enforce_post_limit(
    db: AsyncSession, account_id: uuid.UUID, *, adding: int = 1
) -> None:
    """Reject post creation once the organization's monthly allowance is spent.

    Takes a workspace id because that is what callers hold, but both the limit
    and the usage are the organization's.
    """
    organization = await get_organization_for_account(db, account_id)
    limit = organization.monthly_post_limit
    if limit < 0:
        return
    used = await count_posts_this_month(db, organization.id)
    if not _limit_reached(limit, used, adding):
        return
    plan = tier_name(organization.subscription_tier)
    remaining = max(0, limit - used)
    raise _plan_error(
        f"Monthly post limit reached — the {plan} plan allows {limit} posts per month "
        f"and you have used {used}."
        + (
            f" You can create {remaining} more this month."
            if 0 < remaining < adding
            else ""
        )
        + " Upgrade your plan to create more posts."
    )


async def enforce_member_limit(db: AsyncSession, account: Account) -> None:
    """Reject a new team member/invitation once every seat is taken.

    Seats belong to the organization, so members across all of its workspaces
    are counted (distinct users -- one person in three workspaces is one seat).
    """
    organization = await get_organization_for_account(db, account.id)
    limit = organization.max_team_members
    if limit < 0:
        return
    used = await count_team_members(db, organization.id)
    if not _limit_reached(limit, used, 1):
        return
    plan = tier_name(organization.subscription_tier)
    raise _plan_error(
        f"Team member limit reached — the {plan} plan allows {limit} "
        f"member{'s' if limit != 1 else ''}. Upgrade your plan to add more members."
    )


async def platform_slot_available(
    db: AsyncSession, account_id: uuid.UUID, platform_id: uuid.UUID
) -> bool:
    """Whether this workspace may connect an account on this platform.

    Always true for a platform already connected anywhere in the organization —
    extra profiles on a platform it already pays for are not metered.
    """
    organization = await get_organization_for_account(db, account_id)
    limit = organization.max_platforms
    if limit < 0:
        return True
    connected = await connected_platform_ids(db, organization.id)
    if platform_id in connected:
        return True
    return len(connected) < limit


async def enforce_platform_limit(
    db: AsyncSession, account_id: uuid.UUID, platform_id: uuid.UUID
) -> None:
    if await platform_slot_available(db, account_id, platform_id):
        return
    organization = await get_organization_for_account(db, account_id)
    plan = tier_name(organization.subscription_tier)
    raise _plan_error(
        f"Connected platform limit reached — the {plan} plan allows "
        f"{organization.max_platforms} social platforms. Disconnect one or "
        "upgrade your plan to connect another."
    )


async def enforce_workspace_limit(db: AsyncSession, organization: Organization) -> None:
    """Reject a new workspace once the organization's allowance is spent.

    Enforced on creation only. An organization that already holds more
    workspaces than its current tier permits keeps them -- downgrading should
    not silently make a customer's existing data unreachable.
    """
    limit = organization.max_workspaces
    if limit < 0:
        return
    used = await count_workspaces(db, organization.id)
    if not _limit_reached(limit, used, 1):
        return
    plan = tier_name(organization.subscription_tier)
    raise _plan_error(
        f"Workspace limit reached — the {plan} plan allows {limit} "
        f"workspace{'s' if limit != 1 else ''}. Upgrade your plan to add more."
    )
