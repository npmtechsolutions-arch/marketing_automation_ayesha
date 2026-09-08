"""Two contract fixes from the walkthrough defect log.

**Scheduling happens on the workspace's clock.** The composer used to build a
UTC instant in the browser, so the time a person typed was interpreted in
whatever timezone their laptop was in. An agency in London scheduling for a
Sydney client set a time eleven hours out, and the error moved by an hour
whenever either side's clocks changed. These tests use a workspace timezone
deliberately unlike any plausible machine setting, so a regression that
reintroduces local-machine interpretation cannot pass by coincidence.

**Writes refuse unknown fields.** ``PostResponse`` returns ``target_accounts``
while writes took ``target_account_ids``; sending back the field you were just
given stored nothing and returned 200 -- the settings-writer bug at the level
of the contract. Unknown keys are now a 422, and the response's own name is
accepted as an alias so read-modify-write works.
"""

import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models.post import Post, PostStatus

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"

# Chosen because it is +11/+10 and southern-hemisphere: an implementation that
# fell back to the machine's timezone, or to UTC, gives a different answer.
SYDNEY = "Australia/Sydney"



def _utc(value: datetime) -> datetime:
    """Stored instants, as aware UTC.

    The column is ``DateTime(timezone=True)``, which Postgres honours and the
    SQLite harness does not -- values come back naive there. Normalising in the
    test keeps the assertions about the product rather than about the harness.
    """
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@pytest.fixture
async def workspace(
    db_session, user_factory, account_factory, organization_factory,
    social_account_factory,
):
    async def _make(tz=SYDNEY):
        owner = await user_factory(password=PASSWORD)
        organization = await organization_factory(owner)
        account = await account_factory(owner, organization=organization)
        account.settings = {"timezone": tz}
        await db_session.flush()
        social = await social_account_factory(owner, account, slug="instagram")
        return {
            "owner": owner, "account": account, "account_id": account.id,
            "social_id": social.id,
        }

    return _make


@pytest.fixture
async def draft(db_session):
    async def _make(ws):
        post = Post(
            id=uuid.uuid4(),
            user_id=ws["owner"].id,
            account_id=ws["account_id"],
            content="Scheduled content",
            status=PostStatus.DRAFT,
            target_accounts=[{"social_account_id": str(ws["social_id"])}],
        )
        db_session.add(post)
        await db_session.flush()
        return post

    return _make


def _url(ws, post):
    return f"/api/v1/accounts/{ws['account_id']}/posts/{post.id}/schedule"


# ---------------------------------------------------------------------------
# Scheduling on the workspace's clock
# ---------------------------------------------------------------------------

async def test_a_local_time_is_resolved_in_the_workspace_timezone(
    client, auth_header, workspace, draft, db_session
):
    """10:00 means 10:00 in Sydney, whatever the caller's machine thinks."""
    ws = await workspace()
    post = await draft(ws)
    tz = ZoneInfo(SYDNEY)
    target_day = (datetime.now(tz) + timedelta(days=10)).date()
    local = f"{target_day.isoformat()}T10:00:00"

    response = await client.post(
        f"{_url(ws, post)}?scheduled_at_local={local}",
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code == 200, response.text
    await db_session.refresh(post)
    rendered = _utc(post.scheduled_at).astimezone(tz)
    assert (rendered.hour, rendered.minute) == (10, 0)
    assert rendered.date() == target_day


async def test_the_stored_instant_is_not_the_naive_time_read_as_utc(
    client, auth_header, workspace, draft, db_session
):
    """The specific regression.

    Sydney is ten or eleven hours ahead, so 10:00 local is 23:00 or midnight
    UTC the day before. If the stored instant comes back as 10:00 UTC, the
    naive value was taken at face value -- which is exactly what the endpoint
    used to do.
    """
    ws = await workspace()
    post = await draft(ws)
    tz = ZoneInfo(SYDNEY)
    target_day = (datetime.now(tz) + timedelta(days=10)).date()

    await client.post(
        f"{_url(ws, post)}?scheduled_at_local={target_day.isoformat()}T10:00:00",
        headers=auth_header(ws["owner"]),
    )

    await db_session.refresh(post)
    assert _utc(post.scheduled_at).hour != 10, (
        "the local reading was stored as if it were UTC"
    )
    offset = _utc(post.scheduled_at).astimezone(tz).utcoffset()
    assert offset >= timedelta(hours=10)


async def test_two_workspaces_resolve_the_same_wall_clock_differently(
    client, auth_header, workspace, draft, db_session
):
    """The clearest statement of the contract: identical input, different
    instants, because the workspaces keep different clocks."""
    sydney = await workspace(tz=SYDNEY)
    london = await workspace(tz="Europe/London")
    day = (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat()

    instants = []
    for ws in (sydney, london):
        post = await draft(ws)
        response = await client.post(
            f"{_url(ws, post)}?scheduled_at_local={day}T10:00:00",
            headers=auth_header(ws["owner"]),
        )
        assert response.status_code == 200, response.text
        await db_session.refresh(post)
        instants.append(_utc(post.scheduled_at))

    assert instants[0] != instants[1]


async def test_a_local_time_with_an_offset_is_refused(
    client, auth_header, workspace, draft
):
    """Accepting an offset here would accept an answer the caller cannot have:
    which offset applies depends on the date."""
    ws = await workspace()
    post = await draft(ws)
    day = (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat()

    response = await client.post(
        f"{_url(ws, post)}?scheduled_at_local={day}T10:00:00%2B05:00",
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code == 422


async def test_a_naive_absolute_instant_is_refused(
    client, auth_header, workspace, draft
):
    """It used to be silently read as UTC, which moved the post for every
    workspace not in UTC."""
    ws = await workspace()
    post = await draft(ws)
    day = (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat()

    response = await client.post(
        f"{_url(ws, post)}?scheduled_at={day}T10:00:00",
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code == 422
    assert "offset" in response.text


async def test_an_absolute_instant_still_works(
    client, auth_header, workspace, draft, db_session
):
    """Callers that genuinely hold an instant are unaffected."""
    ws = await workspace()
    post = await draft(ws)
    instant = datetime.now(timezone.utc) + timedelta(days=10)

    response = await client.post(
        f"{_url(ws, post)}?scheduled_at={instant.isoformat().replace('+00:00', 'Z')}",
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code == 200, response.text
    await db_session.refresh(post)
    assert abs((_utc(post.scheduled_at) - instant).total_seconds()) < 2


async def test_exactly_one_time_is_required(client, auth_header, workspace, draft):
    ws = await workspace()
    post = await draft(ws)

    neither = await client.post(_url(ws, post), headers=auth_header(ws["owner"]))
    assert neither.status_code == 422

    day = (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat()
    both = await client.post(
        f"{_url(ws, post)}?scheduled_at={day}T10:00:00Z"
        f"&scheduled_at_local={day}T10:00:00",
        headers=auth_header(ws["owner"]),
    )
    assert both.status_code == 422


async def test_a_local_time_in_the_spring_forward_gap_is_resolved(
    client, auth_header, workspace, draft, db_session
):
    """02:30 does not exist on the transition date. Rather than failing, it
    resolves to the first instant that does -- the same policy recurring
    schedules use, so the two cannot disagree."""
    ws = await workspace(tz="America/New_York")
    post = await draft(ws)

    response = await client.post(
        f"{_url(ws, post)}?scheduled_at_local=2027-03-14T02:30:00",
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code == 200, response.text
    await db_session.refresh(post)
    local = _utc(post.scheduled_at).astimezone(ZoneInfo("America/New_York"))
    assert (local.hour, local.minute) == (3, 30)


# ---------------------------------------------------------------------------
# Write contract
# ---------------------------------------------------------------------------

async def test_an_unknown_field_is_refused_rather_than_dropped(
    client, auth_header, workspace
):
    ws = await workspace()

    response = await client.post(
        f"/api/v1/accounts/{ws['account_id']}/posts/",
        headers=auth_header(ws["owner"]),
        json={"content": "hello", "targt_account_ids": []},
    )

    assert response.status_code == 422
    assert "targt_account_ids" in response.text


async def test_the_responses_own_field_name_is_accepted(
    client, auth_header, workspace, db_session
):
    """Read-modify-write must work: the field the API just handed back cannot
    be one it refuses."""
    ws = await workspace()

    response = await client.post(
        f"/api/v1/accounts/{ws['account_id']}/posts/",
        headers=auth_header(ws["owner"]),
        json={
            "content": "hello",
            "target_accounts": [
                {
                    "social_account_id": str(ws["social_id"]),
                    "platform_name": "Instagram",
                    "account_name": "ig",
                }
            ],
        },
    )

    assert response.status_code in (200, 201), response.text
    targets = response.json()["target_accounts"] or []
    assert [t["social_account_id"] for t in targets] == [str(ws["social_id"])]


async def test_a_post_round_trips_through_its_own_response(
    client, auth_header, workspace
):
    """The whole point of the alias, end to end: create, take the response,
    send it back as an update, and keep the targets."""
    ws = await workspace()
    created = await client.post(
        f"/api/v1/accounts/{ws['account_id']}/posts/",
        headers=auth_header(ws["owner"]),
        json={"content": "first", "target_account_ids": [str(ws["social_id"])]},
    )
    body = created.json()

    updated = await client.put(
        f"/api/v1/accounts/{ws['account_id']}/posts/{body['id']}",
        headers=auth_header(ws["owner"]),
        json={"content": "second", "target_accounts": body["target_accounts"]},
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["content"] == "second"
    targets = updated.json()["target_accounts"] or []
    assert [t["social_account_id"] for t in targets] == [str(ws["social_id"])]


async def test_naming_both_target_fields_is_refused(client, auth_header, workspace):
    """Guessing which the caller meant is how a post publishes to the wrong
    account."""
    ws = await workspace()

    response = await client.post(
        f"/api/v1/accounts/{ws['account_id']}/posts/",
        headers=auth_header(ws["owner"]),
        json={
            "content": "hello",
            "target_account_ids": [str(ws["social_id"])],
            "target_accounts": [],
        },
    )

    assert response.status_code == 422
    assert "not both" in response.text


async def test_updates_refuse_unknown_fields_too(client, auth_header, workspace):
    ws = await workspace()
    created = await client.post(
        f"/api/v1/accounts/{ws['account_id']}/posts/",
        headers=auth_header(ws["owner"]),
        json={"content": "first"},
    )

    response = await client.put(
        f"/api/v1/accounts/{ws['account_id']}/posts/{created.json()['id']}",
        headers=auth_header(ws["owner"]),
        json={"content": "second", "statuss": "draft"},
    )

    assert response.status_code == 422
    assert "statuss" in response.text
