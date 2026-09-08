"""Recurring schedules and the weekly posting queue.

Both live behind the workspace's content permissions, except slot configuration
which is a settings change: deciding when a workspace posts is closer to
"change the workspace" than to "write a post".
"""

import uuid
from datetime import datetime, time, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import verify_account_access as _verify_account_access
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.permissions import CONTENT_CREATE, CONTENT_VIEW, SETTINGS_MANAGE
from app.models.account import Account
from app.models.post import Post, PostStatus
from app.models.recurring_schedule import (
    QueueSlot,
    RecurrenceStatus,
    RecurringSchedule,
)
from app.services import queue_slots, recurrence, recurring
from app.services.activity_service import log_activity

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SlotIn(BaseModel):
    # 0 = Monday .. 6 = Sunday, matching date.weekday().
    weekday: int = Field(..., ge=0, le=6)
    time_local: time
    is_active: bool = True


class SlotsUpdate(BaseModel):
    """The full weekly set, replacing whatever is there.

    A whole-set PUT rather than per-slot CRUD: the UI edits a week as one
    thing, and incremental edits would let a half-applied change leave a
    workspace posting at times nobody chose.
    """

    slots: list[SlotIn] = Field(default_factory=list, max_length=100)


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    weekday: int
    time_local: time
    is_active: bool


class RecurringIn(BaseModel):
    template_post_id: uuid.UUID
    rrule: str = Field(..., min_length=3, max_length=1000)
    starts_at_local: datetime
    name: Optional[str] = Field(None, max_length=200)
    timezone: Optional[str] = Field(None, max_length=64)
    until_local: Optional[datetime] = None
    max_occurrences: Optional[int] = Field(None, ge=1, le=1000)

    @field_validator("starts_at_local", "until_local")
    @classmethod
    def _must_be_naive(cls, value: Optional[datetime]) -> Optional[datetime]:
        """Local wall-clock readings, not instants.

        Accepting an offset here would be accepting an answer to a question
        the caller cannot have: which offset applies depends on the date, and
        the whole point is that it changes twice a year.
        """
        if value is not None and value.tzinfo is not None:
            raise ValueError(
                "send a local wall-clock time without an offset, e.g. "
                "2026-03-02T10:00:00 -- the workspace timezone supplies the rest"
            )
        return value


class RecurringUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    rrule: Optional[str] = Field(None, min_length=3, max_length=1000)
    until_local: Optional[datetime] = None
    max_occurrences: Optional[int] = Field(None, ge=1, le=1000)
    status: Optional[RecurrenceStatus] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _account(account_id: uuid.UUID, db: AsyncSession) -> Account:
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return account


def _serialise(schedule: RecurringSchedule) -> dict:
    return {
        "id": str(schedule.id),
        "name": schedule.name,
        "template_post_id": str(schedule.template_post_id),
        "rrule": schedule.rrule,
        "summary": recurrence.describe(schedule.rrule),
        "timezone": schedule.timezone,
        "starts_at_local": schedule.starts_at_local.isoformat(),
        "until_local": (
            schedule.until_local.isoformat() if schedule.until_local else None
        ),
        "max_occurrences": schedule.max_occurrences,
        "occurrence_count": schedule.occurrence_count,
        "status": schedule.status.value,
        "next_run_at": (
            schedule.next_run_at.isoformat() if schedule.next_run_at else None
        ),
        "last_run_at": (
            schedule.last_run_at.isoformat() if schedule.last_run_at else None
        ),
        "last_error": schedule.last_error,
    }


# ---------------------------------------------------------------------------
# Queue slots
# ---------------------------------------------------------------------------

@router.get("/queue/slots", response_model=list[SlotOut])
async def list_slots(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """The workspace's weekly posting slots."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    rows = (
        await db.execute(
            select(QueueSlot)
            .where(QueueSlot.account_id == account_id)
            .order_by(QueueSlot.weekday, QueueSlot.time_local)
        )
    ).scalars().all()
    return [SlotOut.model_validate(row) for row in rows]


@router.put("/queue/slots", response_model=list[SlotOut])
async def replace_slots(
    account_id: uuid.UUID,
    body: SlotsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Replace the weekly slot configuration."""
    await _verify_account_access(
        account_id, current_user, db, permission=SETTINGS_MANAGE
    )

    seen: set[tuple[int, time]] = set()
    for slot in body.slots:
        key = (slot.weekday, slot.time_local)
        if key in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Duplicate slot for weekday {slot.weekday} at "
                    f"{slot.time_local}. Two identical slots would double-book."
                ),
            )
        seen.add(key)

    existing = (
        await db.execute(select(QueueSlot).where(QueueSlot.account_id == account_id))
    ).scalars().all()
    for row in existing:
        await db.delete(row)
    await db.flush()

    created = []
    for slot in body.slots:
        row = QueueSlot(
            id=uuid.uuid4(),
            account_id=account_id,
            weekday=slot.weekday,
            time_local=slot.time_local,
            is_active=slot.is_active,
        )
        db.add(row)
        created.append(row)
    await db.flush()

    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="queue.slots_updated",
        category="settings",
        description=f"Set {len(created)} posting slot(s) for the week",
        resource_type="queue_slots",
        resource_id=str(account_id),
        resource_name=f"{len(created)} slots",
    )
    return [SlotOut.model_validate(row) for row in created]


@router.get("/queue/upcoming")
async def upcoming(
    account_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """The next slots, each marked free or taken."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    account = await _account(account_id, db)
    return {
        "timezone": account.settings.get("timezone", "UTC") if account.settings else "UTC",
        "slots": await queue_slots.upcoming_slots(db, account, limit=limit),
        **await queue_slots.queue_depth(db, account),
    }


@router.post("/queue/add/{post_id}")
async def add_to_queue(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Place a post in the next free slot."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_CREATE)
    account = await _account(account_id, db)

    post = (
        await db.execute(
            select(Post).where(
                Post.id == post_id,
                Post.account_id == account_id,
                Post.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    try:
        run_at = await queue_slots.next_free_slot(db, account)
    except queue_slots.NoSlotsConfigured as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except queue_slots.QueueFull as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    from app.services import publishing

    post.scheduled_at = run_at
    post.status = PostStatus.SCHEDULED
    await publishing.create_jobs_for_post(db, post, run_at=run_at)
    await db.flush()

    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="post.queued",
        category="post",
        description=f"Queued for {run_at.isoformat()}",
        resource_type="post",
        resource_id=str(post_id),
    )
    return {"post_id": str(post_id), "scheduled_at": run_at.isoformat()}


# ---------------------------------------------------------------------------
# Recurring schedules
# ---------------------------------------------------------------------------

@router.post("/recurring", status_code=status.HTTP_201_CREATED)
async def create_recurring(
    account_id: uuid.UUID,
    body: RecurringIn,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Repeat a template post on a rule."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_CREATE)
    account = await _account(account_id, db)

    template = (
        await db.execute(
            select(Post).where(
                Post.id == body.template_post_id,
                Post.account_id == account_id,
                Post.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template post not found")
    if not template.target_accounts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The template has no target accounts, so every occurrence would "
                "publish nowhere. Pick at least one before scheduling it."
            ),
        )

    zone_name = body.timezone or (
        (account.settings or {}).get("timezone") or "UTC"
    )
    try:
        recurrence.parse(body.rrule, dtstart_local=body.starts_at_local)
    except recurrence.InvalidRecurrence as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    schedule = RecurringSchedule(
        id=uuid.uuid4(),
        account_id=account_id,
        created_by=current_user.id,
        template_post_id=template.id,
        name=body.name,
        rrule=body.rrule.strip(),
        timezone=zone_name,
        starts_at_local=body.starts_at_local,
        until_local=body.until_local,
        max_occurrences=body.max_occurrences,
        status=RecurrenceStatus.ACTIVE,
    )
    await recurring.initialise(schedule)
    if schedule.next_run_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "That rule produces no occurrences in the future. Check the "
                "start date and the end condition."
            ),
        )

    db.add(schedule)
    await db.flush()

    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="recurring.created",
        category="post",
        description=f"Recurring schedule: {recurrence.describe(schedule.rrule)}",
        resource_type="recurring_schedule",
        resource_id=str(schedule.id),
        resource_name=schedule.name or recurrence.describe(schedule.rrule),
    )
    return _serialise(schedule)


@router.get("/recurring")
async def list_recurring(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    rows = (
        await db.execute(
            select(RecurringSchedule)
            .where(RecurringSchedule.account_id == account_id)
            .order_by(RecurringSchedule.next_run_at.asc().nulls_last())
        )
    ).scalars().all()
    return {"schedules": [_serialise(row) for row in rows]}


@router.post("/recurring/preview")
async def preview_recurring(
    account_id: uuid.UUID,
    body: RecurringIn,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """The dates a rule would produce, before committing to it.

    An RRULE is not readable. The only honest way to show someone what
    ``FREQ=MONTHLY;BYDAY=-1FR`` means is to list the dates, in their own
    timezone, including the one where the clocks change.
    """
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    account = await _account(account_id, db)
    zone_name = body.timezone or (account.settings or {}).get("timezone") or "UTC"

    try:
        instants = recurrence.occurrences(
            body.rrule,
            timezone_name=zone_name,
            dtstart_local=body.starts_at_local,
            until_local=body.until_local,
            limit=limit,
        )
    except recurrence.InvalidRecurrence as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    tz = recurrence.zone(zone_name)
    return {
        "timezone": zone_name,
        "summary": recurrence.describe(body.rrule),
        "occurrences": [
            {
                "run_at": instant.isoformat(),
                "local": recurrence.to_local(instant, tz).isoformat(),
                # The offset is what makes a DST shift visible in the preview:
                # two rows an hour apart in UTC and identical in local time is
                # correct, and looks like a bug until you can see why.
                "utc_offset": instant.astimezone(tz).strftime("%z"),
            }
            for instant in instants
        ],
    }


@router.patch("/recurring/{schedule_id}")
async def update_recurring(
    account_id: uuid.UUID,
    schedule_id: uuid.UUID,
    body: RecurringUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Change or pause a schedule."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_CREATE)

    schedule = (
        await db.execute(
            select(RecurringSchedule).where(
                RecurringSchedule.id == schedule_id,
                RecurringSchedule.account_id == account_id,
            )
        )
    ).scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "rrule" in updates:
        try:
            recurrence.parse(updates["rrule"], dtstart_local=schedule.starts_at_local)
        except recurrence.InvalidRecurrence as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    for field, value in updates.items():
        setattr(schedule, field, value)

    # Any change to the rule or the end conditions invalidates next_run_at, and
    # resuming a paused schedule needs one recomputed from now rather than the
    # stale instant it held while paused.
    if {"rrule", "until_local", "max_occurrences", "status"} & set(updates):
        if schedule.status is RecurrenceStatus.ACTIVE:
            schedule.next_run_at = recurring.compute_next_run(
                schedule, after=datetime.now(timezone.utc)
            )
            if schedule.next_run_at is None:
                schedule.status = RecurrenceStatus.COMPLETED
        else:
            schedule.next_run_at = None

    await db.flush()
    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="recurring.updated",
        category="post",
        description=f"Updated recurring schedule ({', '.join(sorted(updates))})",
        resource_type="recurring_schedule",
        resource_id=str(schedule_id),
    )
    return _serialise(schedule)


@router.delete("/recurring/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_recurring(
    account_id: uuid.UUID,
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Stop a schedule.

    Cancels rather than deletes: the posts it already produced are real, and a
    deleted row would leave them with no explanation of where they came from.
    """
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_CREATE)
    schedule = (
        await db.execute(
            select(RecurringSchedule).where(
                RecurringSchedule.id == schedule_id,
                RecurringSchedule.account_id == account_id,
            )
        )
    ).scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    schedule.status = RecurrenceStatus.CANCELLED
    schedule.next_run_at = None
    await db.flush()
    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="recurring.cancelled",
        category="post",
        description="Cancelled a recurring schedule",
        resource_type="recurring_schedule",
        resource_id=str(schedule_id),
    )
    return None
