"""Entitlements read from the database, not from a dictionary.

Limits used to live in ``TIER_LIMITS``, which meant changing one required a
deploy, a customer who negotiated a higher cap could not have it, and nothing
tied the numbers to what Stripe actually bills. They are now Plan/PlanFeature
rows.

The other change is enforcement. The old shape was::

    used = await count(...)          # read
    if used + 1 > limit: reject      # decide
    ...                              # then the caller writes

Two requests arriving at limit-1 both read the same count, both decide they
fit, and the organization ends up one over. For a monthly post cap that is
untidy; for AI requests it is money. :meth:`check_and_increment` collapses the
read and the write into one statement the database serialises.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import Uuid as SAUuid
from sqlalchemy import DateTime as SADateTime
from sqlalchemy import bindparam as sa_bindparam
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.account import Account
from app.models.organization import Organization
from app.models.plan import Feature, FeatureUnit, Plan, PlanFeature, UsageRecord

logger = logging.getLogger(__name__)

# --- Feature keys ---------------------------------------------------------
WORKSPACES = "workspaces"
TEAM_MEMBERS = "team_members"
SOCIAL_ACCOUNTS = "social_accounts"
POSTS_PER_MONTH = "posts_per_month"
AI_REQUESTS_PER_MONTH = "ai_requests_per_month"
STORAGE_BYTES = "storage_bytes"
ANALYTICS_HISTORY_DAYS = "analytics_history_days"
REPORTS_PER_MONTH = "reports_per_month"
WHITE_LABEL = "white_label"
LISTENING_QUERIES = "listening_queries"

# Features whose usage accumulates over a period rather than being counted
# live. Deleting the artefact does not refund these.
METERED_FEATURES = frozenset(
    {POSTS_PER_MONTH, AI_REQUESTS_PER_MONTH, REPORTS_PER_MONTH}
)

# How long a resolved limit is cached. Short enough that a plan change takes
# effect promptly, long enough to keep this off the hot path of every request.
LIMIT_CACHE_TTL_SECONDS = 60


class EntitlementExceeded(HTTPException):
    """Raised when an organization has spent its allowance for a feature.

    402 Payment Required: the request is well-formed and the caller is
    authorised, but the plan does not cover it. A 403 would say "you may never
    do this", which is wrong -- upgrading makes it work.
    """

    def __init__(self, detail: str, feature_key: str, limit: Optional[int]) -> None:
        super().__init__(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=detail)
        self.feature_key = feature_key
        self.limit = limit


def period_start(now: datetime | None = None) -> datetime:
    """Start of the current billing period (calendar month, UTC)."""
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Limit lookup, with a short cache
# ---------------------------------------------------------------------------

class _LimitCache:
    """Redis-backed when available, per-process otherwise.

    The fallback is correct but not shared, so a plan change can take up to the
    TTL to reach every worker. That is the same trade the rate limiter makes.
    """

    def __init__(self) -> None:
        self._redis = None
        self._memory: dict[str, tuple[float, str]] = {}
        url = (settings.REDIS_URL or "").strip()
        if url:
            try:
                import redis

                client = redis.Redis.from_url(
                    url, socket_connect_timeout=1, decode_responses=True
                )
                client.ping()
                self._redis = client
            except Exception:  # noqa: BLE001 - any failure means "no Redis"
                logger.warning(
                    "Redis unavailable; entitlement limits cached per-process, so a "
                    "plan change may take up to %ss to reach every worker.",
                    LIMIT_CACHE_TTL_SECONDS,
                )

    @staticmethod
    def _key(organization_id: uuid.UUID, feature_key: str) -> str:
        return f"entitlement:{organization_id}:{feature_key}"

    def get(self, organization_id: uuid.UUID, feature_key: str) -> str | None:
        key = self._key(organization_id, feature_key)
        if self._redis is not None:
            try:
                return self._redis.get(key)
            except Exception:  # noqa: BLE001
                return None
        import time

        entry = self._memory.get(key)
        if entry is None or entry[0] <= time.time():
            self._memory.pop(key, None)
            return None
        return entry[1]

    def set(self, organization_id: uuid.UUID, feature_key: str, value: str) -> None:
        key = self._key(organization_id, feature_key)
        if self._redis is not None:
            try:
                self._redis.setex(key, LIMIT_CACHE_TTL_SECONDS, value)
                return
            except Exception:  # noqa: BLE001
                return
        import time

        self._memory[key] = (time.time() + LIMIT_CACHE_TTL_SECONDS, value)

    def invalidate_organization(self, organization_id: uuid.UUID) -> None:
        pattern = f"entitlement:{organization_id}:*"
        if self._redis is not None:
            try:
                for key in self._redis.scan_iter(match=pattern):
                    self._redis.delete(key)
                return
            except Exception:  # noqa: BLE001
                return
        prefix = f"entitlement:{organization_id}:"
        for key in [k for k in self._memory if k.startswith(prefix)]:
            self._memory.pop(key, None)

    def clear(self) -> None:
        """Drop everything. Used when a plan itself changes, and by tests."""
        if self._redis is not None:
            try:
                for key in self._redis.scan_iter(match="entitlement:*"):
                    self._redis.delete(key)
                return
            except Exception:  # noqa: BLE001
                return
        self._memory.clear()


_cache = _LimitCache()

# Sentinel distinguishing "unlimited" from "not cached", since both would
# otherwise be represented by a missing value.
_UNLIMITED = "unlimited"
_NOT_GRANTED = "none"


def invalidate_organization(organization_id: uuid.UUID) -> None:
    """Forget cached limits for one organization. Call after a plan change."""
    _cache.invalidate_organization(organization_id)


def invalidate_all() -> None:
    """Forget every cached limit. Call after editing a plan or its features."""
    _cache.clear()


async def get_limit(
    db: AsyncSession, organization: Organization, feature_key: str
) -> Optional[int]:
    """The organization's limit for a feature.

    Returns ``None`` for unlimited and ``0`` for a feature the plan does not
    grant at all -- the difference matters, so a missing PlanFeature row is not
    silently treated as unlimited.
    """
    cached = _cache.get(organization.id, feature_key)
    if cached is not None:
        if cached == _UNLIMITED:
            return None
        if cached == _NOT_GRANTED:
            return 0
        try:
            return int(cached)
        except ValueError:
            pass  # corrupt entry; fall through and re-read

    row = (
        await db.execute(
            select(PlanFeature.limit_value)
            .join(Plan, Plan.id == PlanFeature.plan_id)
            .where(
                Plan.key == organization.subscription_tier.value,
                PlanFeature.feature_key == feature_key,
            )
        )
    ).first()

    if row is None:
        # The plan does not grant this feature.
        _cache.set(organization.id, feature_key, _NOT_GRANTED)
        return 0

    limit = row[0]
    _cache.set(
        organization.id,
        feature_key,
        _UNLIMITED if limit is None else str(limit),
    )
    return limit


async def is_enabled(
    db: AsyncSession, organization: Organization, feature_key: str
) -> bool:
    """Whether a boolean feature is on for this organization."""
    limit = await get_limit(db, organization, feature_key)
    return limit is None or limit > 0


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

# One statement: insert the period's row or add to it, but only while the
# result stays within the limit. If the guard fails, DO UPDATE matches nothing
# and RETURNING yields no row -- which is how the caller learns it was refused.
# Reading the count first and writing it back afterwards would let two requests
# at the limit both pass.
_UPSERT_GUARDED = text(
    "INSERT INTO usage_records "
    "(id, organization_id, feature_key, period_start, count) "
    "VALUES (:id, :organization_id, :feature_key, :period_start, :amount) "
    "ON CONFLICT (organization_id, feature_key, period_start) DO UPDATE "
    "SET count = usage_records.count + :amount "
    "WHERE usage_records.count + :amount <= :limit "
    "RETURNING count"
).bindparams(
    sa_bindparam("id", type_=SAUuid),
    sa_bindparam("organization_id", type_=SAUuid),
    sa_bindparam("period_start", type_=SADateTime(timezone=True)),
)

_UPSERT_UNLIMITED = text(
    "INSERT INTO usage_records "
    "(id, organization_id, feature_key, period_start, count) "
    "VALUES (:id, :organization_id, :feature_key, :period_start, :amount) "
    "ON CONFLICT (organization_id, feature_key, period_start) DO UPDATE "
    "SET count = usage_records.count + :amount "
    "RETURNING count"
).bindparams(
    sa_bindparam("id", type_=SAUuid),
    sa_bindparam("organization_id", type_=SAUuid),
    sa_bindparam("period_start", type_=SADateTime(timezone=True)),
)


async def current_usage(
    db: AsyncSession, organization: Organization, feature_key: str
) -> int:
    """How much of a feature the organization has used.

    Metered features read their period row; stateful ones are counted live, so
    deleting a workspace or disconnecting an account frees the slot.
    """
    if feature_key in METERED_FEATURES:
        return (
            await db.execute(
                select(UsageRecord.count).where(
                    UsageRecord.organization_id == organization.id,
                    UsageRecord.feature_key == feature_key,
                    UsageRecord.period_start == period_start(),
                )
            )
        ).scalar() or 0
    return await _count_stateful(db, organization, feature_key)


async def _count_stateful(
    db: AsyncSession, organization: Organization, feature_key: str
) -> int:
    from sqlalchemy import func as sa_func

    from app.models.platform import SocialAccount
    from app.models.team_member import TeamMember

    if feature_key == WORKSPACES:
        stmt = select(sa_func.count(Account.id)).where(
            Account.organization_id == organization.id,
            Account.deleted_at.is_(None),
        )
    elif feature_key == TEAM_MEMBERS:
        # Distinct people across the organization's workspaces: one person in
        # three workspaces is one seat.
        stmt = (
            select(
                sa_func.count(
                    sa_func.distinct(
                        sa_func.coalesce(
                            sa_func.cast(TeamMember.user_id, __import__("sqlalchemy").String),
                            TeamMember.invitation_email,
                        )
                    )
                )
            )
            .join(Account, Account.id == TeamMember.account_id)
            .where(Account.organization_id == organization.id)
        )
    elif feature_key == STORAGE_BYTES:
        # Was falling through to 0, so the storage allowance always read as
        # unused. Now the sum of what the media library actually holds,
        # excluding soft-deleted files.
        from app.models.media import Media

        stmt = (
            select(sa_func.coalesce(sa_func.sum(Media.size_bytes), 0))
            .join(Account, Account.id == Media.account_id)
            .where(
                Account.organization_id == organization.id,
                Media.deleted_at.is_(None),
            )
        )
    elif feature_key == LISTENING_QUERIES:
        # Counted live, like connections and workspaces, rather than metered.
        # A saved search is a thing that exists, not a spend: metering it would
        # mean deleting one did not give the slot back, so a workspace that
        # created and removed three searches on a 3-query plan would be locked
        # out until the billing period rolled. What *is* metered here is the
        # money each poll spends, and that is recorded on the query itself.
        #
        # Paused queries count. Pausing is not deleting -- the query keeps its
        # history and its slot, and a plan cap that could be dodged by pausing
        # would not be a cap.
        from app.models.listening import ListeningQuery

        stmt = (
            select(sa_func.count(ListeningQuery.id))
            .join(Account, Account.id == ListeningQuery.account_id)
            .where(
                Account.organization_id == organization.id,
                Account.deleted_at.is_(None),
            )
        )
    elif feature_key == SOCIAL_ACCOUNTS:
        stmt = (
            select(sa_func.count(SocialAccount.id))
            .join(Account, Account.id == SocialAccount.account_id)
            .where(
                Account.organization_id == organization.id,
                SocialAccount.is_active.is_(True),
            )
        )
    else:
        return 0
    return (await db.execute(stmt)).scalar() or 0


def _exceeded(feature_key: str, limit: Optional[int], plan_name: str) -> EntitlementExceeded:
    label = feature_key.replace("_", " ")
    return EntitlementExceeded(
        detail=(
            f"You have reached your {plan_name} plan's limit for {label} "
            f"({limit}). Upgrade your plan to continue."
        ),
        feature_key=feature_key,
        limit=limit,
    )


async def check_and_increment(
    db: AsyncSession,
    organization: Organization,
    feature_key: str,
    amount: int = 1,
) -> int:
    """Consume ``amount`` of a metered feature, or refuse.

    Atomic: the limit guard lives in the UPDATE's WHERE clause, so two
    concurrent callers at limit-1 cannot both succeed. Returns the new total.
    """
    limit = await get_limit(db, organization, feature_key)
    plan_name = organization.subscription_tier.value.title()

    if limit is not None and amount > limit:
        # The very first use already exceeds the allowance. Caught here because
        # the guard below only constrains the DO UPDATE branch -- a fresh INSERT
        # would otherwise create a row above the limit.
        raise _exceeded(feature_key, limit, plan_name)

    params = {
        "id": uuid.uuid4(),
        "organization_id": organization.id,
        "feature_key": feature_key,
        "period_start": period_start(),
        "amount": amount,
    }
    if limit is None:
        result = await db.execute(_UPSERT_UNLIMITED, params)
    else:
        result = await db.execute(_UPSERT_GUARDED, {**params, "limit": limit})

    row = result.first()
    if row is None:
        # DO UPDATE matched nothing: the guard rejected it.
        raise _exceeded(feature_key, limit, plan_name)
    return int(row[0])


async def enforce_stateful_limit(
    db: AsyncSession,
    organization: Organization,
    feature_key: str,
    adding: int = 1,
) -> None:
    """Refuse if adding would take a stateful feature over its limit.

    Not atomic, and deliberately so: these are counts of rows that already
    exist, and the row being added is created in the same transaction, so a
    concurrent duplicate is bounded by one rather than unbounded. Metered
    features -- where an overrun costs money -- go through
    :func:`check_and_increment` instead.
    """
    limit = await get_limit(db, organization, feature_key)
    if limit is None:
        return
    used = await current_usage(db, organization, feature_key)
    if used + adding <= limit:
        return
    raise _exceeded(feature_key, limit, organization.subscription_tier.value.title())


async def require_feature(
    db: AsyncSession, organization: Organization, feature_key: str
) -> None:
    """Refuse unless a boolean feature is enabled for this plan."""
    if await is_enabled(db, organization, feature_key):
        return
    raise EntitlementExceeded(
        detail=(
            f"{feature_key.replace('_', ' ').title()} is not included in your "
            f"{organization.subscription_tier.value.title()} plan. Upgrade to enable it."
        ),
        feature_key=feature_key,
        limit=0,
    )


async def usage_summary(
    db: AsyncSession, organization: Organization
) -> list[dict]:
    """Usage against limit for every feature, for the billing page."""
    features = (
        await db.execute(select(Feature).order_by(Feature.sort_order, Feature.key))
    ).scalars().all()

    summary = []
    for feature in features:
        limit = await get_limit(db, organization, feature.key)
        used = (
            0
            if feature.unit is FeatureUnit.BOOLEAN
            else await current_usage(db, organization, feature.key)
        )
        summary.append(
            {
                "key": feature.key,
                "name": feature.name,
                "description": feature.description,
                "unit": feature.unit.value,
                "metered": feature.key in METERED_FEATURES,
                "used": used,
                "limit": limit,
                "unlimited": limit is None,
                "enabled": limit is None or limit > 0,
            }
        )
    return summary


async def get_organization_for_account(
    db: AsyncSession, account_id: uuid.UUID
) -> Organization:
    """The billing entity a workspace belongs to."""
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
