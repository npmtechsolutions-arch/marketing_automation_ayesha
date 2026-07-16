"""LinkedIn OAuth 2.0 connect flow.

Two routers live here:

* ``router``          – authenticated, mounted under
  ``/api/v1/accounts/{account_id}/linkedin``. The frontend calls
  ``GET /authorize`` to obtain the LinkedIn consent URL.
* ``callback_router`` – public (LinkedIn redirects the *browser* here, so there
  is no JWT), mounted under ``/api/v1``. Exchanges the ``code`` for tokens,
  reads the member/organization identity and upserts a ``SocialAccount``.

Identity is carried across the round-trip inside a short-lived signed ``state``
JWT so the public callback can trust which workspace/user initiated the flow.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
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

# ---------------------------------------------------------------------------
# LinkedIn API constants
# ---------------------------------------------------------------------------
LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
LINKEDIN_ORG_ACLS_URL = (
    "https://api.linkedin.com/v2/organizationAcls"
    "?q=roleAssignee&role=ADMINISTRATOR&state=APPROVED"
)

# Scopes requested per target. Personal scopes are covered by the auto-approved
# "Sign In with LinkedIn using OpenID Connect" + "Share on LinkedIn" products.
# Organization scopes additionally require the "Community Management API" product.
SCOPES = {
    "personal": "openid profile email w_member_social",
    "organization": (
        "openid profile email r_organization_social "
        "w_organization_social rw_organization_admin"
    ),
}

_STATE_TYPE = "linkedin_oauth"


def _frontend_redirect(status_: str, reason: str | None = None) -> RedirectResponse:
    """Bounce the browser back to the Social Accounts page with a result flag."""
    params = {"linkedin": status_}
    if reason:
        params["reason"] = reason
    url = f"{settings.FRONTEND_URL}/social-accounts?{urlencode(params)}"
    return RedirectResponse(url)


# ---------------------------------------------------------------------------
# Step 1 – build the consent URL (authenticated)
# ---------------------------------------------------------------------------
@router.get("/authorize")
async def linkedin_authorize(
    account_id: uuid.UUID,
    platform_id: uuid.UUID = Query(..., description="The LinkedIn SocialPlatform id"),
    target: str = Query("personal", pattern="^(personal|organization)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return the LinkedIn OAuth consent URL for the given workspace + platform."""
    await _verify_membership(db, current_user.id, account_id)

    if not settings.LINKEDIN_CLIENT_ID or not settings.LINKEDIN_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "LinkedIn is not configured. Set LINKEDIN_CLIENT_ID and "
                "LINKEDIN_CLIENT_SECRET in the backend .env file."
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
            detail="LinkedIn platform not found in this workspace",
        )

    # Sign identity into the state token (valid 15 minutes).
    state = jwt.encode(
        {
            "type": _STATE_TYPE,
            "account_id": str(account_id),
            "user_id": str(current_user.id),
            "platform_id": str(platform_id),
            "target": target,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    params = {
        "response_type": "code",
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
        "state": state,
        "scope": SCOPES[target],
    }
    return {"auth_url": f"{LINKEDIN_AUTH_URL}?{urlencode(params)}"}


# ---------------------------------------------------------------------------
# Step 2 – handle LinkedIn's redirect (public)
# ---------------------------------------------------------------------------
@callback_router.get("/linkedin/callback")
async def linkedin_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
):
    """Exchange the authorization code and persist the connected account."""
    if error:
        logger.warning("LinkedIn OAuth denied: %s – %s", error, error_description)
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
        target = payload.get("target", "personal")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Invalid LinkedIn OAuth state: %s", exc)
        return _frontend_redirect("error", "invalid_state")

    # 1. Exchange the code for an access token.
    try:
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                LINKEDIN_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
                    "client_id": settings.LINKEDIN_CLIENT_ID,
                    "client_secret": settings.LINKEDIN_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=20.0,
            )
        if token_res.status_code != 200:
            logger.error("LinkedIn token exchange failed: %s", token_res.text)
            return _frontend_redirect("error", "token_exchange_failed")
        token_data = token_res.json()
    except Exception as exc:  # noqa: BLE001
        logger.exception("LinkedIn token exchange error: %s", exc)
        return _frontend_redirect("error", "token_exchange_error")

    access_token = token_data.get("access_token")
    expires_in = token_data.get("expires_in")
    refresh_token = token_data.get("refresh_token")
    if not access_token:
        return _frontend_redirect("error", "no_access_token")

    token_expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        if expires_in
        else None
    )

    # 2. Fetch the member identity (OpenID Connect userinfo).
    try:
        async with httpx.AsyncClient() as client:
            me_res = await client.get(
                LINKEDIN_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=20.0,
            )
        if me_res.status_code != 200:
            logger.error("LinkedIn userinfo failed: %s", me_res.text)
            return _frontend_redirect("error", "userinfo_failed")
        me = me_res.json()
    except Exception as exc:  # noqa: BLE001
        logger.exception("LinkedIn userinfo error: %s", exc)
        return _frontend_redirect("error", "userinfo_error")

    member_sub = me.get("sub")
    member_name = me.get("name") or "LinkedIn User"
    member_picture = me.get("picture")

    # 3. Persist the connected account(s).
    try:
        async with AsyncSessionLocal() as session:
            if target == "organization":
                orgs = await _fetch_admin_organizations(access_token)
                if not orgs:
                    return _frontend_redirect("error", "no_admin_orgs")
                for org in orgs:
                    await _upsert_account(
                        session,
                        account_id=account_id,
                        user_id=user_id,
                        platform_id=platform_id,
                        author_urn=f"urn:li:organization:{org['id']}",
                        target="organization",
                        display_name=org["name"],
                        handle=org.get("vanity"),
                        profile_url=(
                            f"https://www.linkedin.com/company/{org['vanity']}"
                            if org.get("vanity")
                            else f"https://www.linkedin.com/company/{org['id']}"
                        ),
                        profile_image_url=org.get("logo"),
                        access_token=access_token,
                        refresh_token=refresh_token,
                        token_expires_at=token_expires_at,
                        member_id=member_sub,
                    )
            else:
                await _upsert_account(
                    session,
                    account_id=account_id,
                    user_id=user_id,
                    platform_id=platform_id,
                    author_urn=f"urn:li:person:{member_sub}",
                    target="personal",
                    display_name=member_name,
                    handle=member_name,
                    profile_url="https://www.linkedin.com/in/me",
                    profile_image_url=member_picture,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_expires_at=token_expires_at,
                    member_id=member_sub,
                )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to persist LinkedIn account: %s", exc)
        return _frontend_redirect("error", "save_failed")

    return _frontend_redirect("success")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _fetch_admin_organizations(access_token: str) -> list[dict]:
    """Return the organizations the connected member can administer."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    orgs: list[dict] = []
    async with httpx.AsyncClient() as client:
        acls_res = await client.get(LINKEDIN_ORG_ACLS_URL, headers=headers, timeout=20.0)
        if acls_res.status_code != 200:
            logger.error("LinkedIn organizationAcls failed: %s", acls_res.text)
            return orgs
        elements = acls_res.json().get("elements", [])
        for el in elements:
            org_urn = el.get("organization", "")
            org_id = org_urn.split(":")[-1] if org_urn else None
            if not org_id:
                continue
            name, vanity, logo = f"Organization {org_id}", None, None
            try:
                detail_res = await client.get(
                    f"https://api.linkedin.com/v2/organizations/{org_id}"
                    "?projection=(id,localizedName,vanityName)",
                    headers=headers,
                    timeout=15.0,
                )
                if detail_res.status_code == 200:
                    d = detail_res.json()
                    name = d.get("localizedName") or name
                    vanity = d.get("vanityName")
            except Exception:  # noqa: BLE001
                logger.warning("Could not fetch details for org %s", org_id)
            orgs.append({"id": org_id, "name": name, "vanity": vanity, "logo": logo})
    return orgs


async def _upsert_account(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    platform_id: uuid.UUID,
    author_urn: str,
    target: str,
    display_name: str,
    handle: str | None,
    profile_url: str | None,
    profile_image_url: str | None,
    access_token: str,
    refresh_token: str | None,
    token_expires_at: datetime | None,
    member_id: str | None,
) -> None:
    """Create or update the SocialAccount for this LinkedIn author (matched by URN)."""
    existing = (
        await session.execute(
            select(SocialAccount).where(
                SocialAccount.account_id == account_id,
                SocialAccount.platform_id == platform_id,
            )
        )
    ).scalars().all()

    match = next(
        (a for a in existing if (a.config or {}).get("author_urn") == author_urn),
        None,
    )

    config = {
        "author_urn": author_urn,
        "target": target,
        "member_id": member_id,
        "connected_via": "oauth",
    }

    if match is not None:
        match.access_token = access_token
        if refresh_token:
            match.refresh_token = refresh_token
        match.token_expires_at = token_expires_at
        match.config = config
        match.account_name = display_name
        match.account_handle = handle
        if profile_image_url:
            match.profile_image_url = profile_image_url
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
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            config=config,
            is_verified=True,
            is_active=True,
            last_verified_at=datetime.now(timezone.utc),
        )
    )
