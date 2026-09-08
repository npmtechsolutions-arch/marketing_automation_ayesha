"""Suggested posting times, and the line between measured and assumed.

This feature replaced a heatmap drawn from ``Math.random()`` captioned with a
fabricated 22% uplift. The tests that matter here are therefore not about the
arithmetic -- they are about whether a reader can tell a measurement from a
convention. Every one of them checks a flag or a word that carries that
distinction.
"""

import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models.post import Post, PostStatus
from app.models.post_performance import PostPerformance
from app.services import best_times

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


@pytest.fixture
async def workspace(
    db_session, user_factory, account_factory, organization_factory,
    social_account_factory,
):
    async def _make(tz="UTC", slug="instagram"):
        owner = await user_factory(password=PASSWORD)
        organization = await organization_factory(owner)
        account = await account_factory(owner, organization=organization)
        account.settings = {"timezone": tz}
        await db_session.flush()
        connection = await social_account_factory(owner, account, slug=slug)
        return {
            "owner": owner, "account": account, "account_id": account.id,
            "connection": connection, "connection_id": connection.id,
        }

    return _make


@pytest.fixture
async def published(db_session):
    """A published post with performance, at a given local weekday and hour."""

    async def _make(ws, *, weekday, hour, likes=10, days_ago=7, platform="instagram",
                    tz="UTC", target=True):
        zone = ZoneInfo(tz)
        # Walk back to the most recent matching weekday inside the window.
        when = datetime.now(zone) - timedelta(days=days_ago)
        while when.weekday() != weekday:
            when -= timedelta(days=1)
        when = when.replace(hour=hour, minute=0, second=0, microsecond=0)

        post = Post(
            id=uuid.uuid4(), user_id=ws["owner"].id, account_id=ws["account_id"],
            content="A post", status=PostStatus.PUBLISHED,
            published_at=when.astimezone(timezone.utc),
            target_accounts=(
                [{"social_account_id": str(ws["connection_id"])}] if target else []
            ),
        )
        db_session.add(post)
        await db_session.flush()
        db_session.add(PostPerformance(
            id=uuid.uuid4(), post_id=post.id, platform_type=platform,
            likes=likes, comments=0, shares=0, saves=0, reach=100,
            impressions=200, clicks=0, video_views=0,
        ))
        await db_session.flush()
        return post

    return _make


# ---------------------------------------------------------------------------
# The fallback, which is the point
# ---------------------------------------------------------------------------

async def test_no_history_falls_back_and_says_so(db_session, workspace):
    ws = await workspace()

    report = await best_times.analyse(db_session, ws["account"])

    assert report["source"] == "default"
    assert report["sample"]["posts"] == 0
    assert all(s["observed"] is False for s in report["suggestions"])
    assert "usual" in report["explanation"]


async def test_sparse_history_still_falls_back(db_session, workspace, published):
    """Three posts that happened to land on a Tuesday would otherwise make
    Tuesday the recommendation forever."""
    ws = await workspace()
    for offset in range(3):
        await published(ws, weekday=1, hour=11, days_ago=7 + offset * 7)

    report = await best_times.analyse(db_session, ws["account"])

    assert report["sample"]["posts"] == 3
    assert report["sample"]["sufficient"] is False
    assert report["source"] == "default"
    assert str(best_times.MIN_SAMPLE_POSTS) in report["explanation"]


async def test_the_threshold_is_the_boundary(db_session, workspace, published):
    ws = await workspace()
    for index in range(best_times.MIN_SAMPLE_POSTS):
        await published(ws, weekday=index % 7, hour=9 + (index % 3), days_ago=3 + index)

    report = await best_times.analyse(db_session, ws["account"])

    assert report["sample"]["posts"] == best_times.MIN_SAMPLE_POSTS
    assert report["sample"]["sufficient"] is True
    assert report["source"] == "observed"


async def test_defaults_differ_by_platform(db_session, workspace):
    """A generic list for every network would be a worse lie than none."""
    instagram = await workspace(slug="instagram")
    linkedin = await workspace(slug="linkedin")

    ig = await best_times.analyse(
        db_session, instagram["account"],
        social_account_id=instagram["connection_id"],
    )
    li = await best_times.analyse(
        db_session, linkedin["account"],
        social_account_id=linkedin["connection_id"],
    )

    assert [(s["weekday"], s["hour"]) for s in ig["suggestions"]] != \
           [(s["weekday"], s["hour"]) for s in li["suggestions"]]


async def test_an_unknown_platform_gets_the_generic_defaults():
    assert best_times.default_slots("myspace") == best_times.GENERIC_SLOTS
    assert best_times.default_slots(None) == best_times.GENERIC_SLOTS


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

async def test_the_best_slot_wins_on_average_not_volume(db_session, workspace, published):
    """A slot used twenty times out-totals a better one used twice. The
    question is where the next post should go, not where most have gone."""
    ws = await workspace()
    # The two must genuinely disagree, or the test passes against either
    # ranking. Monday carries the larger *total*; Wednesday the better average.
    #   Monday    20 posts x 10 = 200 total, 10 each
    #   Wednesday  3 posts x 50 = 150 total, 50 each
    for offset in range(20):
        await published(ws, weekday=0, hour=9, likes=10, days_ago=4 + offset)
    for offset in range(3):
        await published(ws, weekday=2, hour=18, likes=50, days_ago=5 + offset * 7)

    report = await best_times.analyse(db_session, ws["account"])

    assert report["source"] == "observed"
    top = report["suggestions"][0]
    assert (top["weekday"], top["hour"]) == (2, 18)
    assert top["observed"] is True


async def test_a_slot_tried_once_is_not_promoted(db_session, workspace, published):
    """One spectacular post is an anecdote, not a pattern."""
    ws = await workspace()
    for offset in range(12):
        await published(ws, weekday=0, hour=9, likes=20, days_ago=4 + offset)
    await published(ws, weekday=5, hour=3, likes=5000, days_ago=6)

    report = await best_times.analyse(db_session, ws["account"])

    assert (report["suggestions"][0]["weekday"], report["suggestions"][0]["hour"]) != (5, 3)


async def test_a_never_tried_slot_scores_null_not_zero(db_session, workspace, published):
    """Zero says "we posted here and nobody engaged", which is a different and
    false claim."""
    ws = await workspace()
    for offset in range(12):
        await published(ws, weekday=0, hour=9, days_ago=4 + offset)

    report = await best_times.analyse(db_session, ws["account"])
    untried = next(
        c for c in report["heatmap"] if (c["weekday"], c["hour"]) == (6, 3)
    )

    assert untried["score"] is None
    assert untried["posts"] == 0
    assert untried["observed"] is False


async def test_the_heatmap_covers_the_whole_week(db_session, workspace):
    ws = await workspace()
    report = await best_times.analyse(db_session, ws["account"])

    assert len(report["heatmap"]) == 7 * 24


async def test_hours_are_on_the_workspace_clock(db_session, workspace, published):
    """"Post at 9am" means 9am where the audience is. A UTC hour would be
    wrong for most workspaces."""
    ws = await workspace(tz="Australia/Sydney")
    for offset in range(12):
        await published(ws, weekday=2, hour=9, days_ago=4 + offset, tz="Australia/Sydney")

    report = await best_times.analyse(db_session, ws["account"])

    assert report["scope"]["timezone"] == "Australia/Sydney"
    assert (report["suggestions"][0]["weekday"], report["suggestions"][0]["hour"]) == (2, 9)


async def test_posts_outside_the_window_are_ignored(db_session, workspace, published):
    ws = await workspace()
    for offset in range(12):
        await published(ws, weekday=0, hour=9, days_ago=200 + offset)

    report = await best_times.analyse(db_session, ws["account"], window_days=84)

    assert report["sample"]["posts"] == 0
    assert report["source"] == "default"


async def test_attribution_is_per_connection(db_session, workspace, published):
    """A post sent to two networks contributes each platform's numbers to that
    platform's account only."""
    ws = await workspace(slug="instagram")
    for offset in range(12):
        await published(ws, weekday=0, hour=9, days_ago=4 + offset, platform="facebook")

    scoped = await best_times.analyse(
        db_session, ws["account"], social_account_id=ws["connection_id"]
    )

    # The performance rows are Facebook's; the connection is Instagram's.
    assert scoped["sample"]["posts"] == 0
    assert scoped["source"] == "default"


async def test_a_connection_from_another_workspace_is_refused(
    db_session, workspace
):
    ws = await workspace()
    other = await workspace()

    with pytest.raises(ValueError):
        await best_times.analyse(
            db_session, ws["account"], social_account_id=other["connection_id"]
        )


# ---------------------------------------------------------------------------
# Turning a slot into a real datetime
# ---------------------------------------------------------------------------

async def test_the_next_occurrence_is_in_the_future_on_the_right_day():
    tz = ZoneInfo("America/New_York")
    when = best_times.next_occurrence(2, 14, tz)

    assert when > datetime.now(timezone.utc)
    local = when.astimezone(tz)
    assert (local.weekday(), local.hour) == (2, 14)


async def test_the_next_occurrence_uses_the_workspace_clock():
    """Computed through the same resolution recurring schedules use, so a slot
    inside a spring-forward gap lands on an instant that exists."""
    sydney = best_times.next_occurrence(1, 10, ZoneInfo("Australia/Sydney"))
    london = best_times.next_occurrence(1, 10, ZoneInfo("Europe/London"))

    assert sydney != london


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

async def test_the_endpoint_labels_its_source(client, auth_header, workspace):
    ws = await workspace()

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/analytics/best-times",
            headers=auth_header(ws["owner"]),
        )
    ).json()

    assert body["source"] == "default"
    assert body["sample"]["sufficient"] is False
    assert all(cell["observed"] is False for cell in body["heatmap"])


async def test_the_slots_endpoint_returns_real_datetimes(
    client, auth_header, workspace
):
    ws = await workspace()

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/analytics/best-times/next",
            headers=auth_header(ws["owner"]),
        )
    ).json()

    assert body["source"] == "default"
    assert len(body["slots"]) == 3
    for slot in body["slots"]:
        assert datetime.fromisoformat(slot["run_at"]) > datetime.now(timezone.utc)
        assert slot["observed"] is False


async def test_another_workspace_cannot_read_it(client, auth_header, workspace):
    ws = await workspace()
    other = await workspace()

    response = await client.get(
        f"/api/v1/accounts/{other['account_id']}/analytics/best-times",
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code in (403, 404)
