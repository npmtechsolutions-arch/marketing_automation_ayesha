"""Activity log endpoints."""

import math
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, cast, func, select, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.audit_log import ActivityLog
from app.models.team_member import InvitationStatus, TeamMember
from app.models.user import User
from app.schemas.activity import ActivityLogResponse, ActivityStatsResponse
from app.schemas.common import PaginatedResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _verify_membership(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> TeamMember:
    """Ensure the current user is an accepted member of the account."""
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.user_id == user_id,
            TeamMember.account_id == account_id,
            TeamMember.invitation_status == InvitationStatus.ACCEPTED,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this account",
        )
    return member


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=PaginatedResponse[ActivityLogResponse])
async def list_activity_logs(
    account_id: uuid.UUID,
    category: str | None = Query(None, description="Filter by category (e.g., 'post', 'platform', 'account')"),
    action: str | None = Query(None, description="Filter by action (e.g., 'post.created')"),
    date_from: datetime | None = Query(None, description="Filter from date (ISO 8601)"),
    date_to: datetime | None = Query(None, description="Filter to date (ISO 8601)"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List activity logs for an account with optional filters and pagination."""
    await _verify_membership(db, current_user.id, account_id)

    conditions = [ActivityLog.account_id == account_id]

    if category:
        conditions.append(ActivityLog.category == category)
    if action:
        conditions.append(ActivityLog.action == action)
    if date_from:
        conditions.append(ActivityLog.created_at >= date_from)
    if date_to:
        conditions.append(ActivityLog.created_at <= date_to)
    if resource_type:
        conditions.append(ActivityLog.resource_type == resource_type)
    if status_filter:
        conditions.append(ActivityLog.status == status_filter)

    where_clause = and_(*conditions)

    count_result = await db.execute(
        select(func.count(ActivityLog.id)).where(where_clause)
    )
    total = count_result.scalar() or 0

    stmt = (
        select(ActivityLog)
        .where(where_clause)
        .order_by(ActivityLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    logs = result.scalars().all()

    return PaginatedResponse[ActivityLogResponse](
        items=[ActivityLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.get("/stats", response_model=ActivityStatsResponse)
async def get_activity_stats(
    account_id: uuid.UUID,
    days: int = Query(30, ge=1, le=365, description="Number of days to include in stats"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get activity statistics: actions per day and most active categories."""
    await _verify_membership(db, current_user.id, account_id)

    from datetime import timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    base_conditions = [
        ActivityLog.account_id == account_id,
        ActivityLog.created_at >= cutoff,
    ]

    # Total actions
    total_result = await db.execute(
        select(func.count(ActivityLog.id)).where(and_(*base_conditions))
    )
    total_actions = total_result.scalar() or 0

    # Actions per day
    daily_stmt = (
        select(
            cast(ActivityLog.created_at, Date).label("date"),
            func.count(ActivityLog.id).label("count"),
        )
        .where(and_(*base_conditions))
        .group_by(cast(ActivityLog.created_at, Date))
        .order_by(cast(ActivityLog.created_at, Date).desc())
    )
    daily_result = await db.execute(daily_stmt)
    actions_per_day = [
        {"date": str(row.date), "count": row.count}
        for row in daily_result.all()
    ]

    # Most active categories
    category_stmt = (
        select(
            ActivityLog.category,
            func.count(ActivityLog.id).label("count"),
        )
        .where(and_(*base_conditions))
        .group_by(ActivityLog.category)
        .order_by(func.count(ActivityLog.id).desc())
    )
    category_result = await db.execute(category_stmt)
    most_active_categories = [
        {"category": row.category, "count": row.count}
        for row in category_result.all()
    ]

    return ActivityStatsResponse(
        actions_per_day=actions_per_day,
        most_active_categories=most_active_categories,
        total_actions=total_actions,
    )
