"""The weekly posting queue.

A workspace declares when it posts -- Mon/Wed/Fri at 10:00, say -- and "add to
queue" drops a post into the next of those that is free. It is the same idea as
a recurring schedule seen from the other end: there, one post repeats on a
rule; here, a rule of empty slots is filled by different posts.

Slots are weekday plus local time, so they inherit the same DST handling as
recurrence: 10:00 means 10:00 on the workspace's clock all year, and the UTC
instant moves twice a year rather than the posting hour drifting.
"""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.post import Post, PostStatus
from app.models.recurring_schedule import QueueSlot
from app.services.dashboard import workspace_timezone
from app.services.recurrence import is_ambiguous, is_nonexistent, to_utc

logger = logging.getLogger(__name__)

# How far ahead to look for a free slot. Two months of a three-slot week is
# about 26 openings; if all of those are taken, the answer the user needs is
# "your queue is full", not a date in the next decade.
SEARCH_DAYS = 60

# Statuses that occupy a slot. A draft does not -- it has no scheduled time --
# and neither does a failed or published post, whose slot has come and gone.
OCCUPYING_STATUSES = (
    PostStatus.SCHEDULED,
    PostStatus.PUBLISHING,
)


class QueueFull(Exception):
    """No free slot within the search window."""


class NoSlotsConfigured(Exception):
    """The workspace has not said when it posts."""


async def active_slots(db: AsyncSession, account_id: uuid.UUID) -> list[QueueSlot]:
    """The workspace's slots, in week order."""
    return list(
        (
            await db.execute(
                select(QueueSlot)
                .where(QueueSlot.account_id == account_id, QueueSlot.is_active.is_(True))
                .order_by(QueueSlot.weekday, QueueSlot.time_local)
            )
        ).scalars()
    )


async def _taken_instants(
    db: AsyncSession, account_id: uuid.UUID, *, since: datetime, until: datetime
) -> set[datetime]:
    """UTC instants already spoken for in this workspace.

    Compared as instants rather than as local readings. During the fall-back
    hour two different instants render as the same wall-clock time, and a slot
    at the second of them is genuinely still free.
    """
    rows = (
        await db.execute(
            select(Post.scheduled_at).where(
                Post.account_id == account_id,
                Post.deleted_at.is_(None),
                Post.status.in_(OCCUPYING_STATUSES),
                Post.scheduled_at.is_not(None),
                Post.scheduled_at >= since,
                Post.scheduled_at <= until,
            )
        )
    ).scalars().all()
    return {
        value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        for value in rows
    }


async def upcoming_slots(
    db: AsyncSession,
    account: Account,
    *,
    after: Optional[datetime] = None,
    limit: int = 20,
    include_taken: bool = True,
) -> list[dict]:
    """The next slots on the calendar, each marked free or taken.

    Used by the composer to show where a post would land, and by the calendar
    to draw the week's shape.
    """
    slots = await active_slots(db, account.id)
    if not slots:
        return []

    tz = workspace_timezone(account)
    now = after or datetime.now(timezone.utc)
    horizon = now + timedelta(days=SEARCH_DAYS)
    taken = await _taken_instants(db, account.id, since=now, until=horizon)

    by_weekday: dict[int, list[QueueSlot]] = {}
    for slot in slots:
        by_weekday.setdefault(slot.weekday, []).append(slot)

    found: list[dict] = []
    start_day: date = now.astimezone(tz).date()
    for offset in range(SEARCH_DAYS + 1):
        day = start_day + timedelta(days=offset)
        for slot in sorted(by_weekday.get(day.weekday(), []), key=lambda s: s.time_local):
            local = datetime.combine(day, slot.time_local)
            instant = to_utc(local, tz)
            if instant <= now:
                continue
            is_taken = instant in taken
            if is_taken and not include_taken:
                continue
            found.append(
                {
                    "slot_id": str(slot.id),
                    "weekday": slot.weekday,
                    "local_time": slot.time_local.isoformat(timespec="minutes"),
                    "local_datetime": local.isoformat(),
                    "run_at": instant.isoformat(),
                    "taken": is_taken,
                    # Surfaced so the UI can explain an hour that looks wrong.
                    # Once a year a 02:30 slot really does publish at 03:30.
                    "shifted_for_dst": is_nonexistent(local, tz),
                    "ambiguous_for_dst": is_ambiguous(local, tz),
                }
            )
            if len(found) >= limit:
                return found
    return found


async def next_free_slot(
    db: AsyncSession, account: Account, *, after: Optional[datetime] = None
) -> datetime:
    """The UTC instant of the next unoccupied slot.

    Raises rather than returning None: "there is no slot" and "the slot is
    now" are different answers, and a caller that treats a null as either will
    publish something at the wrong time.
    """
    slots = await active_slots(db, account.id)
    if not slots:
        raise NoSlotsConfigured(
            "This workspace has no posting slots yet. Add some in settings, "
            "then queueing will have somewhere to put a post."
        )

    upcoming = await upcoming_slots(
        db, account, after=after, limit=1, include_taken=False
    )
    if not upcoming:
        raise QueueFull(
            f"Every slot in the next {SEARCH_DAYS} days is taken. "
            "Add more slots, or schedule this post for a specific time."
        )
    return datetime.fromisoformat(upcoming[0]["run_at"])


async def queue_depth(db: AsyncSession, account: Account) -> dict:
    """How full the queue is, for the composer's "add to queue" button."""
    slots = await active_slots(db, account.id)
    if not slots:
        return {"configured": False, "slots_per_week": 0, "queued": 0, "next_free": None}

    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=SEARCH_DAYS)
    taken = await _taken_instants(db, account.id, since=now, until=horizon)

    try:
        next_free = (await next_free_slot(db, account)).isoformat()
    except (QueueFull, NoSlotsConfigured):
        next_free = None

    return {
        "configured": True,
        "slots_per_week": len(slots),
        "queued": len(taken),
        "next_free": next_free,
    }
