"""Nightly analytics collection and retention.

Two jobs. Collect a daily snapshot per connected account, so follower growth
can be shown at all -- nothing previously recorded a follower count at a point
in time, which is why the dashboard's growth figure has been null. And prune
what the organization's plan no longer entitles it to keep.

The upsert is the important part: a re-run must *correct* a day, not duplicate
it. Syncs get retried, a night can be run twice after a deploy, and an operator
will re-run one by hand to fix a gap.
"""

import asyncio
import logging
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connectors.base import NotSupportedError, PlatformRateLimited
from app.connectors.registry import get_provider
from app.models.account import Account
from app.models.analytics_daily import METRIC_FIELDS, AnalyticsDaily
from app.models.platform import SocialAccount
from app.services import entitlement_service as ent

logger = logging.getLogger(__name__)

# Run once a day. The metrics are daily buckets; collecting more often would
# rewrite the same row with the same numbers.
SYNC_INTERVAL_SECONDS = 24 * 60 * 60

# A rate-limited platform is retried a few times with growing gaps. Beyond
# that the day is left unwritten rather than hammered -- a missing row is
# visibly missing, where a wrong one is not.
MAX_ATTEMPTS = 3
BASE_BACKOFF_SECONDS = 5
MAX_BACKOFF_SECONDS = 120

# Floor on retention. A plan with a small allowance still needs enough history
# for a week-over-week comparison to mean anything.
MIN_RETENTION_DAYS = 7


def backoff_delay(attempt: int, retry_after: Optional[int] = None) -> float:
    """Seconds before the next attempt. The platform's own figure wins."""
    if retry_after and retry_after > 0:
        return float(min(retry_after, MAX_BACKOFF_SECONDS))
    raw = min(BASE_BACKOFF_SECONDS * (2 ** max(0, attempt - 1)), MAX_BACKOFF_SECONDS)
    # Jitter, so a workspace's accounts do not all retry in lockstep and
    # re-trigger the same limit.
    return max(1.0, raw * random.uniform(0.75, 1.25))


async def collect_account(
    db: AsyncSession, account: SocialAccount, day: date
) -> Optional[dict]:
    """Fetch one account's metrics for a day, retrying a rate limit.

    Returns the metric mapping, or None when the platform reports nothing --
    which is not an error. Absent metrics stay absent so they store as NULL.
    """
    provider = get_provider(account.platform.slug if account.platform else None)
    since = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    until = since + timedelta(days=1)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return await provider.get_analytics(account, since, until)
        except NotSupportedError:
            # This platform exposes no account-level analytics. Nothing to
            # record, and nothing wrong.
            return None
        except PlatformRateLimited as exc:
            if attempt == MAX_ATTEMPTS:
                logger.warning(
                    "Rate limited collecting %s analytics for %s; leaving the "
                    "day unwritten.", provider.slug, account.id,
                )
                return None
            delay = backoff_delay(attempt, exc.retry_after)
            logger.info(
                "Rate limited on %s; retrying in %.0fs (attempt %d/%d)",
                provider.slug, delay, attempt, MAX_ATTEMPTS,
            )
            await asyncio.sleep(delay)
        except Exception:  # noqa: BLE001 - one account must not stop the sync
            logger.exception(
                "Could not collect %s analytics for account %s",
                provider.slug, account.id,
            )
            return None
    return None


async def upsert_day(
    db: AsyncSession, social_account_id: uuid.UUID, day: date, metrics: dict
) -> None:
    """Write one account-day, correcting it if it already exists.

    Only the metrics actually present are written, so a platform that stopped
    reporting reach does not overwrite yesterday's value with NULL -- and a
    re-run that fetches fewer metrics cannot erase what an earlier one stored.
    """
    values = {
        name: metrics[name] for name in METRIC_FIELDS if metrics.get(name) is not None
    }
    if not values:
        return

    if db.bind.dialect.name == "postgresql":
        statement = pg_insert(AnalyticsDaily).values(
            id=uuid.uuid4(),
            social_account_id=social_account_id,
            date=day,
            **values,
        )
        await db.execute(
            statement.on_conflict_do_update(
                constraint="uq_analytics_daily_day",
                set_={**values, "updated_at": datetime.now(timezone.utc)},
            )
        )
        return

    # SQLite (the test harness) has no matching ON CONFLICT construct through
    # the postgresql dialect helper, so the same semantics are done in two
    # statements. Correctness is identical; only the round-trip count differs.
    existing = (
        await db.execute(
            select(AnalyticsDaily).where(
                AnalyticsDaily.social_account_id == social_account_id,
                AnalyticsDaily.date == day,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            AnalyticsDaily(
                id=uuid.uuid4(),
                social_account_id=social_account_id,
                date=day,
                **values,
            )
        )
    else:
        for name, value in values.items():
            setattr(existing, name, value)
    await db.flush()


async def sync_day(
    db: AsyncSession, *, day: Optional[date] = None
) -> dict:
    """Collect every active account's metrics for a day.

    Defaults to yesterday: a platform's figures for "today" are incomplete
    until the day closes, and storing a partial day as final would understate
    it permanently.
    """
    day = day or (datetime.now(timezone.utc).date() - timedelta(days=1))
    accounts = (
        await db.execute(
            select(SocialAccount)
            .options(selectinload(SocialAccount.platform))
            .where(SocialAccount.is_active.is_(True))
        )
    ).scalars().all()

    summary = {"day": day.isoformat(), "accounts": 0, "written": 0, "skipped": 0}
    for account in accounts:
        summary["accounts"] += 1
        metrics = await collect_account(db, account, day)
        if not metrics:
            summary["skipped"] += 1
            continue
        await upsert_day(db, account.id, day, metrics)
        summary["written"] += 1

    await db.commit()
    if summary["accounts"]:
        logger.info("Analytics sync: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

async def retention_days_for(db: AsyncSession, organization) -> Optional[int]:
    """How much history this organization's plan keeps. None is unlimited."""
    limit = await ent.get_limit(db, organization, ent.ANALYTICS_HISTORY_DAYS)
    if limit is None:
        return None
    return max(MIN_RETENTION_DAYS, int(limit))


async def prune(db: AsyncSession, *, now: Optional[datetime] = None) -> dict:
    """Delete rows older than each organization's entitlement.

    Per organization rather than one global cutoff: the whole point of
    ``analytics_history_days`` being a plan feature is that a Pro workspace
    keeps more than a Free one, and a single cutoff would either over-delete
    for the payer or over-retain for everyone else.
    """
    from app.models.organization import Organization

    now = now or datetime.now(timezone.utc)
    organizations = (
        await db.execute(select(Organization).where(Organization.deleted_at.is_(None)))
    ).scalars().all()

    summary = {"organizations": 0, "deleted": 0, "unlimited": 0}
    for organization in organizations:
        summary["organizations"] += 1
        days = await retention_days_for(db, organization)
        if days is None:
            summary["unlimited"] += 1
            continue

        cutoff = (now - timedelta(days=days)).date()
        account_ids = (
            select(SocialAccount.id)
            .join(Account, Account.id == SocialAccount.account_id)
            .where(Account.organization_id == organization.id)
        )
        result = await db.execute(
            delete(AnalyticsDaily).where(
                AnalyticsDaily.social_account_id.in_(account_ids),
                AnalyticsDaily.date < cutoff,
            )
        )
        summary["deleted"] += result.rowcount or 0

    await db.commit()
    if summary["deleted"]:
        logger.info("Analytics retention: %s", summary)
    return summary


async def refresh_post_metrics(db: AsyncSession, *, limit: int = 200) -> int:
    """Re-pull per-post metrics into post_performances.

    Recently published posts only: engagement on a two-month-old post has
    settled, and re-fetching every post every night would spend the whole rate
    limit on numbers that no longer move.
    """
    from app.api.v1.endpoints.posts import _sync_post_performance
    from app.models.post import Post, PostStatus

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    posts = (
        await db.execute(
            select(Post)
            .where(
                Post.status.in_(
                    [PostStatus.PUBLISHED, PostStatus.PARTIALLY_PUBLISHED]
                ),
                Post.deleted_at.is_(None),
                Post.published_at >= cutoff,
            )
            .order_by(Post.published_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    refreshed = 0
    for post in posts:
        try:
            await _sync_post_performance(post, db)
            refreshed += 1
        except Exception:  # noqa: BLE001 - one post must not stop the pass
            logger.exception("Could not refresh metrics for post %s", post.id)

    await db.commit()
    return refreshed
