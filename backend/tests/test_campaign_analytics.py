"""Campaign-scoped performance aggregation.

The thing under test throughout is **filtering**: a campaign dashboard that
quietly includes a neighbouring campaign's posts, or the workspace's unattached
ones, is worse than no dashboard -- it is a number an agency would put in front
of a client.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.campaign import Campaign, CampaignStatus
from app.models.post import Post, PostStatus
from app.models.post_performance import PostPerformance
from app.services import campaign_analytics

PASSWORD = "TestPass123!"


@pytest.fixture
async def workspace(db_session, user_factory, account_factory, organization_factory):
    async def _make(tz="UTC"):
        owner = await user_factory(password=PASSWORD)
        organization = await organization_factory(owner)
        account = await account_factory(owner, organization=organization)
        account.settings = {"timezone": tz}
        await db_session.flush()
        return {"owner": owner, "organization": organization, "account": account}

    return _make


@pytest.fixture
async def campaign_factory(db_session):
    async def _make(ws, *, name="Spring push", start=None, end=None, status=None):
        campaign = Campaign(
            id=uuid.uuid4(),
            user_id=ws["owner"].id,
            account_id=ws["account"].id,
            name=name,
            platforms=[],
            status=status or CampaignStatus.ACTIVE,
            start_date=start,
            end_date=end,
        )
        db_session.add(campaign)
        await db_session.flush()
        return campaign

    return _make


@pytest.fixture
async def post_factory(db_session):
    async def _make(
        ws, *, campaign=None, created=None, status=PostStatus.PUBLISHED,
        platform="instagram", reach=100, likes=10, comments=0, shares=0,
        saves=0, impressions=0, clicks=0, content="post",
    ):
        post = Post(
            id=uuid.uuid4(),
            user_id=ws["owner"].id,
            account_id=ws["account"].id,
            content=content,
            status=status,
            target_accounts=[],
            campaign_id=campaign.id if campaign is not None else None,
        )
        db_session.add(post)
        await db_session.flush()
        if created is not None:
            post.created_at = created
            await db_session.flush()
        db_session.add(
            PostPerformance(
                id=uuid.uuid4(), post_id=post.id, platform_type=platform,
                impressions=impressions, reach=reach, likes=likes,
                comments=comments, shares=shares, saves=saves, clicks=clicks,
                video_views=0,
            )
        )
        await db_session.flush()
        return post

    return _make


def _window_covering_now():
    """A window wide enough that "created just now" falls inside it."""
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=5), today + timedelta(days=5)


# ---------------------------------------------------------------------------
# Filtering -- the point of the module
# ---------------------------------------------------------------------------

async def test_totals_exclude_another_campaigns_posts(
    db_session, workspace, campaign_factory, post_factory
):
    ws = await workspace()
    start, end = _window_covering_now()
    mine = await campaign_factory(ws, name="Mine", start=start, end=end)
    theirs = await campaign_factory(ws, name="Theirs", start=start, end=end)

    await post_factory(ws, campaign=mine, reach=100, likes=10)
    await post_factory(ws, campaign=theirs, reach=999, likes=999)

    window = campaign_analytics.campaign_window(ws["account"], mine)
    totals = await campaign_analytics.totals(db_session, mine.id, window)

    assert totals["reach"] == 100
    assert totals["engagement"] == 10


async def test_totals_exclude_posts_with_no_campaign(
    db_session, workspace, campaign_factory, post_factory
):
    """The workspace's ordinary posts are not the campaign's work."""
    ws = await workspace()
    start, end = _window_covering_now()
    campaign = await campaign_factory(ws, start=start, end=end)

    await post_factory(ws, campaign=campaign, reach=50, likes=5)
    await post_factory(ws, campaign=None, reach=4000, likes=400)

    window = campaign_analytics.campaign_window(ws["account"], campaign)
    totals = await campaign_analytics.totals(db_session, campaign.id, window)

    assert totals["reach"] == 50
    assert totals["engagement"] == 5


async def test_totals_exclude_posts_created_outside_the_campaign_window(
    db_session, workspace, campaign_factory, post_factory
):
    """A post attached long after the campaign ended is not its work.

    Without the window bound a finished campaign's numbers would keep moving
    every time someone linked an old post to it.
    """
    ws = await workspace()
    today = datetime.now(timezone.utc).date()
    campaign = await campaign_factory(
        ws, start=today - timedelta(days=10), end=today - timedelta(days=5)
    )

    inside = datetime.now(timezone.utc) - timedelta(days=7)
    after = datetime.now(timezone.utc) - timedelta(days=1)
    await post_factory(ws, campaign=campaign, created=inside, reach=70, likes=7)
    await post_factory(ws, campaign=campaign, created=after, reach=800, likes=80)

    window = campaign_analytics.campaign_window(ws["account"], campaign)
    totals = await campaign_analytics.totals(db_session, campaign.id, window)

    assert totals["reach"] == 70
    assert totals["engagement"] == 7


async def test_deleted_posts_are_excluded(
    db_session, workspace, campaign_factory, post_factory
):
    ws = await workspace()
    start, end = _window_covering_now()
    campaign = await campaign_factory(ws, start=start, end=end)

    await post_factory(ws, campaign=campaign, reach=30, likes=3)
    gone = await post_factory(ws, campaign=campaign, reach=500, likes=50)
    gone.deleted_at = datetime.now(timezone.utc)
    await db_session.flush()

    window = campaign_analytics.campaign_window(ws["account"], campaign)
    totals = await campaign_analytics.totals(db_session, campaign.id, window)

    assert totals["reach"] == 30


async def test_top_posts_are_filtered_to_the_campaign(
    db_session, workspace, campaign_factory, post_factory
):
    """The shared analytics query, narrowed -- not a second query that drifts."""
    ws = await workspace()
    start, end = _window_covering_now()
    campaign = await campaign_factory(ws, start=start, end=end)

    await post_factory(ws, campaign=campaign, content="ours", reach=10, likes=1)
    await post_factory(ws, campaign=None, content="not ours", reach=10, likes=900)

    data = await campaign_analytics.dashboard(db_session, ws["account"], campaign)
    titles = [p["title"] for p in data["top_posts"]]

    assert titles == ["ours"]


# ---------------------------------------------------------------------------
# Per-platform split
# ---------------------------------------------------------------------------

async def test_platform_split_groups_by_platform_and_filters(
    db_session, workspace, campaign_factory, post_factory
):
    ws = await workspace()
    start, end = _window_covering_now()
    campaign = await campaign_factory(ws, start=start, end=end)
    other = await campaign_factory(ws, name="Other", start=start, end=end)

    await post_factory(ws, campaign=campaign, platform="instagram", reach=100, likes=10)
    await post_factory(ws, campaign=campaign, platform="instagram", reach=50, likes=5)
    await post_factory(ws, campaign=campaign, platform="facebook", reach=20, likes=2)
    await post_factory(ws, campaign=other, platform="instagram", reach=777, likes=77)

    window = campaign_analytics.campaign_window(ws["account"], campaign)
    split = await campaign_analytics.platform_split(db_session, campaign.id, window)

    by_platform = {row["platform"]: row for row in split}
    assert set(by_platform) == {"instagram", "facebook"}
    assert by_platform["instagram"]["reach"] == 150
    assert by_platform["instagram"]["posts"] == 2
    assert by_platform["facebook"]["reach"] == 20


# ---------------------------------------------------------------------------
# Null is not zero
# ---------------------------------------------------------------------------

async def test_engagement_rate_is_null_without_reach(
    db_session, workspace, campaign_factory, post_factory
):
    """0% engagement reads as "your content failed". Null says "unmeasured"."""
    ws = await workspace()
    start, end = _window_covering_now()
    campaign = await campaign_factory(ws, start=start, end=end)
    await post_factory(ws, campaign=campaign, reach=0, likes=0)

    window = campaign_analytics.campaign_window(ws["account"], campaign)
    totals = await campaign_analytics.totals(db_session, campaign.id, window)

    assert totals["reach"] == 0
    assert totals["engagement_rate"] is None


async def test_engagement_rate_is_a_percentage_of_reach(
    db_session, workspace, campaign_factory, post_factory
):
    ws = await workspace()
    start, end = _window_covering_now()
    campaign = await campaign_factory(ws, start=start, end=end)
    await post_factory(
        ws, campaign=campaign, reach=200, likes=10, comments=5, shares=3, saves=2
    )

    window = campaign_analytics.campaign_window(ws["account"], campaign)
    totals = await campaign_analytics.totals(db_session, campaign.id, window)

    assert totals["engagement"] == 20
    assert totals["engagement_rate"] == 10.0


async def test_an_empty_campaign_reports_zero_totals_and_a_null_rate(
    db_session, workspace, campaign_factory
):
    ws = await workspace()
    start, end = _window_covering_now()
    campaign = await campaign_factory(ws, start=start, end=end)

    window = campaign_analytics.campaign_window(ws["account"], campaign)
    totals = await campaign_analytics.totals(db_session, campaign.id, window)

    assert totals["reach"] == 0
    assert totals["engagement_rate"] is None


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------

async def test_window_uses_the_workspace_clock_not_the_servers(
    db_session, workspace, campaign_factory
):
    """Campaign dates are calendar dates on the workspace's clock.

    A campaign starting on the 10th for a Sydney workspace begins at 00:00
    Sydney -- 13:00 UTC on the 9th -- not at 00:00 UTC.
    """
    ws = await workspace(tz="Australia/Sydney")
    campaign = await campaign_factory(
        ws, start=date(2026, 3, 10), end=date(2026, 3, 20)
    )

    window = campaign_analytics.campaign_window(ws["account"], campaign)

    assert window.timezone_name == "Australia/Sydney"
    assert window.start.astimezone(timezone.utc) == datetime(
        2026, 3, 9, 13, 0, tzinfo=timezone.utc
    )
    # end_date is inclusive to a reader; the window is half-open, so it runs to
    # the start of the 21st.
    assert window.end.astimezone(timezone.utc) == datetime(
        2026, 3, 20, 13, 0, tzinfo=timezone.utc
    )


async def test_a_campaign_with_no_end_date_runs_to_now(
    db_session, workspace, campaign_factory
):
    ws = await workspace()
    campaign = await campaign_factory(ws, start=date(2026, 1, 1), end=None)
    now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    window = campaign_analytics.campaign_window(ws["account"], campaign, now=now)

    assert window.end == now
    assert window.label == "since 2026-01-01"


async def test_a_campaign_with_no_start_date_runs_from_its_creation(
    db_session, workspace, campaign_factory
):
    ws = await workspace()
    campaign = await campaign_factory(ws, start=None, end=None)

    window = campaign_analytics.campaign_window(ws["account"], campaign)

    assert window.start <= datetime.now(timezone.utc)
    assert window.label == "since the campaign was created"


async def test_an_end_before_the_start_does_not_produce_a_negative_window(
    db_session, workspace, campaign_factory
):
    """Otherwise the window silently matches nothing and every total is zero."""
    ws = await workspace()
    campaign = await campaign_factory(
        ws, start=date(2026, 5, 10), end=date(2026, 5, 1)
    )

    window = campaign_analytics.campaign_window(ws["account"], campaign)

    assert window.end >= window.start


# ---------------------------------------------------------------------------
# Progress against schedule
# ---------------------------------------------------------------------------

async def test_progress_counts_published_and_scheduled_posts(
    db_session, workspace, campaign_factory, post_factory
):
    ws = await workspace()
    start, end = _window_covering_now()
    campaign = await campaign_factory(ws, start=start, end=end)

    await post_factory(ws, campaign=campaign, status=PostStatus.PUBLISHED)
    await post_factory(ws, campaign=campaign, status=PostStatus.PARTIALLY_PUBLISHED)
    await post_factory(ws, campaign=campaign, status=PostStatus.SCHEDULED)
    await post_factory(ws, campaign=campaign, status=PostStatus.DRAFT)

    window = campaign_analytics.campaign_window(ws["account"], campaign)
    progress = await campaign_analytics.progress(db_session, campaign, window)

    assert progress["posts_total"] == 4
    # A partial publish reached an audience, so it counts as published.
    assert progress["posts_published"] == 2
    assert progress["posts_scheduled"] == 1
    assert progress["post_progress"] == 0.5


async def test_an_open_ended_campaign_has_no_time_progress(
    db_session, workspace, campaign_factory
):
    """Its window ends "now", so a fraction would always read 100% complete."""
    ws = await workspace()
    campaign = await campaign_factory(ws, start=date(2026, 1, 1), end=None)

    window = campaign_analytics.campaign_window(ws["account"], campaign)
    progress = await campaign_analytics.progress(db_session, campaign, window)

    assert progress["open_ended"] is True
    assert progress["time_progress"] is None
    assert progress["days_total"] is None
    assert progress["days_remaining"] is None
    assert progress["on_track"] is None


async def test_a_campaign_with_no_posts_has_no_post_progress(
    db_session, workspace, campaign_factory
):
    """Null, not 0 -- there is nothing to be a fraction of."""
    ws = await workspace()
    start, end = _window_covering_now()
    campaign = await campaign_factory(ws, start=start, end=end)

    window = campaign_analytics.campaign_window(ws["account"], campaign)
    progress = await campaign_analytics.progress(db_session, campaign, window)

    assert progress["posts_total"] == 0
    assert progress["post_progress"] is None
    assert progress["on_track"] is None


async def test_on_track_compares_publishing_against_elapsed_time(
    db_session, workspace, campaign_factory, post_factory
):
    ws = await workspace()
    now = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)
    # A ten-day campaign, four days elapsed.
    campaign = await campaign_factory(
        ws, start=date(2026, 5, 1), end=date(2026, 5, 10)
    )
    created = datetime(2026, 5, 2, tzinfo=timezone.utc)
    await post_factory(
        ws, campaign=campaign, created=created, status=PostStatus.PUBLISHED
    )
    await post_factory(
        ws, campaign=campaign, created=created, status=PostStatus.SCHEDULED
    )

    window = campaign_analytics.campaign_window(ws["account"], campaign, now=now)
    progress = await campaign_analytics.progress(db_session, campaign, window, now=now)

    # 4 of 10 days elapsed, 1 of 2 posts out: ahead of schedule.
    assert progress["time_progress"] == 0.4
    assert progress["post_progress"] == 0.5
    assert progress["on_track"] is True


# ---------------------------------------------------------------------------
# What the dashboard refuses to claim
# ---------------------------------------------------------------------------

async def test_the_payload_says_what_cannot_be_attributed(
    db_session, workspace, campaign_factory
):
    """analytics_daily has no campaign dimension.

    Follower counts and audience demographics are per-connection daily
    snapshots. Filtering them by campaign would mean inventing attribution, so
    they are absent -- and the payload says why rather than leaving a reader to
    wonder where the follower count went.
    """
    ws = await workspace()
    campaign = await campaign_factory(ws)

    data = await campaign_analytics.dashboard(db_session, ws["account"], campaign)

    assert "audience" not in data
    assert data["not_attributable"]
    assert any("campaign dimension" in note for note in data["not_attributable"])


# ---------------------------------------------------------------------------
# The endpoints
# ---------------------------------------------------------------------------

async def test_performance_endpoint_returns_the_dashboard(
    client, auth_header, db_session, workspace, campaign_factory, post_factory
):
    ws = await workspace()
    start, end = _window_covering_now()
    campaign = await campaign_factory(ws, start=start, end=end)
    other = await campaign_factory(ws, name="Other", start=start, end=end)
    await post_factory(ws, campaign=campaign, reach=100, likes=10)
    await post_factory(ws, campaign=other, reach=999, likes=999)

    response = await client.get(
        f"/api/v1/accounts/{ws['account'].id}/campaigns/{campaign.id}/performance",
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["totals"]["reach"] == 100
    assert body["campaign"]["id"] == str(campaign.id)
    assert body["window"]["timezone"] == "UTC"
    assert body["progress"]["posts_total"] == 1


async def test_performance_needs_analytics_view(
    client, auth_header, db_session, workspace, campaign_factory,
    user_factory, member_factory,
):
    """A contributor may write drafts and may not read the workspace's numbers.

    Reading them one campaign at a time is still reading them.
    """
    from app.models.team_member import InvitationStatus, TeamRole

    ws = await workspace()
    campaign = await campaign_factory(ws)
    contributor = await user_factory(password=PASSWORD)
    await member_factory(
        contributor, ws["account"], role=TeamRole.CONTRIBUTOR,
        invitation_status=InvitationStatus.ACCEPTED,
    )

    response = await client.get(
        f"/api/v1/accounts/{ws['account'].id}/campaigns/{campaign.id}/performance",
        headers=auth_header(contributor),
    )

    assert response.status_code == 403


async def test_another_workspaces_campaign_is_404(
    client, auth_header, workspace, campaign_factory
):
    ws = await workspace()
    other = await workspace()
    campaign = await campaign_factory(other)

    response = await client.get(
        f"/api/v1/accounts/{ws['account'].id}/campaigns/{campaign.id}/performance",
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code == 404


async def test_generate_campaign_report_queues_a_scoped_report(
    client, auth_header, db_session, workspace, campaign_factory
):
    from sqlalchemy import select

    from app.models.report import Report

    ws = await workspace()
    campaign = await campaign_factory(
        ws, name="Spring push", start=date(2026, 4, 1), end=date(2026, 4, 30)
    )

    response = await client.post(
        f"/api/v1/accounts/{ws['account'].id}/campaigns/{campaign.id}/report",
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["campaign_id"] == str(campaign.id)
    # The period is the campaign's span, fixed at request time.
    assert body["period_start"] == "2026-04-01"
    assert body["period_end"] == "2026-04-30"
    assert "Spring push" in body["title"]

    report = (
        await db_session.execute(select(Report).where(Report.id == uuid.UUID(body["id"])))
    ).scalar_one()
    assert report.campaign_id == campaign.id


async def test_generating_a_campaign_report_needs_reports_view(
    client, auth_header, workspace, campaign_factory, user_factory, member_factory
):
    from app.models.team_member import InvitationStatus, TeamRole

    ws = await workspace()
    campaign = await campaign_factory(ws)
    contributor = await user_factory(password=PASSWORD)
    await member_factory(
        contributor, ws["account"], role=TeamRole.CONTRIBUTOR,
        invitation_status=InvitationStatus.ACCEPTED,
    )

    response = await client.post(
        f"/api/v1/accounts/{ws['account'].id}/campaigns/{campaign.id}/report",
        headers=auth_header(contributor),
    )

    assert response.status_code == 403


async def test_a_campaign_report_counts_against_the_report_allowance(
    client, auth_header, workspace, campaign_factory, set_limit
):
    """It is a report. Routing around the meter by going via a campaign would
    make the entitlement meaningless."""
    from app.services import entitlement_service as ent

    ws = await workspace()
    campaign = await campaign_factory(ws)
    await set_limit(ws["organization"], ent.REPORTS_PER_MONTH, 1)
    url = f"/api/v1/accounts/{ws['account'].id}/campaigns/{campaign.id}/report"

    first = await client.post(url, headers=auth_header(ws["owner"]))
    second = await client.post(url, headers=auth_header(ws["owner"]))

    assert first.status_code == 202
    assert second.status_code in (402, 403, 429)


# ---------------------------------------------------------------------------
# The report a client actually receives
# ---------------------------------------------------------------------------

class _FakeStorage:
    def __init__(self):
        self.written: dict[str, bytes] = {}

    def put_object(self, key, data, *, content_type=""):
        self.written[key] = data

    def presign_download(self, key):
        return f"https://example.test/{key}"


async def test_a_campaign_report_renders_from_the_campaigns_posts_only(
    db_session, workspace, campaign_factory, post_factory, monkeypatch
):
    """End to end through the real report pipeline.

    Both the aggregation and the renderers run; the assertion is that the
    figures came from the campaign's posts and not the workspace's.
    """
    from app.models.report import ReportStatus, ReportType
    from app.services import report_jobs

    ws = await workspace()
    start, end = _window_covering_now()
    campaign = await campaign_factory(ws, name="Spring push", start=start, end=end)
    await post_factory(ws, campaign=campaign, reach=120, likes=12)
    await post_factory(ws, campaign=None, reach=9000, likes=900)

    storage = _FakeStorage()
    monkeypatch.setattr(report_jobs.storage, "get_storage", lambda: storage)

    report = await report_jobs.create(
        db_session, ws["account"], report_type=ReportType.CUSTOM,
        created_by=ws["owner"].id, start=start, end=end,
        title="Spring push — campaign report", campaign_id=campaign.id,
    )
    await report_jobs.generate(db_session, report)

    assert report.status is ReportStatus.READY, report.error
    assert report.file_keys
    assert all(storage.written[key] for key in report.file_keys.values())

    summary = report.summary
    assert summary["metrics"]["reach"]["value"] == 120
    assert summary["campaign"]["name"] == "Spring push"
    # The unattached post's 9,000 reach is nowhere in it.
    assert summary["metrics"]["reach"]["value"] != 9120


async def test_a_campaign_report_does_not_claim_audience_figures(
    db_session, workspace, campaign_factory, post_factory, monkeypatch
):
    """Follower movement is not a campaign's to claim.

    analytics_daily is a per-connection daily snapshot with no campaign
    dimension. A campaign report that showed the workspace's follower growth
    would be attributing it to the campaign.
    """
    from app.models.report import ReportType
    from app.services import report_jobs

    ws = await workspace()
    start, end = _window_covering_now()
    campaign = await campaign_factory(ws, start=start, end=end)
    await post_factory(ws, campaign=campaign, reach=10, likes=1)

    monkeypatch.setattr(report_jobs.storage, "get_storage", lambda: _FakeStorage())
    report = await report_jobs.create(
        db_session, ws["account"], report_type=ReportType.CUSTOM,
        created_by=ws["owner"].id, start=start, end=end, campaign_id=campaign.id,
    )
    await report_jobs.generate(db_session, report)

    summary = report.summary
    assert "audience" not in summary
    assert summary["not_attributable"]
    # The campaign summary sentence never mentions audience growth, which is
    # the clause the workspace-wide summary adds and this one must not.
    assert "audience" not in summary["executive_summary"].lower()


async def test_the_rendered_csv_names_each_platform(
    db_session, workspace, campaign_factory, post_factory, monkeypatch,
    social_platform_factory,
):
    """Assert on the bytes, not the payload.

    The first version of this feature produced a correct payload and a CSV
    whose every platform row began with an empty cell: the renderers read
    ``platform_name`` and the campaign split only carried ``platform``. The
    payload-level tests all passed. Found by reading a generated report.
    """
    from app.models.report import ReportFormat, ReportStatus, ReportType
    from app.services import report_jobs

    ws = await workspace()
    await social_platform_factory(ws["owner"], ws["account"], slug="facebook", name="Facebook")
    start, end = _window_covering_now()
    campaign = await campaign_factory(ws, start=start, end=end)
    await post_factory(ws, campaign=campaign, platform="facebook", reach=200, likes=20)

    storage = _FakeStorage()
    monkeypatch.setattr(report_jobs.storage, "get_storage", lambda: storage)
    report = await report_jobs.create(
        db_session, ws["account"], report_type=ReportType.CUSTOM,
        created_by=ws["owner"].id, start=start, end=end, campaign_id=campaign.id,
    )
    await report_jobs.generate(db_session, report)
    assert report.status is ReportStatus.READY, report.error

    csv_key = report.file_keys[ReportFormat.CSV.value]
    body = storage.written[csv_key]
    text = body.decode("utf-8-sig") if isinstance(body, bytes) else body

    platform_line = next(
        line for line in text.splitlines()
        if line.count(",") >= 5 and "200" in line and "REACH" not in line
    )
    assert not platform_line.startswith(","), (
        f"platform row has no name: {platform_line!r}"
    )
    assert "acebook" in platform_line
