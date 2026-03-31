"""Business management endpoints."""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.business import Business
from app.models.team_member import InvitationStatus, TeamMember
from app.models.user import User
from app.schemas.business import BusinessCreate, BusinessResponse, BusinessUpdate
from app.schemas.common import MessageResponse, PaginatedResponse

router = APIRouter(
    prefix="/accounts/{account_id}/businesses",
    tags=["Businesses"],
)


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


@router.get("/", response_model=PaginatedResponse[BusinessResponse])
async def list_businesses(
    account_id: uuid.UUID,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all businesses under an account."""
    await _verify_membership(db, current_user.id, account_id)

    # Count
    count_query = select(func.count()).where(Business.account_id == account_id)
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch page
    businesses_query = (
        select(Business)
        .where(Business.account_id == account_id)
        .order_by(Business.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(businesses_query)
    businesses = result.scalars().all()

    return PaginatedResponse[BusinessResponse](
        items=[BusinessResponse.model_validate(b) for b in businesses],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.post(
    "/",
    response_model=BusinessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_business(
    account_id: uuid.UUID,
    payload: BusinessCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new business under an account."""
    await _verify_membership(db, current_user.id, account_id)

    business = Business(
        id=uuid.uuid4(),
        account_id=account_id,
        name=payload.name,
        industry=payload.industry,
        description=payload.description,
        website=payload.website,
    )
    db.add(business)
    await db.flush()
    await db.refresh(business)

    return BusinessResponse.model_validate(business)


@router.get("/{business_id}", response_model=BusinessResponse)
async def get_business(
    account_id: uuid.UUID,
    business_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a specific business by ID."""
    await _verify_membership(db, current_user.id, account_id)

    result = await db.execute(
        select(Business).where(
            Business.id == business_id,
            Business.account_id == account_id,
        )
    )
    business = result.scalar_one_or_none()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    return BusinessResponse.model_validate(business)


@router.put("/{business_id}", response_model=BusinessResponse)
async def update_business(
    account_id: uuid.UUID,
    business_id: uuid.UUID,
    payload: BusinessUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a business's details."""
    await _verify_membership(db, current_user.id, account_id)

    result = await db.execute(
        select(Business).where(
            Business.id == business_id,
            Business.account_id == account_id,
        )
    )
    business = result.scalar_one_or_none()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    for field, value in update_data.items():
        setattr(business, field, value)

    await db.flush()
    await db.refresh(business)

    return BusinessResponse.model_validate(business)


@router.delete("/{business_id}", response_model=MessageResponse)
async def delete_business(
    account_id: uuid.UUID,
    business_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a business from an account."""
    await _verify_membership(db, current_user.id, account_id)

    result = await db.execute(
        select(Business).where(
            Business.id == business_id,
            Business.account_id == account_id,
        )
    )
    business = result.scalar_one_or_none()
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    await db.delete(business)
    await db.flush()

    return MessageResponse(message="Business deleted successfully")
