"""The weekly queue, and recurring schedules materialising into real posts.

The queue shares recurrence's timezone handling, so it inherits the same DST
obligations: a 10:00 slot is 10:00 on the workspace's clock all year.

The materialisation tests are about one decision -- each occurrence gets its
own post rather than republishing the template. One row cannot hold two
statuses, two permalinks or two sets of metrics, so the alternative loses the
history of every run but the last.
"""

import uuid
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.models.post import Post, PostStatus
from app.models.post_variant import PostVariant
from app.models.publishing_job import JobStatus, PublishingJob
from app.models.recurring_schedule import (
    QueueSlot,
    RecurrenceStatus,
    RecurringSchedule,
)
from app.services import post_cloning, queue_slots, recurrence, recurring

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"
NY = "America/New_York"


@pytest.fixture
async def workspace(
    db_session, user_factory, account_factory, organization_factory,
    social_account_factory,
):
    async def _make(tz="UTC"):
        owner = await user_factory(password=PASSWORD)
        organization = await organization_factory(owner)
        account = await account_factory(owner, organization=organization)
        account.settings = {"timezone": tz}
        await db_session.flush()
        social = await social_account_factory(owner, account, slug="instagram")
        return {
            "owner": owner, "account": account, "account_id": account.id,
            "social": social, "social_id": social.id,
        }

    return _make


@pytest.fixture
async def template_post(db_session):
    async def _make(ws, **extra):
        post = Post(
            id=uuid.uuid4(),
            user_id=ws["owner"].id,
            account_id=ws["account_id"],
            content="Weekly tip",
            title="Tip",
            status=PostStatus.DRAFT,
            target_accounts=[{"social_account_id": str(ws["social_id"])}],
            **extra,
        )
        db_session.add(post)
        await db_session.flush()
        return post

    return _make


async def _add_slots(db_session, account_id, entries):
    for weekday, hour, minute in entries:
        db_session.add(
            QueueSlot(
                id=uuid.uuid4(), account_id=account_id,
                weekday=weekday, time_local=time(hour, minute), is_active=True,
            )
        )
    await db_session.flush()


# ---------------------------------------------------------------------------
# Queue slots
# ---------------------------------------------------------------------------

async def test_next_free_slot_is_the_soonest_configured_one(db_session, workspace):
    ws = await workspace()
    await _add_slots(db_session, ws["account_id"], [(0, 10, 0), (2, 10, 0), (4, 10, 0)])

    # A Tuesday. The next Mon/Wed/Fri slot is Wednesday.
    after = datetime(2026, 6, 2, 12, tzinfo=timezone.utc)
    chosen = await queue_slots.next_free_slot(db_session, ws["account"], after=after)

    assert chosen.weekday() == 2
    assert chosen.hour == 10


async def test_a_taken_slot_is_skipped(db_session, workspace, template_post):
    ws = await workspace()
    await _add_slots(db_session, ws["account_id"], [(0, 10, 0), (2, 10, 0)])
    after = datetime(2026, 6, 2, 12, tzinfo=timezone.utc)

    first = await queue_slots.next_free_slot(db_session, ws["account"], after=after)
    occupied = await template_post(ws)
    occupied.status = PostStatus.SCHEDULED
    occupied.scheduled_at = first
    await db_session.flush()

    second = await queue_slots.next_free_slot(db_session, ws["account"], after=after)

    assert second > first, "the queue handed out the same slot twice"


async def test_a_draft_does_not_occupy_a_slot(db_session, workspace, template_post):
    """A draft has no scheduled time, so it is not in the queue at all."""
    ws = await workspace()
    await _add_slots(db_session, ws["account_id"], [(0, 10, 0)])
    after = datetime(2026, 6, 2, 12, tzinfo=timezone.utc)

    first = await queue_slots.next_free_slot(db_session, ws["account"], after=after)
    draft = await template_post(ws)
    draft.scheduled_at = first          # set, but still a draft
    await db_session.flush()

    assert await queue_slots.next_free_slot(db_session, ws["account"], after=after) == first


async def test_slots_keep_their_local_time_across_a_dst_change(db_session, workspace):
    """A 10:00 Monday slot is 10:00 in March and 10:00 in April."""
    ws = await workspace(tz=NY)
    await _add_slots(db_session, ws["account_id"], [(0, 10, 0)])

    upcoming = await queue_slots.upcoming_slots(
        db_session, ws["account"],
        after=datetime(2026, 3, 1, tzinfo=timezone.utc), limit=6,
    )

    tz = ZoneInfo(NY)
    hours = {
        recurrence.to_local(datetime.fromisoformat(row["run_at"]), tz).hour
        for row in upcoming
    }
    assert hours == {10}
    # And the underlying instants really did shift.
    offsets = {
        datetime.fromisoformat(row["run_at"]).astimezone(tz).utcoffset()
        for row in upcoming
    }
    assert len(offsets) == 2, "expected the window to straddle the transition"


async def test_no_slots_configured_is_its_own_answer(db_session, workspace):
    """Distinct from "the queue is full": one is a setup step, the other is a
    capacity problem, and they need different messages."""
    ws = await workspace()
    with pytest.raises(queue_slots.NoSlotsConfigured):
        await queue_slots.next_free_slot(db_session, ws["account"])


async def test_a_full_queue_raises_rather_than_returning_none(
    db_session, workspace, template_post
):
    ws = await workspace()
    await _add_slots(db_session, ws["account_id"], [(0, 10, 0)])
    after = datetime(2026, 6, 2, 12, tzinfo=timezone.utc)

    # Fill every Monday in the search window.
    for row in await queue_slots.upcoming_slots(
        db_session, ws["account"], after=after, limit=100
    ):
        post = await template_post(ws)
        post.status = PostStatus.SCHEDULED
        post.scheduled_at = datetime.fromisoformat(row["run_at"])
    await db_session.flush()

    with pytest.raises(queue_slots.QueueFull):
        await queue_slots.next_free_slot(db_session, ws["account"], after=after)


async def test_a_slot_in_the_past_is_never_offered(db_session, workspace):
    ws = await workspace()
    await _add_slots(db_session, ws["account_id"], [(d, 10, 0) for d in range(7)])
    now = datetime(2026, 6, 3, 15, tzinfo=timezone.utc)

    rows = await queue_slots.upcoming_slots(db_session, ws["account"], after=now, limit=5)

    assert all(datetime.fromisoformat(row["run_at"]) > now for row in rows)


# ---------------------------------------------------------------------------
# Cloning
# ---------------------------------------------------------------------------

async def test_a_clone_carries_platform_settings_and_variants(
    db_session, workspace, template_post
):
    """The inline duplicate this replaced listed thirteen fields by hand, so a
    duplicated Reel came back a plain feed post and per-platform variants
    disappeared silently."""
    ws = await workspace()
    template = await template_post(
        ws, instagram_post_type="reel", instagram_video_url="https://cdn/x.mp4"
    )
    db_session.add(
        PostVariant(
            id=uuid.uuid4(), post_id=template.id, platform_slug="linkedin",
            content="A more formal version for LinkedIn",
        )
    )
    await db_session.flush()

    clone = await post_cloning.clone_post(db_session, template, user_id=ws["owner"].id)

    assert clone.instagram_post_type == "reel"
    assert clone.instagram_video_url == "https://cdn/x.mp4"
    variants = (
        await db_session.execute(
            select(PostVariant).where(PostVariant.post_id == clone.id)
        )
    ).scalars().all()
    assert [v.platform_slug for v in variants] == ["linkedin"]
    assert variants[0].content == "A more formal version for LinkedIn"


async def test_a_clone_inherits_no_history(db_session, workspace, template_post):
    """A copy that claims the original's published_at, permalink or approval
    is a copy that lies about itself."""
    ws = await workspace()
    template = await template_post(ws)
    template.status = PostStatus.PUBLISHED
    template.published_at = datetime.now(timezone.utc)
    template.posting_results = [{"platform": "instagram", "id": "ig_1"}]
    template.approved_by = ws["owner"].id
    await db_session.flush()

    clone = await post_cloning.clone_post(db_session, template, user_id=ws["owner"].id)

    assert clone.status is PostStatus.DRAFT
    assert clone.published_at is None
    assert clone.posting_results is None
    assert clone.approved_by is None


async def test_a_clone_does_not_share_json_containers(
    db_session, workspace, template_post
):
    """Sharing the list would mean editing the copy edits the original -- and
    a plain JSON column has no change tracking, so that edit would not even be
    saved."""
    ws = await workspace()
    template = await template_post(ws, media_urls=["a.jpg"])

    clone = await post_cloning.clone_post(db_session, template, user_id=ws["owner"].id)
    clone.media_urls.append("b.jpg")

    assert template.media_urls == ["a.jpg"]


# ---------------------------------------------------------------------------
# Materialising a recurring schedule
# ---------------------------------------------------------------------------

async def _schedule(db_session, ws, template, *, rule="FREQ=WEEKLY", tz="UTC",
                    start=None, **extra):
    schedule = RecurringSchedule(
        id=uuid.uuid4(),
        account_id=ws["account_id"],
        created_by=ws["owner"].id,
        template_post_id=template.id,
        rrule=rule,
        timezone=tz,
        starts_at_local=start or datetime(2026, 6, 1, 10, 0),
        status=RecurrenceStatus.ACTIVE,
        **extra,
    )
    await recurring.initialise(schedule)
    db_session.add(schedule)
    await db_session.flush()
    return schedule


async def test_an_occurrence_becomes_its_own_post_with_jobs(
    db_session, workspace, template_post
):
    ws = await workspace()
    template = await template_post(ws)
    schedule = await _schedule(db_session, ws, template)
    schedule.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.flush()

    post = await recurring.materialise(db_session, schedule)
    await db_session.flush()

    assert post is not None and post.id != template.id, (
        "the template was reused instead of copied"
    )
    assert post.status is PostStatus.SCHEDULED
    assert post.content == template.content

    jobs = (
        await db_session.execute(
            select(PublishingJob).where(PublishingJob.post_id == post.id)
        )
    ).scalars().all()
    assert len(jobs) == 1
    assert jobs[0].status is JobStatus.QUEUED


async def test_the_template_is_never_published(db_session, workspace, template_post):
    ws = await workspace()
    template = await template_post(ws)
    schedule = await _schedule(db_session, ws, template)
    schedule.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.flush()

    await recurring.materialise(db_session, schedule)
    await db_session.flush()
    await db_session.refresh(template)

    assert template.status is PostStatus.DRAFT
    assert template.scheduled_at is None


async def test_two_runs_produce_two_distinct_posts(
    db_session, workspace, template_post
):
    """The reason each occurrence is its own row: two runs must leave two
    histories, not one row overwritten twice."""
    ws = await workspace()
    template = await template_post(ws)
    schedule = await _schedule(db_session, ws, template, rule="FREQ=DAILY")
    schedule.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.flush()

    first = await recurring.materialise(db_session, schedule)
    await recurring.advance(db_session, schedule)
    schedule.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    second = await recurring.materialise(db_session, schedule)
    await db_session.flush()

    assert first.id != second.id
    assert schedule.occurrence_count == 2


async def test_compute_next_run_recomputes_rather_than_adding_an_interval(
    db_session, workspace, template_post
):
    """The DST guarantee at the model level.

    The next run after 2 March is 9 March at 10:00 local -- which is a
    *different UTC hour*, because the clocks moved in between. Adding seven
    days to the stored instant would give 15:00 UTC, i.e. 11:00 local, and the
    schedule would post an hour late for the next eight months.
    """
    ws = await workspace(tz=NY)
    template = await template_post(ws)
    schedule = await _schedule(
        db_session, ws, template, rule="FREQ=WEEKLY", tz=NY,
        start=datetime(2026, 3, 2, 10, 0),
    )
    previous = recurrence.to_utc(datetime(2026, 3, 2, 10, 0), ZoneInfo(NY))
    assert previous.hour == 15, "EST: 10:00 New York is 15:00 UTC"

    nxt = recurring.compute_next_run(schedule, after=previous)

    local = recurrence.to_local(nxt, ZoneInfo(NY))
    assert (local.month, local.day) == (3, 9)
    assert local.hour == 10, "the posting hour drifted across the transition"
    assert nxt.hour == 14, "EDT: 10:00 New York is 14:00 UTC"
    assert nxt - previous == timedelta(days=6, hours=23), (
        "a naive seven-day addition would have been wrong by an hour"
    )


async def test_advance_lands_on_the_configured_wall_clock_time(
    db_session, workspace, template_post
):
    """Whatever date advance skips forward to, it is still 10:00 locally."""
    ws = await workspace(tz=NY)
    template = await template_post(ws)
    schedule = await _schedule(
        db_session, ws, template, rule="FREQ=WEEKLY", tz=NY,
        start=datetime(2026, 3, 2, 10, 0),
    )
    schedule.next_run_at = recurrence.to_utc(datetime(2026, 3, 2, 10, 0), ZoneInfo(NY))
    await db_session.flush()

    await recurring.advance(db_session, schedule)

    local = recurrence.to_local(schedule.next_run_at, ZoneInfo(NY))
    assert local.hour == 10 and local.minute == 0
    assert local.weekday() == 0, "still a Monday"
    assert schedule.next_run_at > datetime.now(timezone.utc)


async def test_max_occurrences_completes_the_schedule(
    db_session, workspace, template_post
):
    ws = await workspace()
    template = await template_post(ws)
    schedule = await _schedule(
        db_session, ws, template, rule="FREQ=DAILY", max_occurrences=1
    )
    schedule.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.flush()

    await recurring.materialise(db_session, schedule)
    await recurring.advance(db_session, schedule)

    assert schedule.status is RecurrenceStatus.COMPLETED
    assert schedule.next_run_at is None


async def test_a_deleted_template_cancels_rather_than_looping(
    db_session, workspace, template_post
):
    """Left active, the schedule would retry a missing template every minute
    forever and fill the log with the same failure."""
    ws = await workspace()
    template = await template_post(ws)
    schedule = await _schedule(db_session, ws, template)
    schedule.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    template.deleted_at = datetime.now(timezone.utc)
    await db_session.flush()

    result = await recurring.materialise(db_session, schedule)

    assert result is None
    assert schedule.status is RecurrenceStatus.CANCELLED
    assert schedule.next_run_at is None
    assert "deleted" in (schedule.last_error or "").lower()


async def test_a_backlog_is_skipped_rather_than_flushed(
    db_session, workspace, template_post
):
    """A worker down for a week must not empty seven days of a daily schedule
    into one minute -- that is worse for the customer than the gap."""
    ws = await workspace()
    template = await template_post(ws)
    schedule = await _schedule(db_session, ws, template, rule="FREQ=DAILY")
    schedule.next_run_at = datetime.now(timezone.utc) - timedelta(days=7)
    await db_session.flush()

    await recurring.advance(db_session, schedule)

    assert schedule.next_run_at > datetime.now(timezone.utc)


async def test_run_due_survives_one_broken_schedule(
    db_session, workspace, template_post
):
    """One customer's bad template must not stall every other customer."""
    ws = await workspace()
    good = await _schedule(db_session, ws, await template_post(ws))
    broken_template = await template_post(ws)
    broken = await _schedule(db_session, ws, broken_template)
    broken_template.deleted_at = datetime.now(timezone.utc)

    for schedule in (good, broken):
        schedule.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.flush()

    produced = await recurring.run_due(db_session)

    assert produced == 1
    assert good.occurrence_count == 1
    assert broken.status is RecurrenceStatus.CANCELLED
