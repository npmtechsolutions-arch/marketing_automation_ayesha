"""Facebook OAuth 2.0 connect flow."""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.social_accounts import _verify_membership
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.core.deps import get_current_active_user
from app.models.platform import SocialAccount, SocialPlatform
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()
callback_router = APIRouter()

FACEBOOK_AUTH_URL = "https://www.facebook.com/v18.0/dialog/oauth"
FACEBOOK_TOKEN_URL = "https://graph.facebook.com/v18.0/oauth/access_token"
FACEBOOK_ME_PAGES_URL = "https://graph.facebook.com/v18.0/me/accounts"

_STATE_TYPE = "facebook_oauth"


def _frontend_redirect(status_: str, reason: str | None = None) -> RedirectResponse:
    """Bounce the browser back to the Social Accounts page with a result flag."""
    params = {"facebook": status_}
    if reason:
        params["reason"] = reason
    url = f"{settings.FRONTEND_URL}/social-accounts?{urlencode(params)}"
    return RedirectResponse(url)


# ---------------------------------------------------------------------------
# Step 1 – build the consent URL (authenticated)
# ---------------------------------------------------------------------------
@router.get("/authorize")
async def facebook_authorize(
    account_id: uuid.UUID,
    platform_id: uuid.UUID = Query(..., description="The Facebook SocialPlatform id"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return the Facebook OAuth consent URL for the given workspace + platform."""
    await _verify_membership(db, current_user.id, account_id)

    if not settings.META_APP_ID or not settings.META_APP_SECRET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Meta is not configured. Set META_APP_ID and "
                "META_APP_SECRET in the backend .env file."
            ),
        )

    # Confirm the platform exists in this workspace.
    platform = (
        await db.execute(
            select(SocialPlatform).where(
                SocialPlatform.id == platform_id,
                SocialPlatform.account_id == account_id,
            )
        )
    ).scalar_one_or_none()
    if platform is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Facebook platform not found in this workspace",
        )

    # Sign identity into the state token (valid 15 minutes).
    state = jwt.encode(
        {
            "type": _STATE_TYPE,
            "account_id": str(account_id),
            "user_id": str(current_user.id),
            "platform_id": str(platform_id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    redirect_uri = settings.LINKEDIN_REDIRECT_URI.replace("/linkedin/callback", "/facebook/callback")

    params = {
        "response_type": "code",
        "client_id": settings.META_APP_ID.strip() if settings.META_APP_ID else "",
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": "pages_manage_posts,pages_read_engagement,pages_show_list,read_insights",
    }
    if settings.META_CONFIG_ID:
        params["config_id"] = settings.META_CONFIG_ID.strip()
    return {"auth_url": f"{FACEBOOK_AUTH_URL}?{urlencode(params)}"}


# ---------------------------------------------------------------------------
# Step 2 – handle Facebook's redirect (public)
# ---------------------------------------------------------------------------
@callback_router.get("/facebook/callback")
async def facebook_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
):
    """Exchange the authorization code and persist the connected page."""
    if error:
        logger.warning("Facebook OAuth denied: %s – %s", error, error_description)
        return _frontend_redirect("error", error)

    if not code or not state:
        return _frontend_redirect("error", "missing_code")

    # Validate + decode the signed state.
    try:
        payload = jwt.decode(
            state, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != _STATE_TYPE:
            raise ValueError("bad state type")
        account_id = uuid.UUID(payload["account_id"])
        user_id = uuid.UUID(payload["user_id"])
        platform_id = uuid.UUID(payload["platform_id"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Invalid Facebook OAuth state: %s", exc)
        return _frontend_redirect("error", "invalid_state")

    redirect_uri = settings.LINKEDIN_REDIRECT_URI.replace("/linkedin/callback", "/facebook/callback")

    # 1. Exchange the code for a User Access Token.
    try:
        async with httpx.AsyncClient() as client:
            token_res = await client.get(
                FACEBOOK_TOKEN_URL,
                params={
                    "client_id": settings.META_APP_ID.strip() if settings.META_APP_ID else "",
                    "client_secret": settings.META_APP_SECRET.strip() if settings.META_APP_SECRET else "",
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
                timeout=20.0,
            )
        if token_res.status_code != 200:
            logger.error("Facebook token exchange failed: %s", token_res.text)
            return _frontend_redirect("error", "token_exchange_failed")
        token_data = token_res.json()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Facebook token exchange error: %s", exc)
        return _frontend_redirect("error", "token_exchange_error")

    access_token = token_data.get("access_token")
    expires_in = token_data.get("expires_in")
    if not access_token:
        return _frontend_redirect("error", "no_access_token")

    token_expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        if expires_in
        else None
    )

    # 2. Fetch the linked Facebook Pages (/me/accounts)
    try:
        async with httpx.AsyncClient() as client:
            pages_res = await client.get(
                FACEBOOK_ME_PAGES_URL,
                params={"access_token": access_token},
                timeout=20.0,
            )
        if pages_res.status_code != 200:
            logger.error("Facebook me/accounts fetch failed: %s", pages_res.text)
            return _frontend_redirect("error", "fetch_pages_failed")
        pages_data = pages_res.json().get("data", [])
        if not pages_data:
            return _frontend_redirect("error", "no_linked_pages")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Facebook me/accounts error: %s", exc)
        return _frontend_redirect("error", "fetch_pages_error")

    # Connect/link the first Page found
    first_page = pages_data[0]
    page_id = first_page["id"]
    page_access_token = first_page.get("access_token") or access_token
    page_name = first_page["name"]

    # 3. Fetch detailed Page info (followers/fan_count, picture, handle)
    followers = 0
    username = None
    picture_url = None
    try:
        url_page = f"https://graph.facebook.com/v18.0/{page_id}"
        async with httpx.AsyncClient() as client:
            res_page = await client.get(
                url_page,
                params={"fields": "fan_count,username,picture.type(large)", "access_token": page_access_token},
                timeout=15.0
            )
            if res_page.status_code == 200:
                p_data = res_page.json()
                followers = p_data.get("fan_count", 0)
                username = p_data.get("username")
                picture_url = p_data.get("picture", {}).get("data", {}).get("url")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Facebook Page details fetch failed: %s", exc)

    handle = f"@{username}" if username else f"@{page_id}"

    # 4. Persist/Upsert the Facebook SocialAccount record
    try:
        async with AsyncSessionLocal() as session:
            await _upsert_facebook_account(
                session,
                account_id=account_id,
                user_id=user_id,
                platform_id=platform_id,
                page_id=page_id,
                page_access_token=page_access_token,
                display_name=page_name,
                handle=handle,
                profile_url=f"https://facebook.com/{page_id}",
                profile_image_url=picture_url,
                access_token=access_token,
                token_expires_at=token_expires_at,
                followers=followers,
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to persist Facebook account: %s", exc)
        return _frontend_redirect("error", "save_failed")

    return _frontend_redirect("success")


async def _upsert_facebook_account(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    platform_id: uuid.UUID,
    page_id: str,
    page_access_token: str,
    display_name: str,
    handle: str | None,
    profile_url: str | None,
    profile_image_url: str | None,
    access_token: str,
    token_expires_at: datetime | None,
    followers: int = 0,
) -> None:
    """Create or update the Facebook SocialAccount for this Page ID."""
    existing = (
        await session.execute(
            select(SocialAccount).where(
                SocialAccount.account_id == account_id,
                SocialAccount.platform_id == platform_id,
            )
        )
    ).scalars().all()

    match = next(
        (a for a in existing if (a.config or {}).get("page_id") == page_id),
        None,
    )

    config = {
        "page_id": page_id,
        "page_access_token": page_access_token,
        "connected_via": "oauth",
    }
    
    metadata = {
        "followers": followers,
        "following": 0,
        "posts_count": 0,
    }

    if match is not None:
        match.access_token = access_token
        match.token_expires_at = token_expires_at
        match.config = config
        match.account_name = display_name
        match.account_handle = handle
        if profile_image_url:
            match.profile_image_url = profile_image_url
        match.metadata_ = metadata
        match.is_verified = True
        match.is_active = True
        match.last_verified_at = datetime.now(timezone.utc)
        return

    session.add(
        SocialAccount(
            user_id=user_id,
            account_id=account_id,
            platform_id=platform_id,
            account_name=display_name,
            account_handle=handle,
            profile_url=profile_url,
            profile_image_url=profile_image_url,
            access_token=access_token,
            token_expires_at=token_expires_at,
            config=config,
            metadata_=metadata,
            is_verified=True,
            is_active=True,
            last_verified_at=datetime.now(timezone.utc),
        )
    )
