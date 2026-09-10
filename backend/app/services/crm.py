"""Using a CRM connection: refresh, upsert, disconnect.

The rules this follows, all inherited:

* **Tokens are refreshed before use, not after a failure.** A refresh-on-401
  loop retries a write that may have half-happened; refreshing on expiry does
  not. Mirrors ``_ensure_valid_token`` on the publishing path.
* **A CRM failure is visible on the action that caused it**, and never
  corrupts what it was acting on. Slack's failures are swallowed because a
  chat message is not the point of a publish; a CRM write *is* the point of
  "Send to CRM", so this one surfaces -- but it surfaces as an error on that
  action alone. The inbox thread is not modified on the way in, so there is
  nothing to leave half-written.
* **Nothing is invented.** A contact carries the handle, the platform and a
  link. Not a guessed email, not a company inferred from a display name.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.base import (
    ContactRef,
    CrmAuthExpired,
    CrmNotConnected,
    SocialContact,
)
from app.integrations.registry import get_provider
from app.models.crm_connection import CrmConnection

logger = logging.getLogger(__name__)

# Refreshed this far before expiry, so a write never starts on a token that
# dies mid-request.
REFRESH_MARGIN = timedelta(minutes=5)


async def connection_for(
    db: AsyncSession, organization_id, provider_slug: str
) -> Optional[CrmConnection]:
    return (
        await db.execute(
            select(CrmConnection).where(
                CrmConnection.organization_id == organization_id,
                CrmConnection.provider == provider_slug.lower(),
            )
        )
    ).scalar_one_or_none()


async def save_connection(
    db: AsyncSession, organization_id, provider_slug: str, tokens, *, user_id=None
) -> CrmConnection:
    """Store a new connection, or update the existing one in place.

    In place, because a second row for the same provider would be two portals
    competing for the same action. Reconnecting after an expiry is the common
    case and must not accumulate rows -- 1.9's rule, applied to credentials.
    """
    existing = await connection_for(db, organization_id, provider_slug)
    if existing is None:
        existing = CrmConnection(
            id=uuid.uuid4(),
            organization_id=organization_id,
            provider=provider_slug.lower(),
        )
        db.add(existing)

    existing.access_token = tokens.access_token
    # A provider that does not return a new refresh token on re-consent keeps
    # the old one; overwriting with None would silently un-connect them.
    if tokens.refresh_token:
        existing.refresh_token = tokens.refresh_token
    existing.token_expires_at = tokens.expires_at
    existing.external_account_id = tokens.external_account_id
    existing.external_account_name = tokens.external_account_name
    if user_id is not None:
        existing.connected_by = user_id

    await db.flush()
    return existing


async def ensure_fresh(db: AsyncSession, connection: CrmConnection) -> CrmConnection:
    """Refresh the access token if it is close to expiry.

    Raises :class:`CrmAuthExpired` when the refresh itself is rejected, because
    that needs a human to reconnect and no amount of retrying will fix it.
    """
    expires = connection.token_expires_at
    if expires is None:
        return connection
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires > datetime.now(timezone.utc) + REFRESH_MARGIN:
        return connection
    if not connection.refresh_token:
        raise CrmAuthExpired(
            f"The {connection.provider} connection has expired and cannot be "
            "refreshed. Reconnect it in Settings."
        )

    provider = get_provider(connection.provider)
    tokens = await provider.refresh(connection.refresh_token)
    return await save_connection(
        db, connection.organization_id, connection.provider, tokens
    )


async def send_contact(
    db: AsyncSession, organization_id, contact: SocialContact, *, provider_slug=None
) -> ContactRef:
    """Push one social identity to the organization's CRM.

    Raises rather than returning a failure marker: the caller is an endpoint
    whose entire purpose is this write, and a silent partial success is worse
    than an error a user can read.
    """
    slug = (provider_slug or "hubspot").lower()
    connection = await connection_for(db, organization_id, slug)
    if connection is None or not connection.access_token:
        raise CrmNotConnected(
            f"No {slug} connection for this organization. Connect one in "
            "Settings before sending contacts."
        )

    connection = await ensure_fresh(db, connection)
    provider = get_provider(slug)
    return await provider.upsert_contact(connection, contact)


async def disconnect(db: AsyncSession, connection: CrmConnection) -> bool:
    """Revoke with the provider, then delete the row.

    The row goes whether or not the provider confirmed: a disconnect that left
    the credential behind because the vendor was unreachable is a disconnect
    that did not happen, and the user was told it did.
    """
    revoked = False
    try:
        provider = get_provider(connection.provider)
        revoked = await provider.revoke(connection)
    except Exception:  # noqa: BLE001 - the local delete is what matters
        logger.warning(
            "Could not revoke %s upstream; clearing locally anyway",
            connection.provider, exc_info=True,
        )
    await db.delete(connection)
    await db.flush()
    return revoked
