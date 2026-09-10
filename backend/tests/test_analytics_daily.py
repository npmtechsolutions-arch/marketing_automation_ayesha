"""Daily analytics: upsert, deltas, retention, and null handling.

The null handling is the one that would quietly corrupt every number if it were
wrong. A platform that does not report reach must contribute *nothing* to a
reach total, not a zero -- otherwise the chart shows a real flat line and the
cross-platform average is dragged down by platforms that were never measured.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.analytics_daily import CUMULATIVE_FIELDS, METRIC_FIELDS, AnalyticsDaily
from app.services import analytics_query, analytics_sync
from app.services.dashboard import resolve_range

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"
TODAY = date(2026, 6, 15)
NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)


def _today() -> date:
    """Today on the *workspace's* clock, which these fixtures set to UTC.

    Not ``date.today()``, which is the machine's local date. The analytics
    windows resolve in the workspace timezone, so on a machine east of UTC --
    between local midnight and UTC midnight -- a row written "today" lands a day
    beyond the window and every assertion about it fails.

    The suite passed for weeks and broke at 00:17 IST, which is the whole shape
    of the bug: it was always wrong, and only visible for five and a half hours
    a day. Any CI runner not on UTC would have found it eventually.
    """
    return datetime.now(timezone.utc).date()


@pytest.fixture
async def workspace(
    db_session, user_factory, account_factory, organization_factory,
    social_account_factory,
):
    async def _make(slugs=("instagram",), tz="UTC"):
        owner = await user_factory(password=PASSWORD)
        organization = await organization_factory(owner)
        account = await account_factory(owner, organization=organization)
        account.settings = {"timezone": tz}
        await db_session.flush()
        accounts = [
            await social_account_factory(owner, account, slug=slug) for slug in slugs
        ]
        return {
            "owner": owner, "organization": organization, "account": account,
            "account_id": account.id, "social": accounts,
            "social_ids": [sa.id for sa in accounts],
        }

    return _make


async def _row(db_session, social_id, day, **metrics):
    await analytics_sync.upsert_day(db_session, social_id, day, metrics)
    await db_session.flush()


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

async def test_upsert_writes_a_day(db_session, workspace):
    ws = await workspace()
    await _row(db_session, ws["social_ids"][0], TODAY, followers=100, reach=50)

    row = (await db_session.execute(select(AnalyticsDaily))).scalars().one()
    assert row.followers == 100
    assert row.reach == 50


async def test_upsert_is_idempotent(db_session, workspace):
    """A sync gets retried, a night gets re-run after a deploy, and an operator
    re-runs one by hand. Each must correct the day, not duplicate it."""
    ws = await workspace()
    for _ in range(3):
        await _row(db_session, ws["social_ids"][0], TODAY, followers=100)

    rows = (await db_session.execute(select(AnalyticsDaily))).scalars().all()
    assert len(rows) == 1


async def test_a_re_run_corrects_the_day(db_session, workspace):
    ws = await workspace()
    await _row(db_session, ws["social_ids"][0], TODAY, followers=100)
    await _row(db_session, ws["social_ids"][0], TODAY, followers=125)

    row = (await db_session.execute(select(AnalyticsDaily))).scalars().one()
    assert row.followers == 125


async def test_a_partial_re_run_does_not_erase_other_metrics(db_session, workspace):
    """If a later sync fetches fewer metrics -- a rate limit, a scope change --
    it must not blank what an earlier one already stored."""
    ws = await workspace()
    await _row(db_session, ws["social_ids"][0], TODAY, followers=100, reach=500)
    await _row(db_session, ws["social_ids"][0], TODAY, followers=110)

    row = (await db_session.execute(select(AnalyticsDaily))).scalars().one()
    assert row.followers == 110
    assert row.reach == 500, "a partial sync erased a metric it did not fetch"


async def test_unreported_metrics_stay_null(db_session, workspace):
    """The whole reason every column is nullable."""
    ws = await workspace()
    await _row(db_session, ws["social_ids"][0], TODAY, followers=100)

    row = (await db_session.execute(select(AnalyticsDaily))).scalars().one()
    assert row.reach is None
    assert row.saves is None
    assert row.profile_visits is None


async def test_an_empty_payload_writes_nothing(db_session, workspace):
    """A platform that reported nothing leaves no row, so the gap is visible
    rather than looking like a day of zeros."""
    ws = await workspace()
    await _row(db_session, ws["social_ids"][0], TODAY)
    assert (await db_session.execute(select(AnalyticsDaily))).scalars().all() == []


async def test_days_are_separate_rows(db_session, workspace):
    ws = await workspace()
    for offset in range(3):
        await _row(
            db_session, ws["social_ids"][0], TODAY - timedelta(days=offset),
            followers=100 + offset,
        )
    rows = (await db_session.execute(select(AnalyticsDaily))).scalars().all()
    assert len(rows) == 3


# ---------------------------------------------------------------------------
# Per-platform null handling
# ---------------------------------------------------------------------------

def test_every_metric_a_connector_maps_is_a_real_column():
    """A provider reporting a name that is not a column is silently dropped.

    This replaces a test that drove ``get_analytics`` with ``access_token =
    "mock_token"`` and asserted on the result -- which only ever exercised
    ``mock_account_metrics``, the fabrication removed in this change. It read
    as a guard on provider honesty and was really pinning the field lists of
    invented data, so deleting the invention broke it.

    The invariant worth keeping is the last thing it asserted, and this checks
    it against the real code path: every target name in a connector's
    ``metrics_from`` mapping -- the mapping the live API response is read
    through -- must be a column something can actually store.

    **Two destinations, since 3.8.** ``metrics_from`` is a general normaliser,
    and competitor tracking reads Business Discovery through it into
    ``competitor_snapshots`` rather than ``analytics_daily``. The union is
    accepted rather than the test being scoped per call site: both are metric
    tables with nullable columns and the same absent-is-absent discipline, and
    what this is really guarding against is a *typo* -- a name in neither table
    is dropped in silence, which is how a metric quietly stops being recorded.
    A third destination should be added here, not worked around at the call
    site.
    """
    import ast
    import pathlib

    from app.models.competitor import CompetitorSnapshot

    storable = set(METRIC_FIELDS) | {
        column.name for column in CompetitorSnapshot.__table__.columns
    }

    offenders = []
    for path in sorted(pathlib.Path("app/connectors").glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "metrics_from"
                and len(node.args) == 2
                and isinstance(node.args[1], ast.Dict)
            ):
                continue
            for key in node.args[1].keys:
                if isinstance(key, ast.Constant) and key.value not in storable:
                    offenders.append(f"{path.name}:{node.lineno}: {key.value!r}")

    assert not offenders, (
        "these metric names are not columns of analytics_daily or "
        "competitor_snapshots, so the upsert would drop them without a "
        "word:\n" + "\n".join(offenders)
    )


async def test_a_platform_with_no_account_analytics_refuses_rather_than_guessing():
    """NotSupportedError, not an empty-looking success.

    collect_account treats the refusal as "nothing to record, and nothing
    wrong". A provider that instead returned plausible defaults would write a
    day of numbers nobody measured.
    """
    from unittest.mock import MagicMock

    from app.connectors.base import NotSupportedError
    from app.connectors.registry import get_provider, known_slugs

    account = MagicMock()
    account.access_token = "mock_token"
    account.config = {}

    for slug in known_slugs():
        try:
            reported = await get_provider(slug).get_analytics(account, None, None)
        except NotSupportedError:
            continue
        assert reported == {}, (
            f"{slug} produced metrics for an account with a placeholder token: "
            f"{reported}"
        )

async def test_a_null_platform_does_not_drag_the_total_down(db_session, workspace):
    """Two accounts, one reporting reach. The total is the one real figure --
    not an average halved by a platform that never measured it."""
    ws = await workspace(slugs=("instagram", "twitter"))
    await _row(db_session, ws["social_ids"][0], TODAY, followers=100, reach=1000)
    await _row(db_session, ws["social_ids"][1], TODAY, followers=50)

    window = resolve_range(ws["account"], "today", now=NOW.replace(day=15))
    totals = await analytics_query._totals(db_session, ws["social_ids"], window)
    assert totals["reach"] == 1000
    assert totals["followers"] == 150


async def test_a_metric_nobody_reports_stays_null_in_totals(db_session, workspace):
    ws = await workspace()
    await _row(db_session, ws["social_ids"][0], TODAY, followers=100)

    window = resolve_range(ws["account"], "today", now=NOW)
    totals = await analytics_query._totals(db_session, ws["social_ids"], window)
    assert totals["saves"] is None, "an unmeasured metric became 0"


# ---------------------------------------------------------------------------
# Aggregation rules
# ---------------------------------------------------------------------------

async def test_followers_are_not_summed_across_days(db_session, workspace):
    """1,000 followers on Monday plus 1,010 on Tuesday is not 2,010."""
    ws = await workspace()
    for offset, followers in enumerate((1000, 1010, 1025)):
        await _row(
            db_session, ws["social_ids"][0], TODAY - timedelta(days=offset),
            followers=followers,
        )

    window = resolve_range(ws["account"], "7d", now=NOW)
    totals = await analytics_query._totals(db_session, ws["social_ids"], window)
    assert totals["followers"] == 1000, (
        "the latest snapshot should be taken, not the sum"
    )


async def test_daily_metrics_are_summed(db_session, workspace):
    ws = await workspace()
    for offset in range(3):
        await _row(
            db_session, ws["social_ids"][0], TODAY - timedelta(days=offset),
            reach=100,
        )

    window = resolve_range(ws["account"], "7d", now=NOW)
    totals = await analytics_query._totals(db_session, ws["social_ids"], window)
    assert totals["reach"] == 300


def test_cumulative_fields_are_excluded_from_the_summable_set():
    assert not (set(analytics_query.SUMMABLE_FIELDS) & CUMULATIVE_FIELDS)


# ---------------------------------------------------------------------------
# Delta math
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "current,previous,change,percent",
    [
        (120, 100, 20, 20.0),
        (80, 100, -20, -20.0),
        (100, 100, 0, 0.0),
        # Any increase from nothing is infinite, so there is no percentage.
        (5, 0, 5, None),
        # A missing side makes both null: "up 100%" against a period with no
        # data is a fabrication.
        (None, 100, None, None),
        (100, None, None, None),
        (None, None, None, None),
    ],
)
def test_delta_math(current, previous, change, percent):
    result = analytics_query._delta(current, previous)
    assert result["change"] == change
    assert result["change_percent"] == percent


async def test_overview_compares_with_the_preceding_window(
    client, auth_header, db_session, workspace
):
    ws = await workspace()
    # 100 reach in the current 7 days, 50 in the 7 before.
    await _row(db_session, ws["social_ids"][0], _today(), reach=100)
    await _row(
        db_session, ws["social_ids"][0], _today() - timedelta(days=9), reach=50
    )

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/analytics/summary?range=7d",
            headers=auth_header(ws["owner"]),
        )
    ).json()
    reach = body["metrics"]["reach"]
    assert reach["value"] == 100
    assert reach["previous"] == 50
    assert reach["change"] == 50
    assert reach["change_percent"] == 100.0


async def test_engagement_rate_is_null_without_reach(
    client, auth_header, db_session, workspace
):
    """0% reads as "nobody engaged", which is a different claim from "we could
    not measure it"."""
    ws = await workspace()
    await _row(db_session, ws["social_ids"][0], _today(), likes=10)

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/analytics/summary",
            headers=auth_header(ws["owner"]),
        )
    ).json()
    assert body["metrics"]["engagement_rate"]["value"] is None


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

async def test_retention_respects_the_plan(db_session, workspace, set_limit):
    """The point of analytics_history_days being a plan feature."""
    ws = await workspace()
    await set_limit(ws["organization"], "analytics_history_days", 30)

    for offset in (5, 20, 45, 100):
        await _row(
            db_session, ws["social_ids"][0], TODAY - timedelta(days=offset),
            followers=100,
        )

    summary = await analytics_sync.prune(db_session, now=NOW)
    assert summary["deleted"] == 2

    remaining = (await db_session.execute(select(AnalyticsDaily))).scalars().all()
    assert {r.date for r in remaining} == {
        TODAY - timedelta(days=5), TODAY - timedelta(days=20)
    }


async def test_a_larger_plan_keeps_more(db_session, workspace, set_limit):
    ws = await workspace()
    await set_limit(ws["organization"], "analytics_history_days", 365)
    for offset in (5, 100, 200):
        await _row(
            db_session, ws["social_ids"][0], TODAY - timedelta(days=offset),
            followers=100,
        )

    assert (await analytics_sync.prune(db_session, now=NOW))["deleted"] == 0


async def test_unlimited_retention_deletes_nothing(db_session, workspace, set_limit):
    ws = await workspace()
    await set_limit(ws["organization"], "analytics_history_days", None)
    await _row(
        db_session, ws["social_ids"][0], TODAY - timedelta(days=3000), followers=1
    )

    summary = await analytics_sync.prune(db_session, now=NOW)
    assert summary["deleted"] == 0
    assert summary["unlimited"] == 1


async def test_retention_has_a_floor(db_session, workspace, set_limit):
    """A tiny allowance still needs enough history for a week-over-week
    comparison to mean anything."""
    ws = await workspace()
    await set_limit(ws["organization"], "analytics_history_days", 1)

    days = await analytics_sync.retention_days_for(db_session, ws["organization"])
    assert days >= analytics_sync.MIN_RETENTION_DAYS


async def test_retention_is_per_organization_not_one_global_cutoff(
    db_session, workspace, set_limit
):
    """The point of analytics_history_days being a plan feature: a paying
    workspace keeps more than a free one. A single cutoff would either
    over-delete for the payer or over-retain for everyone else.

    The two organizations must be on *different tiers* -- limits live on the
    plan, so two workspaces on the same plan necessarily share a retention
    window.
    """
    from app.models.account import SubscriptionTier

    short = await workspace()
    long = await workspace()
    long["organization"].subscription_tier = SubscriptionTier.PRO
    await db_session.flush()

    await set_limit(short["organization"], "analytics_history_days", 7)
    await set_limit(long["organization"], "analytics_history_days", 365)

    old = TODAY - timedelta(days=100)
    await _row(db_session, short["social_ids"][0], old, followers=1)
    await _row(db_session, long["social_ids"][0], old, followers=1)

    await analytics_sync.prune(db_session, now=NOW)
    remaining = (await db_session.execute(select(AnalyticsDaily))).scalars().all()
    assert [r.social_account_id for r in remaining] == [long["social_ids"][0]], (
        "retention did not follow each organization's own plan"
    )


# ---------------------------------------------------------------------------
# Backoff
# ---------------------------------------------------------------------------

async def test_backoff_grows_and_respects_the_platform():
    delays = [analytics_sync.backoff_delay(n) for n in range(1, 6)]
    assert delays[0] < delays[-1]
    assert all(d <= analytics_sync.MAX_BACKOFF_SECONDS for d in delays)
    # The platform's own figure wins over the curve.
    assert analytics_sync.backoff_delay(1, retry_after=45) == 45
    assert (
        analytics_sync.backoff_delay(1, retry_after=99999)
        == analytics_sync.MAX_BACKOFF_SECONDS
    )


async def test_backoff_is_jittered():
    """Otherwise a workspace's accounts retry in lockstep and re-trigger the
    same limit."""
    assert len({analytics_sync.backoff_delay(3) for _ in range(30)}) > 1


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

async def test_platforms_breakdown(client, auth_header, db_session, workspace):
    ws = await workspace(slugs=("instagram", "twitter"))
    await _row(db_session, ws["social_ids"][0], _today(), followers=100, reach=500)
    await _row(db_session, ws["social_ids"][1], _today(), followers=50)

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/analytics/platforms",
            headers=auth_header(ws["owner"]),
        )
    ).json()
    by_slug = {p["platform"]: p for p in body["platforms"]}
    assert by_slug["instagram"]["reach"] == 500
    assert by_slug["twitter"]["reach"] is None, "X reports no reach; it must stay null"


async def test_audience_series_and_growth(
    client, auth_header, db_session, workspace
):
    ws = await workspace()
    for offset, followers in ((6, 1000), (0, 1100)):
        await _row(
            db_session, ws["social_ids"][0],
            _today() - timedelta(days=offset), followers=followers,
        )

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/analytics/audience?range=7d",
            headers=auth_header(ws["owner"]),
        )
    ).json()
    assert len(body["series"]) == 2
    assert body["current"] == 1100
    assert body["change"] == 100
    assert body["change_percent"] == 10.0


async def test_growth_is_null_with_a_single_snapshot(
    client, auth_header, db_session, workspace
):
    """One point shows a value, not growth."""
    ws = await workspace()
    await _row(db_session, ws["social_ids"][0], _today(), followers=1000)

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/analytics/audience?range=7d",
            headers=auth_header(ws["owner"]),
        )
    ).json()
    assert body["change"] is None


async def test_posts_are_sortable(client, auth_header, db_session, workspace):
    from app.models.post import Post, PostStatus
    from app.models.post_performance import PostPerformance

    ws = await workspace()
    for likes, impressions in ((5, 900), (50, 100)):
        post = Post(
            id=uuid.uuid4(), user_id=ws["owner"].id, account_id=ws["account_id"],
            content="p", status=PostStatus.PUBLISHED, target_accounts=[],
        )
        db_session.add(post)
        await db_session.flush()
        db_session.add(
            PostPerformance(
                id=uuid.uuid4(), post_id=post.id, platform_type="instagram",
                impressions=impressions, reach=100, likes=likes, comments=0,
                shares=0, saves=0, clicks=0, video_views=0,
            )
        )
    await db_session.flush()

    base = f"/api/v1/accounts/{ws['account_id']}/analytics/posts"
    headers = auth_header(ws["owner"])
    by_engagement = (await client.get(f"{base}?sort=engagement", headers=headers)).json()
    by_impressions = (await client.get(f"{base}?sort=impressions", headers=headers)).json()

    assert by_engagement["posts"][0]["engagement"] == 50
    assert by_impressions["posts"][0]["impressions"] == 900


async def test_csv_export_streams_with_a_filename(
    client, auth_header, db_session, workspace
):
    ws = await workspace()
    await _row(db_session, ws["social_ids"][0], _today(), followers=100, reach=50)

    response = await client.get(
        f"/api/v1/accounts/{ws['account_id']}/analytics/summary?format=csv",
        headers=auth_header(ws["owner"]),
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"

    lines = response.text.strip().splitlines()
    assert lines[0].startswith("metric,value")
    assert any(line.startswith("reach,50") for line in lines)


async def test_csv_renders_null_as_blank_not_the_word_none(
    client, auth_header, db_session, workspace
):
    """A spreadsheet should read an unreported metric as empty, not as text."""
    ws = await workspace()
    await _row(db_session, ws["social_ids"][0], _today(), followers=100)

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/analytics/summary?format=csv",
            headers=auth_header(ws["owner"]),
        )
    ).text
    assert "None" not in body
    assert "saves,," in body.replace(" ", "")


async def test_another_workspaces_analytics_are_not_included(
    client, auth_header, db_session, workspace
):
    mine = await workspace()
    theirs = await workspace()
    await _row(db_session, theirs["social_ids"][0], _today(), followers=9999)

    body = (
        await client.get(
            f"/api/v1/accounts/{mine['account_id']}/analytics/summary",
            headers=auth_header(mine["owner"]),
        )
    ).json()
    assert body["metrics"]["followers"]["value"] is None
    assert body["has_data"] is False


async def test_a_non_member_is_refused(client, auth_header, workspace, user_factory):
    ws = await workspace()
    stranger = await user_factory()
    response = await client.get(
        f"/api/v1/accounts/{ws['account_id']}/analytics/summary",
        headers=auth_header(stranger),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# The analytics fetch over real HTTP
#
# Every other test here uses a mock token, which short-circuits before the
# first request -- so the whole HTTP half of get_analytics was covered only by
# the structural grep in test_connectors.py. That grep caught this code being
# added back as blocking `httpx.Client`; it cannot catch the parsing being
# wrong. These drive the real path through a MockTransport.
# ---------------------------------------------------------------------------


async def test_get_analytics_parses_a_real_response(monkeypatch):
    """A live X response maps onto the metric names the model stores."""
    import httpx

    from app.connectors.registry import get_provider

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/2/users/me"
        return httpx.Response(
            200,
            json={
                "data": {
                    "public_metrics": {
                        "followers_count": 4210,
                        "following_count": 380,
                        "tweet_count": 1290,
                    }
                }
            },
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **k: real_client(*a, **{**k, "transport": httpx.MockTransport(handler)}),
    )

    account = SimpleNamespace(access_token="real-looking-token", config={})
    metrics = await get_provider("twitter").get_analytics(account, None, None)

    assert metrics == {"followers": 4210, "following": 380, "posts_count": 1290}
    # Not merely missing from the dict by accident -- X does not report these
    # on this tier, and absent is what the sync layer stores as null.
    assert "reach" not in metrics and "impressions" not in metrics


async def test_get_analytics_does_not_block_the_event_loop(monkeypatch):
    """The nightly sync walks every connected account in sequence. If one
    provider's fetch parked a thread, a workspace with many connections would
    stall the whole loop rather than just waiting on the network."""
    import asyncio

    import httpx

    from app.connectors.registry import get_provider

    async def handler(request: httpx.Request) -> httpx.Response:
        # Yield inside the request, the way a real socket read would.
        await asyncio.sleep(0)
        return httpx.Response(200, json={"data": {"public_metrics": {"followers_count": 7}}})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **k: real_client(*a, **{**k, "transport": httpx.MockTransport(handler)}),
    )

    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0)

    task = asyncio.create_task(ticker())
    try:
        account = SimpleNamespace(access_token="real-looking-token", config={})
        metrics = await get_provider("twitter").get_analytics(account, None, None)
    finally:
        task.cancel()

    assert metrics == {"followers": 7}
    assert ticks > 0, "nothing else ran during the fetch -- it is still blocking"


async def test_engagement_rate_is_null_when_no_interaction_is_reported(
    db_session, workspace
):
    """Reach without any interaction metric is not 0% engagement.

    A workspace connected only to X and LinkedIn has real reach and an
    entirely unmeasured numerator -- neither exposes account-level likes. The
    old code summed those nulls as zero and reported a confident 0.0%, which
    reads as "your content is failing" rather than "we cannot measure this".
    Found by driving the running server, not by the suite.
    """
    ws = await workspace()
    today = _today()
    await analytics_sync.upsert_day(
        db_session, ws["social_ids"][0], today, {"reach": 61588, "impressions": 154169}
    )
    await db_session.commit()

    window = resolve_range(ws["account"], "7d", None, None)
    payload = await analytics_query.overview(db_session, ws["account"], window)

    assert payload["metrics"]["reach"]["value"] == 61588
    assert payload["metrics"]["engagement_rate"]["value"] is None, (
        "unmeasured interactions were coalesced to zero"
    )


async def test_engagement_rate_counts_a_partially_reported_numerator(
    db_session, workspace
):
    """One reported interaction metric is enough to compute a rate.

    A platform that reports likes but has no "saves" concept genuinely
    contributed no saves, so the absent parts are zero here -- unlike the case
    where nothing at all was reported.
    """
    ws = await workspace()
    today = _today()
    await analytics_sync.upsert_day(
        db_session, ws["social_ids"][0], today, {"reach": 1000, "likes": 250}
    )
    await db_session.commit()

    window = resolve_range(ws["account"], "7d", None, None)
    payload = await analytics_query.overview(db_session, ws["account"], window)

    assert payload["metrics"]["engagement_rate"]["value"] == 25.0


# ---------------------------------------------------------------------------
# The dashboard's own endpoint, found lying in Walk B
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_overview_endpoint_reports_nulls_where_nothing_was_measured(
    client, auth_header, user_factory, account_factory
):
    """A brand-new workspace has measured nothing, and must be told so.

    Found by walking the product as a new customer: the dashboard showed
    "Total Reach 0", "Total Engagement 0" and "Avg Engagement Rate 0.00%" on a
    workspace with no connected accounts and no posts, because the endpoint
    wrapped every aggregate in ``coalesce(..., 0)``. Those read as
    measurements -- "nobody saw your posts" -- rather than as the absence of
    any. The reports and the analytics page were fixed for exactly this in an
    earlier phase; this endpoint was missed because nothing tested it.

    ``total_posts`` stays 0: a count of published posts is a real answer.
    """
    owner = await user_factory(password="hunter2-correct-horse")
    account = await account_factory(owner)

    response = await client.get(
        f"/api/v1/accounts/{account.id}/analytics/overview?period=7d",
        headers=auth_header(owner),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_reach"] is None
    assert body["total_engagement"] is None
    assert body["avg_engagement_rate"] is None
    # Never computed here before -- it was a hardcoded 0 reporting "gained
    # nobody" to every workspace in the product.
    assert body["total_followers_gained"] is None
    assert body["total_posts"] == 0
    # And no comparison can be drawn from an unmeasured previous period.
    assert body["comparison"]["reach_change_pct"] is None
