"""Materialising recurring schedules into real posts and jobs.

Each occurrence becomes its **own post**, copied from the template. The
alternative -- pointing new jobs at the template post itself -- looks simpler
and is wrong in a way that only shows up after the second run: one row cannot
hold two statuses, two published_at times, two permalinks or two sets of
performance rows, so every run would overwrite the last and the history of a
weekly post would be a single row claiming to have been published once.

The template itself is never published. It stays a draft, and the schedule
holds a reference to it.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.post import Post, PostStatus
from app.models.recurring_schedule import RecurrenceStatus, RecurringSchedule
from app.services import post_cloning, publishing, recurrence

logger = logging.getLogger(__name__)

# How many missed occurrences to publish when the worker has been down. One:
# catching up on a fortnight of a daily schedule would post fourteen times in a
# minute, which is worse for the customer than the gap it is repairing. The
# rest are skipped, and next_run_at moves to the next future occurrence.
MAX_CATCHUP = 1

CHECK_INTERVAL_SECONDS = 60


def compute_next_run(
    schedule: RecurringSchedule, *, after: Optional[datetime] = None
) -> Optional[datetime]:
    """The next UTC instant this schedule should fire, or None if it is done.

    Always recomputed from the rule. Never ``next_run_at + interval``: that is
    the arithmetic that walks a 10:00 post to 09:00 after the clocks change.
    """
    if schedule.max_occurrences is not None and (
        schedule.occurrence_count >= schedule.max_occurrences
    ):
        return None
    return recurrence.next_occurrence(
        schedule.rrule,
        timezone_name=schedule.timezone,
        dtstart_local=schedule.starts_at_local,
        after=after or schedule.next_run_at or datetime.now(timezone.utc),
        until_local=schedule.until_local,
    )


async def initialise(schedule: RecurringSchedule) -> RecurringSchedule:
    """Set the first ``next_run_at``, inclusive of the start itself."""
    schedule.next_run_at = recurrence.next_occurrence(
        schedule.rrule,
        timezone_name=schedule.timezone,
        dtstart_local=schedule.starts_at_local,
        after=datetime.now(timezone.utc),
        until_local=schedule.until_local,
        inclusive=True,
    )
    if schedule.next_run_at is None:
        schedule.status = RecurrenceStatus.COMPLETED
    return schedule


async def due_schedules(db: AsyncSession, *, limit: int = 20) -> list[RecurringSchedule]:
    """Active schedules whose time has come, claimed for this worker.

    ``FOR UPDATE SKIP LOCKED`` so two instances cannot both materialise the
    same occurrence -- the failure mode being a duplicate post on the customer's
    feed, which is visible to their audience.
    """
    now = datetime.now(timezone.utc)
    return list(
        (
            await db.execute(
                select(RecurringSchedule)
                .where(
                    RecurringSchedule.status == RecurrenceStatus.ACTIVE,
                    RecurringSchedule.next_run_at.is_not(None),
                    RecurringSchedule.next_run_at <= now,
                )
                .order_by(RecurringSchedule.next_run_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).scalars()
    )


async def materialise(
    db: AsyncSession, schedule: RecurringSchedule
) -> Optional[Post]:
    """Create this occurrence's post and its publishing jobs.

    Returns the new post, or None if the schedule had nothing to do.
    """
    template = (
        await db.execute(
            select(Post)
            .options(selectinload(Post.variants))
            .where(Post.id == schedule.template_post_id, Post.deleted_at.is_(None))
        )
    ).scalar_one_or_none()

    if template is None:
        # The template was deleted underneath the schedule. Stop rather than
        # retry every minute forever, and say why.
        schedule.status = RecurrenceStatus.CANCELLED
        schedule.last_error = "The template post was deleted."
        schedule.next_run_at = None
        logger.warning(
            "Recurring schedule %s cancelled: template post %s is gone",
            schedule.id, schedule.template_post_id,
        )
        return None

    run_at = schedule.next_run_at or datetime.now(timezone.utc)

    occurrence = await post_cloning.clone_post(
        db,
        template,
        user_id=schedule.created_by or template.user_id,
        account_id=schedule.account_id,
        status=PostStatus.SCHEDULED,
        scheduled_at=run_at,
    )
    await publishing.create_jobs_for_post(db, occurrence, run_at=run_at)

    schedule.occurrence_count += 1
    schedule.last_run_at = datetime.now(timezone.utc)
    schedule.last_error = None

    logger.info(
        "Recurring schedule %s produced post %s for %s",
        schedule.id, occurrence.id, run_at.isoformat(),
    )
    return occurrence


async def advance(db: AsyncSession, schedule: RecurringSchedule) -> None:
    """Move ``next_run_at`` past the occurrence just handled.

    Skips anything already in the past beyond ``MAX_CATCHUP`` so a worker that
    was down over a weekend does not empty a week of posts into one minute.
    """
    now = datetime.now(timezone.utc)
    nxt = compute_next_run(schedule, after=schedule.next_run_at or now)

    skipped = 0
    while nxt is not None and nxt <= now:
        skipped += 1
        nxt = compute_next_run(schedule, after=nxt)

    if skipped:
        logger.warning(
            "Recurring schedule %s skipped %d missed occurrence(s); the worker "
            "was behind. Next run %s.",
            schedule.id, skipped, nxt.isoformat() if nxt else "none",
        )

    schedule.next_run_at = nxt
    if nxt is None:
        schedule.status = RecurrenceStatus.COMPLETED
        logger.info("Recurring schedule %s completed", schedule.id)


async def run_due(db: AsyncSession, *, limit: int = 20) -> int:
    """One pass: materialise every due schedule and advance it.

    A failure on one schedule is recorded on that schedule and does not stop
    the others -- one bad template must not stall every customer's queue.
    """
    produced = 0
    for schedule in await due_schedules(db, limit=limit):
        try:
            post = await materialise(db, schedule)
            if post is not None:
                produced += 1
                await advance(db, schedule)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Recurring schedule %s failed to run", schedule.id)
            schedule.last_error = f"{type(exc).__name__}: {exc}"[:500]
            # Move past this occurrence regardless. Leaving next_run_at in the
            # past would retry the same broken occurrence every minute.
            try:
                await advance(db, schedule)
            except Exception:  # noqa: BLE001
                schedule.status = RecurrenceStatus.PAUSED
                schedule.next_run_at = None
    return produced
