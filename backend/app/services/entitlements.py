"""Subscription plan entitlements.

Single source of truth for what each tier includes, plus the checks that hold
accounts to those limits. Both the billing UI and the feature endpoints read
from here, so the numbers shown on the billing page are the numbers enforced.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, SubscriptionTier
from app.models.platform import SocialAccount
from app.models.post import Post
from app.models.team_member import TeamMember

# A limit of -1 means "no cap".
UNLIMITED = -1

TIER_LIMITS: dict[SubscriptionTier, dict[str, int]] = {
    SubscriptionTier.FREE: {"posts": 10, "members": 1, "platforms": 2},
    SubscriptionTier.STARTER: {"posts": 50, "members": 3, "platforms": 5},
    SubscriptionTier.GROWTH: {"posts": 200, "members": 10, "platforms": 8},
    SubscriptionTier.PRO: {"posts": 1000, "members": 25, "platforms": 8},
    SubscriptionTier.ENTERPRISE: {"posts": 99999, "members": 100, "platforms": 8},
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


def apply_tier(account: Account, tier: SubscriptionTier) -> None:
    """Set the account's tier and the entitlement limits that come with it."""
    limits = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])
    account.subscription_tier = tier
    account.monthly_post_limit = limits["posts"]
    account.max_team_members = limits["members"]
    account.max_platforms = limits["platforms"]


# ---------------------------------------------------------------------------
# Usage counters — these define what "used" means on the billing page, so the
# enforcement below and the meters the user sees can never disagree.
# ---------------------------------------------------------------------------

def _month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def count_posts_this_month(db: AsyncSession, account_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count(Post.id)).where(
                Post.account_id == account_id,
                Post.deleted_at.is_(None),
                Post.created_at >= _month_start(),
            )
        )
    ).scalar() or 0


async def count_team_members(db: AsyncSession, account_id: uuid.UUID) -> int:
    """Members and pending invitations both consume a seat."""
    return (
        await db.execute(
            select(func.count(TeamMember.id)).where(TeamMember.account_id == account_id)
        )
    ).scalar() or 0


async def connected_platform_ids(db: AsyncSession, account_id: uuid.UUID) -> set[uuid.UUID]:
    """Platforms the account has at least one live connected account on.

    Two Instagram profiles still count as one platform — the seeded platform
    definitions themselves are free, only actual connections are metered.
    """
    rows = await db.execute(
        select(SocialAccount.platform_id)
        .where(
            SocialAccount.account_id == account_id,
            SocialAccount.is_active.is_(True),
        )
        .distinct()
    )
    return set(rows.scalars().all())


async def count_connected_platforms(db: AsyncSession, account_id: uuid.UUID) -> int:
    return len(await connected_platform_ids(db, account_id))


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


def _limit_reached(limit: int, used: int, adding: int) -> bool:
    return limit >= 0 and used + adding > limit


def _plan_error(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


async def enforce_post_limit(
    db: AsyncSession, account_id: uuid.UUID, *, adding: int = 1
) -> None:
    """Reject post creation once the account's monthly allowance is spent."""
    account = await get_account(db, account_id)
    limit = account.monthly_post_limit
    if limit < 0:
        return
    used = await count_posts_this_month(db, account_id)
    if not _limit_reached(limit, used, adding):
        return
    plan = tier_name(account.subscription_tier)
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
    """Reject a new team member/invitation once every seat is taken."""
    limit = account.max_team_members
    if limit < 0:
        return
    used = await count_team_members(db, account.id)
    if not _limit_reached(limit, used, 1):
        return
    plan = tier_name(account.subscription_tier)
    raise _plan_error(
        f"Team member limit reached — the {plan} plan allows {limit} "
        f"member{'s' if limit != 1 else ''}. Upgrade your plan to add more members."
    )


async def platform_slot_available(
    db: AsyncSession, account_id: uuid.UUID, platform_id: uuid.UUID
) -> bool:
    """Whether the account may connect an account on this platform.

    Always true for a platform that is already connected — extra profiles on a
    platform the account already pays for are not metered.
    """
    account = await get_account(db, account_id)
    limit = account.max_platforms
    if limit < 0:
        return True
    connected = await connected_platform_ids(db, account_id)
    if platform_id in connected:
        return True
    return len(connected) < limit


async def enforce_platform_limit(
    db: AsyncSession, account_id: uuid.UUID, platform_id: uuid.UUID
) -> None:
    if await platform_slot_available(db, account_id, platform_id):
        return
    account = await get_account(db, account_id)
    plan = tier_name(account.subscription_tier)
    raise _plan_error(
        f"Connected platform limit reached — the {plan} plan allows "
        f"{account.max_platforms} social platforms. Disconnect one or upgrade "
        "your plan to connect another."
    )
