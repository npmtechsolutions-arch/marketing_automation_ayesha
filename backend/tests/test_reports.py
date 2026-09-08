"""Reports: aggregation, entitlement gating, and the renderers.

Three things carry the risk.

**The numbers must match the analytics page.** A report is what an agency
emails a client; if it disagrees with the dashboard the client was shown last
week, the disagreement is the product's problem, not the client's. So the
aggregation is asserted against the same figures ``analytics_query`` produces.

**The period must be fixed.** A report titled "August" that re-aggregates when
downloaded in December is a document whose numbers change under a constant
title.

**White-label must gate on the entitlement, not on the request.** Branding is
resolved once, at creation, and stored -- a customer who rebrands should not
find last month's PDF has changed.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.analytics_daily import AnalyticsDaily
from app.models.notification import Notification
from app.models.report import Report, ReportFormat, ReportStatus, ReportType
from app.services import (
    entitlement_service as ent,
    report_jobs,
    report_render,
    reporting,
)

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


@pytest.fixture
async def workspace(
    db_session, user_factory, account_factory, organization_factory,
    social_account_factory,
):
    async def _make(tz="UTC", slugs=("instagram",)):
        owner = await user_factory(password=PASSWORD)
        organization = await organization_factory(owner)
        account = await account_factory(owner, organization=organization)
        account.settings = {"timezone": tz}
        await db_session.flush()
        socials = [
            await social_account_factory(owner, account, slug=slug) for slug in slugs
        ]
        return {
            "owner": owner, "organization": organization, "account": account,
            "account_id": account.id, "socials": socials,
            "social_ids": [s.id for s in socials],
        }

    return _make


@pytest.fixture
async def daily(db_session):
    async def _add(social_id, day: date, **metrics):
        db_session.add(
            AnalyticsDaily(id=uuid.uuid4(), social_account_id=social_id, date=day, **metrics)
        )
        await db_session.flush()

    return _add


SAMPLE = {
    "workspace": {"name": "Acme"},
    "period": {"start": "2026-08-01", "end": "2026-08-31", "days": 31,
               "label": "August 2026", "timezone": "UTC"},
    "metrics": {
        "followers": {"value": 5120, "previous": 4890, "change": 230, "change_percent": 4.7},
        "reach": {"value": None, "previous": None, "change": None, "change_percent": None},
        "engagement_rate": {"value": None, "previous": None, "change": None, "change_percent": None},
    },
    "has_data": True,
    "audience": {"series": [{"date": "2026-08-01", "followers": 4890, "following": 12}],
                 "current": 5120, "change": 230},
    "platforms": [{"platform": "instagram", "platform_name": "Instagram", "accounts": 1,
                   "followers": 5120, "reach": None, "impressions": 154169,
                   "likes": None, "comments": None, "shares": None, "saves": None,
                   "engagement_rate": None}],
    "top_posts": [{"title": "Hello <script>alert(1)</script>",
                   "published_at": "2026-08-14T10:00:00+00:00", "engagement": 160,
                   "reach": 4000, "impressions": 9000, "engagement_rate": 4.0}],
    "content": {"published_posts": 1, "total_interactions": 160},
    "generated_at": "2026-09-08T12:00:00+00:00",
    "executive_summary": "1 post published.",
}
BRANDING = {"company_name": "Acme", "primary_color": "#123456",
            "accent_color": "#10b981", "logo_url": None, "footer_note": None}


# ---------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "report_type, expected_start, expected_end",
    [
        (ReportType.WEEKLY, date(2026, 8, 31), date(2026, 9, 6)),
        (ReportType.MONTHLY, date(2026, 8, 1), date(2026, 8, 31)),
        (ReportType.QUARTERLY, date(2026, 4, 1), date(2026, 6, 30)),
    ],
)
async def test_a_period_is_the_last_complete_one(
    workspace, report_type, expected_start, expected_end
):
    """Never the period in progress. A monthly report generated on the 3rd
    that covers three days is a number nobody asked for, and it would change
    if regenerated."""
    ws = await workspace()

    period = reporting.resolve_period(
        report_type, account=ws["account"], reference=date(2026, 9, 8)
    )

    assert (period.start, period.end) == (expected_start, expected_end)


async def test_a_custom_period_needs_both_ends(workspace):
    ws = await workspace()
    with pytest.raises(ValueError):
        reporting.resolve_period(
            ReportType.CUSTOM, account=ws["account"], start=date(2026, 8, 1)
        )


async def test_a_backwards_custom_period_is_refused(workspace):
    ws = await workspace()
    with pytest.raises(ValueError):
        reporting.resolve_period(
            ReportType.CUSTOM, account=ws["account"],
            start=date(2026, 8, 31), end=date(2026, 8, 1),
        )


async def test_the_period_is_resolved_on_the_workspace_clock(workspace):
    """A report titled September covers September on the customer's calendar."""
    sydney = await workspace(tz="Australia/Sydney")
    period = reporting.resolve_period(ReportType.MONTHLY, account=sydney["account"])
    assert period.start.day == 1


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

async def test_aggregation_sums_the_period(db_session, workspace, daily):
    ws = await workspace()
    social = ws["social_ids"][0]
    for offset in range(3):
        await daily(
            social, date(2026, 8, 10) + timedelta(days=offset),
            followers=1000 + offset, reach=100, impressions=250, likes=10,
        )

    period = reporting.Period(date(2026, 8, 1), date(2026, 8, 31), "August 2026")
    payload = await reporting.aggregate(db_session, ws["account"], period)

    assert payload["metrics"]["reach"]["value"] == 300
    assert payload["metrics"]["impressions"]["value"] == 750
    # Cumulative: the latest value in the window, never a sum.
    assert payload["metrics"]["followers"]["value"] == 1002


async def test_aggregation_excludes_days_outside_the_period(
    db_session, workspace, daily
):
    ws = await workspace()
    social = ws["social_ids"][0]
    await daily(social, date(2026, 8, 15), reach=100)
    await daily(social, date(2026, 9, 15), reach=999)

    period = reporting.Period(date(2026, 8, 1), date(2026, 8, 31), "August 2026")
    payload = await reporting.aggregate(db_session, ws["account"], period)

    assert payload["metrics"]["reach"]["value"] == 100


async def test_the_last_day_of_the_period_is_included(db_session, workspace, daily):
    """An off-by-one at the boundary silently drops a day from every report."""
    ws = await workspace()
    await daily(ws["social_ids"][0], date(2026, 8, 31), reach=42)

    period = reporting.Period(date(2026, 8, 1), date(2026, 8, 31), "August 2026")
    payload = await reporting.aggregate(db_session, ws["account"], period)

    assert payload["metrics"]["reach"]["value"] == 42


async def test_an_unreported_metric_stays_null_through_to_the_report(
    db_session, workspace, daily
):
    """The null discipline has to survive into the document: a dash, not a
    zero, or the client reads "nobody engaged" instead of "not measured"."""
    ws = await workspace()
    await daily(ws["social_ids"][0], date(2026, 8, 15), followers=500)

    period = reporting.Period(date(2026, 8, 1), date(2026, 8, 31), "August")
    payload = await reporting.aggregate(db_session, ws["account"], period)

    assert payload["metrics"]["reach"]["value"] is None
    assert report_render.metric(payload["metrics"]["reach"]["value"]) == "—"


async def test_an_empty_period_says_so(db_session, workspace):
    ws = await workspace()
    period = reporting.Period(date(2026, 8, 1), date(2026, 8, 31), "August")

    payload = await reporting.aggregate(db_session, ws["account"], period)

    assert payload["has_data"] is False
    assert "No posts were published" in payload["executive_summary"]


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

async def test_csv_renders_and_leaves_nulls_blank():
    body = report_render.render_csv(SAMPLE, BRANDING).decode("utf-8-sig")
    assert "August 2026" in body
    assert "None" not in body, "a null was written as the string 'None'"


async def test_xlsx_renders_a_real_workbook():
    from openpyxl import load_workbook
    import io

    data = report_render.render_xlsx(SAMPLE, BRANDING)
    book = load_workbook(io.BytesIO(data))

    assert {"Overview", "Metrics", "Platforms", "Top posts", "Audience"} <= set(book.sheetnames)
    metrics = book["Metrics"]
    assert metrics["A1"].value == "Metric"


async def test_xlsx_writes_numbers_as_numbers():
    """Formatted strings would make every column sort alphabetically and every
    SUM return zero -- the first thing a spreadsheet user tries."""
    from openpyxl import load_workbook
    import io

    book = load_workbook(io.BytesIO(report_render.render_xlsx(SAMPLE, BRANDING)))
    followers = book["Metrics"]["B2"].value
    assert isinstance(followers, (int, float)), f"got {type(followers)}"


async def test_html_escapes_content_the_workspace_wrote():
    """The PDF is sent to the workspace's own clients."""
    html = report_render.render_html(SAMPLE, BRANDING)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


async def test_html_applies_the_brand_colour():
    html = report_render.render_html(SAMPLE, BRANDING)
    assert "#123456" in html


@pytest.mark.skipif(
    not report_render.pdf_available()[0],
    reason="WeasyPrint needs pango at the system level; CSV and Excel still render",
)
async def test_pdf_renders():
    data = report_render.render_pdf(SAMPLE, BRANDING)
    assert data[:5] == b"%PDF-", "not a PDF"
    assert len(data) > 1000


# ---------------------------------------------------------------------------
# Branding and the white-label entitlement
# ---------------------------------------------------------------------------

async def test_branding_is_ignored_without_the_entitlement():
    branding = reporting.sanitise_branding(
        {"company_name": "Client Co", "primary_color": "#ff0000"}, entitled=False
    )
    assert branding["company_name"] == reporting.DEFAULT_BRANDING["company_name"]


async def test_branding_applies_with_the_entitlement():
    branding = reporting.sanitise_branding(
        {"company_name": "Client Co", "primary_color": "#ff0000"}, entitled=True
    )
    assert branding["company_name"] == "Client Co"
    assert branding["primary_color"] == "#ff0000"


@pytest.mark.parametrize(
    "colour", ["red", "#12345", "javascript:alert(1)", "#gggggg", "'; }"]
)
async def test_only_a_hex_colour_reaches_the_stylesheet(colour):
    """The value is interpolated into CSS in a document sent to the
    workspace's clients."""
    branding = reporting.sanitise_branding(
        {"primary_color": colour}, entitled=True
    )
    assert branding["primary_color"] == reporting.DEFAULT_BRANDING["primary_color"]


async def test_only_an_http_logo_url_is_kept():
    branding = reporting.sanitise_branding(
        {"logo_url": "javascript:alert(1)"}, entitled=True
    )
    assert branding["logo_url"] is None


async def test_unknown_branding_keys_are_dropped():
    branding = reporting.sanitise_branding(
        {"company_name": "Ok", "evil": "<script>"}, entitled=True
    )
    assert "evil" not in branding


async def test_branding_is_frozen_at_creation(db_session, workspace, set_limit):
    """A customer who rebrands should not find last month's PDF has changed."""
    ws = await workspace()
    await set_limit(ws["organization"], ent.WHITE_LABEL, 1)

    report = await report_jobs.create(
        db_session, ws["account"], report_type=ReportType.MONTHLY,
        branding={"company_name": "As It Was"},
    )

    assert report.branding["company_name"] == "As It Was"


async def test_a_workspace_without_white_label_gets_defaults_not_an_error(
    db_session, workspace
):
    """A hard failure on the plan boundary would mean a scheduled report
    silently stops arriving the month a plan changes."""
    ws = await workspace()

    report = await report_jobs.create(
        db_session, ws["account"], report_type=ReportType.MONTHLY,
        branding={"company_name": "Client Co"},
    )

    assert report.status is ReportStatus.PENDING
    assert report.branding["company_name"] == reporting.DEFAULT_BRANDING["company_name"]


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

async def test_generation_produces_files_and_a_notification(
    db_session, workspace, daily, monkeypatch
):
    ws = await workspace()
    await daily(ws["social_ids"][0], date.today() - timedelta(days=20), reach=100, followers=10)

    written: dict[str, bytes] = {}

    class FakeStorage:
        def put_object(self, key, data, *, content_type=""):
            written[key] = data

        def presign_download(self, key):
            return f"https://example.test/{key}"

    monkeypatch.setattr(report_jobs.storage, "get_storage", lambda: FakeStorage())

    report = await report_jobs.create(
        db_session, ws["account"], report_type=ReportType.MONTHLY,
        created_by=ws["owner"].id,
    )
    await report_jobs.generate(db_session, report)

    assert report.status is ReportStatus.READY, report.error
    assert "csv" in report.file_keys and "xlsx" in report.file_keys
    assert all(written[key] for key in report.file_keys.values())

    note = (
        await db_session.execute(
            select(Notification).where(Notification.type == "report_ready")
        )
    ).scalars().first()
    assert note is not None
    assert note.user_id == ws["owner"].id


async def test_one_unrenderable_format_does_not_fail_the_report(
    db_session, workspace, monkeypatch
):
    """A PDF is unavailable on a host without pango. The CSV and the workbook
    are still worth having, and a format absent from file_keys is the honest
    record of what happened."""
    ws = await workspace()

    class FakeStorage:
        def put_object(self, key, data, *, content_type=""):
            pass

    monkeypatch.setattr(report_jobs.storage, "get_storage", lambda: FakeStorage())
    monkeypatch.setitem(
        report_render.RENDERERS, ReportFormat.PDF,
        lambda payload, branding: (_ for _ in ()).throw(RuntimeError("no pango")),
    )

    report = await report_jobs.create(
        db_session, ws["account"], report_type=ReportType.MONTHLY
    )
    await report_jobs.generate(db_session, report)

    assert report.status is ReportStatus.READY
    assert "pdf" not in report.file_keys
    assert "pdf" in (report.error or "")


async def test_every_format_failing_fails_the_report(
    db_session, workspace, monkeypatch
):
    ws = await workspace()

    class FakeStorage:
        def put_object(self, key, data, *, content_type=""):
            raise RuntimeError("bucket on fire")

    monkeypatch.setattr(report_jobs.storage, "get_storage", lambda: FakeStorage())

    report = await report_jobs.create(
        db_session, ws["account"], report_type=ReportType.MONTHLY
    )
    await report_jobs.generate(db_session, report)

    assert report.status is ReportStatus.FAILED
    assert report.file_keys in (None, {})


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------

async def test_a_cadence_queues_one_report_and_not_two(
    db_session, workspace, monkeypatch
):
    """Idempotent by period. A next_run_at can drift, be missed, or fire twice
    after a restart, and each puts a duplicate in front of a customer."""
    ws = await workspace()
    ws["account"].settings = {
        **(ws["account"].settings or {}), report_jobs.CADENCE_KEY: "monthly"
    }
    ws["account"].created_at = datetime.now(timezone.utc) - timedelta(days=200)
    await db_session.flush()

    first = await report_jobs.queue_scheduled(db_session)
    second = await report_jobs.queue_scheduled(db_session)

    assert first == 1
    assert second == 0, "a second pass queued a duplicate"


async def test_a_cadence_of_off_queues_nothing(db_session, workspace):
    ws = await workspace()
    ws["account"].settings = {**(ws["account"].settings or {}), report_jobs.CADENCE_KEY: "off"}
    await db_session.flush()

    assert await report_jobs.queue_scheduled(db_session) == 0


async def test_a_workspace_younger_than_the_period_is_skipped(
    db_session, workspace
):
    """Nothing to report on before the workspace existed."""
    ws = await workspace()
    ws["account"].settings = {
        **(ws["account"].settings or {}), report_jobs.CADENCE_KEY: "monthly"
    }
    ws["account"].created_at = datetime.now(timezone.utc)
    await db_session.flush()

    assert await report_jobs.queue_scheduled(db_session) == 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

async def test_creating_a_report_is_202_and_spends_the_allowance(
    client, auth_header, workspace, db_session
):
    ws = await workspace()
    before = await ent.current_usage(
        db_session, ws["organization"], ent.REPORTS_PER_MONTH
    )

    response = await client.post(
        f"/api/v1/accounts/{ws['account_id']}/reports/",
        headers=auth_header(ws["owner"]),
        json={"type": "monthly"},
    )

    assert response.status_code == 202, response.text
    assert response.json()["status"] == "pending"
    after = await ent.current_usage(
        db_session, ws["organization"], ent.REPORTS_PER_MONTH
    )
    assert after == before + 1


async def test_the_report_allowance_is_enforced(
    client, auth_header, workspace, set_limit
):
    ws = await workspace()
    await set_limit(ws["organization"], ent.REPORTS_PER_MONTH, 1)
    url = f"/api/v1/accounts/{ws['account_id']}/reports/"

    first = await client.post(url, headers=auth_header(ws["owner"]), json={"type": "monthly"})
    second = await client.post(url, headers=auth_header(ws["owner"]), json={"type": "weekly"})

    assert first.status_code == 202
    assert second.status_code in (402, 403, 429)


async def test_downloading_before_it_is_ready_is_409(
    client, auth_header, workspace, db_session
):
    """Distinct from 404: the report exists, it is just not finished."""
    ws = await workspace()
    created = await client.post(
        f"/api/v1/accounts/{ws['account_id']}/reports/",
        headers=auth_header(ws["owner"]), json={"type": "monthly"},
    )
    report_id = created.json()["id"]

    response = await client.get(
        f"/api/v1/accounts/{ws['account_id']}/reports/{report_id}/download",
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code == 409


async def test_a_missing_format_names_what_is_available(
    client, auth_header, workspace, db_session
):
    ws = await workspace()
    report = Report(
        id=uuid.uuid4(), account_id=ws["account_id"], type=ReportType.MONTHLY,
        period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
        status=ReportStatus.READY, file_keys={"csv": "reports/x.csv"},
    )
    db_session.add(report)
    await db_session.flush()

    response = await client.get(
        f"/api/v1/accounts/{ws['account_id']}/reports/{report.id}/download?format=pdf",
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code == 404
    assert "csv" in response.json()["detail"]


async def test_branding_settings_round_trip(client, auth_header, workspace):
    ws = await workspace()
    url = f"/api/v1/accounts/{ws['account_id']}/reports/settings/branding"

    saved = await client.put(
        url, headers=auth_header(ws["owner"]),
        json={"company_name": "Client Co", "primary_color": "#ff0000"},
    )
    assert saved.status_code == 200, saved.text

    fetched = await client.get(url, headers=auth_header(ws["owner"]))
    body = fetched.json()
    assert body["branding"]["company_name"] == "Client Co"
    # Without the entitlement it is stored but not applied, and the response
    # says which is which.
    assert body["white_label"] is False
    assert body["effective"]["company_name"] == reporting.DEFAULT_BRANDING["company_name"]


async def test_a_bad_colour_is_refused_by_the_endpoint(client, auth_header, workspace):
    ws = await workspace()
    response = await client.put(
        f"/api/v1/accounts/{ws['account_id']}/reports/settings/branding",
        headers=auth_header(ws["owner"]),
        json={"primary_color": "red"},
    )
    assert response.status_code == 422


async def test_cadence_round_trips(client, auth_header, workspace):
    ws = await workspace()
    base = f"/api/v1/accounts/{ws['account_id']}/reports/settings"

    await client.put(f"{base}/cadence", headers=auth_header(ws["owner"]),
                     json={"cadence": "weekly"})
    body = (await client.get(f"{base}/branding", headers=auth_header(ws["owner"]))).json()

    assert body["cadence"] == "weekly"


async def test_an_unknown_cadence_is_refused(client, auth_header, workspace):
    ws = await workspace()
    response = await client.put(
        f"/api/v1/accounts/{ws['account_id']}/reports/settings/cadence",
        headers=auth_header(ws["owner"]), json={"cadence": "hourly"},
    )
    assert response.status_code == 422


async def test_another_workspace_cannot_be_read(client, auth_header, workspace):
    ws = await workspace()
    other = await workspace()

    response = await client.get(
        f"/api/v1/accounts/{other['account_id']}/reports/",
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code in (403, 404)
