"""CRM integrations, at organization level.

Two routers, the same split the platform OAuth endpoints use:

* ``router`` is authenticated and mounted under an organization -- listing,
  starting a connect, disconnecting;
* ``callback_router`` is public, because the CRM redirects a browser to it and
  that browser carries no bearer token. Identity travels in a short-lived
  signed ``state`` JWT instead, exactly as the platform connectors do it.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import verify_org_access
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.integrations.base import CrmAPIError, CrmAuthExpired
from app.integrations.registry import UnknownProvider, get_provider, known_slugs
from app.models.organization import OrgRole
from app.models.user import User
from app.services import crm
from app.services.activity_service import log_activity

logger = logging.getLogger(__name__)

router = APIRouter()
callback_router = APIRouter()

_STATE_TYPE = "crm_connect"
_STATE_MINUTES = 15


def _provider_or_404(slug: str):
    try:
        return get_provider(slug)
    except UnknownProvider as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/")
async def list_integrations(
    organization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Every CRM this product knows, and whether this organization uses it.

    Never returns a token -- only whether one is stored, which portal it points
    at, and who connected it. An org-wide credential nobody remembers adding is
    one nobody dares remove.
    """
    await verify_org_access(organization_id, current_user, db)

    out = []
    for slug in known_slugs():
        provider = get_provider(slug)
        connection = await crm.connection_for(db, organization_id, slug)
        connected_by_name = None
        if connection is not None and connection.connected_by:
            user = (
                await db.execute(
                    select(User).where(User.id == connection.connected_by)
                )
            ).scalar_one_or_none()
            connected_by_name = user.full_name or user.email if user else None

        out.append({
            "provider": slug,
            "name": provider.name,
            # Whether this deployment has app credentials at all. A "Connect"
            # button that cannot work is worse than an explained absence.
            "configured": provider.is_configured(),
            "connected": connection is not None and bool(connection.access_token),
            "account_name": connection.external_account_name if connection else None,
            "account_id": connection.external_account_id if connection else None,
            "connected_by": connected_by_name,
            "connected_at": (
                connection.created_at.isoformat() if connection else None
            ),
            "capabilities": {
                "contact_upsert": provider.capabilities.supports_contact_upsert,
                # Stated rather than omitted: a reader should be able to see
                # what this integration does not do without reading the code.
                "contact_read": provider.capabilities.supports_contact_read,
                "deals": provider.capabilities.supports_deals,
                "attribution": provider.capabilities.supports_attribution,
            },
        })
    return {"items": out}


@router.get("/{provider_slug}/authorize")
async def authorize(
    organization_id: uuid.UUID,
    provider_slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Start the OAuth dance. Admin or owner only.

    Connecting a CRM gives this product write access to the company's customer
    records, which is not a decision an ordinary member should make on
    everyone's behalf.
    """
    await verify_org_access(
        organization_id, current_user, db, min_role=OrgRole.ADMIN
    )
    provider = _provider_or_404(provider_slug)

    if not provider.is_configured():
        raise HTTPException(
            status_code=400,
            detail=(
                f"{provider.name} is not configured on this deployment. "
                f"Its client id and secret are missing."
            ),
        )

    state = jwt.encode(
        {
            "type": _STATE_TYPE,
            "organization_id": str(organization_id),
            "user_id": str(current_user.id),
            "provider": provider.slug,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=_STATE_MINUTES),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"auth_url": provider.authorize_url(state)}


@callback_router.get("/integrations/{provider_slug}/callback")
async def callback(
    provider_slug: str,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Where the CRM sends the browser back.

    Public by necessity -- a redirected browser carries no bearer token -- so
    identity comes from the signed state and nothing else. Always redirects to
    the app with a result in the query string rather than rendering JSON at a
    user.
    """
    front = settings.FRONTEND_URL.rstrip("/")

    def _back(status_word: str, detail: str = "") -> RedirectResponse:
        from urllib.parse import urlencode

        query = urlencode({"crm": status_word, **({"detail": detail} if detail else {})})
        return RedirectResponse(f"{front}/settings?{query}")

    if error:
        return _back("denied", error[:200])
    if not code or not state:
        return _back("error", "The CRM did not return an authorization code.")

    try:
        payload = jwt.decode(
            state, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError:
        return _back("error", "That connection link has expired. Try again.")

    if payload.get("type") != _STATE_TYPE or payload.get("provider") != provider_slug:
        return _back("error", "That connection link is not valid.")

    try:
        provider = get_provider(provider_slug)
        tokens = await provider.exchange_code(code)
    except (CrmAuthExpired, CrmAPIError) as exc:
        logger.warning("CRM code exchange failed: %s", exc)
        return _back("error", str(exc)[:200])
    except Exception:  # noqa: BLE001
        logger.exception("CRM code exchange blew up")
        return _back("error", "Could not complete the connection.")

    await crm.save_connection(
        db,
        uuid.UUID(payload["organization_id"]),
        provider_slug,
        tokens,
        user_id=uuid.UUID(payload["user_id"]),
    )
    await db.commit()
    return _back("connected")


@router.delete("/{provider_slug}", status_code=status.HTTP_200_OK)
async def disconnect(
    organization_id: uuid.UUID,
    provider_slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Revoke upstream and clear the stored credential."""
    await verify_org_access(
        organization_id, current_user, db, min_role=OrgRole.ADMIN
    )
    _provider_or_404(provider_slug)

    connection = await crm.connection_for(db, organization_id, provider_slug)
    if connection is None:
        raise HTTPException(status_code=404, detail="That CRM is not connected.")

    revoked = await crm.disconnect(db, connection)
    await log_activity(
        db, user_id=current_user.id, account_id=None,
        action="crm.disconnected", category="integration",
        description=f"Disconnected {provider_slug}",
        resource_type="crm_connection", resource_id=provider_slug,
    )
    return {
        "disconnected": True,
        # Said plainly: the local credential is gone either way, and whether
        # the vendor confirmed is a separate fact worth showing.
        "revoked_upstream": revoked,
    }
