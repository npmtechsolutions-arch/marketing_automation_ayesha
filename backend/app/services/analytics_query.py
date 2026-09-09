"""Reading analytics: overview, per-platform, per-post, audience.

All four views share the range resolution from the dashboard, so a date picker
on the analytics page and one on the dashboard mean the same thing.

Two rules run through everything here:

* **Cumulative metrics are not summed.** Followers on Monday plus followers on
  Tuesday is not a number. Aggregates take the latest value in the window, and
  growth is last-minus-first.
* **Null is preserved.** A platform that does not report reach contributes
  nothing to a reach total rather than a zero, and a total with no contributors
  stays null. Summing absent-as-zero would show a real, flat, wrong line and
  drag cross-platform averages down.
"""

import csv
import io
import logging
import uuid
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.analytics_daily import CUMULATIVE_FIELDS, METRIC_FIELDS, AnalyticsDaily
from app.models.platform import SocialAccount, SocialPlatform
from app.models.post import Post
from app.models.post_performance import PostPerformance
from app.services.dashboard import DateRange, resolve_range

logger = logging.getLogger(__name__)

# Metrics that are daily amounts and therefore safe to add up.
SUMMABLE_FIELDS = tuple(f for f in METRIC_FIELDS if f not in CUMULATIVE_FIELDS)


def _window_dates(window: DateRange) -> tuple[date, date]:
    """The inclusive calendar days a window covers.

    The window is half-open in time; AnalyticsDaily stores whole days, so the
    last day is the one before ``end``.
    """
    return window.start.date(), (window.end - timedelta(days=1)).date()


def _delta(current: Optional[float], previous: Optional[float]) -> dict:
    """Change between two periods, as an absolute and a percentage.

    Both are null when either side is missing: "up 100%" computed against a
    period with no data is a fabrication, and a dash is the honest rendering.
    Growth from zero has no percentage either -- any increase is infinite.
    """
    if current is None or previous is None:
        return {"change": None, "change_percent": None}
    change = current - previous
    if not previous:
        return {"change": change, "change_percent": None}
    return {"change": change, "change_percent": round(change / previous * 100, 1)}


async def _account_ids(db: AsyncSession, account_id) -> list:
    return list(
        (
            await db.execute(
                select(SocialAccount.id).where(
                    SocialAccount.account_id == account_id
                )
            )
        ).scalars().all()
    )


async def _totals(
    db: AsyncSession, social_ids: list, window: DateRange
) -> dict[str, Optional[int]]:
    """Aggregate one window into a single row of metrics."""
    if not social_ids:
        return {name: None for name in METRIC_FIELDS}

    start, end = _window_dates(window)
    columns = [
        func.sum(getattr(AnalyticsDaily, name)).label(name)
        for name in SUMMABLE_FIELDS
    ]
    # Cumulative metrics take the most recent value in the window, per account,
    # then add across accounts -- so a workspace's follower total is the sum of
    # each connection's latest count, not of every daily snapshot.
    row = (
        await db.execute(
            select(*columns).where(
                AnalyticsDaily.social_account_id.in_(social_ids),
                AnalyticsDaily.date >= start,
                AnalyticsDaily.date <= end,
            )
        )
    ).one()
    totals: dict[str, Optional[int]] = {
        name: (int(getattr(row, name)) if getattr(row, name) is not None else None)
        for name in SUMMABLE_FIELDS
    }

    for name in CUMULATIVE_FIELDS:
        column = getattr(AnalyticsDaily, name)
        latest = (
            select(
                AnalyticsDaily.social_account_id,
                func.max(AnalyticsDaily.date).label("day"),
            )
            .where(
                AnalyticsDaily.social_account_id.in_(social_ids),
                AnalyticsDaily.date >= start,
                AnalyticsDaily.date <= end,
                column.is_not(None),
            )
            .group_by(AnalyticsDaily.social_account_id)
            .subquery()
        )
        value = (
            await db.execute(
                select(func.sum(column))
                .select_from(AnalyticsDaily)
                .join(
                    latest,
                    (AnalyticsDaily.social_account_id == latest.c.social_account_id)
                    & (AnalyticsDaily.date == latest.c.day),
                )
            )
        ).scalar()
        totals[name] = int(value) if value is not None else None

    return totals


INTERACTION_FIELDS = ("likes", "comments", "shares", "saves")


def _engagement_rate(totals: dict) -> Optional[float]:
    """Interactions over reach, as a percentage.

    Null rather than zero in two cases, both of which would otherwise render as
    a confident 0% -- "nobody engaged with your content" -- when the truth is
    that nothing was measured:

    * **No reach.** There is nothing to divide by.
    * **No interaction metric reported at all.** X and LinkedIn expose no
      account-level likes or comments, so a workspace connected only to those
      has a real reach and an entirely unmeasured numerator. Coalescing that to
      zero produced a 0.0% rate for a workspace with 61,000 reach.

    A partially reported numerator *is* summed with the absent parts as zero:
    a platform that reports likes but has no "saves" concept genuinely
    contributed no saves.
    """
    reach = totals.get("reach")
    if not reach:
        return None
    reported = [totals.get(name) for name in INTERACTION_FIELDS]
    if all(value is None for value in reported):
        return None
    return round(sum(v or 0 for v in reported) / reach * 100, 2)


async def overview(
    db: AsyncSession, account: Account, window: DateRange
) -> dict:
    """Totals for the window, and how they compare with the one before."""
    social_ids = await _account_ids(db, account.id)
    previous_window = window.previous()

    current = await _totals(db, social_ids, window)
    previous = await _totals(db, social_ids, previous_window)

    metrics = {}
    for name in METRIC_FIELDS:
        metrics[name] = {
            "value": current[name],
            "previous": previous[name],
            **_delta(current[name], previous[name]),
        }

    current_rate = _engagement_rate(current)
    previous_rate = _engagement_rate(previous)
    metrics["engagement_rate"] = {
        "value": current_rate,
        "previous": previous_rate,
        **_delta(current_rate, previous_rate),
    }

    return {
        "range": {
            "key": window.label,
            "start": window.start.isoformat(),
            "end": window.end.isoformat(),
            "days": window.days,
            "timezone": window.timezone_name,
        },
        "compared_to": {
            "start": previous_window.start.isoformat(),
            "end": previous_window.end.isoformat(),
        },
        "metrics": metrics,
        # So a client can say "no data yet" rather than drawing an empty chart.
        "has_data": any(current[name] is not None for name in METRIC_FIELDS),
    }


async def platforms(
    db: AsyncSession, account: Account, window: DateRange
) -> list[dict]:
    """Per-platform breakdown, one row per connected platform."""
    start, end = _window_dates(window)
    columns = [
        func.sum(getattr(AnalyticsDaily, name)).label(name)
        for name in SUMMABLE_FIELDS
    ]
    rows = (
        await db.execute(
            select(
                SocialPlatform.slug,
                SocialPlatform.name,
                func.count(func.distinct(SocialAccount.id)).label("accounts"),
                func.max(AnalyticsDaily.followers).label("followers"),
                *columns,
            )
            .select_from(AnalyticsDaily)
            .join(SocialAccount, SocialAccount.id == AnalyticsDaily.social_account_id)
            .join(SocialPlatform, SocialPlatform.id == SocialAccount.platform_id)
            .where(
                SocialAccount.account_id == account.id,
                AnalyticsDaily.date >= start,
                AnalyticsDaily.date <= end,
            )
            .group_by(SocialPlatform.slug, SocialPlatform.name)
            .order_by(SocialPlatform.slug)
        )
    ).all()

    result = []
    for row in rows:
        metrics = {
            name: (int(getattr(row, name)) if getattr(row, name) is not None else None)
            for name in SUMMABLE_FIELDS
        }
        metrics["followers"] = int(row.followers) if row.followers is not None else None
        result.append(
            {
                "platform": row.slug,
                "platform_name": row.name,
                "accounts": int(row.accounts),
                **metrics,
                "engagement_rate": _engagement_rate(metrics),
            }
        )
    return result


async def posts(
    db: AsyncSession,
    account: Account,
    window: DateRange,
    *,
    sort: str = "engagement",
    order: str = "desc",
    limit: int = 50,
    campaign_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    """Content performance, sortable.

    Reads post_performances rather than analytics_daily: per-post numbers are
    per-post, and joining a daily account snapshot to individual posts would
    attribute the whole account's reach to each of them.

    ``campaign_id`` narrows the same query to one campaign's posts. It is a
    filter on this function rather than a separate query so that a figure on a
    campaign dashboard is the figure the analytics page would show for the same
    post -- the drift this project keeps killing starts with a second query
    that means almost the same thing.
    """
    engagement = (
        func.coalesce(func.sum(PostPerformance.likes), 0)
        + func.coalesce(func.sum(PostPerformance.comments), 0)
        + func.coalesce(func.sum(PostPerformance.shares), 0)
        + func.coalesce(func.sum(PostPerformance.saves), 0)
    ).label("engagement")
    impressions = func.coalesce(func.sum(PostPerformance.impressions), 0).label("impressions")
    reach = func.coalesce(func.sum(PostPerformance.reach), 0).label("reach")

    sortable = {
        "engagement": engagement,
        "impressions": impressions,
        "reach": reach,
        "date": Post.published_at,
    }
    column = sortable.get(sort, engagement)
    ordering = column.desc() if order == "desc" else column.asc()

    rows = (
        await db.execute(
            select(
                Post.id, Post.title, Post.content, Post.published_at,
                engagement, impressions, reach,
                func.coalesce(func.sum(PostPerformance.clicks), 0).label("clicks"),
                func.coalesce(func.sum(PostPerformance.video_views), 0).label("video_views"),
                # Rate per post, guarding the divide -- a post with no measured
                # reach reports null, not a division error.
                #
                # Numeric, not Float: Postgres has no round(double precision,
                # int), only round(numeric, int). SQLite accepts either, so a
                # Float cast here passes the whole suite and 500s in
                # production. Found by driving the running server.
                (
                    func.round(
                        cast(
                            func.coalesce(func.sum(PostPerformance.likes), 0)
                            + func.coalesce(func.sum(PostPerformance.comments), 0)
                            + func.coalesce(func.sum(PostPerformance.shares), 0)
                            + func.coalesce(func.sum(PostPerformance.saves), 0),
                            Numeric,
                        )
                        * 100
                        / func.nullif(func.sum(PostPerformance.reach), 0),
                        2,
                    )
                ).label("engagement_rate"),
            )
            .join(PostPerformance, PostPerformance.post_id == Post.id)
            .where(
                Post.account_id == account.id,
                Post.deleted_at.is_(None),
                Post.created_at >= window.start,
                Post.created_at < window.end,
                *(
                    [Post.campaign_id == campaign_id]
                    if campaign_id is not None
                    else []
                ),
            )
            .group_by(Post.id, Post.title, Post.content, Post.published_at)
            .order_by(ordering)
            .limit(limit)
        )
    ).all()

    return [
        {
            "id": str(r.id),
            "title": r.title or (r.content or "")[:80] or "Untitled post",
            "published_at": r.published_at.isoformat() if r.published_at else None,
            "engagement": int(r.engagement),
            "impressions": int(r.impressions),
            "reach": int(r.reach),
            "clicks": int(r.clicks),
            "video_views": int(r.video_views),
            "engagement_rate": (
                float(r.engagement_rate) if r.engagement_rate is not None else None
            ),
        }
        for r in rows
    ]


async def audience(
    db: AsyncSession, account: Account, window: DateRange
) -> dict:
    """Follower series across the window, plus growth.

    One point per day summing each connection's latest count for that day, so a
    day where one platform failed to sync does not read as a collapse in
    audience.
    """
    social_ids = await _account_ids(db, account.id)
    if not social_ids:
        # The same keys as the populated return below. These were "growth" and
        # "growth_percent" while the real path returned "change" and
        # "change_percent", so a workspace with no connected account crashed
        # _executive_summary with KeyError: 'change' -- and every report for a
        # brand-new workspace failed with "Could not gather the numbers".
        return {
            "series": [],
            "current": None,
            "change": None,
            "change_percent": None,
        }

    start, end = _window_dates(window)
    rows = (
        await db.execute(
            select(
                AnalyticsDaily.date,
                func.sum(AnalyticsDaily.followers).label("followers"),
                func.sum(AnalyticsDaily.following).label("following"),
            )
            .where(
                AnalyticsDaily.social_account_id.in_(social_ids),
                AnalyticsDaily.date >= start,
                AnalyticsDaily.date <= end,
                AnalyticsDaily.followers.is_not(None),
            )
            .group_by(AnalyticsDaily.date)
            .order_by(AnalyticsDaily.date)
        )
    ).all()

    series = [
        {
            "date": r.date.isoformat(),
            "followers": int(r.followers) if r.followers is not None else None,
            "following": int(r.following) if r.following is not None else None,
        }
        for r in rows
    ]

    first = series[0]["followers"] if series else None
    last = series[-1]["followers"] if series else None
    return {
        "series": series,
        "current": last,
        # Last minus first within the window, not a sum. Null with fewer than
        # two points -- a single snapshot shows no growth, it shows a value.
        **(
            _delta(last, first)
            if len(series) > 1
            else {"change": None, "change_percent": None}
        ),
    }


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def to_csv(rows: list[dict], columns: Optional[list[str]] = None) -> str:
    """Render rows as CSV.

    Empty cells for null rather than the string "None", so a spreadsheet reads
    an unreported metric as blank instead of as text.
    """
    if not rows:
        return ""
    columns = columns or list(rows[0].keys())
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: ("" if row.get(c) is None else row.get(c)) for c in columns})
    return buffer.getvalue()


def overview_csv(payload: dict) -> str:
    """The overview is nested, so it is flattened one metric per row."""
    return to_csv(
        [
            {
                "metric": name,
                "value": data["value"],
                "previous": data["previous"],
                "change": data["change"],
                "change_percent": data["change_percent"],
            }
            for name, data in payload["metrics"].items()
        ],
        ["metric", "value", "previous", "change", "change_percent"],
    )


def resolve(account: Account, range_key, date_from, date_to) -> DateRange:
    """The shared range resolution, so analytics and the dashboard agree."""
    return resolve_range(account, range_key, date_from, date_to)
