"""YouTube (Google) OAuth 2.0 connect flow.

Mirrors ``linkedin_oauth`` / ``twitter_oauth``:

* ``router``          – authenticated, mounted under
  ``/api/v1/accounts/{account_id}/youtube``. ``GET /authorize`` returns the
  Google consent URL.
* ``callback_router`` – public, mounted under ``/api/v1``; exchanges the code,
  reads the YouTube channel and upserts the connected account.

"Publishing" to YouTube means uploading a video (there is no public API for
community posts), so the connected token carries the ``youtube.upload`` scope.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.social_accounts import _verify_membership
from app.core.config import settings
from app.connectors.base import ProviderAPIError
from app.connectors.registry import get_provider
from app.api.v1.endpoints.oauth_common import (
    apply_reconnect,
    reconnect_claim,
    reconnect_id_from_state,
    validate_reconnect_target,
)
from app.core.database import AsyncSessionLocal, get_db
from app.core.deps import get_current_active_user
from app.models.platform import SocialAccount, SocialPlatform
from app.models.user import User
from app.services.entitlements import enforce_platform_limit, platform_slot_available

logger = logging.getLogger(__name__)

router = APIRouter()
callback_router = APIRouter()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_CHANNELS_URL = (
    "https://www.googleapis.com/youtube/v3/channels"
    "?part=snippet,statistics&mine=true"
)
YOUTUBE_SCOPES = (
    "openid email profile "
    "https://www.googleapis.com/auth/youtube.upload "
    "https://www.googleapis.com/auth/youtube.readonly"
)

_STATE_TYPE = "youtube_oauth"


def _frontend_redirect(status_: str, reason: str | None = None) -> RedirectResponse:
    params = {"youtube": status_}
    if reason:
        params["reason"] = reason
    return RedirectResponse(f"{settings.FRONTEND_URL}/social-accounts?{urlencode(params)}")


# ---------------------------------------------------------------------------
# Step 1 – build the consent URL (authenticated)
# ---------------------------------------------------------------------------
@router.get("/authorize")
async def youtube_authorize(
    account_id: uuid.UUID,
    platform_id: uuid.UUID = Query(..., description="The YouTube SocialPlatform id"),
    reconnect: uuid.UUID | None = Query(
        None,
        description=(
            "Re-authorise an existing connection in place. Without this a "
            "re-connect creates a second row and orphans the first one\'s "
            "post history."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _verify_membership(db, current_user.id, account_id)

    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="YouTube is not configured. Set GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET in .env.",
        )

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
            detail="YouTube platform not found in this workspace",
        )

    # Stop at the plan's platform cap before sending the user off to Google.
    reconnect_target = await validate_reconnect_target(
        db, reconnect_id=reconnect, account_id=account_id, platform_id=platform_id
    )
    # The plan cap counts connections, and a reconnect does not add one. A
    # workspace at its limit must still be able to fix a broken account.
    if reconnect_target is None:
        await enforce_platform_limit(db, account_id, platform_id)

    state = jwt.encode(
        {
            "type": _STATE_TYPE,
            "account_id": str(account_id),
            "user_id": str(current_user.id),
            "platform_id": str(platform_id),
            **reconnect_claim(reconnect_target),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    # Consent URL, scopes and redirect_uri belong to the provider now.
    return {"auth_url": get_provider("youtube").build_authorize_url(state)}


# ---------------------------------------------------------------------------
# Step 2 – handle Google's redirect (public)
# ---------------------------------------------------------------------------
@callback_router.get("/youtube/callback")
async def youtube_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
):
    if error:
        logger.warning("YouTube OAuth denied: %s", error)
        return _frontend_redirect("error", error)
    if not code or not state:
        return _frontend_redirect("error", "missing_code")

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
        logger.warning("Invalid YouTube OAuth state: %s", exc)
        return _frontend_redirect("error", "invalid_state")

    # 1. Exchange the code for tokens. The grant's shape -- verb, credential
    # placement, PKCE verifier -- is the provider's business.
    try:
        tokens = await get_provider("youtube").exchange_code(code)
    except ProviderAPIError as exc:
        logger.error("YouTube token exchange failed: %s", exc.detail)
        return _frontend_redirect(
            "error",
            "token_exchange_failed" if exc.status_code else "token_exchange_error",
        )

    access_token = tokens.access_token
    refresh_token = tokens.refresh_token
    if not access_token:
        return _frontend_redirect("error", "no_access_token")
    token_expires_at = tokens.expires_at

    # 2. Fetch the user's YouTube channel.
    try:
        async with httpx.AsyncClient() as client:
            ch_res = await client.get(
                YOUTUBE_CHANNELS_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=20.0,
            )
        if ch_res.status_code != 200:
            logger.error("YouTube channels fetch failed: %s", ch_res.text)
            return _frontend_redirect("error", "channel_fetch_failed")
        items = ch_res.json().get("items", [])
        if not items:
            return _frontend_redirect("error", "no_channel")
    except Exception as exc:  # noqa: BLE001
        logger.exception("YouTube channels error: %s", exc)
        return _frontend_redirect("error", "channel_fetch_error")

    channel = items[0]
    channel_id = channel.get("id")
    snippet = channel.get("snippet", {})
    stats = channel.get("statistics", {})
    title = snippet.get("title") or "YouTube Channel"
    custom_url = snippet.get("customUrl")
    thumb = (
        snippet.get("thumbnails", {}).get("high", {}).get("url")
        or snippet.get("thumbnails", {}).get("default", {}).get("url")
    )
    subscribers = int(stats.get("subscriberCount", 0) or 0)
    video_count = int(stats.get("videoCount", 0) or 0)

    try:
        async with AsyncSessionLocal() as session:
            # Re-check the plan cap: the consent round-trip may have taken the
            # account past its limit, and the state token can be replayed.
            if not await platform_slot_available(session, account_id, platform_id):
                return _frontend_redirect("error", "plan_limit")
            # A reconnect updates the existing row so every post,
            # publishing job and metric that points at it keeps working.
            # A fresh row would leave all of that pointing at dead
            # credentials.
            reconnect_id = reconnect_id_from_state(payload)
            if reconnect_id is not None and await apply_reconnect(
                session,
                reconnect_id=reconnect_id,
                account_id=account_id,
                platform_id=platform_id,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                config={"channel_id": channel_id},
            ):
                await session.commit()
                return _frontend_redirect("success")

            existing = (
                await session.execute(
                    select(SocialAccount).where(
                        SocialAccount.account_id == account_id,
                        SocialAccount.platform_id == platform_id,
                    )
                )
            ).scalars().all()
            match = next(
                (a for a in existing if (a.config or {}).get("channel_id") == channel_id),
                None,
            )
            config = {"channel_id": channel_id, "connected_via": "oauth"}
            metadata = {"followers": subscribers, "following": 0, "posts_count": video_count}
            profile_url = (
                f"https://www.youtube.com/{custom_url}"
                if custom_url
                else f"https://www.youtube.com/channel/{channel_id}"
            )
            if match is not None:
                match.access_token = access_token
                if refresh_token:
                    match.refresh_token = refresh_token
                match.token_expires_at = token_expires_at
                match.config = config
                match.account_name = title
                match.account_handle = custom_url
                if thumb:
                    match.profile_image_url = thumb
                match.metadata_ = metadata
                match.is_verified = True
                match.is_active = True
                match.last_verified_at = datetime.now(timezone.utc)
            else:
                session.add(
                    SocialAccount(
                        user_id=user_id,
                        account_id=account_id,
                        platform_id=platform_id,
                        account_name=title,
                        account_handle=custom_url,
                        profile_url=profile_url,
                        profile_image_url=thumb,
                        access_token=access_token,
                        refresh_token=refresh_token,
                        token_expires_at=token_expires_at,
                        config=config,
                        metadata_=metadata,
                        is_verified=True,
                        is_active=True,
                        last_verified_at=datetime.now(timezone.utc),
                    )
                )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to persist YouTube account: %s", exc)
        return _frontend_redirect("error", "save_failed")

    return _frontend_redirect("success")
