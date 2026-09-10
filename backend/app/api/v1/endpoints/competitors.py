"""Competitor tracking: follower and post counts for accounts a workspace names.

Every payload here carries three things the UI is not allowed to invent:

* **what is and is not tracked** (`capability_notice`), so the add dialog states
  the absences in the same breath as the offer rather than leaving someone to
  discover that there is no engagement data;
* **how stale each number is**, because Instagram caps Business Discovery at
  roughly one lookup per account per week and "12,400 followers" is a different
  claim from "12,400 followers as of 6 days ago";
* **whether a trend can honestly be drawn**, which needs two snapshots. One
  point is a fact, not a line.

Adding a competitor spends a real lookup to validate the handle. That is
deliberate: a typo tracked silently produces a row that stays empty forever and
reads as an account with no followers.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import AccountNotFound, MissingCredential, ProviderAPIError
from app.core.authz import verify_account_access as _verify_account_access
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.permissions import ANALYTICS_VIEW, CONTENT_CREATE
from app.models.account import Account
from app.models.competitor import CompetitorAccount, CompetitorSnapshot
from app.services import competitors
from app.services import entitlement_service as ent
from app.services.activity_service import log_activity

router = APIRouter()


class CompetitorIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    handle: str = Field(..., min_length=1, max_length=120)


class CompetitorPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: Optional[bool] = None


def _snapshot_json(snapshot: CompetitorSnapshot) -> dict:
    return {
        "date": snapshot.date.isoformat(),
        # Null, never zero. The chart renders a gap and the tooltip an em dash.
        "followers": snapshot.followers,
        "media_count": snapshot.media_count,
    }


def _competitor_json(
    competitor: CompetitorAccount,
    *,
    snapshots: Optional[list[CompetitorSnapshot]] = None,
    snapshot_count: Optional[int] = None,
) -> dict:
    latest = snapshots[-1] if snapshots else None
    count = snapshot_count if snapshot_count is not None else len(snapshots or [])
    next_at = competitors.next_sync_at(competitor)
    return {
        "id": str(competitor.id),
        "platform": competitor.platform,
        "handle": competitor.handle,
        "display_name": competitor.display_name,
        "profile_url": f"https://www.instagram.com/{competitor.handle}/",
        "is_active": competitor.is_active,
        "added_at": competitor.created_at.isoformat() if competitor.created_at else None,
        "last_synced_at": (
            competitor.last_synced_at.isoformat()
            if competitor.last_synced_at else None
        ),
        "next_sync_at": next_at.isoformat() if next_at else None,
        # The words the card shows. Produced here so a component cannot render
        # a number without saying how old it is.
        "staleness_label": competitors.staleness_label(competitor.last_synced_at),
        "last_error": competitor.last_error,
        "healthy": competitor.last_error is None,
        "followers": latest.followers if latest else None,
        "media_count": latest.media_count if latest else None,
        "snapshot_count": count,
        # A trend needs two points; below that the UI says so rather than
        # drawing a line through one.
        "trend_ready": count >= competitors.MIN_SNAPSHOTS_FOR_TREND,
        "trend_pending_label": (
            None if count >= competitors.MIN_SNAPSHOTS_FOR_TREND
            else (
                "First snapshot recorded — a trend appears after next week's "
                "check." if count == 1
                else "No snapshot yet — the first check runs within a week."
            )
        ),
        "snapshots": [_snapshot_json(row) for row in (snapshots or [])],
    }


async def _context(db: AsyncSession, account_id: uuid.UUID) -> dict:
    """The facts every competitor payload repeats."""
    connection = await competitors.discovery_connection(db, account_id)
    return {
        "platform": competitors.PLATFORM,
        "connected": connection is not None,
        # Why the feature is idle, in words the page shows as-is.
        "reason": None if connection is not None else competitors.REQUIREMENT,
        **competitors.capability_notice(),
    }


async def _get_or_404(
    db: AsyncSession, account_id: uuid.UUID, competitor_id: uuid.UUID
) -> CompetitorAccount:
    competitor = (
        await db.execute(
            select(CompetitorAccount).where(
                CompetitorAccount.id == competitor_id,
                # Workspace scope in the same statement as the id.
                CompetitorAccount.account_id == account_id,
            )
        )
    ).scalar_one_or_none()
    if competitor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found"
        )
    return competitor


@router.get("/status")
async def competitor_status(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Whether tracking can run here, and exactly what it covers."""
    await _verify_account_access(account_id, current_user, db, permission=ANALYTICS_VIEW)
    organization = await ent.get_organization_for_account(db, account_id)
    return {
        **await _context(db, account_id),
        "used": await ent.current_usage(db, organization, ent.COMPETITOR_ACCOUNTS),
        "limit": await ent.get_limit(db, organization, ent.COMPETITOR_ACCOUNTS),
        "sync_interval_days": competitors.SYNC_INTERVAL_DAYS,
    }


@router.get("/")
async def list_competitors(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(account_id, current_user, db, permission=ANALYTICS_VIEW)
    rows = (
        await db.execute(
            select(CompetitorAccount)
            .where(CompetitorAccount.account_id == account_id)
            .order_by(CompetitorAccount.created_at.asc())
        )
    ).scalars().all()

    out = []
    for competitor in rows:
        snapshots = await competitors.history(db, competitor.id)
        out.append(_competitor_json(competitor, snapshots=snapshots))
    return {**await _context(db, account_id), "competitors": out}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_competitor(
    account_id: uuid.UUID,
    payload: CompetitorIn,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Add a competitor, validating the handle with one real lookup.

    The lookup is the point. A handle nobody can see -- a typo, a personal
    account, a private one -- is refused here, while the person who typed it is
    still looking at it. Accepting it would produce a tracked row that stays
    empty forever and reads as a competitor with no followers.
    """
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )

    connection = await competitors.discovery_connection(db, account_id)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=competitors.REQUIREMENT,
        )

    handle = competitors.normalise_handle(payload.handle)
    if not handle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter an Instagram handle, for example @nike.",
        )

    existing = (
        await db.execute(
            select(CompetitorAccount.id).where(
                CompetitorAccount.account_id == account_id,
                CompetitorAccount.platform == competitors.PLATFORM,
                CompetitorAccount.handle == handle,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"@{handle} is already being tracked.",
        )

    organization = await ent.get_organization_for_account(db, account_id)
    await ent.enforce_stateful_limit(db, organization, ent.COMPETITOR_ACCOUNTS)

    try:
        data = await competitors.lookup(connection, handle)
    except AccountNotFound as exc:
        # 404 rather than 400: the request was well-formed, the account is the
        # thing that does not exist. The message is the platform's own.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.detail
        ) from exc
    except MissingCredential as exc:
        # 400, not 502: the platform is fine, our stored credential is not.
        # The distinction is the one MissingCredential exists for, and calling
        # it a bad gateway would send someone looking at Meta's status page.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail
        ) from exc
    except ProviderAPIError as exc:
        # Instagram could not answer. Refused rather than added unverified --
        # adding it would mean the first thing the user sees is a row we cannot
        # say anything about.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"Instagram could not be reached to check @{handle}: "
                f"{exc.detail}"
            ),
        ) from exc

    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one()

    competitor = CompetitorAccount(
        id=uuid.uuid4(),
        account_id=account_id,
        platform=competitors.PLATFORM,
        handle=data.get("handle") or handle,
        display_name=data.get("display_name"),
        is_active=True,
        added_by=current_user.id,
    )
    db.add(competitor)
    await db.flush()

    # The validating lookup is also the first snapshot: it has already been
    # spent against Meta's weekly cap, and throwing the numbers away would mean
    # asking again tomorrow for what is already in hand.
    await competitors.upsert_snapshot(
        db, competitor.id, competitors.local_today(account), data
    )
    competitor.last_synced_at = datetime.now(timezone.utc)

    await log_activity(
        db, user_id=current_user.id, account_id=account_id,
        action="competitor.added", category="analytics",
        description=f"Started tracking @{competitor.handle} on Instagram",
        resource_type="competitor_account", resource_id=str(competitor.id),
        resource_name=competitor.handle,
    )
    await db.commit()
    await db.refresh(competitor)

    snapshots = await competitors.history(db, competitor.id)
    return {
        **await _context(db, account_id),
        **_competitor_json(competitor, snapshots=snapshots),
    }


@router.patch("/{competitor_id}")
async def update_competitor(
    account_id: uuid.UUID,
    competitor_id: uuid.UUID,
    payload: CompetitorPatch,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )
    competitor = await _get_or_404(db, account_id, competitor_id)
    if payload.is_active is not None:
        competitor.is_active = payload.is_active
    await db.commit()
    await db.refresh(competitor)
    snapshots = await competitors.history(db, competitor.id)
    return _competitor_json(competitor, snapshots=snapshots)


@router.delete("/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competitor(
    account_id: uuid.UUID,
    competitor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )
    competitor = await _get_or_404(db, account_id, competitor_id)
    await db.delete(competitor)
    await db.commit()


@router.get("/{competitor_id}/history")
async def competitor_history(
    account_id: uuid.UUID,
    competitor_id: uuid.UUID,
    limit: int = Query(90, ge=2, le=365),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(account_id, current_user, db, permission=ANALYTICS_VIEW)
    competitor = await _get_or_404(db, account_id, competitor_id)
    snapshots = await competitors.history(db, competitor.id, limit=limit)
    total = (
        await db.execute(
            select(func.count(CompetitorSnapshot.id)).where(
                CompetitorSnapshot.competitor_id == competitor.id
            )
        )
    ).scalar_one()
    return _competitor_json(competitor, snapshots=snapshots, snapshot_count=total)


@router.post("/{competitor_id}/refresh")
async def refresh_competitor(
    account_id: uuid.UUID,
    competitor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Check one competitor now, if the weekly cap allows it.

    Refused rather than attempted when it does not: Meta counts attempts, not
    successes, so a button that ignored the cap would spend the workspace's
    allowance and get every competitor throttled.
    """
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )
    competitor = await _get_or_404(db, account_id, competitor_id)

    connection = await competitors.discovery_connection(db, account_id)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=competitors.REQUIREMENT,
        )

    if not competitors.is_due(competitor):
        next_at = competitors.next_sync_at(competitor)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Instagram allows about one lookup per account per week, and "
                f"@{competitor.handle} was checked "
                f"{competitors.staleness_label(competitor.last_synced_at)}. "
                f"The next check is due "
                f"{next_at.date().isoformat() if next_at else 'soon'}."
            ),
        )

    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one()
    report = await competitors.sync_competitor(db, competitor, connection, account)
    await db.commit()
    await db.refresh(competitor)

    snapshots = await competitors.history(db, competitor.id)
    return {
        "stored": report["stored"],
        "error": report["error"],
        "competitor": _competitor_json(competitor, snapshots=snapshots),
    }
