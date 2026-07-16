"""Admin panel endpoints (superadmin only)."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.account import Account, SubscriptionTier
from app.models.audit_log import ActivityLog as AuditLog
from app.models.post import Post
from app.models.team_member import TeamMember
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

async def require_superadmin(current_user=Depends(get_current_active_user)):
    """Ensure the current user is a superadmin."""
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required",
        )
    return current_user


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_superadmin: bool
    is_suspended: bool
    email_verified: bool
    last_login_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserDetail(AdminUserResponse):
    accounts: list[dict] = []


class AdminAccountResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    owner_id: uuid.UUID
    subscription_tier: str
    subscription_status: str
    monthly_post_limit: int
    max_team_members: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, a: Account) -> "AdminAccountResponse":
        return cls(
            id=a.id,
            name=a.name,
            slug=a.slug,
            owner_id=a.owner_id,
            subscription_tier=a.subscription_tier.value,
            subscription_status=a.subscription_status.value,
            monthly_post_limit=a.monthly_post_limit,
            max_team_members=a.max_team_members,
            created_at=a.created_at,
        )


class PlatformStatsResponse(BaseModel):
    total_users: int
    active_users: int
    suspended_users: int
    total_accounts: int
    total_posts: int
    published_posts: int
    total_revenue_estimate: float
    accounts_by_tier: dict[str, int]


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    old_values: dict | None = None
    new_values: dict | None = None
    ip_address: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SuspendRequest(BaseModel):
    is_suspended: bool
    reason: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/users", response_model=PaginatedResponse[AdminUserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """List all users with optional search by name or email."""
    conditions = [User.deleted_at.is_(None)]
    if search:
        pattern = f"%{search}%"
        conditions.append(
            or_(User.email.ilike(pattern), User.full_name.ilike(pattern))
        )

    where = and_(*conditions)
    total = (await db.execute(select(func.count(User.id)).where(where))).scalar() or 0

    stmt = (
        select(User)
        .where(where)
        .order_by(User.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    users = (await db.execute(stmt)).scalars().all()

    return PaginatedResponse(
        items=[AdminUserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page else 1,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """Get detailed user info including their accounts."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.accounts).selectinload(TeamMember.account))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    accounts_data = []
    for membership in user.accounts:
        acc = membership.account
        if acc:
            accounts_data.append({
                "account_id": str(acc.id),
                "account_name": acc.name,
                "role": membership.role.value,
                "subscription_tier": acc.subscription_tier.value,
            })

    base = AdminUserResponse.model_validate(user)
    return AdminUserDetail(**base.model_dump(), accounts=accounts_data)


@router.put("/users/{user_id}/suspend", response_model=AdminUserResponse)
async def suspend_user(
    user_id: uuid.UUID,
    body: SuspendRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """Suspend or unsuspend a user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot suspend a superadmin user",
        )

    user.is_suspended = body.is_suspended
    if body.is_suspended:
        user.is_active = False
    else:
        user.is_active = True

    # Log the action
    action = "suspend_user" if body.is_suspended else "unsuspend_user"
    log = AuditLog(
        user_id=current_user.id,
        action=action,
        category="admin",
        description=(
            f"{'Suspended' if body.is_suspended else 'Unsuspended'} user "
            f"{user.email}" + (f" (reason: {body.reason})" if body.reason else "")
        ),
        resource_type="user",
        resource_id=str(user_id),
        new_values={"is_suspended": body.is_suspended, "reason": body.reason},
    )
    db.add(log)
    await db.flush()
    await db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.get("/accounts", response_model=PaginatedResponse[AdminAccountResponse])
async def list_accounts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    tier: SubscriptionTier | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """List all accounts with optional tier filter."""
    conditions = [Account.deleted_at.is_(None)]
    if tier:
        conditions.append(Account.subscription_tier == tier)

    where = and_(*conditions)
    total = (await db.execute(select(func.count(Account.id)).where(where))).scalar() or 0

    stmt = (
        select(Account)
        .where(where)
        .order_by(Account.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    accounts = (await db.execute(stmt)).scalars().all()

    return PaginatedResponse(
        items=[AdminAccountResponse.from_model(a) for a in accounts],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page else 1,
    )


@router.get("/stats", response_model=PlatformStatsResponse)
async def platform_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """Platform-wide statistics."""
    # Users
    total_users = (await db.execute(
        select(func.count(User.id)).where(User.deleted_at.is_(None))
    )).scalar() or 0

    active_users = (await db.execute(
        select(func.count(User.id)).where(User.deleted_at.is_(None), User.is_active.is_(True))
    )).scalar() or 0

    suspended_users = (await db.execute(
        select(func.count(User.id)).where(User.is_suspended.is_(True))
    )).scalar() or 0

    # Accounts
    total_accounts = (await db.execute(
        select(func.count(Account.id)).where(Account.deleted_at.is_(None))
    )).scalar() or 0

    # Posts
    total_posts = (await db.execute(
        select(func.count(Post.id)).where(Post.deleted_at.is_(None))
    )).scalar() or 0

    from app.models.post import PostStatus

    published_posts = (await db.execute(
        select(func.count(Post.id)).where(
            Post.deleted_at.is_(None),
            Post.status == PostStatus.PUBLISHED,
        )
    )).scalar() or 0

    # Accounts by tier
    tier_result = await db.execute(
        select(Account.subscription_tier, func.count(Account.id))
        .where(Account.deleted_at.is_(None))
        .group_by(Account.subscription_tier)
    )
    accounts_by_tier = {row[0].value: row[1] for row in tier_result.all()}

    # Revenue estimate (based on tier counts)
    tier_prices = {
        "free": 0,
        "starter": 29,
        "growth": 79,
        "pro": 199,
        "enterprise": 499,
    }
    revenue = sum(
        tier_prices.get(tier, 0) * count
        for tier, count in accounts_by_tier.items()
    )

    return PlatformStatsResponse(
        total_users=total_users,
        active_users=active_users,
        suspended_users=suspended_users,
        total_accounts=total_accounts,
        total_posts=total_posts,
        published_posts=published_posts,
        total_revenue_estimate=float(revenue),
        accounts_by_tier=accounts_by_tier,
    )


@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogResponse])
async def list_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    action: str | None = None,
    user_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """List audit logs with filters."""
    conditions: list = []
    if action:
        conditions.append(AuditLog.action == action)
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if date_from:
        conditions.append(AuditLog.created_at >= date_from)
    if date_to:
        conditions.append(AuditLog.created_at <= date_to)

    where = and_(*conditions) if conditions else True

    total = (await db.execute(select(func.count(AuditLog.id)).where(where))).scalar() or 0

    stmt = (
        select(AuditLog)
        .where(where)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    logs = (await db.execute(stmt)).scalars().all()

    return PaginatedResponse(
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page else 1,
    )
