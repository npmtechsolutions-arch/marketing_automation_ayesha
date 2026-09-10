"""Social listening: saved searches on X, and what they found.

Every payload here carries the **window** -- how far back the platform's search
can actually reach -- because "no mentions" and "no mentions in the last 7
days" are different claims and only the second is true. The UI renders what
this sends rather than a phrase of its own, so a tier change moves every
surface at once.

The other thing every payload carries is **health**. A query whose last poll
failed says so, with the platform's own reason. An empty stream is a real and
common answer, so a broken search that returns nothing is indistinguishable
from a quiet week unless the failure is on the row -- which is the same
dishonesty as a connector inventing metrics when its API call failed, arriving
from the other direction.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import verify_account_access as _verify_account_access
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.permissions import CONTENT_CREATE, CONTENT_VIEW
from app.models.account import Account
from app.models.listening import ListeningQuery, Mention
from app.services import entitlement_service as ent
from app.services import listening
from app.services.activity_service import log_activity

router = APIRouter()


class QueryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query_text: str = Field(..., min_length=2, max_length=512)


class QueryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: Optional[bool] = None
    query_text: Optional[str] = Field(None, min_length=2, max_length=512)


def _query_json(query: ListeningQuery, hours: int) -> dict:
    next_at = listening.next_poll_at(query, hours)
    return {
        "id": str(query.id),
        "platform": query.platform,
        "query_text": query.query_text,
        "is_active": query.is_active,
        "created_at": query.created_at.isoformat() if query.created_at else None,
        "last_polled_at": (
            query.last_polled_at.isoformat() if query.last_polled_at else None
        ),
        "last_success_at": (
            query.last_success_at.isoformat() if query.last_success_at else None
        ),
        "next_poll_at": next_at.isoformat() if next_at else None,
        # Health, stated rather than implied. `healthy` is false whenever the
        # last attempt failed, however many succeeded before it.
        "last_error": query.last_error,
        "last_error_at": (
            query.last_error_at.isoformat() if query.last_error_at else None
        ),
        "healthy": query.last_error is None,
        # What it has cost. Posts read is the billable unit on X, not requests.
        "requests_made": query.requests_made or 0,
        "posts_read": query.posts_read or 0,
        "estimated_cost_usd": listening.estimated_cost_usd(query.posts_read or 0),
    }


def _mention_json(mention: Mention) -> dict:
    return {
        "id": str(mention.id),
        "listening_query_id": str(mention.listening_query_id),
        "external_id": mention.external_id,
        "author_handle": mention.author_handle,
        "author_name": mention.author_name,
        "text": mention.text,
        "posted_at": mention.posted_at.isoformat() if mention.posted_at else None,
        "url": mention.url,
        "matched_at": mention.matched_at.isoformat() if mention.matched_at else None,
    }


async def _window(db: AsyncSession, account_id: uuid.UUID) -> dict:
    """The facts every listening payload repeats.

    Repeated deliberately. A client that fetches the stream and the query list
    separately must not be able to render one of them without the window.
    """
    connection = await listening.search_connection(db, account_id)
    return {
        "platform": listening.PLATFORM,
        "window_days": listening.window_days(),
        "window_label": listening.window_label(),
        "connected": connection is not None,
        # Why the feature is idle, in words the page can show as-is.
        "reason": None if connection is not None else (
            "Listening runs on X, and this workspace has no X account "
            "connected. Connect one to start watching a search."
        ),
        "cost_note": (
            f"Each poll reads up to {listening.MAX_RESULTS_PER_POLL} posts, and "
            f"X bills per post read ({listening.COST_SOURCE})."
        ),
    }


async def _get_query_or_404(
    db: AsyncSession, account_id: uuid.UUID, query_id: uuid.UUID
) -> ListeningQuery:
    query = (
        await db.execute(
            select(ListeningQuery).where(
                ListeningQuery.id == query_id,
                # Scoped by workspace in the same statement as the id: a
                # separate ownership check after the fetch is how cross-tenant
                # reads get introduced later.
                ListeningQuery.account_id == account_id,
            )
        )
    ).scalar_one_or_none()
    if query is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Listening query not found"
        )
    return query


@router.get("/status")
async def listening_status(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Whether listening can run here, and on what terms."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one()
    organization = await ent.get_organization_for_account(db, account_id)
    limit = await ent.get_limit(db, organization, ent.LISTENING_QUERIES)
    used = await ent.current_usage(db, organization, ent.LISTENING_QUERIES)
    return {
        **await _window(db, account_id),
        "interval_hours": listening.interval_hours(account),
        "interval_options": list(listening.ALLOWED_INTERVALS),
        "max_results_per_poll": listening.MAX_RESULTS_PER_POLL,
        "read_cost_usd": listening.READ_COST_USD,
        "queries_used": used,
        "queries_limit": limit,
    }


@router.get("/queries")
async def list_queries(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one()
    hours = listening.interval_hours(account)
    rows = (
        await db.execute(
            select(ListeningQuery)
            .where(ListeningQuery.account_id == account_id)
            .order_by(ListeningQuery.created_at.desc())
        )
    ).scalars().all()
    return {
        **await _window(db, account_id),
        "interval_hours": hours,
        "queries": [_query_json(row, hours) for row in rows],
    }


@router.post("/queries", status_code=status.HTTP_201_CREATED)
async def create_query(
    account_id: uuid.UUID,
    payload: QueryIn,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Save a search.

    Refused without a connection that can search, rather than accepted and left
    to fail quietly on the first poll: a query that can never run is worse than
    an error, because it looks like it is working.
    """
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )

    connection = await listening.search_connection(db, account_id)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Listening runs on X, and this workspace has no X account "
                "connected. Connect X first."
            ),
        )

    organization = await ent.get_organization_for_account(db, account_id)
    # Stateful, like connected accounts: a saved search is a thing that exists
    # rather than a spend, so deleting one gives the slot back. What costs
    # money is polling, and that is counted on the query itself.
    await ent.enforce_stateful_limit(db, organization, ent.LISTENING_QUERIES)

    text = payload.query_text.strip()
    existing = (
        await db.execute(
            select(ListeningQuery.id).where(
                ListeningQuery.account_id == account_id,
                ListeningQuery.platform == listening.PLATFORM,
                ListeningQuery.query_text == text,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This workspace is already watching that search.",
        )

    query = ListeningQuery(
        id=uuid.uuid4(),
        account_id=account_id,
        platform=listening.PLATFORM,
        query_text=text,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(query)
    await db.flush()
    await log_activity(
        db, user_id=current_user.id, account_id=account_id,
        action="listening.query.created", category="listening",
        description=f"Started watching “{text}” on X",
        resource_type="listening_query", resource_id=str(query.id),
        resource_name=text,
    )
    await db.commit()
    await db.refresh(query)

    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one()
    return {
        **await _window(db, account_id),
        **_query_json(query, listening.interval_hours(account)),
    }


@router.patch("/queries/{query_id}")
async def update_query(
    account_id: uuid.UUID,
    query_id: uuid.UUID,
    payload: QueryPatch,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )
    query = await _get_query_or_404(db, account_id, query_id)

    if payload.is_active is not None:
        query.is_active = payload.is_active
    if payload.query_text is not None:
        text = payload.query_text.strip()
        if text != query.query_text:
            query.query_text = text
            # A new search is a new window: the old cursor points into a
            # different result set, and keeping it would skip everything older
            # than the last match of the *previous* query.
            query.last_result_cursor = None
    await db.commit()
    await db.refresh(query)

    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one()
    return _query_json(query, listening.interval_hours(account))


@router.delete("/queries/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_query(
    account_id: uuid.UUID,
    query_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )
    query = await _get_query_or_404(db, account_id, query_id)
    await db.delete(query)
    await db.commit()


@router.post("/queries/{query_id}/poll")
async def poll_now(
    account_id: uuid.UUID,
    query_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Poll one query immediately.

    Its own endpoint, and its own button, because it spends money: a refresh
    that silently costs a few cents every time someone opens a page is how an
    API bill becomes a surprise.
    """
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )
    query = await _get_query_or_404(db, account_id, query_id)

    connection = await listening.search_connection(db, account_id)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No X account is connected to this workspace, so this search "
                "cannot run."
            ),
        )

    # The sweep is held back by the workspace's interval; this button is held
    # back by nothing, and every press spends money. A leaning finger should
    # not be able to run up a bill.
    wait = listening.manual_poll_allowed_in(query)
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"This search ran less than a minute ago. Each poll costs X API "
                f"credit, so give it {wait}s."
            ),
        )

    report = await listening.poll_query(db, query, connection)
    await db.commit()
    await db.refresh(query)

    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one()
    return {
        **await _window(db, account_id),
        "new_mentions": report["new"],
        "posts_read": report["posts_read"],
        "estimated_cost_usd": listening.estimated_cost_usd(report["posts_read"]),
        "error": report["error"],
        "query": _query_json(query, listening.interval_hours(account)),
    }


@router.get("/mentions")
async def list_mentions(
    account_id: uuid.UUID,
    query_id: Optional[uuid.UUID] = Query(None),
    since: Optional[datetime] = Query(None, description="Only posts on or after this"),
    until: Optional[datetime] = Query(None, description="Only posts before this"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """The stream, newest first by when the author posted."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)

    owned = select(ListeningQuery.id).where(ListeningQuery.account_id == account_id)
    if query_id is not None:
        # Still scoped to the workspace: a query id from another tenant
        # narrows to nothing rather than reading across.
        owned = owned.where(ListeningQuery.id == query_id)

    stmt = select(Mention).where(Mention.listening_query_id.in_(owned))
    if since is not None:
        stmt = stmt.where(Mention.posted_at >= since)
    if until is not None:
        stmt = stmt.where(Mention.posted_at < until)

    total = (
        await db.execute(
            select(func.count()).select_from(stmt.subquery())
        )
    ).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(Mention.posted_at.desc().nulls_last())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()

    return {
        **await _window(db, account_id),
        "total": total,
        "limit": limit,
        "offset": offset,
        # The empty state's words, produced here so no component can render a
        # friendlier and less true version of them.
        "empty_label": (
            f"No mentions in {listening.window_label()}."
            if total == 0 else None
        ),
        "mentions": [_mention_json(row) for row in rows],
    }
