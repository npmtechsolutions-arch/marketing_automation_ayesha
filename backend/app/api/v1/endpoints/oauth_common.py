"""Shared pieces of the OAuth connect flow.

Reconnecting is the reason this module exists. A connection whose token has
expired has to be re-authorised, and the naive way -- run the normal connect
flow and create a fresh SocialAccount -- silently orphans everything that
pointed at the old row: every post's ``target_accounts`` entry, every
PublishingJob, every PostPerformance row keyed on that account. The workspace
ends up with two entries for one page, one of which has all the history and
none of the working credentials.

So a reconnect carries the id of the row to update, from the authorize call
through the state token to the callback, and the tokens land on the *same*
row.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import AccountHealth, SocialAccount

logger = logging.getLogger(__name__)


async def validate_reconnect_target(
    db: AsyncSession,
    *,
    reconnect_id: Optional[uuid.UUID],
    account_id: uuid.UUID,
    platform_id: uuid.UUID,
) -> Optional[SocialAccount]:
    """The account being reconnected, or None for a normal connect.

    Scoped to the workspace *and* the platform: without the platform check a
    caller could point a LinkedIn reconnect at their Instagram row and
    overwrite it with credentials for the wrong service.
    """
    if reconnect_id is None:
        return None

    target = (
        await db.execute(
            select(SocialAccount).where(
                SocialAccount.id == reconnect_id,
                SocialAccount.account_id == account_id,
                SocialAccount.platform_id == platform_id,
            )
        )
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "That connection was not found in this workspace for this "
                "platform."
            ),
        )
    return target


def reconnect_claim(target: Optional[SocialAccount]) -> dict:
    """The state-token claim carrying the reconnect through the redirect."""
    return {"reconnect": str(target.id)} if target is not None else {}


def reconnect_id_from_state(payload: dict) -> Optional[uuid.UUID]:
    raw = payload.get("reconnect")
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        logger.warning("Ignoring an unparseable reconnect claim: %r", raw)
        return None


async def apply_reconnect(
    db: AsyncSession,
    *,
    reconnect_id: uuid.UUID,
    account_id: uuid.UUID,
    platform_id: uuid.UUID,
    access_token: str,
    refresh_token: Optional[str] = None,
    token_expires_at: Optional[datetime] = None,
    display_name: Optional[str] = None,
    handle: Optional[str] = None,
    profile_url: Optional[str] = None,
    profile_image_url: Optional[str] = None,
    config: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> bool:
    """Write fresh credentials onto the existing row. True when it applied.

    Re-checks the workspace and platform: the state token is signed, but this
    is the last point before a credential write and the check is one query.

    The row's id, and therefore every foreign key pointing at it, is untouched
    -- which is the whole purpose. Health resets to CONNECTED because a
    successful re-authorisation is direct evidence the connection works, better
    than waiting up to an hour for the sweep to agree.
    """
    target = (
        await db.execute(
            select(SocialAccount).where(
                SocialAccount.id == reconnect_id,
                SocialAccount.account_id == account_id,
                SocialAccount.platform_id == platform_id,
            )
        )
    ).scalar_one_or_none()
    if target is None:
        logger.warning(
            "Reconnect target %s no longer exists; falling back to a normal "
            "connect.", reconnect_id,
        )
        return False

    target.access_token = access_token
    if refresh_token:
        # Absent means the platform did not rotate it (Meta), or did not return
        # one on re-consent (Google). Keeping the old one is correct in both.
        target.refresh_token = refresh_token
    target.token_expires_at = token_expires_at
    if display_name:
        target.account_name = display_name
    if handle:
        target.account_handle = handle
    if profile_url:
        target.profile_url = profile_url
    if profile_image_url:
        target.profile_image_url = profile_image_url
    if config:
        # Merged, not replaced: the existing config may hold keys this flow
        # does not produce.
        target.config = {**(target.config or {}), **config}
    if metadata:
        target.metadata_ = {**(target.metadata_ or {}), **metadata}

    now = datetime.now(timezone.utc)
    target.is_active = True
    target.is_verified = True
    target.last_verified_at = now
    target.health = AccountHealth.CONNECTED
    target.health_detail = None
    target.health_changed_at = now
    target.last_checked_at = now

    await db.flush()
    logger.info("Reconnected social account %s in place.", reconnect_id)
    return True
