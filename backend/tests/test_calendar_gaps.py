"""Gap analysis, on a workspace that is deliberately not on UTC.

Every fixture here uses **Australia/Sydney**. That is not decoration: a gap is
a statement about a *day*, and a day boundary computed on the wrong clock puts
the gap on the wrong date. On UTC a timezone bug is invisible, which is exactly
how the calendar shipped rendering a 21:29 UTC post as "2:59 AM" on the
following day for a viewer in India.

Sydney is UTC+10/+11, so a post at 23:00 UTC is already *tomorrow* there. Any
test that gets the day right here would get it wrong under a naive
implementation.
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.models.post import Post, PostStatus
from app.models.recurring_schedule import QueueSlot
from app.services import calendar_gaps

PASSWORD = "TestPass123!"
SYDNEY = "Australia/Sydney"


@pytest.fixture
async def workspace(
    db_session, user_factory, account_factory, organization_factory,
    social_account_factory,
):
    async def _make(tz=SYDNEY, slugs=("instagram",)):
        owner = await user_factory(password=PASSWORD)
        organization = await organization_factory(owner)
        account = await account_factory(owner, organization=organization)
        account.settings = {"timezone": tz}
        await db_session.flush()
        socials = [
            await social_account_factory(owner, account, slug=slug) for slug in slugs
        ]
        return {
            "owner": owner, "organization": organization,
            "account": account, "socials": socials,
        }

    return _make


@pytest.fixture
async def queue_slot(db_session):
    async def _make(account, *, weekday: int, hour: int):
        slot = QueueSlot(
            id=uuid.uuid4(), account_id=account.id,
            weekday=weekday, time_local=time(hour=hour), is_active=True,
        )
        db_session.add(slot)
        await db_session.flush()
        return slot

    return _make


@pytest.fixture
async def scheduled_post(db_session):
    async def _make(ws, *, at: datetime, status=PostStatus.SCHEDULED, targets=None):
        post = Post(
            id=uuid.uuid4(), user_id=ws["owner"].id, account_id=ws["account"].id,
            content="already there", status=status, scheduled_at=at,
            target_accounts=targets if targets is not None else [
                {"social_account_id": str(ws["socials"][0].id)}
            ],
        )
        db_session.add(post)
        await db_session.flush()
        return post

    return _make


# A fixed "now" so nothing depends on when the suite runs. Sydney is UTC+11 in
# November, so this instant is 2026-11-02 09:00 local -- a Monday morning.
NOW = datetime(2026, 11, 1, 22, 0, tzinfo=timezone.utc)
WEEK_FROM = date(2026, 11, 2)
WEEK_TO = date(2026, 11, 8)


# ---------------------------------------------------------------------------
# Gap maths
# ---------------------------------------------------------------------------

async def test_an_empty_queue_slot_is_a_gap(
    db_session, workspace, queue_slot
):
    ws = await workspace()
    # Wednesday 10:00 Sydney.
    await queue_slot(ws["account"], weekday=2, hour=10)

    result = await calendar_gaps.analyse(
        db_session, ws["account"], WEEK_FROM, WEEK_TO, now=NOW
    )

    queue = [g for g in result["gaps"] if g["kind"] == "queue_slot"]
    assert len(queue) == 1
    gap = queue[0]
    assert gap["local_datetime"].startswith("2026-11-04T10:00")
    assert gap["slot_source"] == "queue"
    # 10:00 Sydney on 4 November is 23:00 UTC on the 3rd. Getting this right
    # is the difference between a correct gap and one a day early.
    assert gap["run_at"].startswith("2026-11-03T23:00")


async def test_a_filled_queue_slot_is_not_a_gap(
    db_session, workspace, queue_slot, scheduled_post
):
    ws = await workspace()
    await queue_slot(ws["account"], weekday=2, hour=10)
    # The same instant, expressed in UTC.
    await scheduled_post(ws, at=datetime(2026, 11, 3, 23, 0, tzinfo=timezone.utc))

    result = await calendar_gaps.analyse(
        db_session, ws["account"], WEEK_FROM, WEEK_TO, now=NOW
    )

    assert [g for g in result["gaps"] if g["kind"] == "queue_slot"] == []


async def test_occupancy_is_compared_on_the_workspace_clock_not_the_servers(
    db_session, workspace, queue_slot, scheduled_post
):
    """The test the whole file exists for.

    A post at 23:00 UTC on 3 November is 10:00 Sydney on the **4th**. An
    implementation that bucketed by the UTC date would put it on the 3rd, leave
    the 4th looking empty, and report a gap for a slot that is taken.
    """
    ws = await workspace()
    await queue_slot(ws["account"], weekday=2, hour=10)   # Wednesday, local
    post_at = datetime(2026, 11, 3, 23, 0, tzinfo=timezone.utc)
    await scheduled_post(ws, at=post_at)

    result = await calendar_gaps.analyse(
        db_session, ws["account"], WEEK_FROM, WEEK_TO, now=NOW
    )

    # Wednesday the 4th is occupied, so no queue gap and no best-time gap there.
    assert all(
        not g["local_datetime"].startswith("2026-11-04") for g in result["gaps"]
    )
    assert result["summary"]["scheduled_posts"] == 1


async def test_a_slot_that_has_already_passed_is_not_a_gap(
    db_session, workspace, queue_slot
):
    ws = await workspace()
    # Monday 08:00 Sydney is 21:00 UTC Sunday -- an hour before NOW.
    await queue_slot(ws["account"], weekday=0, hour=8)

    result = await calendar_gaps.analyse(
        db_session, ws["account"], WEEK_FROM, WEEK_TO, now=NOW
    )

    monday = [
        g for g in result["gaps"]
        if g["kind"] == "queue_slot" and g["local_datetime"].startswith("2026-11-02")
    ]
    assert monday == [], "history is not a gap to fill"


async def test_a_draft_does_not_fill_a_slot(
    db_session, workspace, queue_slot, scheduled_post
):
    """A draft is not on the calendar, which is the point of the analysis."""
    ws = await workspace()
    await queue_slot(ws["account"], weekday=2, hour=10)
    await scheduled_post(
        ws, at=datetime(2026, 11, 3, 23, 0, tzinfo=timezone.utc),
        status=PostStatus.DRAFT,
    )

    result = await calendar_gaps.analyse(
        db_session, ws["account"], WEEK_FROM, WEEK_TO, now=NOW
    )

    assert len([g for g in result["gaps"] if g["kind"] == "queue_slot"]) == 1


async def test_best_time_gaps_are_labelled_default_without_history(
    db_session, workspace
):
    """No history means the suggestion is a convention, and says so."""
    ws = await workspace()

    result = await calendar_gaps.analyse(
        db_session, ws["account"], WEEK_FROM, WEEK_TO, now=NOW
    )

    best = [g for g in result["gaps"] if g["kind"] == "best_time"]
    assert best, "an empty week should suggest something"
    assert all(g["slot_source"] == "default" for g in best)
    assert any("usual instagram posting time" in g["reason"] for g in best)
    assert result["slot_sources"]["instagram"]["source"] == "default"


async def test_a_day_with_a_post_gets_no_best_time_suggestion(
    db_session, workspace, scheduled_post
):
    """Per day, not per hour: a second post two hours later is noise."""
    ws = await workspace()
    # 10:00 Sydney Thursday 5 Nov == 23:00 UTC Wednesday 4 Nov.
    await scheduled_post(ws, at=datetime(2026, 11, 4, 23, 0, tzinfo=timezone.utc))

    result = await calendar_gaps.analyse(
        db_session, ws["account"], WEEK_FROM, WEEK_TO, now=NOW
    )

    assert all(
        not g["local_datetime"].startswith("2026-11-05")
        for g in result["gaps"] if g["kind"] == "best_time"
    )


async def test_the_range_is_bounded(db_session, workspace):
    ws = await workspace()

    with pytest.raises(ValueError):
        await calendar_gaps.analyse(
            db_session, ws["account"], date(2026, 1, 1), date(2026, 12, 31), now=NOW
        )
    with pytest.raises(ValueError):
        await calendar_gaps.analyse(
            db_session, ws["account"], date(2026, 11, 8), date(2026, 11, 2), now=NOW
        )


# ---------------------------------------------------------------------------
# Stale platforms
# ---------------------------------------------------------------------------

async def test_a_connected_platform_with_nothing_recent_is_flagged(
    db_session, workspace
):
    ws = await workspace(slugs=("instagram", "twitter"))

    result = await calendar_gaps.analyse(
        db_session, ws["account"], WEEK_FROM, WEEK_TO, now=NOW
    )

    stale = {s["platform"] for s in result["stale_platforms"]}
    assert stale == {"instagram", "twitter"}
    assert all(str(calendar_gaps.STALE_AFTER_DAYS) in s["reason"]
               for s in result["stale_platforms"])


async def test_a_platform_with_a_recent_post_is_not_stale(
    db_session, workspace, scheduled_post
):
    ws = await workspace(slugs=("instagram", "twitter"))
    instagram, twitter = ws["socials"]
    await scheduled_post(
        ws, at=NOW - timedelta(days=2), status=PostStatus.PUBLISHED,
        targets=[{"social_account_id": str(instagram.id)}],
    )

    result = await calendar_gaps.analyse(
        db_session, ws["account"], WEEK_FROM, WEEK_TO, now=NOW
    )

    stale = {s["platform"] for s in result["stale_platforms"]}
    assert stale == {"twitter"}, "instagram posted two days ago"


async def test_a_post_older_than_the_window_does_not_clear_staleness(
    db_session, workspace, scheduled_post
):
    ws = await workspace()
    await scheduled_post(
        ws,
        at=NOW - timedelta(days=calendar_gaps.STALE_AFTER_DAYS + 3),
        status=PostStatus.PUBLISHED,
    )

    result = await calendar_gaps.analyse(
        db_session, ws["account"], WEEK_FROM, WEEK_TO, now=NOW
    )

    assert [s["platform"] for s in result["stale_platforms"]] == ["instagram"]


async def test_a_scheduled_future_post_keeps_a_platform_off_the_stale_list(
    db_session, workspace, scheduled_post
):
    """Silent for two weeks but something is queued -- that is not neglect."""
    ws = await workspace()
    await scheduled_post(ws, at=NOW + timedelta(days=3))

    result = await calendar_gaps.analyse(
        db_session, ws["account"], WEEK_FROM, WEEK_TO, now=NOW
    )

    assert result["stale_platforms"] == []


# ---------------------------------------------------------------------------
# The endpoints
# ---------------------------------------------------------------------------

def _url(account_id, suffix=""):
    return f"/api/v1/accounts/{account_id}/calendar{suffix}"


@pytest.fixture
def patched_provider(monkeypatch):
    """The plan generator's provider, stubbed."""
    from app.services import content_plan

    def _install(count=5):
        async def _call(user_prompt, system_prompt, model):
            items = ", ".join(
                f'{{"index": {i}, "content": "Filled slot {i}", "hashtags": ["ops"]}}'
                for i in range(count)
            )
            return f"[{items}]", 5, 9

        real = content_plan.generate_copy

        async def _generate(db, system, user, **kwargs):
            kwargs.pop("callers", None)
            return await real(db, system, user, callers={
                "openai": _call, "anthropic": _call, "gemini": _call,
            }, **kwargs)

        monkeypatch.setattr(content_plan, "generate_copy", _generate)
        monkeypatch.setattr(
            content_plan.ai_assist, "resolve_provider",
            lambda requested=None: ("openai", "gpt-4o-mini"),
        )

    return _install


async def test_the_suggestions_endpoint_is_readable_and_unmetered(
    client, auth_header, workspace, queue_slot, set_limit,
):
    """Looking at your own calendar does not cost an AI request."""
    from app.services import entitlement_service as ent

    ws = await workspace()
    await queue_slot(ws["account"], weekday=2, hour=10)
    # No allowance at all: a metered endpoint would refuse here.
    await set_limit(ws["organization"], ent.AI_REQUESTS_PER_MONTH, 0)

    response = await client.get(
        _url(ws["account"].id, "/suggestions"),
        params={"from": WEEK_FROM.isoformat(), "to": WEEK_TO.isoformat()},
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["window"]["timezone"] == SYDNEY
    assert body["gaps"]
    assert {g["slot_source"] for g in body["gaps"]} <= {"queue", "observed", "default"}


async def test_an_impossible_range_is_refused_with_a_reason(
    client, auth_header, workspace,
):
    ws = await workspace()

    response = await client.get(
        _url(ws["account"].id, "/suggestions"),
        params={"from": "2026-11-08", "to": "2026-11-02"},
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code == 422
    assert "before its start" in response.json()["detail"]


async def test_suggest_fill_creates_proposals_not_posts(
    client, auth_header, db_session, workspace, patched_provider, set_limit,
):
    """The guarantee, restated at the smaller scale.

    Filling a gap produces a proposal. Nothing is scheduled into the gap and
    nothing is published; a person still accepts it, through the same endpoint
    the monthly plan uses.
    """
    from sqlalchemy import func, select

    from app.services import entitlement_service as ent

    ws = await workspace()
    await set_limit(ws["organization"], ent.AI_REQUESTS_PER_MONTH, 50)
    patched_provider()

    response = await client.post(
        _url(ws["account"].id, "/suggest-fill"),
        headers=auth_header(ws["owner"]),
        json={
            "goal": "engagement",
            "slots": [{
                "local_datetime": "2026-11-04T10:00:00",
                "social_account_id": str(ws["socials"][0].id),
            }],
        },
    )

    assert response.status_code == 201, response.text
    plan = response.json()
    assert len(plan["items"]) == 1
    item = plan["items"][0]
    assert item["status"] == "proposed"
    assert item["post_id"] is None
    # 10:00 Sydney, stored as the instant it actually is.
    assert item["scheduled_at"].startswith("2026-11-03T23:00")

    # And no post exists yet.
    posts = (await db_session.execute(select(func.count(Post.id)))).scalar()
    assert posts == 0


async def test_a_filled_proposal_is_accepted_through_the_plan_endpoint(
    client, auth_header, db_session, workspace, patched_provider, set_limit,
):
    """One acceptance path, not two.

    A second path to a draft would be a second chance to get "never schedule"
    wrong, so suggest-fill stores a plan and reuses the monthly plan's accept.
    """
    from sqlalchemy import select

    from app.services import entitlement_service as ent

    ws = await workspace()
    await set_limit(ws["organization"], ent.AI_REQUESTS_PER_MONTH, 50)
    await set_limit(ws["organization"], ent.POSTS_PER_MONTH, 50)
    patched_provider()

    plan = (await client.post(
        _url(ws["account"].id, "/suggest-fill"),
        headers=auth_header(ws["owner"]),
        json={"slots": [{
            "local_datetime": "2026-11-04T10:00:00",
            "social_account_id": str(ws["socials"][0].id),
        }]},
    )).json()

    accepted = await client.post(
        f"/api/v1/accounts/{ws['account'].id}/ai/monthly-plan/{plan['id']}/accept",
        headers=auth_header(ws["owner"]),
        json={"item_ids": [plan["items"][0]["id"]]},
    )

    assert accepted.status_code == 200, accepted.text
    post = (
        await db_session.execute(
            select(Post).where(
                Post.id == uuid.UUID(accepted.json()["created"][0]["post_id"])
            )
        )
    ).scalar_one()
    assert post.status is PostStatus.DRAFT
    assert post.scheduled_at is None, "accepting a gap fill must not schedule it"


async def test_a_slot_with_an_offset_is_refused(
    client, auth_header, workspace, patched_provider, set_limit,
):
    """local_datetime is a reading on the workspace's clock, not an instant.

    Accepting one with an offset would mean two callers sending the same wall
    clock got different slots -- the bug the composer's schedule field had.
    """
    from app.services import entitlement_service as ent

    ws = await workspace()
    await set_limit(ws["organization"], ent.AI_REQUESTS_PER_MONTH, 50)
    patched_provider()

    response = await client.post(
        _url(ws["account"].id, "/suggest-fill"),
        headers=auth_header(ws["owner"]),
        json={"slots": [{
            "local_datetime": "2026-11-04T10:00:00+05:30",
            "social_account_id": str(ws["socials"][0].id),
        }]},
    )

    assert response.status_code == 422
    assert "workspace's clock" in response.json()["detail"]


async def test_filling_a_gap_for_an_unconnected_account_is_refused(
    client, auth_header, workspace, patched_provider, set_limit,
):
    from app.services import entitlement_service as ent

    ws = await workspace()
    other = await workspace()
    await set_limit(ws["organization"], ent.AI_REQUESTS_PER_MONTH, 50)
    patched_provider()

    response = await client.post(
        _url(ws["account"].id, "/suggest-fill"),
        headers=auth_header(ws["owner"]),
        json={"slots": [{
            "local_datetime": "2026-11-04T10:00:00",
            "social_account_id": str(other["socials"][0].id),
        }]},
    )

    assert response.status_code == 404


async def test_suggest_fill_costs_the_same_as_a_plan(
    client, auth_header, workspace, patched_provider, set_limit,
):
    """It runs the same generator, so it is priced the same."""
    from app.services import entitlement_service as ent

    ws = await workspace()
    await set_limit(ws["organization"], ent.AI_REQUESTS_PER_MONTH, 4)
    patched_provider()

    response = await client.post(
        _url(ws["account"].id, "/suggest-fill"),
        headers=auth_header(ws["owner"]),
        json={"slots": [{
            "local_datetime": "2026-11-04T10:00:00",
            "social_account_id": str(ws["socials"][0].id),
        }]},
    )

    assert response.status_code in (402, 403, 429), response.text
