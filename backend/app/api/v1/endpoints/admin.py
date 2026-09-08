"""Admin panel endpoints (superadmin only)."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.account import Account
from app.models.api_error import ApiError
from app.models.organization import Organization, SubscriptionTier
from app.models.audit_log import ActivityLog as AuditLog
from app.models.plan import Feature, Plan, PlanFeature
from app.models.platform import AccountHealth, SocialAccount, SocialPlatform
from app.models.post import Post
from app.models.team_member import TeamMember
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.services import entitlement_service, error_log, revenue

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


def _jsonable(value):
    """Audit values go into a JSON column, so Decimals and enums must not.

    A Decimal price raises on serialisation; an enum would store its repr.
    """
    from decimal import Decimal
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "value") and not isinstance(value, (str, int, float, bool)):
        return value.value
    return value


def _audit(
    current_user,
    action: str,
    description: str,
    *,
    resource_type: str,
    resource_id: str,
    old_values: dict | None = None,
    new_values: dict | None = None,
) -> "AuditLog":
    """Build an audit row for an admin write.

    A helper rather than a copy per endpoint: the plan endpoints shipped
    without any audit trail at all, and four hand-written blocks is how the
    fifth one gets forgotten too. Every superadmin write in this module goes
    through here.
    """
    return AuditLog(
        user_id=current_user.id,
        action=action,
        category="admin",
        description=description,
        resource_type=resource_type,
        resource_id=resource_id,
        old_values=old_values,
        new_values=new_values,
    )


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
    # Resolved from the plan, not copied off the organization row. None is
    # unlimited. An operator looking at this list has to see the number
    # enforcement would actually apply.
    monthly_post_limit: int | None = None
    max_team_members: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    async def from_model(
        cls, db: AsyncSession, a: Account, organization: Organization
    ) -> "AdminAccountResponse":
        """Subscription fields come from the workspace's organization."""
        return cls(
            id=a.id,
            name=a.name,
            slug=a.slug,
            owner_id=a.owner_id,
            subscription_tier=organization.subscription_tier.value,
            subscription_status=organization.subscription_status.value,
            monthly_post_limit=await entitlement_service.get_limit(
                db, organization, entitlement_service.POSTS_PER_MONTH
            ),
            max_team_members=await entitlement_service.get_limit(
                db, organization, entitlement_service.TEAM_MEMBERS
            ),
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
                "subscription_tier": (
                    acc.organization.subscription_tier.value
                    if acc.organization is not None
                    else None
                ),
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
        # The tier lives on the workspace's organization now.
        conditions.append(Organization.subscription_tier == tier)

    where = and_(*conditions)
    total = (
        await db.execute(
            select(func.count(Account.id))
            .join(Organization, Organization.id == Account.organization_id)
            .where(where)
        )
    ).scalar() or 0

    # Select both sides: the response needs the organization's subscription
    # fields, which no longer exist on the workspace row.
    stmt = (
        select(Account, Organization)
        .join(Organization, Organization.id == Account.organization_id)
        .where(where)
        .order_by(Account.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = (await db.execute(stmt)).all()

    return PaginatedResponse(
        items=[await AdminAccountResponse.from_model(db, a, org) for a, org in rows],
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
    # Grouped by the organization's tier, counting live organizations rather
    # than workspaces -- one company on Growth is one Growth subscription
    # however many workspaces it owns.
    tier_result = await db.execute(
        select(Organization.subscription_tier, func.count(Organization.id))
        .where(Organization.deleted_at.is_(None))
        .group_by(Organization.subscription_tier)
    )
    accounts_by_tier = {row[0].value: row[1] for row in tier_result.all()}

    # MRR comes from the same place /admin/revenue reads it: the plans table,
    # counting only ACTIVE subscriptions.
    #
    # This was a hard-coded price dict -- 29/79/199/499 against real plan
    # prices of 49/149/399/0 -- applied to every organization regardless of
    # whether it was paying. Two admin screens quoting different revenue is
    # the drift that moving pricing into the database in 1.3 existed to end.
    mrr = (await revenue.summary(db))["mrr"]

    return PlatformStatsResponse(
        total_users=total_users,
        active_users=active_users,
        suspended_users=suspended_users,
        total_accounts=total_accounts,
        total_posts=total_posts,
        published_posts=published_posts,
        total_revenue_estimate=mrr,
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


# ---------------------------------------------------------------------------
# Plans and limits
#
# Limits used to be a dict in the source, so changing one needed a deploy and a
# customer who negotiated a higher cap could not have it. These endpoints are
# the reason the numbers moved into the database.
# ---------------------------------------------------------------------------

class AdminFeatureResponse(BaseModel):
    key: str
    name: str
    description: str | None = None
    unit: str
    is_metered: bool
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class AdminPlanFeatureResponse(BaseModel):
    feature_key: str
    name: str
    unit: str
    # NULL means unlimited, 0 means the plan does not include the feature.
    limit_value: int | None = None
    unlimited: bool


class AdminPlanResponse(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    stripe_price_id: str | None = None
    price_monthly: float
    is_active: bool
    sort_order: int
    features: list[AdminPlanFeatureResponse] = []


class AdminPlanCreate(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    price_monthly: Decimal = Field(default=Decimal("0"), ge=0)
    stripe_price_id: str | None = None
    is_active: bool = True
    sort_order: int = 0
    # feature key -> limit (None = unlimited). Omitted features default to 0.
    limits: dict[str, int | None] = {}


class AdminPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    price_monthly: Decimal | None = Field(default=None, ge=0)
    stripe_price_id: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class AdminPlanLimitsUpdate(BaseModel):
    """A partial update: only the features named are touched."""

    limits: dict[str, int | None]


async def _plan_response(db: AsyncSession, plan: Plan) -> AdminPlanResponse:
    rows = (
        await db.execute(
            select(PlanFeature, Feature)
            .join(Feature, Feature.key == PlanFeature.feature_key)
            .where(PlanFeature.plan_id == plan.id)
            .order_by(Feature.sort_order, Feature.key)
        )
    ).all()
    return AdminPlanResponse(
        id=plan.id,
        key=plan.key,
        name=plan.name,
        stripe_price_id=plan.stripe_price_id,
        price_monthly=float(plan.price_monthly or 0),
        is_active=plan.is_active,
        sort_order=plan.sort_order,
        features=[
            AdminPlanFeatureResponse(
                feature_key=pf.feature_key,
                name=feature.name,
                unit=feature.unit.value,
                limit_value=pf.limit_value,
                unlimited=pf.limit_value is None,
            )
            for pf, feature in rows
        ],
    )


async def _get_plan_or_404(db: AsyncSession, plan_id: uuid.UUID) -> Plan:
    plan = (
        await db.execute(select(Plan).where(Plan.id == plan_id))
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
        )
    return plan


async def _validate_feature_keys(db: AsyncSession, keys) -> None:
    if not keys:
        return
    known = set(
        (await db.execute(select(Feature.key).where(Feature.key.in_(keys))))
        .scalars()
        .all()
    )
    unknown = sorted(set(keys) - known)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown feature keys: {', '.join(unknown)}",
        )


@router.get("/features", response_model=list[AdminFeatureResponse])
async def list_features(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """The feature catalogue every plan draws its limits from."""
    features = (
        await db.execute(select(Feature).order_by(Feature.sort_order, Feature.key))
    ).scalars().all()
    return [AdminFeatureResponse.model_validate(f) for f in features]


@router.get("/plans", response_model=list[AdminPlanResponse])
async def list_plans(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    plans = (
        await db.execute(select(Plan).order_by(Plan.sort_order, Plan.key))
    ).scalars().all()
    return [await _plan_response(db, plan) for plan in plans]


@router.get("/plans/{plan_id}", response_model=AdminPlanResponse)
async def get_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    return await _plan_response(db, await _get_plan_or_404(db, plan_id))


@router.post(
    "/plans", response_model=AdminPlanResponse, status_code=status.HTTP_201_CREATED
)
async def create_plan(
    payload: AdminPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """Add a plan.

    Every known feature gets a row, defaulting to 0 -- an absent PlanFeature is
    read as "not granted", so leaving them out would work but would make the
    plan's actual shape invisible in the admin UI.
    """
    existing = (
        await db.execute(select(Plan.id).where(Plan.key == payload.key))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A plan with key '{payload.key}' already exists",
        )
    await _validate_feature_keys(db, payload.limits.keys())

    plan = Plan(
        id=uuid.uuid4(),
        key=payload.key,
        name=payload.name,
        stripe_price_id=payload.stripe_price_id,
        price_monthly=payload.price_monthly,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )
    db.add(plan)

    features = (await db.execute(select(Feature.key))).scalars().all()
    for key in features:
        db.add(
            PlanFeature(
                id=uuid.uuid4(),
                plan_id=plan.id,
                feature_key=key,
                limit_value=payload.limits.get(key, 0),
            )
        )
    db.add(
        _audit(
            current_user,
            "create_plan",
            f"Created plan '{payload.name}' ({payload.key}) at {payload.price_monthly}/mo",
            resource_type="plan",
            resource_id=str(plan.id),
            new_values={
                "key": payload.key,
                "name": payload.name,
                "price_monthly": float(payload.price_monthly),
                "is_active": payload.is_active,
                "limits": payload.limits,
            },
        )
    )
    await db.flush()
    entitlement_service.invalidate_all()
    return await _plan_response(db, plan)


@router.patch("/plans/{plan_id}", response_model=AdminPlanResponse)
async def update_plan(
    plan_id: uuid.UUID,
    payload: AdminPlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    plan = await _get_plan_or_404(db, plan_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )
    # Captured before the writes, so the audit row can say what changed rather
    # than only what it changed to.
    previous = {field: getattr(plan, field) for field in updates}
    for field, value in updates.items():
        setattr(plan, field, value)

    db.add(
        _audit(
            current_user,
            "update_plan",
            f"Updated plan '{plan.name}' ({plan.key}): "
            + ", ".join(sorted(updates)),
            resource_type="plan",
            resource_id=str(plan.id),
            old_values={k: _jsonable(v) for k, v in previous.items()},
            new_values={k: _jsonable(v) for k, v in updates.items()},
        )
    )
    await db.flush()
    entitlement_service.invalidate_all()
    return await _plan_response(db, plan)


@router.put("/plans/{plan_id}/limits", response_model=AdminPlanResponse)
async def update_plan_limits(
    plan_id: uuid.UUID,
    payload: AdminPlanLimitsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """Change what a plan allows.

    Limits are cached for 60s per organization, so the whole cache is dropped
    here -- otherwise an operator would raise a cap and watch it not take
    effect, and try again.
    """
    plan = await _get_plan_or_404(db, plan_id)
    await _validate_feature_keys(db, payload.limits.keys())

    before = {
        row.feature_key: row.limit_value
        for row in (
            await db.execute(
                select(PlanFeature).where(PlanFeature.plan_id == plan.id)
            )
        ).scalars()
        if row.feature_key in payload.limits
    }

    for feature_key, limit_value in payload.limits.items():
        if limit_value is not None and limit_value < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Limit for '{feature_key}' cannot be negative; "
                    "use null for unlimited"
                ),
            )
        existing = (
            await db.execute(
                select(PlanFeature).where(
                    PlanFeature.plan_id == plan.id,
                    PlanFeature.feature_key == feature_key,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                PlanFeature(
                    id=uuid.uuid4(),
                    plan_id=plan.id,
                    feature_key=feature_key,
                    limit_value=limit_value,
                )
            )
        else:
            existing.limit_value = limit_value

    db.add(
        _audit(
            current_user,
            "update_plan_limits",
            f"Changed limits on plan '{plan.name}' ({plan.key}): "
            + ", ".join(sorted(payload.limits)),
            resource_type="plan",
            resource_id=str(plan.id),
            old_values=before,
            new_values=dict(payload.limits),
        )
    )
    await db.flush()
    entitlement_service.invalidate_all()
    return await _plan_response(db, plan)


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """Retire a plan.

    Deactivates rather than deletes: organizations reference a plan by tier
    key, and removing the row would leave them with no limits at all -- which
    reads as "nothing granted" and would lock them out of their own data.
    """
    plan = await _get_plan_or_404(db, plan_id)
    plan.is_active = False
    db.add(
        _audit(
            current_user,
            "deactivate_plan",
            f"Retired plan '{plan.name}' ({plan.key})",
            resource_type="plan",
            resource_id=str(plan.id),
            old_values={"is_active": True},
            new_values={"is_active": False},
        )
    )
    await db.flush()
    entitlement_service.invalidate_all()
    return None


# ---------------------------------------------------------------------------
# Revenue (scope 19.1)
# ---------------------------------------------------------------------------

@router.get("/revenue")
async def revenue_metrics(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """MRR, ARR, plan mix, churn and trial conversion.

    Prices come from the ``plans`` table, so a change made in the plans UI is
    reflected here immediately -- the point of moving pricing out of a Python
    dict in 1.3 was that the report and the biller read one number.
    """
    return {
        **await revenue.summary(db),
        "churn": await revenue.churn(db, days=days),
        "trials": await revenue.trial_conversions(db, days=days),
        # Movement figures are only as complete as the event log behind them.
        "tracking_since": (
            lambda value: value.isoformat() if value else None
        )(await revenue.tracking_since(db)),
    }


@router.get("/revenue/trend")
async def revenue_trend(
    days: int = Query(90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """Daily MRR, for the chart.

    Reconstructed from ``subscription_events``, which is why the payload
    carries ``tracking_since``: before that instant there is no history, and a
    chart that drew zero there would show a revenue cliff that never happened.
    """
    return await revenue.trend(db, days=days)


# ---------------------------------------------------------------------------
# Connected-account health (scope 19.2)
# ---------------------------------------------------------------------------

@router.get("/connection-health")
async def connection_health(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """Counts by health state, plus every failed connection with its owner.

    The per-workspace strip added in 1.9 tells one customer their connection is
    broken. This is the other direction: which customers are broken right now,
    so support can reach them before they notice a post did not go out.
    """
    counts = {state.value: 0 for state in AccountHealth}
    rows = (
        await db.execute(
            select(SocialAccount.health, func.count().label("total"))
            .where(SocialAccount.is_active.is_(True))
            .group_by(SocialAccount.health)
        )
    ).all()
    for row in rows:
        key = row.health.value if hasattr(row.health, "value") else str(row.health)
        counts[key] = int(row.total)

    failed = (
        await db.execute(
            select(
                SocialAccount.id,
                SocialAccount.account_name,
                SocialAccount.health_detail,
                SocialAccount.health_changed_at,
                SocialPlatform.slug.label("platform"),
                Account.id.label("workspace_id"),
                Account.name.label("workspace"),
                Organization.id.label("organization_id"),
                Organization.name.label("organization"),
                Organization.subscription_tier,
            )
            .select_from(SocialAccount)
            .join(SocialPlatform, SocialPlatform.id == SocialAccount.platform_id)
            .join(Account, Account.id == SocialAccount.account_id)
            .outerjoin(Organization, Organization.id == Account.organization_id)
            .where(
                SocialAccount.is_active.is_(True),
                SocialAccount.health == AccountHealth.FAILED,
            )
            # Oldest failure first: a connection that has been broken for a
            # week is more urgent than one that broke this morning.
            .order_by(SocialAccount.health_changed_at.asc().nulls_last())
            .limit(limit)
        )
    ).all()

    return {
        "counts": counts,
        "total": sum(counts.values()),
        "failed": [
            {
                "id": str(row.id),
                "account_name": row.account_name,
                "platform": row.platform,
                "detail": row.health_detail,
                "checked_at": (
                    row.health_changed_at.isoformat() if row.health_changed_at else None
                ),
                "workspace_id": str(row.workspace_id),
                "workspace": row.workspace,
                "organization_id": (
                    str(row.organization_id) if row.organization_id else None
                ),
                "organization": row.organization,
                "plan": (
                    row.subscription_tier.value
                    if row.subscription_tier is not None
                    and hasattr(row.subscription_tier, "value")
                    else row.subscription_tier
                ),
            }
            for row in failed
        ],
    }


# ---------------------------------------------------------------------------
# API errors (scope 19.3)
# ---------------------------------------------------------------------------

@router.get("/errors")
async def list_api_errors(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    exception_class: str | None = Query(None),
    path: str | None = Query(None),
    since: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """Recorded 5xx responses, newest first.

    ``path`` matches a prefix rather than exactly, so filtering on
    ``/api/v1/accounts`` finds every workspace's failures instead of needing
    the id.
    """
    filters = []
    if exception_class:
        filters.append(ApiError.exception_class == exception_class)
    if path:
        filters.append(ApiError.path.startswith(path))
    if since:
        filters.append(ApiError.created_at >= since)

    total = (
        await db.execute(select(func.count()).select_from(ApiError).where(*filters))
    ).scalar_one()

    rows = (
        await db.execute(
            select(ApiError)
            .where(*filters)
            .order_by(ApiError.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return {
        "items": [
            {
                "id": str(row.id),
                "path": row.path,
                "method": row.method,
                "status_code": row.status_code,
                "exception_class": row.exception_class,
                "message": row.message,
                "user_id": str(row.user_id) if row.user_id else None,
                "organization_id": (
                    str(row.organization_id) if row.organization_id else None
                ),
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "retention_days": error_log.RETENTION_DAYS,
    }


@router.get("/errors/summary")
async def api_error_summary(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """What is failing most, and how often, over the window."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    by_class = (
        await db.execute(
            select(
                ApiError.exception_class,
                func.count().label("total"),
                func.max(ApiError.created_at).label("last_seen"),
            )
            .where(ApiError.created_at >= since)
            .group_by(ApiError.exception_class)
            .order_by(func.count().desc())
            .limit(20)
        )
    ).all()

    by_path = (
        await db.execute(
            select(ApiError.path, func.count().label("total"))
            .where(ApiError.created_at >= since)
            .group_by(ApiError.path)
            .order_by(func.count().desc())
            .limit(20)
        )
    ).all()

    return {
        "days": days,
        "total": await error_log.count_since(db, since),
        "by_exception": [
            {
                "exception_class": row.exception_class,
                "count": int(row.total),
                "last_seen": row.last_seen.isoformat() if row.last_seen else None,
            }
            for row in by_class
        ],
        "by_path": [
            {"path": row.path, "count": int(row.total)} for row in by_path
        ],
    }


@router.get("/errors/{error_id}")
async def get_api_error(
    error_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_superadmin),
):
    """One error, with its traceback.

    Separate from the list because a traceback is several kilobytes and putting
    fifty of them in a page payload would make the list unusable.
    """
    row = (
        await db.execute(select(ApiError).where(ApiError.id == error_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Error not found"
        )
    return {
        "id": str(row.id),
        "path": row.path,
        "method": row.method,
        "status_code": row.status_code,
        "exception_class": row.exception_class,
        "message": row.message,
        "traceback": row.traceback,
        "user_id": str(row.user_id) if row.user_id else None,
        "organization_id": str(row.organization_id) if row.organization_id else None,
        "created_at": row.created_at.isoformat(),
    }
