"""Social platform management endpoints."""

import math
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.platform import SocialAccount, SocialPlatform
from app.models.team_member import InvitationStatus, TeamMember
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.social_account import SocialAccountResponse
from app.schemas.social_platform import (
    SocialPlatformCreate,
    SocialPlatformResponse,
    SocialPlatformUpdate,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    """Generate a URL-friendly slug from a platform name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug.strip("-")


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


def _platform_to_response(platform: SocialPlatform) -> SocialPlatformResponse:
    """Convert a SocialPlatform ORM instance to a response schema with account count."""
    return SocialPlatformResponse(
        id=platform.id,
        user_id=platform.user_id,
        account_id=platform.account_id,
        name=platform.name,
        slug=platform.slug,
        icon=platform.icon,
        color=platform.color,
        description=platform.description,
        api_config_template=platform.api_config_template,
        base_url=platform.base_url,
        is_active=platform.is_active,
        sort_order=platform.sort_order,
        social_accounts_count=len(platform.social_accounts) if platform.social_accounts else 0,
        created_at=platform.created_at,
        updated_at=platform.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=PaginatedResponse[SocialPlatformResponse])
async def list_social_platforms(
    account_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all social platforms defined for this account."""
    await _verify_membership(db, current_user.id, account_id)

    count_result = await db.execute(
        select(func.count()).select_from(SocialPlatform).where(
            SocialPlatform.account_id == account_id
        )
    )
    total = count_result.scalar() or 0

    if total == 0:
        # Auto-seed standard platforms for the workspace/account
        platforms_data = [
            {"name": "Facebook", "slug": "facebook", "icon": "facebook", "color": "#1877F2",
             "description": "Meta's social networking platform",
             "base_url": "https://graph.facebook.com/v18.0",
             "api_config_template": {"fields": [
                 {"key": "app_id", "label": "App ID", "type": "text", "required": True},
                 {"key": "app_secret", "label": "App Secret", "type": "password", "required": True},
                 {"key": "page_id", "label": "Page ID", "type": "text", "required": True},
             ]}},
            {"name": "Instagram", "slug": "instagram", "icon": "instagram", "color": "#E4405F",
             "description": "Photo and video sharing platform",
             "base_url": "https://graph.facebook.com/v18.0",
             "api_config_template": {"fields": [
                 {"key": "app_id", "label": "App ID", "type": "text", "required": True},
                 {"key": "app_secret", "label": "App Secret", "type": "password", "required": True},
                 {"key": "ig_user_id", "label": "Instagram User ID", "type": "text", "required": True},
             ]}},
            {"name": "LinkedIn", "slug": "linkedin", "icon": "linkedin", "color": "#0A66C2",
             "description": "Professional networking platform",
             "base_url": "https://api.linkedin.com/v2",
             "api_config_template": {"fields": [
                 {"key": "client_id", "label": "Client ID", "type": "text", "required": True},
                 {"key": "client_secret", "label": "Client Secret", "type": "password", "required": True},
                 {"key": "organization_id", "label": "Organization ID", "type": "text", "required": False},
             ]}},
            {"name": "X (Twitter)", "slug": "twitter", "icon": "twitter", "color": "#000000",
             "description": "Microblogging and social networking",
             "base_url": "https://api.twitter.com/2",
             "api_config_template": {"fields": [
                 {"key": "api_key", "label": "API Key", "type": "text", "required": True},
                 {"key": "api_secret", "label": "API Secret", "type": "password", "required": True},
                 {"key": "bearer_token", "label": "Bearer Token", "type": "password", "required": True},
             ]}},
            {"name": "YouTube", "slug": "youtube", "icon": "youtube", "color": "#FF0000",
             "description": "Video sharing platform",
             "base_url": "https://www.googleapis.com/youtube/v3",
             "api_config_template": {"fields": [
                 {"key": "api_key", "label": "API Key", "type": "text", "required": True},
                 {"key": "channel_id", "label": "Channel ID", "type": "text", "required": True},
             ]}},
            {"name": "TikTok", "slug": "tiktok", "icon": "tiktok", "color": "#010101",
             "description": "Short-form video platform",
             "base_url": "https://open.tiktokapis.com/v2",
             "api_config_template": {"fields": [
                 {"key": "client_key", "label": "Client Key", "type": "text", "required": True},
                 {"key": "client_secret", "label": "Client Secret", "type": "password", "required": True},
             ]}},
        ]
        for i, pdata in enumerate(platforms_data):
            db.add(SocialPlatform(
                id=uuid.uuid4(),
                user_id=current_user.id,
                account_id=account_id,
                name=pdata["name"],
                slug=pdata["slug"],
                icon=pdata["icon"],
                color=pdata["color"],
                description=pdata["description"],
                base_url=pdata["base_url"],
                api_config_template=pdata["api_config_template"],
                sort_order=i,
                is_active=True,
            ))
        await db.commit()
        
        # Query total count again
        count_result = await db.execute(
            select(func.count()).select_from(SocialPlatform).where(
                SocialPlatform.account_id == account_id
            )
        )
        total = count_result.scalar() or 0

    stmt = (
        select(SocialPlatform)
        .where(SocialPlatform.account_id == account_id)
        .order_by(SocialPlatform.sort_order, SocialPlatform.name)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    platforms = result.scalars().all()

    return PaginatedResponse[SocialPlatformResponse](
        items=[_platform_to_response(p) for p in platforms],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.post("/", response_model=SocialPlatformResponse, status_code=status.HTTP_201_CREATED)
async def create_social_platform(
    account_id: uuid.UUID,
    body: SocialPlatformCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new social media platform definition."""
    await _verify_membership(db, current_user.id, account_id)

    slug = body.slug if body.slug else _slugify(body.name)

    # Check for duplicate slug within the account
    existing = await db.execute(
        select(SocialPlatform).where(
            SocialPlatform.account_id == account_id,
            SocialPlatform.slug == slug,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A platform with slug '{slug}' already exists in this account",
        )

    platform = SocialPlatform(
        user_id=current_user.id,
        account_id=account_id,
        name=body.name,
        slug=slug,
        icon=body.icon,
        color=body.color,
        description=body.description,
        api_config_template=body.api_config_template,
        base_url=body.base_url,
    )
    db.add(platform)
    await db.flush()
    await db.refresh(platform)

    return _platform_to_response(platform)


@router.get("/{platform_id}", response_model=SocialPlatformResponse)
async def get_social_platform(
    account_id: uuid.UUID,
    platform_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a single social platform with account count."""
    await _verify_membership(db, current_user.id, account_id)

    result = await db.execute(
        select(SocialPlatform).where(
            SocialPlatform.id == platform_id,
            SocialPlatform.account_id == account_id,
        )
    )
    platform = result.scalar_one_or_none()
    if platform is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social platform not found",
        )

    return _platform_to_response(platform)


@router.put("/{platform_id}", response_model=SocialPlatformResponse)
async def update_social_platform(
    account_id: uuid.UUID,
    platform_id: uuid.UUID,
    body: SocialPlatformUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a social platform definition."""
    await _verify_membership(db, current_user.id, account_id)

    result = await db.execute(
        select(SocialPlatform).where(
            SocialPlatform.id == platform_id,
            SocialPlatform.account_id == account_id,
        )
    )
    platform = result.scalar_one_or_none()
    if platform is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social platform not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    # If name is updated but slug is not, auto-update slug
    if "name" in update_data and "slug" not in update_data:
        update_data["slug"] = _slugify(update_data["name"])

    for field, value in update_data.items():
        setattr(platform, field, value)

    await db.flush()
    await db.refresh(platform)

    return _platform_to_response(platform)


@router.delete("/{platform_id}", response_model=MessageResponse)
async def delete_social_platform(
    account_id: uuid.UUID,
    platform_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a social platform and all its associated accounts (cascade)."""
    await _verify_membership(db, current_user.id, account_id)

    result = await db.execute(
        select(SocialPlatform).where(
            SocialPlatform.id == platform_id,
            SocialPlatform.account_id == account_id,
        )
    )
    platform = result.scalar_one_or_none()
    if platform is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social platform not found",
        )

    await db.delete(platform)
    await db.flush()

    return MessageResponse(message="Social platform and associated accounts deleted successfully")


@router.get("/{platform_id}/accounts", response_model=PaginatedResponse[SocialAccountResponse])
async def list_platform_social_accounts(
    account_id: uuid.UUID,
    platform_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all social accounts for a specific platform."""
    await _verify_membership(db, current_user.id, account_id)

    # Verify platform exists
    platform_result = await db.execute(
        select(SocialPlatform).where(
            SocialPlatform.id == platform_id,
            SocialPlatform.account_id == account_id,
        )
    )
    if platform_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social platform not found",
        )

    count_result = await db.execute(
        select(func.count()).select_from(SocialAccount).where(
            SocialAccount.platform_id == platform_id,
            SocialAccount.account_id == account_id,
        )
    )
    total = count_result.scalar() or 0

    stmt = (
        select(SocialAccount)
        .where(
            SocialAccount.platform_id == platform_id,
            SocialAccount.account_id == account_id,
        )
        .order_by(SocialAccount.account_name)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    accounts = result.scalars().all()

    return PaginatedResponse[SocialAccountResponse](
        items=[SocialAccountResponse.model_validate(a) for a in accounts],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )
