"""Campaign-scoped performance: totals, schedule progress, per-platform split.

Everything here is built from ``post_performances`` joined through
``posts.campaign_id``. That is the only table in the system with a campaign
dimension, and the constraint shapes what a campaign dashboard can honestly
show:

* **Account-level analytics cannot be attributed to a campaign.**
  ``analytics_daily`` is a per-connection daily snapshot -- followers, account
  reach, audience demographics. None of it knows which campaign was running, so
  filtering it by campaign would mean inventing attribution. Followers and
  audience are therefore absent from this module rather than approximated, and
  the report payload says so instead of drawing a number.

* **Post metrics are per-post, so they add up.** Reach, impressions,
  interactions and clicks for the campaign's posts are genuinely the campaign's.

One further limitation, stated because it is invisible otherwise:
``PostPerformance`` columns are ``nullable=False, default=0``, so a platform
that does not report a metric is stored as ``0`` and cannot be told apart from
one that reported zero. This module does not pretend to recover that
distinction -- what it does do is refuse to divide by an unmeasured
denominator, which is where a fabricated 0% would otherwise come from.

Top posts come from :func:`app.services.analytics_query.posts` with a campaign
filter rather than a query of their own, so a post's numbers here are the
numbers the analytics page shows for that post.
"""

import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.campaign import Campaign
from app.models.platform import SocialPlatform
from app.models.post import Post, PostStatus
from app.models.post_performance import PostPerformance
from app.services import analytics_query
from app.services.dashboard import DateRange, workspace_timezone

# The statuses that mean "this post actually went out". PARTIALLY_PUBLISHED
# counts: something reached an audience, and its performance rows are real.
PUBLISHED_STATUSES = (PostStatus.PUBLISHED, PostStatus.PARTIALLY_PUBLISHED)

INTERACTION_FIELDS = ("likes", "comments", "shares", "saves")
SUM_FIELDS = ("impressions", "reach", "clicks", "video_views", *INTERACTION_FIELDS)


def campaign_window(
    account: Account, campaign: Campaign, *, now: Optional[datetime] = None
) -> DateRange:
    """The campaign's own window, as a half-open [start, end) range in UTC.

    Campaign dates are stored as plain calendar dates, which are dates *on the
    workspace's clock* -- a campaign running "1st to 30th" for a Sydney
    workspace does not start at 00:00 UTC. They are therefore resolved in the
    workspace timezone and converted, the same way
    :func:`app.services.dashboard.resolve_range` does it, so a campaign window
    and a dashboard window mean the same thing.

    Either bound may be missing, and neither is guessed:

    * no ``start_date`` -- the campaign began when it was created;
    * no ``end_date`` -- it is still running, so the window ends now.
    """
    tz = workspace_timezone(account)
    now = (now or datetime.now(timezone.utc)).astimezone(tz)

    if campaign.start_date is not None:
        start_local = datetime.combine(campaign.start_date, time.min, tzinfo=tz)
    else:
        created = campaign.created_at
        if created.tzinfo is None:
            # SQLite hands back naive datetimes for timezone-aware columns.
            created = created.replace(tzinfo=timezone.utc)
        start_local = created.astimezone(tz)

    if campaign.end_date is not None:
        # end_date is inclusive to a reader; the window is half-open, so it
        # runs to the start of the following day.
        end_local = datetime.combine(
            campaign.end_date + timedelta(days=1), time.min, tzinfo=tz
        )
    else:
        end_local = now

    # A campaign whose end precedes its start would otherwise produce a
    # negative window that silently matches nothing.
    if end_local < start_local:
        end_local = start_local

    return DateRange(
        start=start_local.astimezone(timezone.utc),
        end=end_local.astimezone(timezone.utc),
        label=_window_label(campaign),
        timezone_name=str(tz),
    )


def _window_label(campaign: Campaign) -> str:
    if campaign.start_date and campaign.end_date:
        return f"{campaign.start_date.isoformat()} to {campaign.end_date.isoformat()}"
    if campaign.start_date:
        return f"since {campaign.start_date.isoformat()}"
    return "since the campaign was created"


def _engagement_rate(totals: dict[str, int]) -> Optional[float]:
    """Interactions over reach, as a percentage -- or null.

    Null rather than zero when there is no reach to divide by. The same rule as
    :func:`app.services.analytics_query._engagement_rate`; the second of that
    function's two null cases (no interaction metric reported at all) cannot be
    detected here, because post_performances stores unreported as 0.
    """
    reach = totals.get("reach") or 0
    if not reach:
        return None
    interactions = sum(totals.get(name, 0) for name in INTERACTION_FIELDS)
    return round(interactions / reach * 100, 2)


def _sum_columns():
    return [
        func.coalesce(func.sum(getattr(PostPerformance, name)), 0).label(name)
        for name in SUM_FIELDS
    ]


def _campaign_posts_filter(campaign_id: uuid.UUID, window: DateRange):
    """Posts belonging to this campaign, created inside its window.

    The window bound matters: a post attached to a campaign long after it ended
    is not part of what that campaign did, and counting it would let a
    finished campaign's numbers keep moving.
    """
    return (
        Post.campaign_id == campaign_id,
        Post.deleted_at.is_(None),
        Post.created_at >= window.start,
        Post.created_at < window.end,
    )


async def totals(
    db: AsyncSession, campaign_id: uuid.UUID, window: DateRange
) -> dict[str, Any]:
    """Aggregate every performance row for the campaign's posts."""
    row = (
        await db.execute(
            select(*_sum_columns())
            .select_from(PostPerformance)
            .join(Post, Post.id == PostPerformance.post_id)
            .where(*_campaign_posts_filter(campaign_id, window))
        )
    ).one()

    result: dict[str, Any] = {name: int(getattr(row, name)) for name in SUM_FIELDS}
    result["engagement"] = sum(result[name] for name in INTERACTION_FIELDS)
    result["engagement_rate"] = _engagement_rate(result)
    return result


async def _platform_names(db: AsyncSession) -> dict[str, str]:
    """Slug to display name, for the platforms the workspace knows about."""
    rows = (
        await db.execute(select(SocialPlatform.slug, SocialPlatform.name))
    ).all()
    return {slug: name for slug, name in rows}


async def platform_split(
    db: AsyncSession, campaign_id: uuid.UUID, window: DateRange
) -> list[dict[str, Any]]:
    """Per-platform totals for the campaign, one row per platform posted to.

    Grouped on ``post_performances.platform_type`` rather than on the post's
    target accounts: performance rows are already per platform, and a post sent
    to two platforms has one row for each.

    Carries ``platform_name`` as well as the slug because that is the key the
    report renderers read. Without it every platform row in the CSV, the
    workbook and the PDF rendered with an empty first column -- caught by
    reading a generated report rather than by the tests, which asserted on the
    payload and never on the bytes.
    """
    names = await _platform_names(db)
    rows = (
        await db.execute(
            select(
                PostPerformance.platform_type,
                func.count(func.distinct(Post.id)).label("posts"),
                *_sum_columns(),
            )
            .select_from(PostPerformance)
            .join(Post, Post.id == PostPerformance.post_id)
            .where(*_campaign_posts_filter(campaign_id, window))
            .group_by(PostPerformance.platform_type)
            .order_by(PostPerformance.platform_type)
        )
    ).all()

    split = []
    for row in rows:
        metrics = {name: int(getattr(row, name)) for name in SUM_FIELDS}
        metrics["engagement"] = sum(metrics[name] for name in INTERACTION_FIELDS)
        slug = row.platform_type
        split.append(
            {
                "platform": slug,
                # Falls back to the slug rather than to null: an unrecognised
                # platform_type should still be named in a client's report.
                "platform_name": names.get(slug) or (slug or "").title(),
                "posts": int(row.posts),
                **metrics,
                "engagement_rate": _engagement_rate(metrics),
            }
        )
    return split


async def progress(
    db: AsyncSession,
    campaign: Campaign,
    window: DateRange,
    *,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """How far through the campaign is, in time and in posts.

    Both fractions are null when their denominator does not exist -- an
    open-ended campaign has no elapsed *fraction*, and a campaign with no posts
    linked has no publishing progress. Reporting either as 0 would read as
    "nothing has happened yet" when the truth is "there is nothing to measure
    against", which is the same mistake as a 0% engagement rate.
    """
    now = now or datetime.now(timezone.utc)

    counts = dict(
        (
            await db.execute(
                select(Post.status, func.count(Post.id))
                .where(
                    Post.campaign_id == campaign.id,
                    Post.deleted_at.is_(None),
                )
                .group_by(Post.status)
            )
        ).all()
    )
    posts_total = sum(counts.values())
    posts_published = sum(counts.get(st, 0) for st in PUBLISHED_STATUSES)
    posts_scheduled = counts.get(PostStatus.SCHEDULED, 0)

    total_days = max(1, (window.end - window.start).days)
    elapsed_days = (min(now, window.end) - window.start).days
    elapsed_days = max(0, min(elapsed_days, total_days))

    # A campaign with no end date has a window that ends "now", so its time
    # fraction would always be 100% -- a meaningless number dressed as a
    # complete one.
    scheduled_run = campaign.end_date is not None
    time_progress = round(elapsed_days / total_days, 4) if scheduled_run else None
    post_progress = (
        round(posts_published / posts_total, 4) if posts_total else None
    )

    return {
        "starts_on": campaign.start_date.isoformat() if campaign.start_date else None,
        "ends_on": campaign.end_date.isoformat() if campaign.end_date else None,
        "open_ended": not scheduled_run,
        "days_total": total_days if scheduled_run else None,
        "days_elapsed": elapsed_days,
        "days_remaining": (
            max(0, total_days - elapsed_days) if scheduled_run else None
        ),
        "time_progress": time_progress,
        "posts_total": posts_total,
        "posts_published": posts_published,
        "posts_scheduled": posts_scheduled,
        "post_progress": post_progress,
        # Only meaningful when both fractions exist. "On track" against an
        # unknown deadline or an empty campaign is not a judgement worth
        # rendering.
        "on_track": (
            None
            if time_progress is None or post_progress is None
            else post_progress >= time_progress
        ),
    }


async def dashboard(
    db: AsyncSession,
    account: Account,
    campaign: Campaign,
    *,
    top_limit: int = 5,
    now: Optional[datetime] = None,
    window: Optional[DateRange] = None,
) -> dict[str, Any]:
    """The whole campaign performance payload, in one place.

    Shared by ``GET /campaigns/{id}/performance`` and by campaign-scoped
    reports, so the dashboard and the PDF a client receives cannot disagree.

    ``window`` overrides the campaign's own window. Reports pass the period
    they stored at creation: an open-ended campaign's window ends "now", so a
    report that re-derived it would cover a different span every time it was
    regenerated, and a client's second copy would not match their first.
    """
    window = window or campaign_window(account, campaign, now=now)

    totals_row = await totals(db, campaign.id, window)
    return {
        "campaign": {
            "id": str(campaign.id),
            "name": campaign.name,
            "objective": campaign.objective,
            "status": campaign.status.value,
        },
        "window": {
            "start": window.start.isoformat(),
            "end": window.end.isoformat(),
            "label": window.label,
            "timezone": window.timezone_name,
        },
        "totals": totals_row,
        "progress": await progress(db, campaign, window, now=now),
        "platforms": await platform_split(db, campaign.id, window),
        "top_posts": await analytics_query.posts(
            db, account, window,
            sort="engagement", order="desc", limit=top_limit,
            campaign_id=campaign.id,
        ),
        "budget": {
            "total": campaign.budget_total,
            "spent": campaign.budget_spent,
            "remaining": (
                campaign.budget_total - campaign.budget_spent
                if campaign.budget_total is not None
                else None
            ),
        },
        # Named so a reader of the report knows what is missing and why, rather
        # than wondering where the follower count went.
        "not_attributable": [
            "Follower counts and audience demographics are account-level daily "
            "snapshots with no campaign dimension, so they cannot be attributed "
            "to a single campaign."
        ],
    }


__all__ = [
    "campaign_window",
    "dashboard",
    "platform_split",
    "progress",
    "totals",
]
