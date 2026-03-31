"""Platform connection endpoints (social media OAuth)."""

import math
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.account import Account
from app.models.platform import Platform, PlatformType
from app.models.team_member import InvitationStatus, TeamMember
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.platform import (
    PlatformCallback,
    PlatformConnect,
    PlatformResponse,
    PlatformUpdate,
)

router = APIRouter(
    prefix="/accounts/{account_id}/platforms",
    tags=["Platform Connections"],
)

# OAuth configuration per platform
_OAUTH_CONFIGS: dict[str, dict] = {
    "facebook": {
        "authorize_url": "https://www.facebook.com/v18.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
        "scope": "pages_manage_posts,pages_read_engagement,pages_show_list",
        "client_id_setting": "META_APP_ID",
        "client_secret_setting": "META_APP_SECRET",
    },
    "instagram": {
        "authorize_url": "https://www.facebook.com/v18.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
        "scope": "instagram_basic,instagram_content_publish,pages_show_list",
        "client_id_setting": "META_APP_ID",
        "client_secret_setting": "META_APP_SECRET",
    },
    "linkedin": {
        "authorize_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "scope": "r_liteprofile w_member_social r_organization_social w_organization_social",
        "client_id_setting": "LINKEDIN_CLIENT_ID",
        "client_secret_setting": "LINKEDIN_CLIENT_SECRET",
    },
    "twitter": {
        "authorize_url": "https://twitter.com/i/oauth2/authorize",
        "token_url": "https://api.twitter.com/2/oauth2/token",
        "scope": "tweet.read tweet.write users.read offline.access",
        "client_id_setting": "TWITTER_CLIENT_ID",
        "client_secret_setting": "TWITTER_CLIENT_SECRET",
    },
    "google_business": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scope": "https://www.googleapis.com/auth/business.manage",
        "client_id_setting": "GOOGLE_CLIENT_ID",
        "client_secret_setting": "GOOGLE_CLIENT_SECRET",
    },
}


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


@router.get("/", response_model=PaginatedResponse[PlatformResponse])
async def list_platforms(
    account_id: uuid.UUID,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all connected platforms for an account."""
    await _verify_membership(db, current_user.id, account_id)

    count_query = select(func.count()).where(Platform.account_id == account_id)
    total = (await db.execute(count_query)).scalar() or 0

    platforms_query = (
        select(Platform)
        .where(Platform.account_id == account_id)
        .order_by(Platform.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(platforms_query)
    platforms = result.scalars().all()

    return PaginatedResponse[PlatformResponse](
        items=[PlatformResponse.model_validate(p) for p in platforms],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.post("/connect")
async def connect_platform(
    account_id: uuid.UUID,
    payload: PlatformConnect,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Initiate an OAuth flow for a social platform.

    Returns the authorization URL the frontend should redirect the user to.
    """
    await _verify_membership(db, current_user.id, account_id)

    # Check platform limit
    acct_result = await db.execute(
        select(Account).where(Account.id == account_id, Account.deleted_at.is_(None))
    )
    account = acct_result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    platform_count_result = await db.execute(
        select(func.count()).where(Platform.account_id == account_id)
    )
    platform_count = platform_count_result.scalar() or 0
    if platform_count >= account.max_platforms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Platform limit reached ({account.max_platforms}). "
            "Upgrade your plan to connect more platforms.",
        )

    platform_key = payload.platform_type.lower()
    oauth_config = _OAUTH_CONFIGS.get(platform_key)
    if oauth_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform: {payload.platform_type}. "
            f"Supported: {', '.join(_OAUTH_CONFIGS.keys())}",
        )

    client_id = getattr(settings, oauth_config["client_id_setting"], "")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OAuth is not configured for {payload.platform_type}",
        )

    # Build the state parameter for CSRF protection
    state = f"{account_id}:{current_user.id}:{platform_key}"

    params = {
        "client_id": client_id,
        "redirect_uri": payload.redirect_uri,
        "scope": oauth_config["scope"],
        "response_type": "code",
        "state": state,
    }

    authorization_url = f"{oauth_config['authorize_url']}?{urlencode(params)}"

    return {
        "authorization_url": authorization_url,
        "platform_type": payload.platform_type,
        "state": state,
    }


@router.post(
    "/callback",
    response_model=PlatformResponse,
    status_code=status.HTTP_201_CREATED,
)
async def handle_oauth_callback(
    account_id: uuid.UUID,
    payload: PlatformCallback,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Handle the OAuth callback after the user authorizes the platform.

    Exchanges the authorization code for access/refresh tokens and creates
    the Platform record. In production, this would call the platform's
    token endpoint.
    """
    await _verify_membership(db, current_user.id, account_id)

    platform_key = payload.platform_type.lower()
    oauth_config = _OAUTH_CONFIGS.get(platform_key)
    if oauth_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform: {payload.platform_type}",
        )

    # TODO: Exchange the authorization code for tokens by calling
    # the platform's token endpoint:
    #
    # async with httpx.AsyncClient() as client:
    #     resp = await client.post(oauth_config["token_url"], data={
    #         "grant_type": "authorization_code",
    #         "code": payload.code,
    #         "client_id": getattr(settings, oauth_config["client_id_setting"]),
    #         "client_secret": getattr(settings, oauth_config["client_secret_setting"]),
    #         "redirect_uri": redirect_uri,
    #     })
    #     token_data = resp.json()
    #
    # For now, store the code as a placeholder token.

    try:
        platform_type_enum = PlatformType(platform_key)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid platform type: {platform_key}",
        )

    platform = Platform(
        id=uuid.uuid4(),
        user_id=current_user.id,
        account_id=account_id,
        platform_type=platform_type_enum,
        platform_account_id="pending_oauth_exchange",
        access_token=payload.code,  # Placeholder until real exchange
        is_active=True,
    )
    db.add(platform)
    await db.flush()
    await db.refresh(platform)

    return PlatformResponse.model_validate(platform)


@router.put("/{platform_id}", response_model=PlatformResponse)
async def update_platform(
    account_id: uuid.UUID,
    platform_id: uuid.UUID,
    payload: PlatformUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a connected platform's settings."""
    await _verify_membership(db, current_user.id, account_id)

    result = await db.execute(
        select(Platform).where(
            Platform.id == platform_id,
            Platform.account_id == account_id,
        )
    )
    platform = result.scalar_one_or_none()
    if platform is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform connection not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    for field, value in update_data.items():
        # Map schema field "metadata" to model column "metadata_"
        attr_name = "metadata_" if field == "metadata" else field
        setattr(platform, attr_name, value)

    await db.flush()
    await db.refresh(platform)

    return PlatformResponse.model_validate(platform)


@router.delete("/{platform_id}", response_model=MessageResponse)
async def disconnect_platform(
    account_id: uuid.UUID,
    platform_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Disconnect (delete) a platform connection."""
    await _verify_membership(db, current_user.id, account_id)

    result = await db.execute(
        select(Platform).where(
            Platform.id == platform_id,
            Platform.account_id == account_id,
        )
    )
    platform = result.scalar_one_or_none()
    if platform is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform connection not found",
        )

    await db.delete(platform)
    await db.flush()

    return MessageResponse(message="Platform disconnected successfully")


@router.post("/{platform_id}/refresh", response_model=PlatformResponse)
async def refresh_platform_token(
    account_id: uuid.UUID,
    platform_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Refresh the access token for a connected platform.

    Uses the stored refresh token to obtain new credentials from the
    platform's OAuth token endpoint.
    """
    await _verify_membership(db, current_user.id, account_id)

    result = await db.execute(
        select(Platform).where(
            Platform.id == platform_id,
            Platform.account_id == account_id,
        )
    )
    platform = result.scalar_one_or_none()
    if platform is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform connection not found",
        )

    if not platform.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token available for this platform. "
            "Please reconnect the platform.",
        )

    platform_key = platform.platform_type.value
    oauth_config = _OAUTH_CONFIGS.get(platform_key)
    if oauth_config is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth configuration not found for this platform type",
        )

    # TODO: Call the platform's token endpoint to refresh the tokens:
    #
    # async with httpx.AsyncClient() as client:
    #     resp = await client.post(oauth_config["token_url"], data={
    #         "grant_type": "refresh_token",
    #         "refresh_token": platform.refresh_token,
    #         "client_id": getattr(settings, oauth_config["client_id_setting"]),
    #         "client_secret": getattr(settings, oauth_config["client_secret_setting"]),
    #     })
    #     if resp.status_code != 200:
    #         raise HTTPException(status_code=502, detail="Failed to refresh token")
    #     token_data = resp.json()
    #     platform.access_token = token_data["access_token"]
    #     platform.refresh_token = token_data.get("refresh_token", platform.refresh_token)
    #     platform.token_expires_at = ...

    platform.last_synced_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(platform)

    return PlatformResponse.model_validate(platform)
