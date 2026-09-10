"""Competitor tracking, and the four ways it could overclaim.

Business Discovery returns a name and two numbers for public Instagram
business accounts. Everything below defends the gap between that and what a
"competitor intelligence" screen usually implies:

* **A typo is refused at the moment it is typed.** A handle nobody can see,
  tracked silently, produces a row that stays empty forever and reads as a
  competitor with no followers.
* **Absent is not zero.** A private account yields a name and no counts; the
  snapshot stores NULL and the chart shows a gap.
* **Every number says how old it is.** The cap is roughly weekly, so a figure
  on screen is days old by definition.
* **A trend needs two points.** One snapshot is a fact, not a line.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.connectors.base import AccountNotFound, ProviderAPIError
from app.models.competitor import CompetitorAccount, CompetitorSnapshot
from app.services import competitors

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def discovery(monkeypatch):
    """Answer Business Discovery with a script instead of Meta."""
    from app.connectors.registry import get_provider

    provider = get_provider("instagram")
    state = {
        "calls": [],
        "result": {
            "handle": "rival", "display_name": "Rival Co",
            "followers": 12400, "media_count": 310,
        },
        "raises": None,
    }

    async def _lookup(social_account, handle):
        state["calls"].append(handle)
        if state["raises"] is not None:
            raise state["raises"]
        return state["result"]

    monkeypatch.setattr(provider, "lookup_account", _lookup, raising=False)
    return state


@pytest.fixture
async def workspace(
    user_factory, account_factory, social_account_factory, set_limit, db_session
):
    """A workspace with an Instagram *business* connection.

    The business account id is what makes the connection usable: Meta requires
    Discovery to be asked as one, so a connection without it cannot ask at all.
    """
    from app.models.organization import Organization

    async def _make(*, connect_ig=True, business=True, limit=5):
        owner = await user_factory(password=PASSWORD)
        account = await account_factory(owner)
        organization = (
            await db_session.execute(
                select(Organization).where(Organization.id == account.organization_id)
            )
        ).scalar_one()
        if limit is not None:
            await set_limit(organization, "competitor_accounts", limit)
        connection = None
        if connect_ig:
            connection = await social_account_factory(
                owner, account, slug="instagram",
                config=(
                    {"instagram_business_account_id": "17841400000000000"}
                    if business else {}
                ),
            )
        return {
            "owner": owner, "account": account, "connection": connection,
            "organization": organization, "account_id": account.id,
        }

    return _make


async def _competitor(db_session, ctx, handle="rival", **extra) -> CompetitorAccount:
    competitor = CompetitorAccount(
        id=uuid.uuid4(),
        account_id=ctx["account_id"],
        platform="instagram",
        handle=handle,
        is_active=True,
        **extra,
    )
    db_session.add(competitor)
    await db_session.flush()
    return competitor


# ---------------------------------------------------------------------------
# Validation at add time
# ---------------------------------------------------------------------------

async def test_a_handle_nobody_can_see_is_refused_at_add_time(
    client, auth_header, workspace, discovery
):
    """The whole reason adding costs a real lookup.

    Tracked silently, a typo produces a row that never fills in and reads as a
    competitor with no followers -- a fabricated fact about a real company.
    """
    ctx = await workspace()
    discovery["raises"] = AccountNotFound(
        "instagram",
        "Instagram has no visible business account called @rivl. Business "
        "Discovery can only see public business and creator accounts.",
    )

    response = await client.post(
        f"/api/v1/accounts/{ctx['account_id']}/competitors/",
        headers=auth_header(ctx["owner"]),
        json={"handle": "@rivl"},
    )

    assert response.status_code == 404
    assert "no visible business account" in response.json()["detail"]
    # And nothing was stored.
    assert discovery["calls"] == ["rivl"]


async def test_a_platform_outage_does_not_add_an_unverified_row(
    client, auth_header, workspace, discovery
):
    ctx = await workspace()
    discovery["raises"] = ProviderAPIError(
        "instagram", "Business Discovery failed: 503 upstream", status_code=503
    )

    response = await client.post(
        f"/api/v1/accounts/{ctx['account_id']}/competitors/",
        headers=auth_header(ctx["owner"]),
        json={"handle": "rival"},
    )

    assert response.status_code == 502
    assert "could not be reached" in response.json()["detail"]


async def test_adding_stores_the_validating_lookup_as_the_first_snapshot(
    client, auth_header, workspace, discovery
):
    """It has already been spent against the weekly cap; throwing the numbers
    away would mean asking again tomorrow for what is already in hand."""
    ctx = await workspace()

    body = (
        await client.post(
            f"/api/v1/accounts/{ctx['account_id']}/competitors/",
            headers=auth_header(ctx["owner"]),
            json={"handle": "@Rival"},
        )
    ).json()

    # Handle normalised: '@Rival' and 'rival' are one account on Instagram.
    assert body["handle"] == "rival"
    assert body["display_name"] == "Rival Co"
    assert body["followers"] == 12400
    assert body["snapshot_count"] == 1
    assert body["trend_ready"] is False
    assert "trend appears after next week" in body["trend_pending_label"]


async def test_the_same_handle_cannot_be_tracked_twice(
    client, auth_header, workspace, discovery
):
    ctx = await workspace()
    url = f"/api/v1/accounts/{ctx['account_id']}/competitors/"
    headers = auth_header(ctx["owner"])

    assert (
        await client.post(url, headers=headers, json={"handle": "rival"})
    ).status_code == 201
    # Same account, typed differently.
    duplicate = await client.post(url, headers=headers, json={"handle": "@RIVAL"})

    assert duplicate.status_code == 409


# ---------------------------------------------------------------------------
# Snapshot idempotency
# ---------------------------------------------------------------------------

async def test_two_syncs_on_one_day_correct_the_day_rather_than_duplicate_it(
    db_session, workspace, discovery
):
    """analytics_daily's rule. Two points on one Tuesday is a chart that
    disagrees with itself."""
    ctx = await workspace()
    competitor = await _competitor(db_session, ctx)

    await competitors.sync_competitor(
        db_session, competitor, ctx["connection"], ctx["account"]
    )
    discovery["result"] = {**discovery["result"], "followers": 12450}
    competitor.last_synced_at = None  # the sweep's cap is tested separately
    await competitors.sync_competitor(
        db_session, competitor, ctx["connection"], ctx["account"]
    )

    rows = (
        await db_session.execute(
            select(CompetitorSnapshot).where(
                CompetitorSnapshot.competitor_id == competitor.id
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].followers == 12450


async def test_a_field_the_api_stopped_returning_does_not_erase_what_we_knew(
    db_session, workspace, discovery
):
    ctx = await workspace()
    competitor = await _competitor(db_session, ctx)
    await competitors.sync_competitor(
        db_session, competitor, ctx["connection"], ctx["account"]
    )

    # The account went private: Discovery answers with a name and no counts.
    discovery["result"] = {"handle": "rival", "display_name": "Rival Co"}
    competitor.last_synced_at = None
    await competitors.sync_competitor(
        db_session, competitor, ctx["connection"], ctx["account"]
    )

    row = (
        await db_session.execute(
            select(CompetitorSnapshot).where(
                CompetitorSnapshot.competitor_id == competitor.id
            )
        )
    ).scalar_one()
    # Last week's number survives; it is not overwritten with NULL and not
    # replaced with a 0.
    assert row.followers == 12400


async def test_a_lookup_with_no_counts_stores_no_row_at_all(
    db_session, workspace, discovery
):
    """A row of NULLs would say "we looked and they have nothing", which is not
    what happened. What did happen is on the competitor's error field."""
    ctx = await workspace()
    competitor = await _competitor(db_session, ctx)
    discovery["result"] = {"handle": "rival", "display_name": "Rival Co"}

    await competitors.sync_competitor(
        db_session, competitor, ctx["connection"], ctx["account"]
    )

    rows = (
        await db_session.execute(
            select(CompetitorSnapshot).where(
                CompetitorSnapshot.competitor_id == competitor.id
            )
        )
    ).scalars().all()
    assert rows == []


async def test_a_zero_from_instagram_is_kept_as_a_zero(
    db_session, workspace, discovery
):
    """The mirror image: a real measured zero is real. A brand new account
    genuinely has no posts."""
    ctx = await workspace()
    competitor = await _competitor(db_session, ctx)
    discovery["result"] = {
        "handle": "rival", "display_name": "Rival Co",
        "followers": 0, "media_count": 0,
    }

    await competitors.sync_competitor(
        db_session, competitor, ctx["connection"], ctx["account"]
    )

    row = (
        await db_session.execute(
            select(CompetitorSnapshot).where(
                CompetitorSnapshot.competitor_id == competitor.id
            )
        )
    ).scalar_one()
    assert row.followers == 0
    assert row.media_count == 0


# ---------------------------------------------------------------------------
# The weekly cap
# ---------------------------------------------------------------------------

async def test_a_competitor_checked_this_week_is_left_alone_by_the_sweep(
    db_session, workspace, discovery
):
    ctx = await workspace()
    await _competitor(
        db_session, ctx,
        last_synced_at=datetime.now(timezone.utc) - timedelta(days=3),
    )

    totals = await competitors.sync_all(db_session)

    assert totals["checked"] == 0
    assert discovery["calls"] == []


async def test_a_competitor_not_checked_for_a_week_is_due(db_session, workspace):
    ctx = await workspace()
    competitor = await _competitor(
        db_session, ctx,
        last_synced_at=datetime.now(timezone.utc) - timedelta(days=8),
    )

    assert competitors.is_due(competitor) is True


async def test_a_failed_check_still_counts_against_the_cap(
    db_session, workspace, discovery
):
    """Meta counts attempts, not successes. Retrying a failing handle every six
    hours would spend the week's allowance and throttle everything else."""
    ctx = await workspace()
    competitor = await _competitor(db_session, ctx)
    discovery["raises"] = AccountNotFound("instagram", "gone private")

    await competitors.sync_competitor(
        db_session, competitor, ctx["connection"], ctx["account"]
    )

    assert competitor.last_synced_at is not None
    assert competitors.is_due(competitor) is False


async def test_refreshing_by_hand_before_the_cap_is_refused(
    client, auth_header, workspace, db_session, discovery
):
    ctx = await workspace()
    competitor = await _competitor(
        db_session, ctx, last_synced_at=datetime.now(timezone.utc) - timedelta(days=2)
    )
    await db_session.flush()

    response = await client.post(
        f"/api/v1/accounts/{ctx['account_id']}/competitors/{competitor.id}/refresh",
        headers=auth_header(ctx["owner"]),
    )

    assert response.status_code == 429
    assert "one lookup per account per week" in response.json()["detail"]
    assert discovery["calls"] == []


async def test_a_paused_competitor_is_never_checked(db_session, workspace, discovery):
    ctx = await workspace()
    competitor = await _competitor(db_session, ctx)
    competitor.is_active = False

    totals = await competitors.sync_all(db_session)

    assert totals["checked"] == 0
    assert competitors.is_due(competitor) is False


# ---------------------------------------------------------------------------
# Staleness, and what the UI is told
# ---------------------------------------------------------------------------

async def test_every_number_is_served_with_how_old_it_is(
    client, auth_header, workspace, db_session, discovery
):
    ctx = await workspace()
    await _competitor(
        db_session, ctx,
        last_synced_at=datetime.now(timezone.utc) - timedelta(days=6),
    )
    await db_session.flush()

    body = (
        await client.get(
            f"/api/v1/accounts/{ctx['account_id']}/competitors/",
            headers=auth_header(ctx["owner"]),
        )
    ).json()

    assert body["competitors"][0]["staleness_label"] == "as of 6 days ago"


async def test_a_competitor_never_checked_says_so_rather_than_implying_freshness(
    db_session, workspace
):
    assert competitors.staleness_label(None) == "not checked yet"


async def test_the_payload_states_what_is_not_tracked(
    client, auth_header, workspace
):
    """The add dialog has to say the absences in the same breath as the offer.

    Someone who reads "competitor tracking" and is not told otherwise will
    assume engagement is in there; it is not, on any Meta tier.
    """
    ctx = await workspace()
    body = (
        await client.get(
            f"/api/v1/accounts/{ctx['account_id']}/competitors/status",
            headers=auth_header(ctx["owner"]),
        )
    ).json()

    joined = " ".join(body["not_tracked"]).lower()
    assert "engagement" in joined
    assert "how often they post" in joined
    assert "top-performing" in joined
    assert "restricted by meta" in body["not_tracked_reason"].lower()
    assert body["sync_interval_days"] == 7


async def test_a_trend_needs_two_points(
    client, auth_header, workspace, db_session, discovery
):
    ctx = await workspace()
    competitor = await _competitor(db_session, ctx)
    db_session.add(
        CompetitorSnapshot(
            id=uuid.uuid4(), competitor_id=competitor.id,
            date=date(2026, 9, 1), followers=12000,
        )
    )
    await db_session.flush()
    url = f"/api/v1/accounts/{ctx['account_id']}/competitors/"
    headers = auth_header(ctx["owner"])

    one = (await client.get(url, headers=headers)).json()["competitors"][0]
    assert one["trend_ready"] is False
    assert one["trend_pending_label"]

    db_session.add(
        CompetitorSnapshot(
            id=uuid.uuid4(), competitor_id=competitor.id,
            date=date(2026, 9, 8), followers=12400,
        )
    )
    await db_session.flush()

    two = (await client.get(url, headers=headers)).json()["competitors"][0]
    assert two["trend_ready"] is True
    assert two["trend_pending_label"] is None
    assert [s["followers"] for s in two["snapshots"]] == [12000, 12400]


async def test_a_failed_check_is_visible_on_the_row(
    client, auth_header, workspace, db_session
):
    ctx = await workspace()
    competitor = await _competitor(db_session, ctx)
    competitor.last_error = "Instagram has no visible business account called @rival."
    competitor.last_error_at = datetime.now(timezone.utc)
    await db_session.flush()

    body = (
        await client.get(
            f"/api/v1/accounts/{ctx['account_id']}/competitors/",
            headers=auth_header(ctx["owner"]),
        )
    ).json()

    assert body["competitors"][0]["healthy"] is False
    assert "no visible business account" in body["competitors"][0]["last_error"]


# ---------------------------------------------------------------------------
# Capability gating, entitlements, tenancy
# ---------------------------------------------------------------------------

async def test_a_workspace_with_no_instagram_is_told_the_requirement(
    client, auth_header, workspace, discovery
):
    ctx = await workspace(connect_ig=False)
    headers = auth_header(ctx["owner"])
    base = f"/api/v1/accounts/{ctx['account_id']}/competitors"

    status_body = (await client.get(f"{base}/status", headers=headers)).json()
    assert status_body["connected"] is False
    assert "Instagram business" in status_body["reason"]

    refused = await client.post(
        f"{base}/", headers=headers, json={"handle": "rival"}
    )
    assert refused.status_code == 400
    assert discovery["calls"] == []


async def test_an_instagram_connection_with_no_business_id_cannot_ask(
    client, auth_header, workspace
):
    """Meta requires the call to be made *as* a business account. A personal
    connection is not a smaller version of that; it cannot ask at all."""
    ctx = await workspace(business=False)

    body = (
        await client.get(
            f"/api/v1/accounts/{ctx['account_id']}/competitors/status",
            headers=auth_header(ctx["owner"]),
        )
    ).json()

    assert body["connected"] is False


async def test_adding_past_the_plan_limit_is_refused(
    client, auth_header, workspace, discovery
):
    ctx = await workspace(limit=1)
    url = f"/api/v1/accounts/{ctx['account_id']}/competitors/"
    headers = auth_header(ctx["owner"])

    assert (
        await client.post(url, headers=headers, json={"handle": "rival"})
    ).status_code == 201
    discovery["result"] = {**discovery["result"], "handle": "other"}
    second = await client.post(url, headers=headers, json={"handle": "other"})

    assert second.status_code == 402
    assert "competitor accounts" in second.json()["detail"]


async def test_removing_a_competitor_gives_the_slot_back(
    client, auth_header, workspace, discovery
):
    ctx = await workspace(limit=1)
    url = f"/api/v1/accounts/{ctx['account_id']}/competitors/"
    headers = auth_header(ctx["owner"])

    created = await client.post(url, headers=headers, json={"handle": "rival"})
    assert (
        await client.delete(
            f"{url}{created.json()['id']}", headers=headers
        )
    ).status_code == 204

    discovery["result"] = {**discovery["result"], "handle": "other"}
    again = await client.post(url, headers=headers, json={"handle": "other"})
    assert again.status_code == 201


async def test_another_workspace_cannot_see_or_touch_a_competitor(
    client, auth_header, workspace, db_session, discovery
):
    mine = await workspace()
    theirs = await workspace()
    competitor = await _competitor(db_session, mine, handle="myrival")
    await db_session.flush()

    intruder = auth_header(theirs["owner"])
    base = f"/api/v1/accounts/{theirs['account_id']}/competitors"

    listed = (await client.get(f"{base}/", headers=intruder)).json()
    assert listed["competitors"] == []

    assert (
        await client.get(f"{base}/{competitor.id}/history", headers=intruder)
    ).status_code == 404
    assert (
        await client.delete(f"{base}/{competitor.id}", headers=intruder)
    ).status_code == 404


async def test_a_competitor_whose_connection_vanished_says_why(
    db_session, workspace, discovery
):
    ctx = await workspace(connect_ig=False)
    competitor = await _competitor(db_session, ctx)

    totals = await competitors.sync_all(db_session)

    assert totals["errors"] == 1
    assert competitor.last_error and "No Instagram business account" in competitor.last_error


async def test_snapshots_are_dated_on_the_workspace_clock(
    db_session, workspace, discovery
):
    """A snapshot dated by the server lands a day out for a workspace east or
    west of it -- the bug six analytics tests carried for weeks."""
    ctx = await workspace()
    ctx["account"].settings = {"timezone": "Australia/Sydney"}
    competitor = await _competitor(db_session, ctx)

    # 22:00 UTC is already tomorrow in Sydney.
    moment = datetime(2026, 9, 10, 22, 0, tzinfo=timezone.utc)
    await competitors.sync_competitor(
        db_session, competitor, ctx["connection"], ctx["account"], now=moment
    )

    row = (
        await db_session.execute(
            select(CompetitorSnapshot).where(
                CompetitorSnapshot.competitor_id == competitor.id
            )
        )
    ).scalar_one()
    assert row.date == date(2026, 9, 11)


async def test_a_placeholder_token_refuses_by_name_instead_of_calling_meta(
    db_session, workspace
):
    """No fabricated follower count for a real company.

    Every other read in this codebase short-circuits a placeholder token to an
    empty result. Here that would be worse than useless: a competitor card
    showing "—" is indistinguishable from a private account, and a number
    would be an invented fact about someone else's business. The connector
    refuses by name, and the row says so.
    """
    ctx = await workspace(connect_ig=True)
    # The factory's default token is a development placeholder.
    competitor = await _competitor(db_session, ctx)

    report = await competitors.sync_competitor(
        db_session, competitor, ctx["connection"], ctx["account"]
    )

    assert "placeholder token" in (report["error"] or "")
    assert competitor.last_error and "placeholder token" in competitor.last_error
    rows = (
        await db_session.execute(
            select(CompetitorSnapshot).where(
                CompetitorSnapshot.competitor_id == competitor.id
            )
        )
    ).scalars().all()
    assert rows == []


async def test_a_placeholder_credential_is_a_400_not_a_bad_gateway(
    client, auth_header, workspace
):
    """MissingCredential exists to make this distinction.

    Instagram is fine; our stored token is a development placeholder. Calling
    that a bad gateway sends someone to Meta's status page to debug their own
    connection.
    """
    ctx = await workspace()

    response = await client.post(
        f"/api/v1/accounts/{ctx['account_id']}/competitors/",
        headers=auth_header(ctx["owner"]),
        json={"handle": "nike"},
    )

    assert response.status_code == 400
    assert "placeholder token" in response.json()["detail"]
