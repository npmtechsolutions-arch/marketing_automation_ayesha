"""The unified inbox."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.authz import verify_account_access as _verify_account_access
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.permissions import CONTENT_CREATE, CONTENT_VIEW
from app.models.inbox import (
    InboxMessage,
    InboxThread,
    ThreadStatus,
    ThreadType,
)
from app.models.platform import SocialAccount, SocialPlatform
from app.models.team_member import TeamMember
from app.services import inbox_actions, inbox_sync
from app.services.activity_service import log_activity

router = APIRouter()


class ReplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(..., min_length=1, max_length=5000)


class NoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(..., min_length=1, max_length=5000)


class AssignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Null unassigns. Explicit rather than a separate endpoint: "nobody" is a
    # legitimate assignee.
    assigned_to: Optional[uuid.UUID] = None


class TagsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tags: list[str] = Field(default_factory=list, max_length=50)


class StatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: ThreadStatus


def _thread_json(thread: InboxThread, platform: Optional[str] = None) -> dict:
    return {
        "id": str(thread.id),
        "type": thread.type.value,
        "platform": platform,
        "social_account_id": str(thread.social_account_id),
        "participant": thread.participant,
        "participant_handle": thread.participant_handle,
        "permalink": thread.permalink,
        "status": thread.status.value,
        "assigned_to": str(thread.assigned_to) if thread.assigned_to else None,
        "tags": thread.tags or [],
        "unread_count": thread.unread_count,
        "last_message_at": (
            thread.last_message_at.isoformat() if thread.last_message_at else None
        ),
        "last_message_preview": thread.last_message_preview,
    }


def _message_json(message: InboxMessage) -> dict:
    return {
        "id": str(message.id),
        "direction": message.direction.value,
        "author": message.author,
        "author_handle": message.author_handle,
        "author_user_id": (
            str(message.author_user_id) if message.author_user_id else None
        ),
        "body": message.body,
        "media": message.media or [],
        "created_at": message.created_at.isoformat(),
    }


async def _get_thread(
    db: AsyncSession, account_id: uuid.UUID, thread_id: uuid.UUID
) -> InboxThread:
    thread = (
        await db.execute(
            select(InboxThread).where(
                InboxThread.id == thread_id, InboxThread.account_id == account_id
            )
        )
    ).scalar_one_or_none()
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.get("/")
async def list_threads(
    account_id: uuid.UUID,
    platform: Optional[str] = Query(None),
    thread_status: Optional[ThreadStatus] = Query(None, alias="status"),
    type: Optional[ThreadType] = Query(None),
    assigned_to: Optional[uuid.UUID] = Query(None),
    unassigned: bool = Query(False),
    tag: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Threads, newest activity first."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)

    query = (
        select(InboxThread, SocialPlatform.slug)
        .join(SocialAccount, SocialAccount.id == InboxThread.social_account_id)
        .join(SocialPlatform, SocialPlatform.id == SocialAccount.platform_id)
        .where(InboxThread.account_id == account_id)
    )
    if platform:
        query = query.where(SocialPlatform.slug == platform.lower())
    if thread_status:
        query = query.where(InboxThread.status == thread_status)
    if type:
        query = query.where(InboxThread.type == type)
    if unassigned:
        query = query.where(InboxThread.assigned_to.is_(None))
    elif assigned_to:
        query = query.where(InboxThread.assigned_to == assigned_to)

    rows = (
        await db.execute(
            query.order_by(InboxThread.last_message_at.desc().nulls_last()).limit(limit)
        )
    ).all()

    threads = [_thread_json(row[0], row[1]) for row in rows]
    if tag:
        # Filtered in Python: the column is JSON, and a containment operator
        # differs between Postgres and the SQLite test harness. The list is
        # already bounded by `limit`.
        wanted = tag.strip().lower()
        threads = [t for t in threads if wanted in (t["tags"] or [])]

    return {
        "threads": threads,
        "counts": await _counts(db, account_id),
    }


async def _counts(db: AsyncSession, account_id: uuid.UUID) -> dict:
    rows = (
        await db.execute(
            select(InboxThread.status, func.count())
            .where(InboxThread.account_id == account_id)
            .group_by(InboxThread.status)
        )
    ).all()
    counts = {s.value: 0 for s in ThreadStatus}
    for row in rows:
        key = row[0].value if hasattr(row[0], "value") else str(row[0])
        counts[key] = int(row[1])
    return counts


@router.get("/capabilities")
async def inbox_capabilities(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """What each connected platform can actually give us.

    Served so the UI can say "X does not support direct messages" instead of
    showing an empty list that looks like a quiet inbox.
    """
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    rows = (
        await db.execute(
            select(SocialPlatform.slug, SocialAccount.account_name, SocialAccount.id)
            .join(SocialAccount, SocialAccount.platform_id == SocialPlatform.id)
            .where(
                SocialAccount.account_id == account_id,
                SocialAccount.is_active.is_(True),
            )
        )
    ).all()
    return {
        "connections": [
            {
                "social_account_id": str(row.id),
                "platform": row.slug,
                "account_name": row.account_name,
                "supports": inbox_sync.supported_sources(row.slug),
            }
            for row in rows
        ]
    }


@router.get("/{thread_id}")
async def get_thread(
    account_id: uuid.UUID,
    thread_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """One thread with its messages. Opening it marks it read."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    thread = (
        await db.execute(
            select(InboxThread)
            .options(selectinload(InboxThread.messages))
            .where(InboxThread.id == thread_id, InboxThread.account_id == account_id)
        )
    ).scalar_one_or_none()
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    thread.unread_count = 0
    await db.flush()
    return {
        **_thread_json(thread),
        "messages": [_message_json(m) for m in thread.messages],
    }


@router.post("/{thread_id}/reply")
async def reply_to_thread(
    account_id: uuid.UUID,
    thread_id: uuid.UUID,
    body: ReplyIn,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Send a reply through the platform.

    Replying is a publishing action, not a viewing one, so it needs write
    permission: a viewer who can read the inbox must not be able to speak to
    the workspace's customers in its name.
    """
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_CREATE)
    thread = await _get_thread(db, account_id, thread_id)

    connection = (
        await db.execute(
            select(SocialAccount)
            .options(selectinload(SocialAccount.platform))
            .where(SocialAccount.id == thread.social_account_id)
        )
    ).scalar_one_or_none()
    if connection is None:
        raise HTTPException(
            status_code=409, detail="That connection has been removed."
        )

    try:
        message = await inbox_actions.reply(
            db, thread, connection, body=body.body, user_id=current_user.id
        )
    except inbox_actions.ReplyNotSupported as exc:
        # 422, not 500: the request is well-formed and the platform simply
        # cannot do this. The UI disables the box on the same information.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except inbox_actions.ReplyFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    await log_activity(
        db, user_id=current_user.id, account_id=account_id,
        action="inbox.replied", category="inbox",
        description=f"Replied to {thread.participant}",
        resource_type="inbox_thread", resource_id=str(thread_id),
    )
    return _message_json(message)


@router.post("/{thread_id}/note")
async def add_note(
    account_id: uuid.UUID,
    thread_id: uuid.UUID,
    body: NoteIn,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """An internal note. Never leaves the workspace."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    thread = await _get_thread(db, account_id, thread_id)
    message = await inbox_actions.add_note(
        db, thread, body=body.body, user_id=current_user.id
    )
    return _message_json(message)


@router.put("/{thread_id}/assign")
async def assign_thread(
    account_id: uuid.UUID,
    thread_id: uuid.UUID,
    body: AssignIn,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    thread = await _get_thread(db, account_id, thread_id)

    if body.assigned_to is not None:
        member = (
            await db.execute(
                select(TeamMember.id).where(
                    TeamMember.account_id == account_id,
                    TeamMember.user_id == body.assigned_to,
                )
            )
        ).scalar_one_or_none()
        # Assigning to someone outside the workspace would put a thread in a
        # queue nobody can see.
        if member is None:
            raise HTTPException(
                status_code=400,
                detail="That person is not a member of this workspace.",
            )

    thread.assigned_to = body.assigned_to
    await db.flush()
    return _thread_json(thread)


@router.put("/{thread_id}/tags")
async def set_tags(
    account_id: uuid.UUID,
    thread_id: uuid.UUID,
    body: TagsIn,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    thread = await _get_thread(db, account_id, thread_id)
    thread.tags = inbox_actions.normalise_tags(body.tags)
    await db.flush()
    return _thread_json(thread)


@router.put("/{thread_id}/status")
async def set_status(
    account_id: uuid.UUID,
    thread_id: uuid.UUID,
    body: StatusIn,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    thread = await _get_thread(db, account_id, thread_id)
    await inbox_actions.set_status(db, thread, body.status)
    await log_activity(
        db, user_id=current_user.id, account_id=account_id,
        action=f"inbox.{body.status.value}", category="inbox",
        description=f"Marked a thread {body.status.value}",
        resource_type="inbox_thread", resource_id=str(thread_id),
    )
    return _thread_json(thread)


@router.post("/sync")
async def sync_now(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Poll this workspace's connections immediately."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    connections = (
        await db.execute(
            select(SocialAccount)
            .options(selectinload(SocialAccount.platform))
            .where(
                SocialAccount.account_id == account_id,
                SocialAccount.is_active.is_(True),
            )
        )
    ).scalars().all()

    totals = {"new_messages": 0, "unsupported": [], "errors": []}
    for connection in connections:
        report = await inbox_sync.sync_connection(db, connection)
        totals["new_messages"] += report["new_messages"]
        totals["unsupported"].extend(
            f"{connection.platform.slug if connection.platform else '?'}:{kind}"
            for kind in report["unsupported"]
        )
        totals["errors"].extend(report["errors"])
    return totals


@router.post("/{thread_id}/send-to-crm")
async def send_thread_to_crm(
    account_id: uuid.UUID,
    thread_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Create or update a CRM contact for the person in this conversation.

    ``content.create`` rather than ``content.view``: this acts on a customer
    relationship in a system outside this product. Reading a thread and filing
    the person into the company's CRM are different kinds of act, and a viewer
    should be able to do the first without the second.

    **Idempotent.** The provider searches on ``platform:handle`` before writing,
    so pressing this twice updates one contact rather than making two. HubSpot's
    own dedupe is on email, which a social inbox does not have -- see
    ``app.integrations.hubspot``.

    **The thread is not modified.** A CRM failure surfaces here, on the action
    that caused it, and leaves the conversation exactly as it was; there is no
    half-written state to recover from.
    """
    from app.integrations.base import (
        CrmAPIError,
        CrmAuthExpired,
        CrmNotConnected,
        SocialContact,
    )
    from app.services import crm
    from app.services.entitlements import get_organization_for_account

    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )

    thread = (
        await db.execute(
            select(InboxThread).where(
                InboxThread.id == thread_id, InboxThread.account_id == account_id
            )
        )
    ).scalar_one_or_none()
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    handle = (thread.participant_handle or "").strip()
    if not handle:
        # Without a handle there is no identity to key on, so a send would
        # create a fresh duplicate every time. Refusing is the honest answer.
        raise HTTPException(
            status_code=409,
            detail=(
                "This conversation has no social handle, so it cannot be "
                "matched to a contact without creating duplicates."
            ),
        )

    platform_slug = (
        await db.execute(
            select(SocialPlatform.slug)
            .join(SocialAccount, SocialAccount.platform_id == SocialPlatform.id)
            .where(SocialAccount.id == thread.social_account_id)
        )
    ).scalar_one_or_none() or "social"

    organization = await get_organization_for_account(db, account_id)
    contact = SocialContact(
        handle=handle,
        platform=platform_slug,
        display_name=thread.participant or None,
        conversation_url=thread.permalink,
    )

    try:
        result = await crm.send_contact(db, organization.id, contact)
    except CrmNotConnected as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CrmAuthExpired as exc:
        # Reconnect, not retry. Saying "try again" about a dead credential is
        # how an integration stays broken for a month.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CrmAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    await log_activity(
        db, user_id=current_user.id, account_id=account_id,
        action="crm.contact_sent", category="integration",
        description=f"Sent {handle} to the CRM",
        resource_type="inbox_thread", resource_id=str(thread.id),
    )
    return {
        "contact_id": result.provider_id,
        # So the UI can say "created" or "updated" rather than a bare success
        # that leaves a user wondering whether they made a duplicate.
        "created": result.created,
        "url": result.url,
    }
