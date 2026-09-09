"""Job-based publishing: create, claim, execute, retry, derive.

The old path published inline. An endpoint set the post to PUBLISHING and fired
a background task that looped over targets and wrote a JSON blob of results.
Three things were wrong with that and all three are why this exists:

* **Not durable.** A process death mid-loop left the post in PUBLISHING. The
  sweeper's only recourse was to reset the whole post and republish *every*
  target, including ones that had already succeeded -- so recovery could
  double-post.
* **Not retryable per target.** One expired token failed the post; the healthy
  accounts had to be republished with it.
* **Not observable.** A failure was a string in a JSON array. No attempt count,
  no next-retry time, no record of what the platform actually said.

A job per (post, account) fixes all three. Backoff is stored as ``run_at``
rather than slept on, so a pending retry survives a restart.
"""

import asyncio
import logging
import os
import random
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.platform import SocialAccount
from app.services import account_health
from app.models.post import Post, PostStatus
from app.models.publishing_job import (
    TERMINAL_STATUSES,
    JobStatus,
    LogLevel,
    PublishingJob,
    PublishingLog,
)

logger = logging.getLogger(__name__)

# --- retry policy ----------------------------------------------------------

DEFAULT_MAX_ATTEMPTS = 3
# First retry after 30s, then 60s, 120s... A platform that is rate limiting or
# briefly unwell recovers within minutes; anything longer is a real fault and
# waiting out the attempts is better than hammering.
BASE_BACKOFF_SECONDS = 30
MAX_BACKOFF_SECONDS = 30 * 60
# Full jitter. Without it, a burst of jobs that fail together retries together
# forever -- the thundering herd that turns one platform hiccup into a
# self-inflicted outage.
BACKOFF_JITTER = 0.25

# A claim older than this belonged to a process that died. Generous because a
# legitimate multi-target publish can run ~13 minutes (YouTube's 600s upload +
# a 180s render + Instagram's polling), and requeuing a job that is still
# running risks a double post.
STALE_CLAIM_MINUTES = 20


def worker_id() -> str:
    """Identifies the claiming process in ``claimed_by``.

    Host plus pid: enough for an operator to find the process that stranded a
    job, and stable for the life of that process.
    """
    return f"{socket.gethostname()}:{os.getpid()}"


def backoff_delay(attempts: int, retry_after: Optional[int] = None) -> int:
    """Seconds to wait before the next attempt.

    ``retry_after`` -- the platform telling us exactly when to come back, from
    a 429 -- always wins. Guessing shorter gets us rate limited again; guessing
    longer delays the post for no reason.
    """
    if retry_after is not None and retry_after > 0:
        return min(int(retry_after), MAX_BACKOFF_SECONDS)
    raw = min(BASE_BACKOFF_SECONDS * (2 ** max(0, attempts - 1)), MAX_BACKOFF_SECONDS)
    jitter = raw * BACKOFF_JITTER
    # Clamp after jittering, not before: +25% on an already-capped value would
    # put the delay above the ceiling the cap exists to enforce.
    return max(1, min(int(raw + random.uniform(-jitter, jitter)), MAX_BACKOFF_SECONDS))


# --- creating jobs ---------------------------------------------------------

async def create_jobs_for_post(
    db: AsyncSession,
    post: Post,
    *,
    run_at: Optional[datetime] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> list[PublishingJob]:
    """One job per target account. ``run_at`` defaults to now (publish now).

    Any non-terminal jobs already on the post are cancelled first, so
    rescheduling a post cannot leave an older run pending against the same
    account.
    """
    now = datetime.now(timezone.utc)
    run_at = run_at or now

    existing = (
        await db.execute(
            select(PublishingJob).where(
                PublishingJob.post_id == post.id,
                PublishingJob.status.notin_(TERMINAL_STATUSES),
            )
        )
    ).scalars().all()
    for job in existing:
        job.status = JobStatus.CANCELLED
        job.last_error = "Superseded by a newer publish request"

    jobs: list[PublishingJob] = []
    for target in post.target_accounts or []:
        raw_id = target.get("social_account_id")
        if not raw_id:
            continue
        try:
            account_id = uuid.UUID(str(raw_id))
        except (ValueError, TypeError):
            logger.warning(
                "Post %s has a target with an unusable social_account_id %r; "
                "skipping it.", post.id, raw_id,
            )
            continue

        job = PublishingJob(
            id=uuid.uuid4(),
            post_id=post.id,
            social_account_id=account_id,
            status=JobStatus.QUEUED,
            run_at=run_at,
            attempts=0,
            max_attempts=max_attempts,
        )
        db.add(job)
        jobs.append(job)

    await db.flush()
    for job in jobs:
        db.add(
            PublishingLog(
                id=uuid.uuid4(),
                job_id=job.id,
                level=LogLevel.INFO,
                message=(
                    "Queued for immediate publishing"
                    if run_at <= now
                    else f"Queued for {run_at.isoformat()}"
                ),
            )
        )
    await db.flush()
    return jobs


# --- claiming --------------------------------------------------------------

async def claim_due_jobs(
    db: AsyncSession, *, limit: int = 10, claimant: Optional[str] = None
) -> list[uuid.UUID]:
    """Claim up to ``limit`` due jobs for this worker.

    ``FOR UPDATE SKIP LOCKED`` is what makes running more than one instance
    safe: rows this transaction locks are invisible to a second worker's
    SELECT, so it takes the next batch instead of the same one. The claim is
    committed while the locks are still held, so by the time they release the
    rows no longer match ``status == QUEUED`` and cannot be taken twice.

    Returns ids rather than instances because execution happens in its own
    session -- a job that runs for ten minutes must not hold this one open.
    """
    claimant = claimant or worker_id()
    now = datetime.now(timezone.utc)

    rows = (
        await db.execute(
            select(PublishingJob)
            .where(
                PublishingJob.status == JobStatus.QUEUED,
                PublishingJob.run_at <= now,
            )
            .order_by(PublishingJob.run_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()

    claimed: list[uuid.UUID] = []
    for job in rows:
        job.status = JobStatus.CLAIMED
        job.claimed_by = claimant
        job.claimed_at = now
        claimed.append(job.id)

    if claimed:
        await db.commit()
    return claimed


async def requeue_stale_claims(db: AsyncSession) -> int:
    """Return jobs whose worker died back to the queue.

    Ported from the old post-level sweep. Doing it per job is what makes it
    safe: the post-level version reset every target, so a recovery republished
    accounts that had already succeeded. A job that has exhausted its attempts
    is failed rather than requeued, so a job that reliably strands the worker
    cannot loop forever.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_CLAIM_MINUTES)
    stale = (
        await db.execute(
            select(PublishingJob)
            .where(
                PublishingJob.status.in_([JobStatus.CLAIMED, JobStatus.RUNNING]),
                PublishingJob.claimed_at < cutoff,
            )
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    if not stale:
        return 0

    for job in stale:
        was = job.status
        if job.attempts >= job.max_attempts:
            job.status = JobStatus.FAILED
            job.last_error = (
                "Publishing was interrupted repeatedly (worker restart or "
                "timeout) and has run out of attempts."
            )
            level, message = LogLevel.ERROR, (
                f"Abandoned after being stuck in {was.value} with no attempts left"
            )
        else:
            job.status = JobStatus.QUEUED
            job.claimed_by = None
            job.claimed_at = None
            job.run_at = datetime.now(timezone.utc)
            level, message = LogLevel.WARNING, (
                f"Requeued after being stuck in {was.value} since the worker died"
            )
        db.add(
            PublishingLog(
                id=uuid.uuid4(), job_id=job.id, level=level, message=message
            )
        )
        logger.warning("Job %s: %s", job.id, message)

    await db.commit()
    return len(stale)


# --- executing -------------------------------------------------------------

# Caps how many jobs publish to the platforms at once across the process. A
# burst of scheduled posts becoming due together would otherwise start
# unbounded concurrent work -- ffmpeg renders, platform uploads, a DB session
# each. Acquired before the session is opened so queued work waits without
# holding a connection.
_PUBLISH_SEMAPHORE = asyncio.Semaphore(settings.MAX_CONCURRENT_PUBLISHES)


async def execute_job(job_id: uuid.UUID) -> None:
    """Run one job to completion, or schedule its retry.

    Opens its own session: a publish can take minutes and must not hold the
    claiming transaction. Every exit path is recorded, because a job that goes
    quiet is indistinguishable from one that never ran.
    """
    async with _PUBLISH_SEMAPHORE:
        await _execute_job_inner(job_id)


async def _execute_job_inner(job_id: uuid.UUID) -> None:
    from app.api.v1.endpoints.posts import _ensure_valid_token
    from app.connectors.base import MediaRef, resolve_content, variant_for_slug
    from app.connectors.registry import get_provider

    async with AsyncSessionLocal() as db:
        job = (
            await db.execute(
                select(PublishingJob)
                .options(selectinload(PublishingJob.post))
                .where(PublishingJob.id == job_id)
            )
        ).scalar_one_or_none()
        if job is None or job.status in TERMINAL_STATUSES:
            return

        job.status = JobStatus.RUNNING
        job.attempts += 1
        attempt_label = f"attempt {job.attempts}/{job.max_attempts}"
        await db.commit()

        post = job.post
        account = (
            await db.execute(
                select(SocialAccount)
                .options(selectinload(SocialAccount.platform))
                .where(SocialAccount.id == job.social_account_id)
            )
        ).scalar_one_or_none()

        if post is None or post.deleted_at is not None:
            await _finish(db, job, JobStatus.CANCELLED, "The post no longer exists")
            return
        if account is None:
            await _finish(
                db, job, JobStatus.FAILED, "Social account not found", retryable=False
            )
            await _derive_and_commit(db, job.post_id)
            return

        slug = (account.platform.slug if account.platform else "").lower()
        provider = get_provider(slug)

        try:
            await _ensure_valid_token(account, db)
            # The platform's own version if the author wrote one, else the
            # master post. Variants are eager-loaded on Post, so this is a list
            # scan rather than a query inside the publish path.
            variant_row = variant_for_slug(post, provider.slug)
            content = resolve_content(post, provider.slug, variant_row)
            if content.is_customised:
                await _log(
                    db, job, LogLevel.INFO,
                    f"Using the {provider.slug} variant "
                    f"(overrides: {', '.join(content.overridden)})",
                )
            media = [MediaRef(url=u) for u in content.media_urls]
            result = await provider.publish_post(content, media, account)
        except Exception as exc:  # noqa: BLE001 - a crash is a failed attempt
            logger.exception("Job %s raised on %s", job.id, attempt_label)
            await _schedule_retry_or_fail(
                db, job, error=f"{type(exc).__name__}: {exc}", retryable=True
            )
            await _derive_and_commit(db, job.post_id)
            return

        if result.succeeded:
            job.external_post_id = result.external_post_id
            job.post_url = result.post_url or (
                f"https://mock-{slug}.com/posts/{result.external_post_id}"
            )
            await _finish(
                db, job, JobStatus.SUCCEEDED,
                f"Published on {attempt_label}",
                platform_response={
                    "external_post_id": result.external_post_id,
                    "post_url": job.post_url,
                },
            )
        elif result.status == "manual_required":
            # No API exists for this; retrying cannot help. FAILED with the
            # reason recorded, so the UI can offer the manual-publish helper.
            job.manual_required = True
            await _finish(
                db, job, JobStatus.FAILED, result.error or "Manual publishing required",
                retryable=False,
                platform_response={"manual_required": True, "error": result.error},
            )
        else:
            # A platform rejecting our credentials is stronger evidence than
            # any expiry arithmetic, and waiting up to an hour for the health
            # sweep to notice would let the next scheduled post fail the same
            # way.
            if _looks_like_auth_failure(result.error):
                account_health.mark_auth_failure(
                    account,
                    f"Publishing was rejected: {(result.error or '')[:200]}",
                )
            await _schedule_retry_or_fail(
                db, job,
                error=result.error or "Publishing failed",
                retryable=result.retryable,
                retry_after=getattr(result, "retry_after", None),
            )

        await _derive_and_commit(db, job.post_id)


# Substrings that mean "these credentials are no longer good", as opposed to a
# transient platform problem. Deliberately narrow: marking an account FAILED on
# a timeout would send a false alarm and teach people to ignore the real ones.
_AUTH_FAILURE_MARKERS = (
    "401", "invalid_token", "invalid access token", "token expired",
    "expired access token", "oauthexception", "invalid_grant",
    "revoked", "unauthorized", "malformed access token",
)


def _looks_like_auth_failure(error: Optional[str]) -> bool:
    lowered = (error or "").lower()
    return any(marker in lowered for marker in _AUTH_FAILURE_MARKERS)


async def _log(
    db: AsyncSession,
    job: PublishingJob,
    level: LogLevel,
    message: str,
    platform_response: Optional[dict] = None,
) -> None:
    """Append one line to a job's history."""
    db.add(
        PublishingLog(
            id=uuid.uuid4(),
            job_id=job.id,
            level=level,
            message=message,
            platform_response=platform_response,
        )
    )
    await db.flush()


async def _finish(
    db: AsyncSession,
    job: PublishingJob,
    status: JobStatus,
    message: str,
    *,
    retryable: bool = False,
    platform_response: Optional[dict] = None,
) -> None:
    job.status = status
    job.claimed_at = None
    if status is not JobStatus.SUCCEEDED:
        job.last_error = message
    db.add(
        PublishingLog(
            id=uuid.uuid4(),
            job_id=job.id,
            level=LogLevel.INFO if status is JobStatus.SUCCEEDED else LogLevel.ERROR,
            message=message,
            platform_response=platform_response,
        )
    )
    await db.commit()


async def _schedule_retry_or_fail(
    db: AsyncSession,
    job: PublishingJob,
    *,
    error: str,
    retryable: bool,
    retry_after: Optional[int] = None,
) -> None:
    """Back off and requeue, or give up.

    A permanent error (a revoked token, a rejected payload) is failed
    immediately: burning three attempts on it delays the user's feedback by
    minutes and tells them nothing new.
    """
    job.last_error = error
    job.claimed_at = None

    if not retryable or job.attempts >= job.max_attempts:
        job.status = JobStatus.FAILED
        reason = (
            "no attempts left" if retryable else "the error is not retryable"
        )
        db.add(
            PublishingLog(
                id=uuid.uuid4(),
                job_id=job.id,
                level=LogLevel.ERROR,
                message=f"Failed after {job.attempts} attempt(s) -- {reason}: {error}",
                platform_response={"error": error, "retryable": retryable},
            )
        )
        await db.commit()
        return

    delay = backoff_delay(job.attempts, retry_after)
    job.status = JobStatus.QUEUED
    job.claimed_by = None
    job.run_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
    db.add(
        PublishingLog(
            id=uuid.uuid4(),
            job_id=job.id,
            level=LogLevel.WARNING,
            message=(
                f"Attempt {job.attempts}/{job.max_attempts} failed; retrying in "
                f"{delay}s"
                + (" (platform asked us to wait)" if retry_after else "")
                + f": {error}"
            ),
            platform_response={"error": error, "retry_after": retry_after},
        )
    )
    await db.commit()


# --- deriving the post's status -------------------------------------------

def _result_status(job: PublishingJob) -> str:
    """How a job reads in ``posting_results``.

    Maps the job's own vocabulary onto the one the API has always used:
    SUCCEEDED is "published", and a job that failed because no API exists keeps
    "manual_required" so the UI can tell the two apart.
    """
    if job.status is JobStatus.SUCCEEDED:
        return "published"
    if job.status is JobStatus.FAILED and job.manual_required:
        return "manual_required"
    return job.status.value


async def derive_post_status(db: AsyncSession, post_id: uuid.UUID) -> Optional[Post]:
    """Recompute a post's status from its jobs.

    The post no longer carries an independent status that can disagree with
    what actually happened -- it is a function of the jobs. ``posting_results``
    is rebuilt from the same rows so the existing API shape keeps working, but
    it is now a projection rather than a second source of truth.
    """
    post = (
        await db.execute(select(Post).where(Post.id == post_id))
    ).scalar_one_or_none()
    if post is None:
        return None

    jobs = (
        await db.execute(
            select(PublishingJob).where(PublishingJob.post_id == post_id)
        )
    ).scalars().all()
    if not jobs:
        return post

    succeeded = [j for j in jobs if j.status is JobStatus.SUCCEEDED]
    failed = [j for j in jobs if j.status is JobStatus.FAILED]
    pending = [j for j in jobs if not j.is_terminal]

    post.posting_results = [
        {
            "social_account_id": str(j.social_account_id),
            "job_id": str(j.id),
            "status": _result_status(j),
            "external_post_id": j.external_post_id,
            "post_url": j.post_url,
            "error": j.last_error,
            "attempts": j.attempts,
        }
        for j in jobs
    ]

    if pending:
        # Still working. Anything already published stays published; the post
        # is not final until every job is.
        post.status = PostStatus.PUBLISHING
        post.error_message = None
    elif succeeded and not failed:
        post.status = PostStatus.PUBLISHED
        post.published_at = post.published_at or datetime.now(timezone.utc)
        post.error_message = None
    elif succeeded and failed:
        post.status = PostStatus.PARTIALLY_PUBLISHED
        post.published_at = post.published_at or datetime.now(timezone.utc)
        post.error_message = failed[0].last_error or "Some account postings failed"
    elif failed:
        post.status = PostStatus.FAILED
        post.error_message = failed[0].last_error or "Publishing failed"
    else:
        # Everything was cancelled -- the post was superseded or its targets
        # disappeared. Leave it where a user can act on it.
        post.status = PostStatus.DRAFT
        post.error_message = None

    await _seed_performance_rows(db, post, succeeded)
    await db.flush()
    return post


async def _derive_and_commit(db: AsyncSession, post_id: uuid.UUID) -> None:
    await derive_post_status(db, post_id)
    await db.commit()


async def _seed_performance_rows(
    db: AsyncSession, post: Post, succeeded: list[PublishingJob]
) -> None:
    """Deliberately does nothing. Kept as the record of why.

    This used to insert a fully zeroed PostPerformance row for every platform a
    post published to, "the zeroed metric rows the analytics page reads". A row
    of zeros is not an empty state -- it is a measurement claiming that nobody
    saw the post and nobody engaged with it.

    For most posts the zeros were replaced within a sync and nobody noticed.
    For X and LinkedIn they never were: those platforms expose no per-post
    metrics fetch, so a post there kept a permanent, confident "0 reach, 0
    likes" that was indistinguishable from a real result. Removing the
    fabricated metrics in the connectors would have achieved nothing while this
    still ran.

    An absent row is the honest state, and every reader already handles it:
    ``Post.performance`` returns None, ``analytics_query.posts`` inner-joins so
    the post simply is not listed yet, and the calendar now says the platform
    reports no metrics instead of drawing zeros. The row is created by
    ``_sync_post_performance`` when real numbers arrive.
    """
    return


# --- the worker ------------------------------------------------------------

# asyncio holds only a weak reference to tasks from create_task(), so without
# this a running publish can be garbage-collected mid-flight -- leaving the job
# in RUNNING and the post never posted.
_running: set[asyncio.Task] = set()


def spawn(job_id: uuid.UUID) -> None:
    task = asyncio.create_task(execute_job(job_id))
    _running.add(task)
    task.add_done_callback(_running.discard)


async def pending_job_count(db: AsyncSession) -> int:
    return (
        await db.execute(
            select(func.count(PublishingJob.id)).where(
                PublishingJob.status.notin_(TERMINAL_STATUSES)
            )
        )
    ).scalar() or 0


async def job_count_for_post(db: AsyncSession, post_id: uuid.UUID) -> int:
    """How many jobs exist for a post, in any state."""
    return (
        await db.execute(
            select(func.count(PublishingJob.id)).where(
                PublishingJob.post_id == post_id
            )
        )
    ).scalar() or 0
