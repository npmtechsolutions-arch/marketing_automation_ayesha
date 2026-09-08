"""The publishing worker loop.

Deliberately not Celery. The loop is a plain asyncio task started in the
FastAPI lifespan, and the durability that Celery would have provided comes from
the database instead: jobs are rows, a claim is a transaction, and a retry is a
future ``run_at``. Nothing is held in a broker that can disagree with the
database about what was published.

What changed from the post-level version: this used to claim whole *posts* and
republish every one of their targets on recovery -- so a process death after
two of three platforms had succeeded republished those two. Claiming is now per
job, so recovery resumes exactly the work that did not finish.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.post import Post, PostStatus
from app.services import (
    account_health,
    analytics_sync,
    error_log,
    publishing,
    recurring,
    report_jobs,
)

logger = logging.getLogger(__name__)

# How often the loop looks for work. Also the worst-case delay between a post
# becoming due and its jobs being claimed.
POLL_SECONDS = 5
# Jobs claimed per pass. The publish semaphore bounds how many actually run at
# once; this only bounds how many are spoken for in one transaction.
CLAIM_BATCH = 10


async def enqueue_due_posts() -> int:
    """Move posts whose scheduled time has arrived into PUBLISHING.

    Scheduling already created the jobs with a future ``run_at``, so normally
    this only flips the post's status. It also creates jobs for a due post that
    has none -- posts scheduled before this existed, and any case where job
    creation was lost -- so a scheduled post cannot sit due-but-idle forever.

    Claiming the post row with ``FOR UPDATE SKIP LOCKED`` keeps two instances
    from creating two sets of jobs for the same post.
    """
    created = 0
    async with AsyncSessionLocal() as session:
        try:
            now = datetime.now(timezone.utc)
            posts = (
                await session.execute(
                    select(Post)
                    .where(
                        Post.status == PostStatus.SCHEDULED,
                        Post.scheduled_at <= now,
                        Post.deleted_at.is_(None),
                    )
                    .with_for_update(skip_locked=True)
                )
            ).scalars().all()
            if not posts:
                return 0

            for post in posts:
                existing = await publishing.job_count_for_post(session, post.id)
                if existing == 0:
                    jobs = await publishing.create_jobs_for_post(
                        session, post, run_at=now
                    )
                    created += len(jobs)
                    logger.info(
                        "Due post %s had no jobs; created %d.", post.id, len(jobs)
                    )
                # PUBLISHING while its jobs run; the terminal status is derived
                # from them when they finish.
                post.status = PostStatus.PUBLISHING
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Error enqueuing due posts")
            return 0
    return created


async def run_due_jobs() -> int:
    """Claim due jobs and start them.

    Claiming and executing are separate sessions on purpose: a publish can take
    minutes (a 600s YouTube upload, a 180s render), and holding the claiming
    transaction open for that would pin a database connection and block the
    next pass.
    """
    async with AsyncSessionLocal() as session:
        try:
            job_ids = await publishing.claim_due_jobs(session, limit=CLAIM_BATCH)
        except Exception:
            await session.rollback()
            logger.exception("Error claiming publishing jobs")
            return 0

    for job_id in job_ids:
        publishing.spawn(job_id)
    if job_ids:
        logger.info("Claimed %d publishing job(s).", len(job_ids))
    return len(job_ids)


async def recover_stale_jobs() -> int:
    async with AsyncSessionLocal() as session:
        try:
            return await publishing.requeue_stale_claims(session)
        except Exception:
            await session.rollback()
            logger.exception("Error recovering stale publishing jobs")
            return 0


# The health sweep runs on its own cadence inside the same loop rather than as
# a second task: one loop is one thing to reason about, and the sweep is cheap
# enough that gating it on elapsed time is simpler than scheduling it.
_last_health_sweep: float = 0.0


async def maybe_sweep_account_health() -> None:
    """Run the connection health sweep at most hourly."""
    global _last_health_sweep

    now = asyncio.get_running_loop().time()
    if _last_health_sweep and now - _last_health_sweep < account_health.SWEEP_INTERVAL_SECONDS:
        return
    _last_health_sweep = now

    async with AsyncSessionLocal() as session:
        try:
            await account_health.sweep(session)
        except Exception:
            await session.rollback()
            logger.exception("Account health sweep failed")


_last_analytics_sync: float = 0.0


async def maybe_sync_analytics() -> None:
    """Collect yesterday's analytics and prune expired history, once a day.

    Gated on elapsed time in the same loop rather than a separate scheduler:
    one loop is one thing to reason about, and the alternative was the Celery
    beat that Phase 1.5 removed.
    """
    global _last_analytics_sync

    now = asyncio.get_running_loop().time()
    if (
        _last_analytics_sync
        and now - _last_analytics_sync < analytics_sync.SYNC_INTERVAL_SECONDS
    ):
        return
    _last_analytics_sync = now

    async with AsyncSessionLocal() as session:
        try:
            await analytics_sync.sync_day(session)
            await analytics_sync.refresh_post_metrics(session)
            await analytics_sync.prune(session)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Analytics sync failed")


_last_error_prune: float = 0.0
ERROR_PRUNE_INTERVAL_SECONDS = 24 * 60 * 60


async def maybe_prune_api_errors() -> None:
    """Drop recorded 5xx rows past their retention window, once a day.

    In its own pass rather than folded into the analytics one: an analytics
    failure must not stop the error table from being trimmed, and vice versa.
    """
    global _last_error_prune

    now = asyncio.get_running_loop().time()
    if _last_error_prune and now - _last_error_prune < ERROR_PRUNE_INTERVAL_SECONDS:
        return
    _last_error_prune = now

    async with AsyncSessionLocal() as session:
        try:
            await error_log.prune(session)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Pruning api_errors failed")


_last_recurring_check: float = 0.0


async def materialise_recurring() -> None:
    """Turn due recurring schedules into posts, about once a minute.

    Not every poll: the loop runs every 5 seconds, and a schedule is due at
    minute granularity at best, so checking twelve times as often would be
    twelve times the queries for the same answer.
    """
    global _last_recurring_check

    now = asyncio.get_running_loop().time()
    if (
        _last_recurring_check
        and now - _last_recurring_check < recurring.CHECK_INTERVAL_SECONDS
    ):
        return
    _last_recurring_check = now

    async with AsyncSessionLocal() as session:
        try:
            produced = await recurring.run_due(session)
            await session.commit()
            if produced:
                logger.info("Recurring schedules produced %d post(s)", produced)
        except Exception:
            await session.rollback()
            logger.exception("Materialising recurring schedules failed")


_last_report_check: float = 0.0


async def run_reports() -> None:
    """Generate queued reports and queue any the schedule is due.

    Rate-limited to once a minute like the recurrence pass: rendering is
    CPU-bound in this process, and checking twelve times as often would be
    twelve times the queries for the same answer.
    """
    global _last_report_check

    now = asyncio.get_running_loop().time()
    if (
        _last_report_check
        and now - _last_report_check < report_jobs.CHECK_INTERVAL_SECONDS
    ):
        return
    _last_report_check = now

    async with AsyncSessionLocal() as session:
        try:
            await report_jobs.queue_scheduled(session)
            generated = await report_jobs.run_pending(session)
            await session.commit()
            if generated:
                logger.info("Generated %d report(s)", generated)
        except Exception:
            await session.rollback()
            logger.exception("Report generation pass failed")


async def scheduled_post_worker():
    logger.info(
        "Starting publishing worker (poll=%ss, batch=%d, max concurrent=%d).",
        POLL_SECONDS, CLAIM_BATCH, settings.MAX_CONCURRENT_PUBLISHES,
    )
    while True:
        try:
            await materialise_recurring()
            await run_reports()
            await enqueue_due_posts()
            await run_due_jobs()
            await recover_stale_jobs()
            await maybe_sweep_account_health()
            await maybe_sync_analytics()
            await maybe_prune_api_errors()
        except Exception:
            # One bad pass must not end the loop, or scheduled posts stop
            # going out until someone restarts the process.
            logger.exception("Error in the publishing worker loop")
        await asyncio.sleep(POLL_SECONDS)
