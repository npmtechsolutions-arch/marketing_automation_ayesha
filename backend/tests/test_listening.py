"""Social listening on X, and the three ways it could lie.

The feature is a rolling seven-day search that costs money per poll, which
makes three failure modes worth pinning harder than the happy path:

* **Silence that is really a breakage.** A search whose credential has no
  funding returns nothing, and nothing is also what a genuinely quiet week
  returns. Every test here that touches a failure asserts the reason is *on
  the query row*, because that is the only thing distinguishing the two.
* **A window left unsaid.** "No mentions" is a claim about the world; "no
  mentions in the last 7 days" is a claim about what we looked at. Only the
  second is true, and the payloads carry it so no component can render the
  friendlier version.
* **A poll that pays twice for the same answer.** Re-polling must be free of
  visible effect, and the cursor must only ever move forward.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.connectors.base import MissingCredential, ProviderAPIError
from app.models.listening import ListeningQuery, Mention
from app.services import listening

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def x_search(monkeypatch):
    """Answer ``search_recent`` with a script instead of X.

    Patched on the provider rather than at the HTTP layer: the connector's own
    search is covered in test_connectors, and what these tests are about is
    what the *service* does with each outcome.
    """
    from app.connectors.registry import get_provider

    provider = get_provider("twitter")
    state = {"calls": [], "result": {"items": [], "requests": 1, "posts_read": 0},
             "raises": None}

    async def _search(social_account, query, *, since_id=None, max_results=25):
        state["calls"].append(
            {"query": query, "since_id": since_id, "max_results": max_results}
        )
        if state["raises"] is not None:
            raise state["raises"]
        return state["result"]

    monkeypatch.setattr(provider, "search_recent", _search, raising=False)
    return state


def _tweet(external_id: str, *, handle="someone", minutes_ago=5, body="Hello"):
    return {
        "external_id": external_id,
        "author": handle.title(),
        "author_handle": handle,
        "body": body,
        "created_at": datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        "permalink": f"https://x.com/{handle}/status/{external_id}",
    }


@pytest.fixture
async def workspace(
    user_factory, account_factory, social_account_factory, set_limit, db_session
):
    """A workspace with an X connection, which is what makes listening legal.

    ``queries_limit`` defaults to a few rather than to the plan's own number:
    new workspaces land on Free, which includes **no** saved searches at all
    (polling costs money, and a free plan that spends it is a cost centre), so
    every test that creates one would otherwise be testing the 402.
    """
    from app.models.organization import Organization

    async def _make(*, connect_x=True, token="real-x-token", queries_limit=5):
        owner = await user_factory(password=PASSWORD)
        account = await account_factory(owner)
        organization = (
            await db_session.execute(
                select(Organization).where(Organization.id == account.organization_id)
            )
        ).scalar_one()
        if queries_limit is not None:
            await set_limit(organization, "listening_queries", queries_limit)
        connection = None
        if connect_x:
            connection = await social_account_factory(
                owner, account, slug="twitter", access_token=token
            )
        return {
            "owner": owner, "account": account, "connection": connection,
            "organization": organization, "account_id": account.id,
        }

    return _make


async def _query(db_session, ctx, text="marketengine", **extra) -> ListeningQuery:
    query = ListeningQuery(
        id=uuid.uuid4(),
        account_id=ctx["account_id"],
        platform="twitter",
        query_text=text,
        is_active=True,
        **extra,
    )
    db_session.add(query)
    await db_session.flush()
    return query


# ---------------------------------------------------------------------------
# Idempotency: a re-poll must be free of visible effect
# ---------------------------------------------------------------------------

async def test_repolling_the_same_results_stores_nothing_new(
    db_session, workspace, x_search
):
    ctx = await workspace()
    query = await _query(db_session, ctx)
    x_search["result"] = {
        "items": [_tweet("1900000000000000001"), _tweet("1900000000000000002")],
        "requests": 1, "posts_read": 2,
    }

    first = await listening.poll_query(db_session, query, ctx["connection"])
    second = await listening.poll_query(db_session, query, ctx["connection"])

    assert first["new"] == 2
    # The second poll may legitimately see the same posts -- X can re-serve
    # them -- and must recognise every one of them.
    assert second["new"] == 0
    stored = (
        await db_session.execute(
            select(Mention).where(Mention.listening_query_id == query.id)
        )
    ).scalars().all()
    assert len(stored) == 2


async def test_a_repoll_asks_only_for_what_is_new(db_session, workspace, x_search):
    """since_id is what stops a six-hourly poll re-paying for the same window."""
    ctx = await workspace()
    query = await _query(db_session, ctx)
    x_search["result"] = {
        "items": [_tweet("1900000000000000005"), _tweet("1900000000000000009")],
        "requests": 1, "posts_read": 2,
    }

    await listening.poll_query(db_session, query, ctx["connection"])
    await listening.poll_query(db_session, query, ctx["connection"])

    assert x_search["calls"][0]["since_id"] is None
    assert x_search["calls"][1]["since_id"] == "1900000000000000009"


async def test_the_cursor_never_moves_backward(db_session, workspace, x_search):
    """A later page of older posts must not drag the marker back.

    If it did, the next poll would re-read everything in between -- and on a
    per-post-billed API, re-reading is re-paying.
    """
    ctx = await workspace()
    query = await _query(db_session, ctx)

    x_search["result"] = {
        "items": [_tweet("1900000000000000009")], "requests": 1, "posts_read": 1,
    }
    await listening.poll_query(db_session, query, ctx["connection"])
    x_search["result"] = {
        "items": [_tweet("1900000000000000001")], "requests": 1, "posts_read": 1,
    }
    await listening.poll_query(db_session, query, ctx["connection"])

    assert query.last_result_cursor == "1900000000000000009"


async def test_an_item_with_no_external_id_is_skipped(db_session, workspace, x_search):
    """2.5's rule: with no id there is no way to recognise it next time, so
    storing it would guarantee a duplicate on the next poll."""
    ctx = await workspace()
    query = await _query(db_session, ctx)
    x_search["result"] = {
        "items": [{**_tweet("x"), "external_id": None}, _tweet("1900000000000000003")],
        "requests": 1, "posts_read": 2,
    }

    report = await listening.poll_query(db_session, query, ctx["connection"])

    assert report["new"] == 1


async def test_an_existing_mention_is_never_rewritten(db_session, workspace, x_search):
    ctx = await workspace()
    query = await _query(db_session, ctx)
    x_search["result"] = {
        "items": [_tweet("1900000000000000004", handle="ada", body="First rendering")],
        "requests": 1, "posts_read": 1,
    }
    await listening.poll_query(db_session, query, ctx["connection"])

    # The same post, re-served with an edited display name and body.
    x_search["result"] = {
        "items": [_tweet("1900000000000000004", handle="ada", body="Rewritten")],
        "requests": 1, "posts_read": 1,
    }
    await listening.poll_query(db_session, query, ctx["connection"])

    stored = (
        await db_session.execute(
            select(Mention).where(Mention.listening_query_id == query.id)
        )
    ).scalars().all()
    assert len(stored) == 1
    assert stored[0].text == "First rendering"


# ---------------------------------------------------------------------------
# A failed credential is visible, never an empty-but-healthy stream
# ---------------------------------------------------------------------------

async def test_a_placeholder_token_is_a_visible_failure_not_an_empty_stream(
    db_session, workspace
):
    """The site-#2 lesson, arriving from the other direction.

    A development token that answered "no mentions" would be indistinguishable
    from a funded account that genuinely found none -- so the connector raises
    and the query records why.
    """
    ctx = await workspace(token="mock_token_for_tests")
    query = await _query(db_session, ctx)

    report = await listening.poll_query(db_session, query, ctx["connection"])

    assert report["new"] == 0
    assert "placeholder token" in (report["error"] or "")
    assert query.last_error and "placeholder token" in query.last_error
    assert query.last_success_at is None


async def test_an_unfunded_account_says_so_on_the_query(
    db_session, workspace, x_search
):
    ctx = await workspace()
    query = await _query(db_session, ctx)
    x_search["raises"] = ProviderAPIError(
        "twitter",
        "X refused the search: this developer account has no pay-per-use "
        "credits left.",
        status_code=402,
    )

    report = await listening.poll_query(db_session, query, ctx["connection"])

    assert "credits" in report["error"]
    assert query.last_error and "credits" in query.last_error
    assert query.last_error_at is not None


async def test_a_failure_still_moves_the_clock(db_session, workspace, x_search):
    """Otherwise a broken query retries on every sweep, which on a metered API
    is how a broken integration becomes an expensive one."""
    ctx = await workspace()
    query = await _query(db_session, ctx)
    x_search["raises"] = ProviderAPIError("twitter", "nope", status_code=500)

    await listening.poll_query(db_session, query, ctx["connection"])

    assert query.last_polled_at is not None


async def test_a_success_after_a_failure_clears_the_error(
    db_session, workspace, x_search
):
    ctx = await workspace()
    query = await _query(db_session, ctx)
    x_search["raises"] = MissingCredential("twitter", "no credential")
    await listening.poll_query(db_session, query, ctx["connection"])
    assert query.last_error is not None

    x_search["raises"] = None
    x_search["result"] = {"items": [], "requests": 1, "posts_read": 0}
    await listening.poll_query(db_session, query, ctx["connection"])

    assert query.last_error is None
    assert query.last_success_at is not None


async def test_a_query_whose_connection_vanished_says_why(
    db_session, workspace, x_search
):
    ctx = await workspace(connect_x=False)
    query = await _query(db_session, ctx)

    totals = await listening.sync_all(db_session)

    assert totals["errors"] == 1
    assert query.last_error and "No X account is connected" in query.last_error


# ---------------------------------------------------------------------------
# Cost, and the interval that governs it
# ---------------------------------------------------------------------------

async def test_each_poll_records_what_it_read(db_session, workspace, x_search):
    ctx = await workspace()
    query = await _query(db_session, ctx)
    x_search["result"] = {
        "items": [_tweet(f"19000000000000000{n:02d}") for n in range(10, 14)],
        "requests": 1, "posts_read": 4,
    }

    await listening.poll_query(db_session, query, ctx["connection"])
    await listening.poll_query(db_session, query, ctx["connection"])

    assert query.requests_made == 2
    # Billed per post read, not per request: two requests, eight reads.
    assert query.posts_read == 8
    assert listening.estimated_cost_usd(query.posts_read) == round(8 * 0.005, 4)


async def test_the_workspace_interval_decides_whether_a_query_is_due(
    db_session, workspace
):
    ctx = await workspace()
    account = ctx["account"]
    now = datetime.now(timezone.utc)
    query = await _query(db_session, ctx, last_polled_at=now - timedelta(hours=4))

    account.settings = {**(account.settings or {}), "listening_interval_hours": 6}
    assert listening.is_due(query, listening.interval_hours(account), now) is False

    account.settings = {**(account.settings or {}), "listening_interval_hours": 3}
    assert listening.is_due(query, listening.interval_hours(account), now) is True


async def test_a_query_polled_recently_is_left_alone_by_the_sweep(
    db_session, workspace, x_search
):
    ctx = await workspace()
    await _query(
        db_session, ctx,
        last_polled_at=datetime.now(timezone.utc) - timedelta(minutes=30),
    )

    totals = await listening.sync_all(db_session)

    assert totals["polled"] == 0
    assert x_search["calls"] == []


async def test_a_paused_query_is_never_polled(db_session, workspace, x_search):
    ctx = await workspace()
    query = await _query(db_session, ctx)
    query.is_active = False

    totals = await listening.sync_all(db_session)

    assert totals["polled"] == 0
    assert listening.is_due(query, 1) is False


async def test_an_unknown_interval_falls_back_to_the_default(db_session, workspace):
    ctx = await workspace()
    ctx["account"].settings = {"listening_interval_hours": 2}
    assert listening.interval_hours(ctx["account"]) == listening.DEFAULT_INTERVAL_HOURS


async def test_a_free_form_interval_is_refused_not_clamped():
    """Someone who asks for hourly and silently gets six-hourly will read the
    stream as broken. The settings writer's accept-and-drop rule."""
    with pytest.raises(ValueError):
        listening.validate_interval(2)
    with pytest.raises(ValueError):
        listening.validate_interval("soon")
    assert listening.validate_interval(3) == 3


# ---------------------------------------------------------------------------
# The window, in every payload
# ---------------------------------------------------------------------------

async def test_the_window_is_stated_everywhere_the_api_answers(
    client, auth_header, workspace
):
    ctx = await workspace()
    base = f"/api/v1/accounts/{ctx['account_id']}/listening"
    headers = auth_header(ctx["owner"])

    for path in ("/status", "/queries", "/mentions"):
        body = (await client.get(base + path, headers=headers)).json()
        assert body["window_days"] == 7, path
        assert body["window_label"] == "the last 7 days", path


async def test_an_empty_stream_says_the_window_not_just_no_mentions(
    client, auth_header, workspace
):
    """"No mentions" is a claim about the world. "No mentions in the last 7
    days" is a claim about what we looked at, and only the second is true."""
    ctx = await workspace()
    response = await client.get(
        f"/api/v1/accounts/{ctx['account_id']}/listening/mentions",
        headers=auth_header(ctx["owner"]),
    )
    body = response.json()

    assert body["total"] == 0
    assert body["empty_label"] == "No mentions in the last 7 days."


async def test_the_window_comes_from_the_connector_not_a_constant(monkeypatch):
    """A tier change moves every surface at once, because they all read this."""
    from app.connectors.registry import get_provider
    from dataclasses import replace

    provider = get_provider("twitter")
    monkeypatch.setattr(
        provider, "capabilities",
        replace(provider.capabilities, search_window_days=30),
        raising=False,
    )
    assert listening.window_label() == "the last 30 days"


# ---------------------------------------------------------------------------
# Capability gating, entitlements and tenancy, through the API
# ---------------------------------------------------------------------------

async def test_a_workspace_with_no_x_connection_is_told_why_not_shown_nothing(
    client, auth_header, workspace
):
    ctx = await workspace(connect_x=False)
    headers = auth_header(ctx["owner"])
    base = f"/api/v1/accounts/{ctx['account_id']}/listening"

    status_body = (await client.get(f"{base}/status", headers=headers)).json()
    assert status_body["connected"] is False
    assert "no X account connected" in status_body["reason"]

    # And creating one is refused rather than accepted and left to fail on the
    # first poll, which would look like it was working.
    created = await client.post(
        f"{base}/queries", headers=headers, json={"query_text": "marketengine"}
    )
    assert created.status_code == 400
    assert "no X account" in created.json()["detail"]


async def test_creating_a_query_at_the_plan_limit_is_refused(
    client, auth_header, workspace
):
    ctx = await workspace(queries_limit=1)
    headers = auth_header(ctx["owner"])
    base = f"/api/v1/accounts/{ctx['account_id']}/listening"

    first = await client.post(
        f"{base}/queries", headers=headers, json={"query_text": "first search"}
    )
    assert first.status_code == 201

    second = await client.post(
        f"{base}/queries", headers=headers, json={"query_text": "second search"}
    )
    assert second.status_code == 402
    assert "listening queries" in second.json()["detail"]


async def test_deleting_a_query_gives_the_slot_back(
    client, auth_header, workspace
):
    """The reason this is a stateful count rather than a monthly meter.

    A saved search is a thing that exists, not a spend. Metering it would mean
    a workspace that created and removed one search was locked out until the
    billing period rolled -- for a search that no longer exists.
    """
    ctx = await workspace(queries_limit=1)
    headers = auth_header(ctx["owner"])
    base = f"/api/v1/accounts/{ctx['account_id']}/listening"

    created = await client.post(
        f"{base}/queries", headers=headers, json={"query_text": "only one"}
    )
    query_id = created.json()["id"]
    assert (
        await client.delete(f"{base}/queries/{query_id}", headers=headers)
    ).status_code == 204

    again = await client.post(
        f"{base}/queries", headers=headers, json={"query_text": "a different one"}
    )
    assert again.status_code == 201


async def test_the_same_search_cannot_be_saved_twice(
    client, auth_header, workspace
):
    """Two rows would poll twice and bill twice for one answer."""
    ctx = await workspace()
    headers = auth_header(ctx["owner"])
    base = f"/api/v1/accounts/{ctx['account_id']}/listening"

    assert (
        await client.post(
            f"{base}/queries", headers=headers, json={"query_text": "brand"}
        )
    ).status_code == 201
    duplicate = await client.post(
        f"{base}/queries", headers=headers, json={"query_text": "brand"}
    )
    assert duplicate.status_code == 409


async def test_another_workspace_cannot_read_or_touch_a_query(
    client, auth_header, workspace, db_session
):
    mine = await workspace()
    theirs = await workspace()
    query = await _query(db_session, mine, text="my brand")
    await db_session.flush()

    intruder = auth_header(theirs["owner"])
    base = f"/api/v1/accounts/{theirs['account_id']}/listening"

    # Not visible in their list...
    listed = (await client.get(f"{base}/queries", headers=intruder)).json()
    assert listed["queries"] == []

    # ...not addressable by id...
    assert (
        await client.patch(
            f"{base}/queries/{query.id}", headers=intruder, json={"is_active": False}
        )
    ).status_code == 404

    # ...and not reachable by filtering the stream at it.
    stream = (
        await client.get(
            f"{base}/mentions?query_id={query.id}", headers=intruder
        )
    ).json()
    assert stream["total"] == 0


async def test_a_broken_query_reads_as_broken_in_the_list(
    client, auth_header, workspace, db_session
):
    ctx = await workspace()
    query = await _query(db_session, ctx)
    query.last_error = "X refused the search: no pay-per-use credits left."
    query.last_error_at = datetime.now(timezone.utc)
    await db_session.flush()

    body = (
        await client.get(
            f"/api/v1/accounts/{ctx['account_id']}/listening/queries",
            headers=auth_header(ctx["owner"]),
        )
    ).json()
    row = body["queries"][0]

    assert row["healthy"] is False
    assert "credits" in row["last_error"]


async def test_changing_the_search_text_clears_the_cursor(
    client, auth_header, workspace, db_session
):
    """A new search is a new result set; the old marker points into a
    different one and would skip everything older than its last match."""
    ctx = await workspace()
    query = await _query(db_session, ctx, last_result_cursor="1900000000000000009")
    await db_session.flush()

    await client.patch(
        f"/api/v1/accounts/{ctx['account_id']}/listening/queries/{query.id}",
        headers=auth_header(ctx["owner"]),
        json={"query_text": "something else entirely"},
    )
    await db_session.refresh(query)

    assert query.last_result_cursor is None


async def test_the_poll_endpoint_reports_the_cost_of_that_poll(
    client, auth_header, workspace, db_session, x_search
):
    ctx = await workspace()
    query = await _query(db_session, ctx)
    await db_session.flush()
    x_search["result"] = {
        "items": [_tweet("1900000000000000020"), _tweet("1900000000000000021")],
        "requests": 1, "posts_read": 2,
    }

    body = (
        await client.post(
            f"/api/v1/accounts/{ctx['account_id']}/listening/queries/{query.id}/poll",
            headers=auth_header(ctx["owner"]),
        )
    ).json()

    assert body["new_mentions"] == 2
    assert body["posts_read"] == 2
    assert body["estimated_cost_usd"] == round(2 * 0.005, 4)
    assert body["error"] is None


async def test_the_settings_writer_accepts_a_listed_interval_and_refuses_others(
    client, auth_header, workspace
):
    """#18's contract: the setting has a home, and a bad value is a 422 rather
    than a 200 that changes nothing."""
    ctx = await workspace()
    headers = auth_header(ctx["owner"])
    base = f"/api/v1/accounts/{ctx['account_id']}/settings"

    good = await client.put(
        f"{base}/", headers=headers, json={"settings": {"listening_interval_hours": 12}}
    )
    assert good.status_code == 200
    assert good.json()["settings"]["listening_interval_hours"] == 12

    bad = await client.put(
        f"{base}/", headers=headers, json={"settings": {"listening_interval_hours": 2}}
    )
    assert bad.status_code == 422


async def test_polling_by_hand_twice_in_a_row_is_refused(
    client, auth_header, workspace, db_session, x_search
):
    """The button spends money on every press.

    The scheduled sweep is held back by the workspace's interval; nothing held
    this back, so a page that re-polled on focus -- or a leaning finger --
    could run up a bill a few cents at a time.
    """
    ctx = await workspace()
    query = await _query(db_session, ctx)
    await db_session.flush()
    x_search["result"] = {"items": [], "requests": 1, "posts_read": 0}
    url = (
        f"/api/v1/accounts/{ctx['account_id']}/listening/queries/{query.id}/poll"
    )
    headers = auth_header(ctx["owner"])

    assert (await client.post(url, headers=headers)).status_code == 200
    second = await client.post(url, headers=headers)

    assert second.status_code == 429
    assert "costs X API credit" in second.json()["detail"]
    # And it really did not run: one call reached the platform, not two.
    assert len(x_search["calls"]) == 1
