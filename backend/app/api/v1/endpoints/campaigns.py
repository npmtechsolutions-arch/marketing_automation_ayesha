"""Campaign management endpoints."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.campaign import Campaign, CampaignStatus
from app.models.post import Post, PostStatus
from app.models.post_performance import PostPerformance
from app.models.team_member import TeamMember, TeamRole
from app.schemas.common import MessageResponse, PaginatedResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas (campaign-specific, not in shared schemas yet)
# ---------------------------------------------------------------------------

class CampaignCreate(BaseModel):
    name: str
    objective: str | None = None
    platforms: list[dict]
    budget_total: float | None = None
    budget_daily: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    strategy_id: uuid.UUID | None = None


class CampaignUpdate(BaseModel):
    name: str | None = None
    objective: str | None = None
    platforms: list[dict] | None = None
    budget_total: float | None = None
    budget_daily: float | None = None
    start_date: date | None = None
    end_date: date | None = None


class CampaignResponse(BaseModel):
    id: uuid.UUID
    name: str
    objective: str | None = None
    platforms: list[dict]
    budget_total: float | None = None
    budget_daily: float | None = None
    budget_spent: float
    status: str
    start_date: date | None = None
    end_date: date | None = None
    strategy_id: uuid.UUID | None = None
    results: dict | None = None
    post_count: int = 0
    created_at: str  # ISO string
    updated_at: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, c: Campaign, post_count: int = 0) -> "CampaignResponse":
        return cls(
            id=c.id,
            name=c.name,
            objective=c.objective,
            platforms=c.platforms,
            budget_total=c.budget_total,
            budget_daily=c.budget_daily,
            budget_spent=c.budget_spent,
            status=c.status.value,
            start_date=c.start_date,
            end_date=c.end_date,
            strategy_id=c.strategy_id,
            results=c.results,
            post_count=post_count,
            created_at=c.created_at.isoformat() if c.created_at else "",
            updated_at=c.updated_at.isoformat() if c.updated_at else None,
        )


class CampaignStats(BaseModel):
    post_count: int
    published_count: int
    scheduled_count: int
    reach: int
    impressions: int
    engagement: int
    clicks: int
    engagement_rate: float
    budget_total: float | None = None
    budget_spent: float
    budget_remaining: float | None = None


class CampaignPostItem(BaseModel):
    id: uuid.UUID
    title: str | None = None
    content: str
    status: str
    platforms: list[str]
    published_at: str | None = None
    reach: int
    engagement: int


class AttachPostsBody(BaseModel):
    post_ids: list[uuid.UUID]


class SpendBody(BaseModel):
    amount: float
    mode: str = "add"  # "add" (increment) or "set" (overwrite)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _verify_account_access(
    account_id: uuid.UUID, user, db: AsyncSession, *, min_role: TeamRole | None = None
) -> TeamMember:
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.account_id == account_id,
            TeamMember.user_id == user.id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this account")
    role_hierarchy = [TeamRole.VIEWER, TeamRole.EDITOR, TeamRole.MANAGER, TeamRole.ADMIN, TeamRole.OWNER]
    if min_role and role_hierarchy.index(member.role) < role_hierarchy.index(min_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires at least {min_role.value} role")
    return member


async def _get_campaign_or_404(
    campaign_id: uuid.UUID, account_id: uuid.UUID, db: AsyncSession
) -> Campaign:
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.account_id == account_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign


async def _count_posts(campaign_id: uuid.UUID, db: AsyncSession) -> int:
    """Count non-deleted posts linked to a campaign."""
    return (
        await db.execute(
            select(func.count(Post.id)).where(
                Post.campaign_id == campaign_id, Post.deleted_at.is_(None)
            )
        )
    ).scalar() or 0


def _post_platforms(post: Post) -> list[str]:
    """Extract distinct platform names a post targets."""
    names: list[str] = []
    for acc in (post.target_accounts or []):
        name = (acc.get("platform_name") or acc.get("platform") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _aggregate_perf(post: Post) -> tuple[int, int]:
    """Sum (reach, engagement) across a post's loaded performances."""
    perfs = post.performances if "performances" in post.__dict__ else []
    reach = sum(p.reach for p in perfs)
    engagement = sum(p.likes + p.comments + p.shares + p.saves for p in perfs)
    return reach, engagement


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=PaginatedResponse[CampaignResponse])
async def list_campaigns(
    account_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: CampaignStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """List campaigns for the account."""
    await _verify_account_access(account_id, current_user, db)

    conditions = [Campaign.account_id == account_id]
    if status_filter:
        conditions.append(Campaign.status == status_filter)

    from sqlalchemy import and_

    where = and_(*conditions)
    total = (await db.execute(select(func.count(Campaign.id)).where(where))).scalar() or 0

    stmt = (
        select(Campaign)
        .where(where)
        .order_by(Campaign.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    campaigns = (await db.execute(stmt)).scalars().all()

    # Post counts for the fetched campaigns in one grouped query (avoids N+1).
    campaign_ids = [c.id for c in campaigns]
    counts: dict[uuid.UUID, int] = {}
    if campaign_ids:
        rows = await db.execute(
            select(Post.campaign_id, func.count(Post.id))
            .where(Post.campaign_id.in_(campaign_ids), Post.deleted_at.is_(None))
            .group_by(Post.campaign_id)
        )
        counts = {cid: cnt for cid, cnt in rows.all()}

    return PaginatedResponse(
        items=[CampaignResponse.from_model(c, counts.get(c.id, 0)) for c in campaigns],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page else 1,
    )


@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    account_id: uuid.UUID,
    body: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Create a new campaign."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.EDITOR)

    campaign = Campaign(
        user_id=current_user.id,
        account_id=account_id,
        name=body.name,
        objective=body.objective,
        platforms=body.platforms,
        budget_total=body.budget_total,
        budget_daily=body.budget_daily,
        start_date=body.start_date,
        end_date=body.end_date,
        strategy_id=body.strategy_id,
        status=CampaignStatus.DRAFT,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return CampaignResponse.from_model(campaign, await _count_posts(campaign.id, db))


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    account_id: uuid.UUID,
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Get campaign details."""
    await _verify_account_access(account_id, current_user, db)
    campaign = await _get_campaign_or_404(campaign_id, account_id, db)
    return CampaignResponse.from_model(campaign, await _count_posts(campaign_id, db))


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    account_id: uuid.UUID,
    campaign_id: uuid.UUID,
    body: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Update campaign details. Only draft or paused campaigns can be edited."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.EDITOR)
    campaign = await _get_campaign_or_404(campaign_id, account_id, db)

    if campaign.status not in (CampaignStatus.DRAFT, CampaignStatus.PAUSED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit campaign with status '{campaign.status.value}'",
        )

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)

    await db.flush()
    await db.refresh(campaign)
    return CampaignResponse.from_model(campaign, await _count_posts(campaign.id, db))


@router.delete("/{campaign_id}", response_model=MessageResponse)
async def delete_campaign(
    account_id: uuid.UUID,
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Delete a campaign. Only draft campaigns can be deleted."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.MANAGER)
    campaign = await _get_campaign_or_404(campaign_id, account_id, db)

    if campaign.status != CampaignStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft campaigns can be deleted. Use cancel for active campaigns.",
        )

    await db.delete(campaign)
    await db.flush()
    return MessageResponse(message="Campaign deleted successfully")


@router.post("/{campaign_id}/activate", response_model=CampaignResponse)
async def activate_campaign(
    account_id: uuid.UUID,
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Activate a campaign."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.MANAGER)
    campaign = await _get_campaign_or_404(campaign_id, account_id, db)

    if campaign.status not in (CampaignStatus.DRAFT, CampaignStatus.PAUSED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot activate campaign with status '{campaign.status.value}'",
        )

    campaign.status = CampaignStatus.ACTIVE
    await db.flush()
    await db.refresh(campaign)
    return CampaignResponse.from_model(campaign, await _count_posts(campaign.id, db))


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    account_id: uuid.UUID,
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Pause an active campaign."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.MANAGER)
    campaign = await _get_campaign_or_404(campaign_id, account_id, db)

    if campaign.status != CampaignStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only active campaigns can be paused",
        )

    campaign.status = CampaignStatus.PAUSED
    await db.flush()
    await db.refresh(campaign)
    return CampaignResponse.from_model(campaign, await _count_posts(campaign.id, db))


@router.post("/{campaign_id}/complete", response_model=CampaignResponse)
async def complete_campaign(
    account_id: uuid.UUID,
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Mark a campaign as completed."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.MANAGER)
    campaign = await _get_campaign_or_404(campaign_id, account_id, db)

    if campaign.status not in (CampaignStatus.ACTIVE, CampaignStatus.PAUSED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete campaign with status '{campaign.status.value}'",
        )

    campaign.status = CampaignStatus.COMPLETED
    await db.flush()
    await db.refresh(campaign)
    return CampaignResponse.from_model(campaign, await _count_posts(campaign.id, db))


# ---------------------------------------------------------------------------
# Campaign hub: linked posts, aggregated stats, and budget spend
# ---------------------------------------------------------------------------

@router.get("/{campaign_id}/stats", response_model=CampaignStats)
async def campaign_stats(
    account_id: uuid.UUID,
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Aggregated performance of all posts linked to the campaign."""
    await _verify_account_access(account_id, current_user, db)
    campaign = await _get_campaign_or_404(campaign_id, account_id, db)

    # Post counts by status (single grouped query).
    status_rows = await db.execute(
        select(Post.status, func.count(Post.id))
        .where(Post.campaign_id == campaign_id, Post.deleted_at.is_(None))
        .group_by(Post.status)
    )
    status_counts = {st: cnt for st, cnt in status_rows.all()}
    post_count = sum(status_counts.values())
    published = status_counts.get(PostStatus.PUBLISHED, 0) + status_counts.get(
        PostStatus.PARTIALLY_PUBLISHED, 0
    )
    scheduled = status_counts.get(PostStatus.SCHEDULED, 0)

    # Performance sums across linked posts.
    perf_row = (
        await db.execute(
            select(
                func.coalesce(func.sum(PostPerformance.reach), 0),
                func.coalesce(func.sum(PostPerformance.impressions), 0),
                func.coalesce(
                    func.sum(
                        PostPerformance.likes
                        + PostPerformance.comments
                        + PostPerformance.shares
                        + PostPerformance.saves
                    ),
                    0,
                ),
                func.coalesce(func.sum(PostPerformance.clicks), 0),
            )
            .select_from(PostPerformance)
            .join(Post, Post.id == PostPerformance.post_id)
            .where(Post.campaign_id == campaign_id, Post.deleted_at.is_(None))
        )
    ).one()
    reach, impressions, engagement, clicks = (int(v) for v in perf_row)
    rate = round(engagement / reach, 4) if reach else 0.0
    remaining = (
        campaign.budget_total - campaign.budget_spent
        if campaign.budget_total is not None
        else None
    )

    return CampaignStats(
        post_count=post_count,
        published_count=published,
        scheduled_count=scheduled,
        reach=reach,
        impressions=impressions,
        engagement=engagement,
        clicks=clicks,
        engagement_rate=rate,
        budget_total=campaign.budget_total,
        budget_spent=campaign.budget_spent,
        budget_remaining=remaining,
    )


@router.get("/{campaign_id}/posts", response_model=list[CampaignPostItem])
async def list_campaign_posts(
    account_id: uuid.UUID,
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """List the posts currently linked to this campaign."""
    await _verify_account_access(account_id, current_user, db)
    await _get_campaign_or_404(campaign_id, account_id, db)

    posts = (
        await db.execute(
            select(Post)
            .options(selectinload(Post.performances))
            .where(Post.campaign_id == campaign_id, Post.deleted_at.is_(None))
            .order_by(Post.created_at.desc())
        )
    ).scalars().all()

    items = []
    for p in posts:
        reach, engagement = _aggregate_perf(p)
        items.append(
            CampaignPostItem(
                id=p.id,
                title=p.title,
                content=p.content,
                status=p.status.value,
                platforms=_post_platforms(p),
                published_at=p.published_at.isoformat() if p.published_at else None,
                reach=reach,
                engagement=engagement,
            )
        )
    return items


@router.get("/{campaign_id}/available-posts", response_model=list[CampaignPostItem])
async def list_available_posts(
    account_id: uuid.UUID,
    campaign_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """List account posts not yet linked to any campaign (candidates to add)."""
    await _verify_account_access(account_id, current_user, db)
    await _get_campaign_or_404(campaign_id, account_id, db)

    posts = (
        await db.execute(
            select(Post)
            .options(selectinload(Post.performances))
            .where(
                Post.account_id == account_id,
                Post.campaign_id.is_(None),
                Post.deleted_at.is_(None),
            )
            .order_by(Post.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    items = []
    for p in posts:
        reach, engagement = _aggregate_perf(p)
        items.append(
            CampaignPostItem(
                id=p.id,
                title=p.title,
                content=p.content,
                status=p.status.value,
                platforms=_post_platforms(p),
                published_at=p.published_at.isoformat() if p.published_at else None,
                reach=reach,
                engagement=engagement,
            )
        )
    return items


@router.post("/{campaign_id}/posts", response_model=MessageResponse)
async def attach_posts(
    account_id: uuid.UUID,
    campaign_id: uuid.UUID,
    body: AttachPostsBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Link one or more of the account's posts to this campaign."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.EDITOR)
    await _get_campaign_or_404(campaign_id, account_id, db)

    if not body.post_ids:
        return MessageResponse(message="No posts provided")

    result = await db.execute(
        update(Post)
        .where(
            Post.id.in_(body.post_ids),
            Post.account_id == account_id,
            Post.deleted_at.is_(None),
        )
        .values(campaign_id=campaign_id)
    )
    await db.flush()
    return MessageResponse(message=f"{result.rowcount} post(s) added to campaign")


@router.delete("/{campaign_id}/posts/{post_id}", response_model=MessageResponse)
async def detach_post(
    account_id: uuid.UUID,
    campaign_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Remove a post from this campaign (the post itself is not deleted)."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.EDITOR)
    await _get_campaign_or_404(campaign_id, account_id, db)

    result = await db.execute(
        update(Post)
        .where(
            Post.id == post_id,
            Post.campaign_id == campaign_id,
            Post.account_id == account_id,
        )
        .values(campaign_id=None)
    )
    await db.flush()
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not linked to this campaign"
        )
    return MessageResponse(message="Post removed from campaign")


@router.post("/{campaign_id}/spend", response_model=CampaignResponse)
async def log_spend(
    account_id: uuid.UUID,
    campaign_id: uuid.UUID,
    body: SpendBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Record budget spend. mode='add' increments, mode='set' overwrites the total spent."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.EDITOR)
    campaign = await _get_campaign_or_404(campaign_id, account_id, db)

    if body.mode == "set":
        campaign.budget_spent = max(0.0, body.amount)
    else:
        campaign.budget_spent = max(0.0, (campaign.budget_spent or 0.0) + body.amount)

    await db.flush()
    await db.refresh(campaign)
    return CampaignResponse.from_model(campaign, await _count_posts(campaign.id, db))
