"""Durable publishing: jobs, backoff, retry, derived post status.

Publishing used to be an inline loop whose only record was a JSON blob. These
pin what replaced it -- that work survives a restart, that a failure retries
with backoff instead of vanishing, and that a post's status is a function of
its jobs rather than a second thing that can disagree with them.

The two-worker claim test needs two real transactions and lives in
test_publishing_concurrency.py, which skips without Postgres.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.post import Post, PostStatus
from app.models.publishing_job import JobStatus, LogLevel, PublishingJob, PublishingLog
from app.services import publishing

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


def _aware(value):
    """SQLite drops tzinfo on read; Postgres keeps it."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@pytest.fixture
async def post_with_targets(
    db_session, user_factory, account_factory, social_account_factory
):
    async def _make(target_count=2, status=PostStatus.DRAFT):
        owner = await user_factory(password=PASSWORD)
        account = await account_factory(owner)
        accounts = [
            await social_account_factory(owner, account, slug=slug)
            for slug in (["instagram", "facebook", "linkedin"] * 2)[:target_count]
        ]
        post = Post(
            id=uuid.uuid4(),
            user_id=owner.id,
            account_id=account.id,
            content="Durable publishing",
            status=status,
            target_accounts=[
                {"social_account_id": str(sa.id), "platform_name": "X",
                 "account_name": sa.account_name}
                for sa in accounts
            ],
        )
        db_session.add(post)
        await db_session.flush()
        return {
            "owner": owner, "account": account, "accounts": accounts, "post": post,
            # Captured before anything commits: a commit expires the instances,
            # and reading .id back would be IO outside the greenlet context.
            "post_id": post.id,
            "account_ids": [sa.id for sa in accounts],
        }

    return _make


async def _jobs_for(db_session, post_id):
    db_session.expire_all()
    return (
        await db_session.execute(
            select(PublishingJob)
            .where(PublishingJob.post_id == post_id)
            .order_by(PublishingJob.created_at)
        )
    ).scalars().all()


# ---------------------------------------------------------------------------
# Creating jobs
# ---------------------------------------------------------------------------

async def test_one_job_per_target(db_session, post_with_targets):
    ctx = await post_with_targets(target_count=3)
    jobs = await publishing.create_jobs_for_post(db_session, ctx["post"])

    assert len(jobs) == 3
    assert {j.social_account_id for j in jobs} == {sa.id for sa in ctx["accounts"]}
    assert {j.status for j in jobs} == {JobStatus.QUEUED}
    assert all(j.attempts == 0 for j in jobs)


async def test_creating_jobs_writes_a_log_line(db_session, post_with_targets):
    """A job with no history is indistinguishable from one that never ran."""
    ctx = await post_with_targets(target_count=1)
    jobs = await publishing.create_jobs_for_post(db_session, ctx["post"])

    logs = (
        await db_session.execute(
            select(PublishingLog).where(PublishingLog.job_id == jobs[0].id)
        )
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].level is LogLevel.INFO


async def test_scheduling_sets_a_future_run_at(db_session, post_with_targets):
    ctx = await post_with_targets(target_count=1)
    when = datetime.now(timezone.utc) + timedelta(hours=2)
    jobs = await publishing.create_jobs_for_post(db_session, ctx["post"], run_at=when)

    assert _aware(jobs[0].run_at) > datetime.now(timezone.utc)


async def test_rescheduling_cancels_the_superseded_jobs(db_session, post_with_targets):
    """Otherwise a reschedule leaves the original run pending and the post goes
    out twice."""
    ctx = await post_with_targets(target_count=2)
    first = await publishing.create_jobs_for_post(db_session, ctx["post"])
    second = await publishing.create_jobs_for_post(db_session, ctx["post"])

    db_session.expire_all()
    all_jobs = await _jobs_for(db_session, ctx["post_id"])
    by_id = {j.id: j for j in all_jobs}
    assert all(by_id[j.id].status is JobStatus.CANCELLED for j in first)
    assert all(by_id[j.id].status is JobStatus.QUEUED for j in second)


async def test_a_target_with_an_unusable_id_is_skipped(db_session, post_with_targets):
    ctx = await post_with_targets(target_count=1)
    ctx["post"].target_accounts = list(ctx["post"].target_accounts) + [
        {"social_account_id": "not-a-uuid"}, {"platform_name": "no id at all"},
    ]
    jobs = await publishing.create_jobs_for_post(db_session, ctx["post"])
    assert len(jobs) == 1


# ---------------------------------------------------------------------------
# Claiming
# ---------------------------------------------------------------------------

async def test_claim_takes_only_due_jobs(db_session, post_with_targets):
    ctx = await post_with_targets(target_count=2)
    await publishing.create_jobs_for_post(
        db_session, ctx["post"], run_at=datetime.now(timezone.utc) + timedelta(hours=1)
    )

    assert await publishing.claim_due_jobs(db_session) == []


async def test_claim_marks_the_worker(db_session, post_with_targets):
    ctx = await post_with_targets(target_count=2)
    await publishing.create_jobs_for_post(db_session, ctx["post"])

    claimed = await publishing.claim_due_jobs(db_session, claimant="worker-a")
    assert len(claimed) == 2

    for job in await _jobs_for(db_session, ctx["post_id"]):
        assert job.status is JobStatus.CLAIMED
        assert job.claimed_by == "worker-a"
        assert job.claimed_at is not None


async def test_a_claimed_job_is_not_claimed_again(db_session, post_with_targets):
    """Single-session version of the guarantee; the two-worker case is in
    test_publishing_concurrency.py."""
    ctx = await post_with_targets(target_count=2)
    await publishing.create_jobs_for_post(db_session, ctx["post"])

    first = await publishing.claim_due_jobs(db_session)
    second = await publishing.claim_due_jobs(db_session)
    assert len(first) == 2
    assert second == []


# ---------------------------------------------------------------------------
# Backoff
# ---------------------------------------------------------------------------

def test_backoff_grows_and_is_capped():
    delays = [publishing.backoff_delay(n) for n in range(1, 12)]
    # Jitter is +/-25%, so compare against the un-jittered curve loosely.
    assert delays[0] < delays[3] < delays[6]
    assert all(d <= publishing.MAX_BACKOFF_SECONDS for d in delays)
    assert delays[-1] >= publishing.MAX_BACKOFF_SECONDS * 0.7


def test_backoff_is_jittered():
    """Without jitter, jobs that fail together retry together forever -- one
    platform hiccup becomes a self-inflicted thundering herd."""
    samples = {publishing.backoff_delay(4) for _ in range(40)}
    assert len(samples) > 1, "backoff is deterministic; a failed batch will synchronise"


def test_retry_after_overrides_the_curve():
    """The platform telling us when to come back beats our guess."""
    assert publishing.backoff_delay(1, retry_after=300) == 300
    assert publishing.backoff_delay(9, retry_after=45) == 45
    # ...but not past the ceiling, so a hostile header cannot park a job for a week.
    assert publishing.backoff_delay(1, retry_after=999999) == publishing.MAX_BACKOFF_SECONDS
    # A nonsense value falls back to the curve.
    assert publishing.backoff_delay(1, retry_after=0) > 0


# ---------------------------------------------------------------------------
# Stale claim recovery
# ---------------------------------------------------------------------------

async def test_a_stale_claim_is_requeued(db_session, post_with_targets):
    """The worker died holding it. Requeue rather than lose the post."""
    ctx = await post_with_targets(target_count=1)
    jobs = await publishing.create_jobs_for_post(db_session, ctx["post"])
    job = jobs[0]
    job.status = JobStatus.RUNNING
    job.attempts = 1
    job.claimed_by = "dead-worker"
    job.claimed_at = datetime.now(timezone.utc) - timedelta(
        minutes=publishing.STALE_CLAIM_MINUTES + 5
    )
    await db_session.flush()

    assert await publishing.requeue_stale_claims(db_session) == 1

    db_session.expire_all()
    refreshed = (await _jobs_for(db_session, ctx["post_id"]))[0]
    assert refreshed.status is JobStatus.QUEUED
    assert refreshed.claimed_by is None


async def test_a_fresh_claim_is_left_alone(db_session, post_with_targets):
    """A publish can legitimately run for ten minutes; requeuing one that is
    still uploading would post it twice."""
    ctx = await post_with_targets(target_count=1)
    jobs = await publishing.create_jobs_for_post(db_session, ctx["post"])
    jobs[0].status = JobStatus.RUNNING
    jobs[0].claimed_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    await db_session.flush()

    assert await publishing.requeue_stale_claims(db_session) == 0


async def test_a_stale_job_with_no_attempts_left_is_failed(
    db_session, post_with_targets
):
    """Otherwise a job that reliably kills its worker loops forever."""
    ctx = await post_with_targets(target_count=1)
    jobs = await publishing.create_jobs_for_post(db_session, ctx["post"])
    jobs[0].status = JobStatus.RUNNING
    jobs[0].attempts = jobs[0].max_attempts
    jobs[0].claimed_at = datetime.now(timezone.utc) - timedelta(
        minutes=publishing.STALE_CLAIM_MINUTES + 1
    )
    await db_session.flush()

    await publishing.requeue_stale_claims(db_session)
    db_session.expire_all()
    assert (await _jobs_for(db_session, ctx["post_id"]))[0].status is JobStatus.FAILED


# ---------------------------------------------------------------------------
# Derived post status
# ---------------------------------------------------------------------------

async def _set_statuses(db_session, post_id, *statuses):
    jobs = await _jobs_for(db_session, post_id)
    for job, status in zip(jobs, statuses):
        job.status = status
        if status is JobStatus.FAILED:
            job.last_error = f"boom {job.social_account_id}"
        if status is JobStatus.SUCCEEDED:
            job.external_post_id = "ext_1"
    await db_session.flush()
    return jobs


@pytest.mark.parametrize(
    "statuses,expected",
    [
        ((JobStatus.SUCCEEDED, JobStatus.SUCCEEDED), PostStatus.PUBLISHED),
        ((JobStatus.SUCCEEDED, JobStatus.FAILED), PostStatus.PARTIALLY_PUBLISHED),
        ((JobStatus.FAILED, JobStatus.FAILED), PostStatus.FAILED),
        ((JobStatus.SUCCEEDED, JobStatus.QUEUED), PostStatus.PUBLISHING),
        ((JobStatus.CANCELLED, JobStatus.CANCELLED), PostStatus.DRAFT),
    ],
)
async def test_post_status_is_derived_from_its_jobs(
    db_session, post_with_targets, statuses, expected
):
    """The post no longer carries a status that can disagree with what actually
    happened -- it is a function of the jobs."""
    ctx = await post_with_targets(target_count=2)
    await publishing.create_jobs_for_post(db_session, ctx["post"])
    await _set_statuses(db_session, ctx["post_id"], *statuses)

    post = await publishing.derive_post_status(db_session, ctx["post_id"])
    assert post.status is expected


async def test_derived_results_carry_the_error_and_attempts(
    db_session, post_with_targets
):
    ctx = await post_with_targets(target_count=2)
    await publishing.create_jobs_for_post(db_session, ctx["post"])
    jobs = await _set_statuses(
        db_session, ctx["post_id"], JobStatus.SUCCEEDED, JobStatus.FAILED
    )
    jobs[1].attempts = 3
    await db_session.flush()

    post = await publishing.derive_post_status(db_session, ctx["post_id"])
    results = {r["social_account_id"]: r for r in post.posting_results}

    ok = results[str(jobs[0].social_account_id)]
    bad = results[str(jobs[1].social_account_id)]
    assert ok["status"] == "published"
    assert bad["status"] == "failed"
    assert bad["attempts"] == 3
    assert "boom" in bad["error"]
    assert bad["job_id"] == str(jobs[1].id)
    assert post.error_message == bad["error"]


async def test_manual_required_survives_derivation(db_session, post_with_targets):
    """A YouTube Community post has no API. It is a failure, but the UI shows a
    'publish by hand' helper rather than a red error, so it must stay
    distinguishable from a real failure."""
    ctx = await post_with_targets(target_count=1)
    jobs = await publishing.create_jobs_for_post(db_session, ctx["post"])
    jobs[0].status = JobStatus.FAILED
    jobs[0].manual_required = True
    jobs[0].last_error = "Post this one by hand"
    await db_session.flush()

    post = await publishing.derive_post_status(db_session, ctx["post_id"])
    assert post.posting_results[0]["status"] == "manual_required"
    assert post.status is PostStatus.FAILED


async def test_publishing_does_not_invent_a_zeroed_performance_row(
    db_session, post_with_targets
):
    """A published post starts with no metrics, not with zeroes.

    Publishing used to seed a fully zeroed PostPerformance row per platform.
    That is not an empty state -- it says the post was measured and reached
    nobody. On X and LinkedIn, which expose no per-post metrics fetch, the
    zeroes were never replaced, so those posts kept a permanent confident
    "0 reach" that looked exactly like a real result.

    The row is created when real numbers arrive instead.
    """
    from app.models.post_performance import PostPerformance

    ctx = await post_with_targets(target_count=2)
    await publishing.create_jobs_for_post(db_session, ctx["post"])
    await _set_statuses(
        db_session, ctx["post_id"], JobStatus.SUCCEEDED, JobStatus.FAILED
    )

    await publishing.derive_post_status(db_session, ctx["post_id"])

    rows = (
        await db_session.execute(
            select(PostPerformance).where(PostPerformance.post_id == ctx["post_id"])
        )
    ).scalars().all()
    assert rows == []

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def _jobs_url(account_id, post_id, suffix=""):
    return f"/api/v1/accounts/{account_id}/posts/{post_id}/jobs{suffix}"


async def test_publishing_now_creates_jobs_instead_of_publishing_inline(
    client, auth_header, db_session, post_with_targets
):
    """The endpoint used to fire a background task in this process. A restart
    between the response and the platform call lost the publish with no record
    that it had been asked for."""
    ctx = await post_with_targets(target_count=2)

    response = await client.post(
        f"/api/v1/accounts/{ctx['account'].id}/posts/{ctx['post_id']}/publish",
        headers=auth_header(ctx["owner"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "publishing"

    jobs = await _jobs_for(db_session, ctx["post_id"])
    assert len(jobs) == 2
    assert {j.status for j in jobs} == {JobStatus.QUEUED}


async def test_publishing_a_post_with_no_targets_is_refused(
    client, auth_header, db_session, user_factory, account_factory
):
    """It used to report success and write a hardcoded Instagram metrics row."""
    owner = await user_factory(password=PASSWORD)
    account = await account_factory(owner)
    post = Post(
        id=uuid.uuid4(), user_id=owner.id, account_id=account.id,
        content="Nowhere to go", status=PostStatus.DRAFT, target_accounts=[],
    )
    db_session.add(post)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/accounts/{account.id}/posts/{post.id}/publish",
        headers=auth_header(owner),
    )
    assert response.status_code == 400
    assert "target" in response.json()["detail"].lower()


async def test_jobs_endpoint_returns_jobs_with_their_logs(
    client, auth_header, db_session, post_with_targets
):
    ctx = await post_with_targets(target_count=2)
    await publishing.create_jobs_for_post(db_session, ctx["post"])

    response = await client.get(
        _jobs_url(ctx["account"].id, ctx["post_id"]), headers=auth_header(ctx["owner"])
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["post_id"] == str(ctx["post_id"])
    assert len(body["jobs"]) == 2
    job = body["jobs"][0]
    assert job["status"] == "queued"
    assert job["attempts"] == 0
    assert job["attempts_remaining"] == job["max_attempts"]
    assert job["platform_slug"] is not None
    assert len(job["logs"]) == 1, "the queue event should be visible"


async def test_jobs_endpoint_exposes_the_platform_response(
    client, auth_header, db_session, post_with_targets
):
    """The reason this exists: 'failed' alone sends someone into the logs."""
    ctx = await post_with_targets(target_count=1)
    jobs = await publishing.create_jobs_for_post(db_session, ctx["post"])
    db_session.add(
        PublishingLog(
            id=uuid.uuid4(), job_id=jobs[0].id, level=LogLevel.ERROR,
            message="Attempt 1/3 failed; retrying in 30s",
            platform_response={"error": {"code": 190, "message": "token expired"}},
        )
    )
    await db_session.flush()

    body = (
        await client.get(
            _jobs_url(ctx["account"].id, ctx["post_id"]),
            headers=auth_header(ctx["owner"]),
        )
    ).json()
    responses = [entry["platform_response"] for entry in body["jobs"][0]["logs"]]
    assert {"error": {"code": 190, "message": "token expired"}} in responses


async def test_jobs_endpoint_denied_to_a_non_member(
    client, auth_header, user_factory, post_with_targets
):
    ctx = await post_with_targets(target_count=1)
    stranger = await user_factory()
    response = await client.get(
        _jobs_url(ctx["account"].id, ctx["post_id"]), headers=auth_header(stranger)
    )
    assert response.status_code == 403


# --- retry -----------------------------------------------------------------

async def test_retry_requeues_only_the_failed_job(
    client, auth_header, db_session, post_with_targets
):
    """The whole point of per-target jobs: the account that already published
    must not be published to again."""
    ctx = await post_with_targets(target_count=2)
    await publishing.create_jobs_for_post(db_session, ctx["post"])
    ok, bad = await _set_statuses(
        db_session, ctx["post_id"], JobStatus.SUCCEEDED, JobStatus.FAILED
    )
    bad.attempts = 3
    await db_session.flush()
    ok_id, bad_id = ok.id, bad.id

    response = await client.post(
        _jobs_url(ctx["account"].id, ctx["post_id"], f"/{bad_id}/retry"),
        headers=auth_header(ctx["owner"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "queued"
    assert response.json()["attempts"] == 0, "a manual retry gets a full allowance"

    by_id = {j.id: j for j in await _jobs_for(db_session, ctx["post_id"])}
    assert by_id[bad_id].status is JobStatus.QUEUED
    assert by_id[ok_id].status is JobStatus.SUCCEEDED, "the good target was disturbed"


async def test_retry_records_who_asked(
    client, auth_header, db_session, post_with_targets
):
    ctx = await post_with_targets(target_count=1)
    jobs = await publishing.create_jobs_for_post(db_session, ctx["post"])
    jobs[0].status = JobStatus.FAILED
    await db_session.flush()
    job_id = jobs[0].id

    body = (
        await client.post(
            _jobs_url(ctx["account"].id, ctx["post_id"], f"/{job_id}/retry"),
            headers=auth_header(ctx["owner"]),
        )
    ).json()
    assert any(
        "Requeued manually" in entry["message"] and ctx["owner"].email in entry["message"]
        for entry in body["logs"]
    )


async def test_retrying_a_succeeded_job_is_refused(
    client, auth_header, db_session, post_with_targets
):
    """It would post the content a second time, which cannot be undone."""
    ctx = await post_with_targets(target_count=1)
    jobs = await publishing.create_jobs_for_post(db_session, ctx["post"])
    jobs[0].status = JobStatus.SUCCEEDED
    await db_session.flush()
    job_id = jobs[0].id

    response = await client.post(
        _jobs_url(ctx["account"].id, ctx["post_id"], f"/{job_id}/retry"),
        headers=auth_header(ctx["owner"]),
    )
    assert response.status_code == 409
    assert "second time" in response.json()["detail"]


async def test_retrying_a_running_job_is_refused(
    client, auth_header, db_session, post_with_targets
):
    ctx = await post_with_targets(target_count=1)
    jobs = await publishing.create_jobs_for_post(db_session, ctx["post"])
    jobs[0].status = JobStatus.RUNNING
    await db_session.flush()
    job_id = jobs[0].id

    response = await client.post(
        _jobs_url(ctx["account"].id, ctx["post_id"], f"/{job_id}/retry"),
        headers=auth_header(ctx["owner"]),
    )
    assert response.status_code == 409


async def test_retry_requires_publish_permission(
    client, auth_header, db_session, user_factory, member_factory, post_with_targets
):
    """A VIEWER can see why a post failed but cannot make it post again."""
    from app.models.team_member import InvitationStatus, TeamRole

    ctx = await post_with_targets(target_count=1)
    jobs = await publishing.create_jobs_for_post(db_session, ctx["post"])
    jobs[0].status = JobStatus.FAILED
    await db_session.flush()
    job_id = jobs[0].id

    viewer = await user_factory()
    await member_factory(
        viewer, ctx["account"], role=TeamRole.VIEWER,
        invitation_status=InvitationStatus.ACCEPTED,
    )

    assert (
        await client.get(
            _jobs_url(ctx["account"].id, ctx["post_id"]), headers=auth_header(viewer)
        )
    ).status_code == 200

    response = await client.post(
        _jobs_url(ctx["account"].id, ctx["post_id"], f"/{job_id}/retry"),
        headers=auth_header(viewer),
    )
    assert response.status_code == 403


async def test_retrying_an_unknown_job_is_404(
    client, auth_header, post_with_targets
):
    ctx = await post_with_targets(target_count=1)
    response = await client.post(
        _jobs_url(ctx["account"].id, ctx["post_id"], f"/{uuid.uuid4()}/retry"),
        headers=auth_header(ctx["owner"]),
    )
    assert response.status_code == 404
