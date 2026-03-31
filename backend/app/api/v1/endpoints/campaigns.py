"""Campaign management endpoints."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.campaign import Campaign, CampaignStatus
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
    created_at: str  # ISO string
    updated_at: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, c: Campaign) -> "CampaignResponse":
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
            created_at=c.created_at.isoformat() if c.created_at else "",
            updated_at=c.updated_at.isoformat() if c.updated_at else None,
        )


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

    return PaginatedResponse(
        items=[CampaignResponse.from_model(c) for c in campaigns],
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
    return CampaignResponse.from_model(campaign)


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
    return CampaignResponse.from_model(campaign)


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
    return CampaignResponse.from_model(campaign)


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
    return CampaignResponse.from_model(campaign)


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
    return CampaignResponse.from_model(campaign)


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
    return CampaignResponse.from_model(campaign)
