"""X (Twitter) OAuth 2.0 connect flow (Authorization Code + PKCE).

Mirrors ``linkedin_oauth`` / ``facebook_oauth``:

* ``router``          – authenticated, mounted under
  ``/api/v1/accounts/{account_id}/twitter``. ``GET /authorize`` returns the
  X consent URL.
* ``callback_router`` – public, mounted under ``/api/v1``; exchanges the code
  (with the PKCE verifier) and upserts the connected account.

X uses PKCE, so a per-request ``code_verifier`` must survive the redirect. We
carry it (and the workspace identity) inside the short-lived signed ``state`` JWT.
"""

import base64
import hashlib
import logging
import secrets
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

TWITTER_AUTH_URL = "https://twitter.com/i/oauth2/authorize"
TWITTER_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
TWITTER_ME_URL = (
    "https://api.twitter.com/2/users/me?user.fields=profile_image_url,username,public_metrics"
)
TWITTER_SCOPES = "tweet.read tweet.write users.read offline.access"

_STATE_TYPE = "twitter_oauth"


def _frontend_redirect(status_: str, reason: str | None = None) -> RedirectResponse:
    params = {"twitter": status_}
    if reason:
        params["reason"] = reason
    return RedirectResponse(f"{settings.FRONTEND_URL}/social-accounts?{urlencode(params)}")


def _pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for PKCE S256."""
    verifier = secrets.token_urlsafe(64)[:100]
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return verifier, challenge


# ---------------------------------------------------------------------------
# Step 1 – build the consent URL (authenticated)
# ---------------------------------------------------------------------------
@router.get("/authorize")
async def twitter_authorize(
    account_id: uuid.UUID,
    platform_id: uuid.UUID = Query(..., description="The X/Twitter SocialPlatform id"),
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

    if not settings.TWITTER_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X (Twitter) is not configured. Set TWITTER_CLIENT_ID / TWITTER_CLIENT_SECRET in .env.",
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
            detail="X/Twitter platform not found in this workspace",
        )

    # Stop at the plan's platform cap before sending the user off to X.
    reconnect_target = await validate_reconnect_target(
        db, reconnect_id=reconnect, account_id=account_id, platform_id=platform_id
    )
    # The plan cap counts connections, and a reconnect does not add one. A
    # workspace at its limit must still be able to fix a broken account.
    if reconnect_target is None:
        await enforce_platform_limit(db, account_id, platform_id)

    verifier, challenge = _pkce_pair()
    state = jwt.encode(
        {
            "type": _STATE_TYPE,
            "account_id": str(account_id),
            "user_id": str(current_user.id),
            "platform_id": str(platform_id),
            **reconnect_claim(reconnect_target),
            "cv": verifier,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    # Consent URL, scopes and redirect_uri belong to the provider now.
    return {"auth_url": get_provider("twitter").build_authorize_url(state, challenge)}


# ---------------------------------------------------------------------------
# Step 2 – handle X's redirect (public)
# ---------------------------------------------------------------------------
@callback_router.get("/twitter/callback")
async def twitter_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
):
    if error:
        logger.warning("X OAuth denied: %s – %s", error, error_description)
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
        code_verifier = payload["cv"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Invalid X OAuth state: %s", exc)
        return _frontend_redirect("error", "invalid_state")

    # 1. Exchange the code for tokens. The grant's shape -- verb, credential
    # placement, PKCE verifier -- is the provider's business.
    try:
        tokens = await get_provider("twitter").exchange_code(code, code_verifier)
    except ProviderAPIError as exc:
        logger.error("X (Twitter) token exchange failed: %s", exc.detail)
        return _frontend_redirect(
            "error",
            "token_exchange_failed" if exc.status_code else "token_exchange_error",
        )

    access_token = tokens.access_token
    refresh_token = tokens.refresh_token
    if not access_token:
        return _frontend_redirect("error", "no_access_token")
    token_expires_at = tokens.expires_at

    # 2. Fetch the authenticated user.
    try:
        async with httpx.AsyncClient() as client:
            me_res = await client.get(
                TWITTER_ME_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=20.0,
            )
        if me_res.status_code != 200:
            logger.error("X users/me failed: %s", me_res.text)
            return _frontend_redirect("error", "userinfo_failed")
        me = me_res.json().get("data", {})
    except Exception as exc:  # noqa: BLE001
        logger.exception("X users/me error: %s", exc)
        return _frontend_redirect("error", "userinfo_error")

    x_user_id = me.get("id")
    name = me.get("name") or "X User"
    username = me.get("username")
    picture = me.get("profile_image_url")
    followers = (me.get("public_metrics") or {}).get("followers_count", 0)

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
                config={"twitter_user_id": x_user_id, "username": username},
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
                (a for a in existing if (a.config or {}).get("twitter_user_id") == x_user_id),
                None,
            )
            config = {
                "twitter_user_id": x_user_id,
                "username": username,
                "connected_via": "oauth",
            }
            metadata = {"followers": followers, "following": 0, "posts_count": 0}
            handle = f"@{username}" if username else None
            profile_url = f"https://x.com/{username}" if username else None
            if match is not None:
                match.access_token = access_token
                if refresh_token:
                    match.refresh_token = refresh_token
                match.token_expires_at = token_expires_at
                match.config = config
                match.account_name = name
                match.account_handle = handle
                if picture:
                    match.profile_image_url = picture
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
                        account_name=name,
                        account_handle=handle,
                        profile_url=profile_url,
                        profile_image_url=picture,
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
        logger.exception("Failed to persist X account: %s", exc)
        return _frontend_redirect("error", "save_failed")

    return _frontend_redirect("success")
