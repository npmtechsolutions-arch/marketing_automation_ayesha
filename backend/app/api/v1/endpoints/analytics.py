"""Analytics endpoints with proper SQLAlchemy aggregate queries."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.post import Post, PostStatus
from app.models.post_performance import PostPerformance
from app.models.team_member import TeamMember
from app.schemas.analytics import (
    AnalyticsExport,
    AnalyticsOverview,
    PerformanceTrend,
    TopPost,
)
from app.schemas.common import MessageResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _verify_account_access(account_id: uuid.UUID, user, db: AsyncSession) -> TeamMember:
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.account_id == account_id,
            TeamMember.user_id == user.id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this account",
        )
    return member


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

    delta = _period_to_timedelta(period)
    now = datetime.now(timezone.utc)
    period_start = now - delta
    prev_period_start = period_start - delta

    # Current period
    current_stmt = (
        select(
            func.coalesce(func.sum(PostPerformance.reach), 0).label("total_reach"),
            func.coalesce(
                func.sum(PostPerformance.likes + PostPerformance.comments + PostPerformance.shares + PostPerformance.saves),
                0,
            ).label("total_engagement"),
            func.coalesce(func.avg(PostPerformance.engagement_rate), 0.0).label("avg_engagement_rate"),
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
            func.coalesce(func.sum(PostPerformance.reach), 0).label("total_reach"),
            func.coalesce(
                func.sum(PostPerformance.likes + PostPerformance.comments + PostPerformance.shares + PostPerformance.saves),
                0,
            ).label("total_engagement"),
            func.coalesce(func.avg(PostPerformance.engagement_rate), 0.0).label("avg_engagement_rate"),
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

    def _pct_change(current_val: float, prev_val: float) -> float | None:
        if prev_val == 0:
            return None
        return round(((current_val - prev_val) / prev_val) * 100, 2)

    comparison = {
        "reach_change_pct": _pct_change(float(current.total_reach), float(prev.total_reach)),
        "engagement_change_pct": _pct_change(float(current.total_engagement), float(prev.total_engagement)),
        "engagement_rate_change_pct": _pct_change(float(current.avg_engagement_rate), float(prev.avg_engagement_rate)),
    }

    return AnalyticsOverview(
        total_reach=int(current.total_reach),
        total_engagement=int(current.total_engagement),
        avg_engagement_rate=round(float(current.avg_engagement_rate), 4),
        total_followers_gained=0,  # Requires platform-specific follower tracking
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
