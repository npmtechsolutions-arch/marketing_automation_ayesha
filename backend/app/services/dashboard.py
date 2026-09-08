"""One dashboard payload, one round of queries.

The dashboard used to be several endpoints, each with its own date handling,
and the widgets could disagree about what "last 7 days" meant. This computes
the range once and answers every widget from it.

**Ranges are resolved in the workspace's timezone, not the server's.** "Today"
for a team in Sydney is not the same fourteen hours as "today" in UTC, and a
dashboard that quietly uses the server's clock shows an agency the wrong day's
numbers every morning.

**No N+1.** Each widget is one aggregate query over the range; nothing loops
over posts issuing per-row lookups. The cost of the whole payload is a fixed
number of queries regardless of how much content the workspace has.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.audit_log import ActivityLog
from app.models.platform import AccountHealth, SocialAccount
from app.models.post import Post, PostStatus
from app.models.post_performance import PostPerformance

logger = logging.getLogger(__name__)

RANGES = ("today", "yesterday", "7d", "30d", "90d", "custom")

# Statuses that mean "somebody has to look at this", shared with the review
# workflow so the dashboard count and the queue cannot disagree.
PENDING_REVIEW_STATUSES = (
    PostStatus.IN_REVIEW,
    PostStatus.PENDING_APPROVAL,
    PostStatus.CLIENT_REVIEW,
)

FAILED_STATUSES = (PostStatus.FAILED, PostStatus.PARTIALLY_PUBLISHED)


def workspace_timezone(account: Account) -> ZoneInfo:
    """The workspace's timezone, defaulting to UTC.

    Stored on the settings blob rather than a column, like the approval flags:
    it is a preference, and a migration per preference is not a trade worth
    making. An unrecognised name falls back to UTC rather than failing the
    dashboard -- a wrong-by-hours chart is better than no chart, and the
    fallback is logged.
    """
    name = ((account.settings or {}).get("timezone") or "UTC").strip()
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning(
            "Workspace %s has an unusable timezone %r; using UTC.", account.id, name
        )
        return ZoneInfo("UTC")


@dataclass(frozen=True)
class DateRange:
    """A half-open window [start, end) in UTC, plus what it was asked for."""

    start: datetime
    end: datetime
    label: str
    timezone_name: str

    @property
    def days(self) -> int:
        return max(1, (self.end - self.start).days)

    def previous(self) -> "DateRange":
        """The equally long window immediately before, for growth comparisons."""
        span = self.end - self.start
        return DateRange(
            start=self.start - span, end=self.start,
            label=f"previous_{self.label}", timezone_name=self.timezone_name,
        )


def resolve_range(
    account: Account,
    range_key: str = "7d",
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    *,
    now: Optional[datetime] = None,
) -> DateRange:
    """Turn a range key into concrete UTC bounds.

    Days are whole days in the workspace's timezone, then converted -- so
    "today" starts at local midnight, not at 00:00 UTC. The window is half-open
    so a post published at exactly midnight belongs to one day, not two.
    """
    tz = workspace_timezone(account)
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    today = now.date()

    if range_key == "custom":
        if date_from is None or date_to is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A custom range needs both 'from' and 'to'.",
            )
        if date_to < date_from:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'to' cannot be before 'from'.",
            )
        start_date, end_date = date_from, date_to
    elif range_key == "today":
        start_date = end_date = today
    elif range_key == "yesterday":
        start_date = end_date = today - timedelta(days=1)
    elif range_key in ("7d", "30d", "90d"):
        # Inclusive of today: "last 7 days" means the last seven days a person
        # has lived through, which includes the one they are in.
        start_date = today - timedelta(days=int(range_key[:-1]) - 1)
        end_date = today
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown range '{range_key}'. Use one of: {', '.join(RANGES)}.",
        )

    start = datetime.combine(start_date, time.min, tzinfo=tz)
    # Half-open: the day after the last one included.
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
    return DateRange(
        start=start.astimezone(timezone.utc),
        end=end.astimezone(timezone.utc),
        label=range_key,
        timezone_name=str(tz),
    )


# ---------------------------------------------------------------------------
# The widgets
# ---------------------------------------------------------------------------

async def _post_counts(db: AsyncSession, account_id, window: DateRange) -> dict:
    """Published / scheduled / failed / drafts, in one pass over posts.

    Conditional aggregates rather than four queries: the row set is identical,
    and four round trips for one table is the shape that becomes slow first.
    """
    def count_if(condition) -> Any:
        return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)

    row = (
        await db.execute(
            select(
                count_if(Post.status == PostStatus.PUBLISHED).label("published"),
                count_if(Post.status == PostStatus.SCHEDULED).label("scheduled"),
                count_if(Post.status.in_(FAILED_STATUSES)).label("failed"),
                count_if(Post.status == PostStatus.DRAFT).label("drafts"),
                count_if(Post.status.in_(PENDING_REVIEW_STATUSES)).label("pending"),
                func.count(Post.id).label("total"),
            ).where(
                Post.account_id == account_id,
                Post.deleted_at.is_(None),
                Post.created_at >= window.start,
                Post.created_at < window.end,
            )
        )
    ).one()
    return {
        "published": int(row.published), "scheduled": int(row.scheduled),
        "failed": int(row.failed), "drafts": int(row.drafts),
        "total": int(row.total),
    }


async def _pending_approvals(db: AsyncSession, account_id) -> int:
    """Deliberately *not* range-filtered.

    A post submitted three weeks ago is still waiting; hiding it because it
    falls outside "last 7 days" is how an approval queue silently grows.
    """
    return int(
        (
            await db.execute(
                select(func.count(Post.id)).where(
                    Post.account_id == account_id,
                    Post.deleted_at.is_(None),
                    Post.status.in_(PENDING_REVIEW_STATUSES),
                )
            )
        ).scalar()
        or 0
    )


async def _engagement(db: AsyncSession, account_id, window: DateRange) -> dict:
    """Totals across every performance row for posts in the range."""
    row = (
        await db.execute(
            select(
                func.coalesce(func.sum(PostPerformance.impressions), 0),
                func.coalesce(func.sum(PostPerformance.reach), 0),
                func.coalesce(func.sum(PostPerformance.likes), 0),
                func.coalesce(func.sum(PostPerformance.comments), 0),
                func.coalesce(func.sum(PostPerformance.shares), 0),
                func.coalesce(func.sum(PostPerformance.saves), 0),
                func.coalesce(func.sum(PostPerformance.clicks), 0),
                func.coalesce(func.sum(PostPerformance.video_views), 0),
            )
            .join(Post, Post.id == PostPerformance.post_id)
            .where(
                Post.account_id == account_id,
                Post.deleted_at.is_(None),
                Post.created_at >= window.start,
                Post.created_at < window.end,
            )
        )
    ).one()
    impressions, reach, likes, comments, shares, saves, clicks, views = (
        int(v) for v in row
    )
    interactions = likes + comments + shares + saves
    return {
        "impressions": impressions,
        "reach": reach,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "saves": saves,
        "clicks": clicks,
        "video_views": views,
        "interactions": interactions,
        # Against reach rather than impressions: reach is people, impressions
        # counts the same person twice. Null rather than zero when there is
        # nothing to divide by -- 0% reads as "bad", not "no data".
        "engagement_rate": (
            round(interactions / reach * 100, 2) if reach else None
        ),
    }


async def _top_posts(db: AsyncSession, account_id, window: DateRange, limit=5) -> list:
    """The five posts with the most interactions in the range.

    One grouped query with the ordering done in SQL, rather than fetching every
    post and sorting in Python.
    """
    engagement = (
        func.coalesce(func.sum(PostPerformance.likes), 0)
        + func.coalesce(func.sum(PostPerformance.comments), 0)
        + func.coalesce(func.sum(PostPerformance.shares), 0)
        + func.coalesce(func.sum(PostPerformance.saves), 0)
    ).label("engagement")

    rows = (
        await db.execute(
            select(
                Post.id, Post.title, Post.content, Post.status, Post.published_at,
                engagement,
                func.coalesce(func.sum(PostPerformance.impressions), 0).label("impressions"),
                func.coalesce(func.sum(PostPerformance.reach), 0).label("reach"),
            )
            .join(PostPerformance, PostPerformance.post_id == Post.id)
            .where(
                Post.account_id == account_id,
                Post.deleted_at.is_(None),
                Post.created_at >= window.start,
                Post.created_at < window.end,
            )
            .group_by(Post.id, Post.title, Post.content, Post.status, Post.published_at)
            .order_by(engagement.desc())
            .limit(limit)
        )
    ).all()

    return [
        {
            "id": str(r.id),
            "title": r.title or (r.content or "")[:60] or "Untitled post",
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "published_at": r.published_at.isoformat() if r.published_at else None,
            "engagement": int(r.engagement),
            "impressions": int(r.impressions),
            "reach": int(r.reach),
        }
        for r in rows
    ]


async def _recent_activity(db: AsyncSession, account_id, limit=10) -> list:
    """Not range-filtered: "recent" means recent, and an empty feed because
    nothing happened in the chosen window is confusing rather than informative.
    """
    rows = (
        await db.execute(
            select(ActivityLog)
            .where(ActivityLog.account_id == account_id)
            .order_by(ActivityLog.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": str(a.id),
            "action": a.action,
            "description": a.description,
            "category": a.category,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ]


async def _connected_accounts(db: AsyncSession, account_id) -> dict:
    """Connections and their health, for the warning strip."""
    rows = (
        await db.execute(
            select(
                SocialAccount.id, SocialAccount.account_name, SocialAccount.health,
                SocialAccount.health_detail, SocialAccount.last_checked_at,
                SocialAccount.platform_id,
            ).where(
                SocialAccount.account_id == account_id,
                SocialAccount.is_active.is_(True),
            )
        )
    ).all()

    accounts = [
        {
            "id": str(r.id),
            "account_name": r.account_name,
            "health": r.health.value if hasattr(r.health, "value") else str(r.health),
            "health_detail": r.health_detail,
            "last_checked_at": (
                r.last_checked_at.isoformat() if r.last_checked_at else None
            ),
        }
        for r in rows
    ]
    counts: dict[str, int] = {}
    for entry in accounts:
        counts[entry["health"]] = counts.get(entry["health"], 0) + 1

    return {
        "total": len(accounts),
        "connected": counts.get(AccountHealth.CONNECTED.value, 0),
        "expiring": counts.get(AccountHealth.EXPIRING.value, 0),
        "failed": counts.get(AccountHealth.FAILED.value, 0),
        "unknown": counts.get(AccountHealth.UNKNOWN.value, 0),
        "needs_attention": (
            counts.get(AccountHealth.EXPIRING.value, 0)
            + counts.get(AccountHealth.FAILED.value, 0)
        ),
        "accounts": accounts,
    }


async def _followers(db: AsyncSession, account_id, window: DateRange) -> dict:
    """Follower total and growth.

    Growth needs a daily snapshot table (analytics_daily, arriving in 1.11).
    Until then the total comes from each connection's cached metadata and
    growth is **null** -- not zero. Zero means "no change measured"; null means
    "not measured", and showing a flat 0% would be a claim we cannot support.
    """
    rows = (
        await db.execute(
            select(SocialAccount.metadata_).where(
                SocialAccount.account_id == account_id,
                SocialAccount.is_active.is_(True),
            )
        )
    ).scalars().all()

    total = 0
    for meta in rows:
        try:
            total += int((meta or {}).get("followers") or 0)
        except (TypeError, ValueError):
            continue

    return {
        "total": total,
        "growth": None,
        "growth_percent": None,
        # So the client can render "growth unavailable" rather than "0".
        "growth_available": False,
    }


async def build(
    db: AsyncSession,
    account: Account,
    *,
    range_key: str = "7d",
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    now: Optional[datetime] = None,
) -> dict:
    """The whole dashboard payload."""
    window = resolve_range(account, range_key, date_from, date_to, now=now)
    account_id = account.id

    posts = await _post_counts(db, account_id, window)
    engagement = await _engagement(db, account_id, window)

    return {
        "range": {
            "key": window.label,
            "start": window.start.isoformat(),
            "end": window.end.isoformat(),
            "days": window.days,
            "timezone": window.timezone_name,
        },
        "connected_accounts": await _connected_accounts(db, account_id),
        "posts": posts,
        "pending_approvals": await _pending_approvals(db, account_id),
        "engagement": engagement,
        "followers": await _followers(db, account_id, window),
        "top_posts": await _top_posts(db, account_id, window),
        "recent_activity": await _recent_activity(db, account_id),
    }
