"""The dashboard: one payload, one range, resolved in the workspace's timezone.

Range boundaries carry the weight. "Today" for a team in Sydney is not the same
fourteen hours as "today" in UTC, and a dashboard that quietly uses the
server's clock shows an agency the wrong day's numbers every morning.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.post import Post, PostStatus
from app.models.post_performance import PostPerformance
from app.services import dashboard

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"
# A deliberately awkward instant: 2026-06-01 22:00 UTC is already 2026-06-02 in
# Sydney (+10) and still 2026-06-01 in New York (-4).
NOW = datetime(2026, 6, 1, 22, 0, tzinfo=timezone.utc)


@pytest.fixture
async def workspace(
    db_session, user_factory, account_factory, organization_factory
):
    async def _make(tz=None):
        owner = await user_factory(password=PASSWORD)
        organization = await organization_factory(owner)
        account = await account_factory(owner, organization=organization)
        if tz:
            account.settings = {"timezone": tz}
            await db_session.flush()
        return {
            "owner": owner, "account": account, "account_id": account.id,
        }

    return _make


async def _post(db_session, ws, *, status=PostStatus.PUBLISHED, created_at=None, **kw):
    post = Post(
        id=uuid.uuid4(), user_id=ws["owner"].id, account_id=ws["account_id"],
        content="A post", status=status, target_accounts=[], **kw,
    )
    db_session.add(post)
    await db_session.flush()
    if created_at is not None:
        # created_at has a server default, so it is set after the insert.
        post.created_at = created_at
        await db_session.flush()
    return post


# ---------------------------------------------------------------------------
# Range boundaries
# ---------------------------------------------------------------------------

async def test_today_uses_the_workspace_timezone_not_the_server(
    db_session, workspace
):
    """The behaviour this exists for.

    At 22:00 UTC it is already tomorrow in Sydney and still today in New York,
    so the same instant has to produce two different windows.
    """
    sydney = dashboard.resolve_range(
        (await workspace(tz="Australia/Sydney"))["account"], "today", now=NOW
    )
    new_york = dashboard.resolve_range(
        (await workspace(tz="America/New_York"))["account"], "today", now=NOW
    )

    assert sydney.start != new_york.start, (
        "two workspaces on opposite sides of the date line got the same window"
    )
    # Sydney is +10, so its local day started at 14:00 UTC the previous day.
    assert sydney.start == datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
    # New York is -4, so its local day started at 04:00 UTC today.
    assert new_york.start == datetime(2026, 6, 1, 4, 0, tzinfo=timezone.utc)


async def test_the_window_is_half_open(db_session, workspace):
    """A post published at exactly midnight belongs to one day, not two."""
    window = dashboard.resolve_range(
        (await workspace(tz="UTC"))["account"], "today", now=NOW
    )
    assert window.start == datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    assert window.end == datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "key,expected_days",
    [("today", 1), ("yesterday", 1), ("7d", 7), ("30d", 30), ("90d", 90)],
)
async def test_range_lengths(db_session, workspace, key, expected_days):
    """"Last 7 days" means the last seven days a person has lived through,
    which includes the one they are in."""
    window = dashboard.resolve_range(
        (await workspace(tz="UTC"))["account"], key, now=NOW
    )
    assert window.days == expected_days


async def test_yesterday_does_not_include_today(db_session, workspace):
    window = dashboard.resolve_range(
        (await workspace(tz="UTC"))["account"], "yesterday", now=NOW
    )
    assert window.end == datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)


async def test_custom_range_needs_both_ends(db_session, workspace):
    from fastapi import HTTPException

    account = (await workspace())["account"]
    with pytest.raises(HTTPException) as exc:
        dashboard.resolve_range(account, "custom", date_from=NOW.date(), now=NOW)
    assert exc.value.status_code == 400


async def test_custom_range_rejects_a_backwards_window(db_session, workspace):
    from fastapi import HTTPException

    account = (await workspace())["account"]
    with pytest.raises(HTTPException):
        dashboard.resolve_range(
            account, "custom",
            date_from=NOW.date(), date_to=NOW.date() - timedelta(days=3), now=NOW,
        )


async def test_an_unknown_range_is_refused(db_session, workspace):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        dashboard.resolve_range((await workspace())["account"], "last_week", now=NOW)
    assert "Unknown range" in exc.value.detail


async def test_an_unusable_timezone_falls_back_rather_than_failing(
    db_session, workspace
):
    """A wrong-by-hours chart beats no chart; the fallback is logged."""
    ws = await workspace(tz="Mars/Olympus_Mons")
    window = dashboard.resolve_range(ws["account"], "today", now=NOW)
    assert window.timezone_name == "UTC"


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------

async def test_payload_shape(client, auth_header, db_session, workspace):
    ws = await workspace(tz="UTC")
    response = await client.get(
        f"/api/v1/accounts/{ws['account_id']}/settings/dashboard?range=7d",
        headers=auth_header(ws["owner"]),
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert set(body) == {
        "range", "connected_accounts", "posts", "pending_approvals",
        "engagement", "followers", "top_posts", "recent_activity",
    }
    assert set(body["range"]) == {"key", "start", "end", "days", "timezone"}
    assert set(body["posts"]) >= {"published", "scheduled", "failed", "drafts"}
    assert body["range"]["timezone"] == "UTC"


async def test_counts_respect_the_range(client, auth_header, db_session, workspace):
    ws = await workspace(tz="UTC")
    inside = datetime.now(timezone.utc) - timedelta(days=2)
    outside = datetime.now(timezone.utc) - timedelta(days=40)
    await _post(db_session, ws, status=PostStatus.PUBLISHED, created_at=inside)
    await _post(db_session, ws, status=PostStatus.FAILED, created_at=inside)
    await _post(db_session, ws, status=PostStatus.PUBLISHED, created_at=outside)

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/settings/dashboard?range=7d",
            headers=auth_header(ws["owner"]),
        )
    ).json()
    assert body["posts"]["published"] == 1
    assert body["posts"]["failed"] == 1

    wider = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/settings/dashboard?range=90d",
            headers=auth_header(ws["owner"]),
        )
    ).json()
    assert wider["posts"]["published"] == 2


async def test_pending_approvals_ignore_the_range(
    client, auth_header, db_session, workspace
):
    """A post submitted three weeks ago is still waiting. Hiding it because it
    falls outside "last 7 days" is how a queue silently grows."""
    ws = await workspace(tz="UTC")
    await _post(
        db_session, ws, status=PostStatus.IN_REVIEW,
        created_at=datetime.now(timezone.utc) - timedelta(days=40),
    )

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/settings/dashboard?range=7d",
            headers=auth_header(ws["owner"]),
        )
    ).json()
    assert body["pending_approvals"] == 1


async def test_engagement_rate_is_null_with_nothing_to_divide_by(
    client, auth_header, db_session, workspace
):
    """0% reads as "bad"; null reads as "no data"."""
    ws = await workspace(tz="UTC")
    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/settings/dashboard",
            headers=auth_header(ws["owner"]),
        )
    ).json()
    assert body["engagement"]["engagement_rate"] is None


async def test_engagement_totals_and_top_posts(
    client, auth_header, db_session, workspace
):
    ws = await workspace(tz="UTC")
    for likes in (5, 50):
        post = await _post(db_session, ws)
        db_session.add(
            PostPerformance(
                id=uuid.uuid4(), post_id=post.id, platform_type="instagram",
                impressions=1000, reach=500, likes=likes, comments=1,
                shares=0, saves=0, clicks=0, video_views=0,
            )
        )
    await db_session.flush()

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/settings/dashboard",
            headers=auth_header(ws["owner"]),
        )
    ).json()
    assert body["engagement"]["impressions"] == 2000
    assert body["engagement"]["likes"] == 55
    assert body["engagement"]["engagement_rate"] is not None

    top = body["top_posts"]
    assert len(top) == 2
    assert top[0]["engagement"] >= top[1]["engagement"], "top posts are not sorted"


async def test_follower_growth_is_null_until_daily_snapshots_exist(
    client, auth_header, db_session, workspace
):
    """Growth needs analytics_daily (1.11). Showing a flat 0% would be a claim
    we cannot support."""
    ws = await workspace(tz="UTC")
    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/settings/dashboard",
            headers=auth_header(ws["owner"]),
        )
    ).json()
    assert body["followers"]["growth"] is None
    assert body["followers"]["growth_available"] is False
    assert isinstance(body["followers"]["total"], int)


async def test_connected_accounts_carry_health(
    client, auth_header, db_session, workspace, social_account_factory
):
    ws = await workspace(tz="UTC")
    await social_account_factory(ws["owner"], ws["account"])
    await db_session.flush()

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/settings/dashboard",
            headers=auth_header(ws["owner"]),
        )
    ).json()
    assert body["connected_accounts"]["total"] == 1
    assert body["connected_accounts"]["unknown"] == 1
    assert body["connected_accounts"]["accounts"][0]["health"] == "unknown"


# ---------------------------------------------------------------------------
# Tenancy
# ---------------------------------------------------------------------------

async def test_another_workspaces_data_is_not_counted(
    client, auth_header, db_session, workspace
):
    mine = await workspace(tz="UTC")
    theirs = await workspace(tz="UTC")
    await _post(db_session, theirs, status=PostStatus.PUBLISHED)
    await _post(db_session, theirs, status=PostStatus.IN_REVIEW)

    body = (
        await client.get(
            f"/api/v1/accounts/{mine['account_id']}/settings/dashboard",
            headers=auth_header(mine["owner"]),
        )
    ).json()
    assert body["posts"]["published"] == 0
    assert body["pending_approvals"] == 0
    assert body["top_posts"] == []


async def test_a_non_member_is_refused(
    client, auth_header, workspace, user_factory
):
    ws = await workspace()
    stranger = await user_factory()
    response = await client.get(
        f"/api/v1/accounts/{ws['account_id']}/settings/dashboard",
        headers=auth_header(stranger),
    )
    assert response.status_code == 403
