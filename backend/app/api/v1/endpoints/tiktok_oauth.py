"""TikTok OAuth 2.0 connect flow (Authorization Code + PKCE).

Mirrors ``twitter_oauth``, which is the other PKCE flow here:

* ``router``          – authenticated, mounted under
  ``/api/v1/accounts/{account_id}/tiktok``. ``GET /authorize`` returns the
  TikTok consent URL.
* ``callback_router`` – public, mounted under ``/api/v1``; exchanges the code
  (with the PKCE verifier) and upserts the connected account.

TikTok requires PKCE, so a per-request ``code_verifier`` must survive the
redirect. It travels — with the workspace identity — inside the short-lived
signed ``state`` JWT, because the callback is public and carries no bearer
token.

The one thing this flow records that the others do not is the **audit state**.
An app TikTok has not audited may only post ``SELF_ONLY``, and the connection
has to remember that: it decides the privacy level of every publish and the
sentence the user is shown afterwards. It is written as ``unaudited`` at
connect time and is a deliberate, human step to change — see
docs/WALKTHROUGH-B.md.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.oauth_common import (
    apply_reconnect,
    reconnect_claim,
    reconnect_id_from_state,
    validate_reconnect_target,
)
from app.api.v1.endpoints.social_accounts import _verify_membership
from app.connectors.base import ProviderAPIError
from app.connectors.registry import get_provider
from app.connectors.tiktok import AuditState
from app.connectors.twitter import TwitterProvider
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.core.deps import get_current_active_user
from app.models.platform import SocialAccount, SocialPlatform
from app.models.user import User
from app.services.entitlements import enforce_platform_limit, platform_slot_available

logger = logging.getLogger(__name__)

router = APIRouter()
callback_router = APIRouter()

TIKTOK_USER_URL = (
    "https://open.tiktokapis.com/v2/user/info/"
    "?fields=open_id,union_id,display_name,avatar_url,follower_count"
)

_STATE_TYPE = "tiktok_oauth"


def _frontend_redirect(status_: str, reason: str | None = None) -> RedirectResponse:
    params = {"tiktok": status_}
    if reason:
        params["reason"] = reason
    return RedirectResponse(
        f"{settings.FRONTEND_URL}/social-accounts?{urlencode(params)}"
    )


# ---------------------------------------------------------------------------
# Step 1 – build the consent URL (authenticated)
# ---------------------------------------------------------------------------
@router.get("/authorize")
async def tiktok_authorize(
    account_id: uuid.UUID,
    platform_id: uuid.UUID = Query(..., description="The TikTok SocialPlatform id"),
    reconnect: uuid.UUID | None = Query(
        None,
        description=(
            "Re-authorise an existing connection in place. Without this a "
            "re-connect creates a second row and orphans the first one's "
            "post history."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _verify_membership(db, current_user.id, account_id)

    provider = get_provider("tiktok")
    if not provider.is_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "TikTok is not configured. Set TIKTOK_CLIENT_KEY / "
                "TIKTOK_CLIENT_SECRET in .env."
            ),
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
            detail="TikTok platform not found in this workspace",
        )

    reconnect_target = await validate_reconnect_target(
        db, reconnect_id=reconnect, account_id=account_id, platform_id=platform_id
    )
    # The plan cap counts connections, and a reconnect does not add one.
    if reconnect_target is None:
        await enforce_platform_limit(db, account_id, platform_id)

    # PKCE S256, identical arithmetic to X's -- borrowed rather than copied so
    # the two cannot drift into two different implementations of one RFC.
    verifier, challenge = TwitterProvider.pkce_pair()
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

    return {"auth_url": provider.build_authorize_url(state, challenge)}


# ---------------------------------------------------------------------------
# Step 2 – handle TikTok's redirect (public)
# ---------------------------------------------------------------------------
@callback_router.get("/tiktok/callback")
async def tiktok_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
):
    if error:
        logger.warning("TikTok OAuth denied: %s – %s", error, error_description)
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
        logger.warning("Invalid TikTok OAuth state: %s", exc)
        return _frontend_redirect("error", "invalid_state")

    try:
        tokens = await get_provider("tiktok").exchange_code(code, code_verifier)
    except ProviderAPIError as exc:
        logger.error("TikTok token exchange failed: %s", exc.detail)
        return _frontend_redirect(
            "error",
            "token_exchange_failed" if exc.status_code else "token_exchange_error",
        )

    access_token = tokens.access_token
    refresh_token = tokens.refresh_token
    if not access_token:
        return _frontend_redirect("error", "no_access_token")
    token_expires_at = tokens.expires_at

    try:
        async with httpx.AsyncClient() as client:
            me_res = await client.get(
                TIKTOK_USER_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=20.0,
            )
        if me_res.status_code != 200:
            logger.error("TikTok user/info failed: %s", me_res.text)
            return _frontend_redirect("error", "userinfo_failed")
        me = ((me_res.json() or {}).get("data") or {}).get("user") or {}
    except Exception as exc:  # noqa: BLE001
        logger.exception("TikTok user/info error: %s", exc)
        return _frontend_redirect("error", "userinfo_error")

    open_id = me.get("open_id")
    name = me.get("display_name") or "TikTok User"
    picture = me.get("avatar_url")
    # Absent stays absent. user.info.stats may not have been granted, and a
    # follower count of 0 would render as a measurement rather than a gap.
    followers = me.get("follower_count")
    metadata = {"followers": followers} if followers is not None else {}

    config = {
        "open_id": open_id,
        "connected_via": "oauth",
        # Every publish reads this. Unaudited means SELF_ONLY, which is the
        # honest default for an app TikTok has not reviewed.
        AuditState.KEY: AuditState.UNAUDITED,
    }

    try:
        async with AsyncSessionLocal() as session:
            # The consent round-trip may have taken the workspace past its
            # limit, and the state token can be replayed.
            if not await platform_slot_available(session, account_id, platform_id):
                return _frontend_redirect("error", "plan_limit")

            reconnect_id = reconnect_id_from_state(payload)
            if reconnect_id is not None and await apply_reconnect(
                session,
                reconnect_id=reconnect_id,
                account_id=account_id,
                platform_id=platform_id,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                config=config,
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
                (a for a in existing if (a.config or {}).get("open_id") == open_id),
                None,
            )
            if match is not None:
                match.access_token = access_token
                if refresh_token:
                    match.refresh_token = refresh_token
                match.token_expires_at = token_expires_at
                # Preserve an audit state someone has already advanced by hand;
                # re-authorising does not un-audit an app.
                match.config = {
                    **config,
                    AuditState.KEY: AuditState.of(match),
                }
                match.account_name = name
                if picture:
                    match.profile_image_url = picture
                if metadata:
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
        logger.exception("Failed to persist TikTok account: %s", exc)
        return _frontend_redirect("error", "save_failed")

    return _frontend_redirect("success")
