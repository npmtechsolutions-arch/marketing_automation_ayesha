import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.services import analytics_query, dashboard
from app.services import best_times as best_times_service
from app.core.deps import get_current_active_user
from app.models.account import Account
from app.models.post import Post, PostStatus
from app.models.post_performance import PostPerformance
from app.api.v1.endpoints.posts import _sync_post_performance
from app.schemas.analytics import (
    AnalyticsExport,
    AnalyticsOverview,
    PerformanceTrend,
    TopPost,
)
from app.core.authz import verify_account_access as _verify_account_access

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_account_sync_locks: dict[uuid.UUID, asyncio.Lock] = {}

def _get_account_sync_lock(account_id: uuid.UUID) -> asyncio.Lock:
    if account_id not in _account_sync_locks:
        _account_sync_locks[account_id] = asyncio.Lock()
    return _account_sync_locks[account_id]

async def _sync_all_account_posts(account_id: uuid.UUID, db: AsyncSession) -> None:
    """Sync performance metrics for all published posts under the account."""
    lock = _get_account_sync_lock(account_id)
    async with lock:
        now = datetime.now(timezone.utc)
        limit_date = now - timedelta(days=90)
        # Fetch all published posts within 90 days
        stmt = (
            select(Post)
            .where(
                Post.account_id == account_id,
                Post.deleted_at.is_(None),
                Post.status == PostStatus.PUBLISHED,
                Post.published_at >= limit_date,
            )
            .options(selectinload(Post.performances))
        )
        result = await db.execute(stmt)
        posts = result.scalars().all()

        synced_any = False
        for post in posts:
            needs_sync = False
            if not post.performances:
                needs_sync = True
            else:
                for perf in post.performances:
                    fetched_at = perf.fetched_at
                    if fetched_at.tzinfo is None:
                        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
                    # Sync if fetched_at is older than 5 minutes
                    if now - fetched_at > timedelta(minutes=5):
                        needs_sync = True
                        break
            
            if needs_sync:
                try:
                    await _sync_post_performance(post, db)
                    synced_any = True
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(
                        "Failed to sync performance for post %s: %s", post.id, e
                    )
        
        if synced_any:
            await db.commit()


def _period_to_timedelta(period: str) -> timedelta:
    mapping = {"7d": timedelta(days=7), "30d": timedelta(days=30), "90d": timedelta(days=90)}
    return mapping.get(period, timedelta(days=30))


class ExportResponse(BaseModel):
    download_url: str
    expires_at: datetime


class PlatformBreakdownItem(BaseModel):
    platform: str
    impressions: int
    reach: int
    likes: int
    comments: int
    shares: int
    clicks: int
    engagement_rate: float
    post_count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=AnalyticsOverview)
async def analytics_overview(
    account_id: uuid.UUID,
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Aggregate analytics metrics with comparison to the previous period."""
    await _verify_account_access(account_id, current_user, db)
    await _sync_all_account_posts(account_id, db)

    delta = _period_to_timedelta(period)
    now = datetime.now(timezone.utc)
    period_start = now - delta
    prev_period_start = period_start - delta

    # Current period
    # No coalesce to 0 anywhere here. SUM and AVG over no rows are NULL, which
    # is the honest answer for a workspace that has measured nothing -- and the
    # difference between "nobody saw the post" and "we have not measured" is
    # the whole of this project's numbers doctrine. COUNT is left alone: zero
    # posts published is a measurement.
    current_stmt = (
        select(
            func.sum(PostPerformance.reach).label("total_reach"),
            func.sum(
                PostPerformance.likes + PostPerformance.comments
                + PostPerformance.shares + PostPerformance.saves
            ).label("total_engagement"),
            func.avg(PostPerformance.engagement_rate).label("avg_engagement_rate"),
            func.count(func.distinct(PostPerformance.post_id)).label("total_posts"),
        )
        .join(Post, Post.id == PostPerformance.post_id)
        .where(
            Post.account_id == account_id,
            Post.deleted_at.is_(None),
            Post.status == PostStatus.PUBLISHED,
            PostPerformance.created_at >= period_start,
        )
    )
    current = (await db.execute(current_stmt)).one()

    # Previous period for comparison
    prev_stmt = (
        select(
            func.sum(PostPerformance.reach).label("total_reach"),
            func.sum(
                PostPerformance.likes + PostPerformance.comments
                + PostPerformance.shares + PostPerformance.saves
            ).label("total_engagement"),
            func.avg(PostPerformance.engagement_rate).label("avg_engagement_rate"),
        )
        .join(Post, Post.id == PostPerformance.post_id)
        .where(
            Post.account_id == account_id,
            Post.deleted_at.is_(None),
            Post.status == PostStatus.PUBLISHED,
            PostPerformance.created_at >= prev_period_start,
            PostPerformance.created_at < period_start,
        )
    )
    prev = (await db.execute(prev_stmt)).one()

    def _pct_change(current_val, prev_val) -> float | None:
        # A change needs both ends. An unmeasured previous period is not a
        # baseline of zero, and dividing by it would report a rise out of
        # nothing -- which is how the dashboard came to show a green "+%" on a
        # workspace that had never published.
        if current_val is None or prev_val is None or float(prev_val) == 0:
            return None
        return round(((float(current_val) - float(prev_val)) / float(prev_val)) * 100, 2)

    comparison = {
        "reach_change_pct": _pct_change(current.total_reach, prev.total_reach),
        "engagement_change_pct": _pct_change(current.total_engagement, prev.total_engagement),
        "engagement_rate_change_pct": _pct_change(
            current.avg_engagement_rate, prev.avg_engagement_rate
        ),
    }

    # Was `total_followers_gained=0` with a comment saying follower tracking
    # did not exist. It does -- analytics_daily records it and
    # analytics_query.audience() computes the change with the right null
    # handling (a single snapshot is a value, not growth). A hardcoded 0 was
    # reporting "gained nobody" to every workspace, measured or not.
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one()
    window = analytics_query.resolve(account, period, None, None)
    audience = await analytics_query.audience(db, account, window)

    return AnalyticsOverview(
        total_reach=int(current.total_reach) if current.total_reach is not None else None,
        total_engagement=(
            int(current.total_engagement) if current.total_engagement is not None else None
        ),
        avg_engagement_rate=(
            round(float(current.avg_engagement_rate), 4)
            if current.avg_engagement_rate is not None else None
        ),
        total_followers_gained=audience.get("change"),
        total_posts=int(current.total_posts),
        period=period,
        comparison=comparison,
    )


@router.get("/top-posts", response_model=list[TopPost])
async def top_posts(
    account_id: uuid.UUID,
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Return the top-performing posts by engagement rate."""
    await _verify_account_access(account_id, current_user, db)
    await _sync_all_account_posts(account_id, db)

    delta = _period_to_timedelta(period)
    period_start = datetime.now(timezone.utc) - delta

    stmt = (
        select(
            Post.id.label("post_id"),
            Post.content,
            PostPerformance.platform_type.label("platform"),
            PostPerformance.engagement_rate,
            (
                PostPerformance.likes
                + PostPerformance.comments
                + PostPerformance.shares
                + PostPerformance.saves
            ).label("total_engagement"),
            Post.published_at,
        )
        .join(PostPerformance, PostPerformance.post_id == Post.id)
        .where(
            Post.account_id == account_id,
            Post.deleted_at.is_(None),
            Post.status == PostStatus.PUBLISHED,
            Post.published_at >= period_start,
        )
        .order_by(PostPerformance.engagement_rate.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    return [
        TopPost(
            post_id=row.post_id,
            content=row.content[:200] if row.content else "",
            platform=row.platform,
            engagement_rate=row.engagement_rate,
            total_engagement=row.total_engagement,
            published_at=row.published_at,
        )
        for row in rows
    ]


@router.get("/trends", response_model=list[PerformanceTrend])
async def performance_trends(
    account_id: uuid.UUID,
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    group_by: str = Query("day", pattern="^(day|week|month)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Performance trends over time grouped by day, week, or month."""
    await _verify_account_access(account_id, current_user, db)
    await _sync_all_account_posts(account_id, db)

    delta = _period_to_timedelta(period)
    period_start = datetime.now(timezone.utc) - delta

    # Build the date truncation expression
    if group_by == "day":
        date_trunc = func.date_trunc("day", PostPerformance.created_at)
    elif group_by == "week":
        date_trunc = func.date_trunc("week", PostPerformance.created_at)
    else:
        date_trunc = func.date_trunc("month", PostPerformance.created_at)

    stmt = (
        select(
            date_trunc.label("period_date"),
            func.coalesce(func.sum(PostPerformance.impressions), 0).label("impressions"),
            func.coalesce(func.sum(PostPerformance.reach), 0).label("reach"),
            func.coalesce(
                func.sum(
                    PostPerformance.likes
                    + PostPerformance.comments
                    + PostPerformance.shares
                    + PostPerformance.saves
                ),
                0,
            ).label("engagement"),
        )
        .join(Post, Post.id == PostPerformance.post_id)
        .where(
            Post.account_id == account_id,
            Post.deleted_at.is_(None),
            PostPerformance.created_at >= period_start,
        )
        .group_by(date_trunc)
        .order_by(date_trunc.asc())
    )
    rows = (await db.execute(stmt)).all()

    return [
        PerformanceTrend(
            date=row.period_date.strftime("%Y-%m-%d") if row.period_date else "",
            impressions=int(row.impressions),
            reach=int(row.reach),
            engagement=int(row.engagement),
            followers=0,  # Requires separate follower tracking
        )
        for row in rows
    ]


@router.get("/platform-breakdown", response_model=list[PlatformBreakdownItem])
async def platform_breakdown(
    account_id: uuid.UUID,
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Metrics broken down by platform."""
    await _verify_account_access(account_id, current_user, db)
    await _sync_all_account_posts(account_id, db)

    delta = _period_to_timedelta(period)
    period_start = datetime.now(timezone.utc) - delta

    stmt = (
        select(
            PostPerformance.platform_type.label("platform"),
            func.coalesce(func.sum(PostPerformance.impressions), 0).label("impressions"),
            func.coalesce(func.sum(PostPerformance.reach), 0).label("reach"),
            func.coalesce(func.sum(PostPerformance.likes), 0).label("likes"),
            func.coalesce(func.sum(PostPerformance.comments), 0).label("comments"),
            func.coalesce(func.sum(PostPerformance.shares), 0).label("shares"),
            func.coalesce(func.sum(PostPerformance.clicks), 0).label("clicks"),
            func.coalesce(func.avg(PostPerformance.engagement_rate), 0.0).label("engagement_rate"),
            func.count(func.distinct(PostPerformance.post_id)).label("post_count"),
        )
        .join(Post, Post.id == PostPerformance.post_id)
        .where(
            Post.account_id == account_id,
            Post.deleted_at.is_(None),
            PostPerformance.created_at >= period_start,
        )
        .group_by(PostPerformance.platform_type)
        .order_by(func.sum(PostPerformance.reach).desc())
    )
    rows = (await db.execute(stmt)).all()

    return [
        PlatformBreakdownItem(
            platform=row.platform,
            impressions=int(row.impressions),
            reach=int(row.reach),
            likes=int(row.likes),
            comments=int(row.comments),
            shares=int(row.shares),
            clicks=int(row.clicks),
            engagement_rate=round(float(row.engagement_rate), 4),
            post_count=int(row.post_count),
        )
        for row in rows
    ]


@router.post("/export", response_model=ExportResponse)
async def export_analytics(
    account_id: uuid.UUID,
    body: AnalyticsExport,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Generate an analytics report (placeholder - returns a download URL)."""
    await _verify_account_access(account_id, current_user, db)

    # Placeholder: In production, queue a background job to generate the report
    # and upload to S3, then return a presigned URL.
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    download_url = (
        f"https://storage.marketengine.ai/reports/{account_id}/"
        f"analytics_{body.period}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.{body.format}"
    )

    return ExportResponse(download_url=download_url, expires_at=expires)


# ---------------------------------------------------------------------------
# Range-based analytics (scope §12)
#
# These take the same date-range parameters as the dashboard, resolved by the
# same code -- so a picker on the analytics page and one on the dashboard mean
# the same window. Each accepts ?format=csv and streams the same data.
# ---------------------------------------------------------------------------

def _csv_response(body: str, filename: str) -> StreamingResponse:
    """Stream rather than build a string response.

    A 90-day export across many accounts is large enough that holding the whole
    encoded body in memory per request is worth avoiding, and the browser gets
    a download prompt either way.
    """
    return StreamingResponse(
        iter([body]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            # The body is user-influenced text; stop a browser sniffing it into
            # something it will render.
            "X-Content-Type-Options": "nosniff",
        },
    )


async def _range_context(account_id, current_user, db, range_key, date_from, date_to):
    await _verify_account_access(account_id, current_user, db)
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one()
    return account, analytics_query.resolve(account, range_key, date_from, date_to)


@router.get("/summary")
async def analytics_summary(
    account_id: uuid.UUID,
    range: str = Query("30d"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    format: str | None = Query(None, pattern="^csv$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Totals for the window, with deltas against the preceding one."""
    account, window = await _range_context(
        account_id, current_user, db, range, date_from, date_to
    )
    payload = await analytics_query.overview(db, account, window)
    if format == "csv":
        return _csv_response(
            analytics_query.overview_csv(payload),
            f"analytics-overview-{window.start.date()}-to-{window.end.date()}.csv",
        )
    return payload


@router.get("/platforms")
async def analytics_platforms(
    account_id: uuid.UUID,
    range: str = Query("30d"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    format: str | None = Query(None, pattern="^csv$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Per-platform breakdown."""
    account, window = await _range_context(
        account_id, current_user, db, range, date_from, date_to
    )
    rows = await analytics_query.platforms(db, account, window)
    if format == "csv":
        return _csv_response(
            analytics_query.to_csv(rows),
            f"analytics-platforms-{window.start.date()}-to-{window.end.date()}.csv",
        )
    return {"platforms": rows}


@router.get("/posts")
async def analytics_posts(
    account_id: uuid.UUID,
    range: str = Query("30d"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    sort: str = Query("engagement", pattern="^(engagement|impressions|reach|date)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=500),
    format: str | None = Query(None, pattern="^csv$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Content performance, sortable."""
    account, window = await _range_context(
        account_id, current_user, db, range, date_from, date_to
    )
    rows = await analytics_query.posts(
        db, account, window, sort=sort, order=order, limit=limit
    )
    if format == "csv":
        return _csv_response(
            analytics_query.to_csv(rows),
            f"analytics-posts-{window.start.date()}-to-{window.end.date()}.csv",
        )
    return {"posts": rows}


@router.get("/audience")
async def analytics_audience(
    account_id: uuid.UUID,
    range: str = Query("30d"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    format: str | None = Query(None, pattern="^csv$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Follower growth over the window."""
    account, window = await _range_context(
        account_id, current_user, db, range, date_from, date_to
    )
    payload = await analytics_query.audience(db, account, window)
    if format == "csv":
        return _csv_response(
            analytics_query.to_csv(payload["series"]),
            f"analytics-audience-{window.start.date()}-to-{window.end.date()}.csv",
        )
    return payload


@router.get("/best-times")
async def best_times(
    account_id: uuid.UUID,
    social_account_id: uuid.UUID | None = Query(
        None, description="Narrow to one connection. Omit for the whole workspace."
    ),
    window_days: int = Query(84, ge=14, le=365),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """When this account's posts have actually performed, by weekday and hour.

    The payload carries a ``source`` of ``observed`` or ``default``, and every
    heatmap cell carries ``observed``. A caller must respect both: below the
    sample threshold these are the platform's usual posting times, not this
    account's data, and presenting them as measurements is the fabrication this
    feature replaced.

    Hours are on the workspace's clock. ``analytics_daily`` is not consulted --
    it stores a date and no hour, so it cannot say anything about time of day.
    """
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await _verify_account_access(account_id, current_user, db)

    try:
        return await best_times_service.analyse(
            db, account,
            social_account_id=social_account_id,
            window_days=window_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/best-times/next")
async def best_time_slots(
    account_id: uuid.UUID,
    social_account_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """The suggested slots as concrete upcoming datetimes.

    So a chip in the composer can fill the scheduler without the browser doing
    weekday arithmetic in its own timezone -- the mistake the S2 defect was.
    """
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await _verify_account_access(account_id, current_user, db)

    report = await best_times_service.analyse(
        db, account, social_account_id=social_account_id
    )
    tz = dashboard.workspace_timezone(account)
    return {
        "source": report["source"],
        "timezone": tz.key,
        "explanation": report["explanation"],
        "slots": [
            {
                **suggestion,
                "run_at": best_times_service.next_occurrence(
                    suggestion["weekday"], suggestion["hour"], tz
                ).isoformat(),
                "local": best_times_service.next_occurrence(
                    suggestion["weekday"], suggestion["hour"], tz
                ).astimezone(tz).strftime("%Y-%m-%dT%H:%M"),
            }
            for suggestion in report["suggestions"]
        ],
    }
