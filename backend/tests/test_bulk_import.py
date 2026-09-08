"""Bulk-importing posts from a CSV.

Two things carry the risk here.

**The dry run must be a dry run.** A validation pass that quietly created rows,
or quietly spent quota, would be worse than no preview at all -- the user is
being asked to approve something on the basis that nothing has happened yet.

**The quota reservation must be one operation.** Fifty separate increments let
a concurrent import interleave and carry a workspace past its allowance, and
leave a partial spend behind if the run fails halfway.
"""

import io
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models.post import Post, PostStatus
from app.models.post_variant import PostVariant
from app.services import bulk_import, entitlement_service as ent

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
        for slug in slugs:
            await social_account_factory(owner, account, slug=slug)
        return {
            "owner": owner, "organization": organization,
            "account": account, "account_id": account.id,
        }

    return _make


def _future(days=10, hour=9):
    when = datetime.now() + timedelta(days=days)
    return f"{when.date().isoformat()} {hour:02d}:00"


def _csv(rows: list[str], header: str = "content,scheduled_at,platforms,media_urls,link") -> bytes:
    return ("\n".join([header, *rows]) + "\n").encode("utf-8")


async def _upload(client, auth_header, ws, body: bytes, *, confirm=False, name="posts.csv"):
    return await client.post(
        f"/api/v1/accounts/{ws['account_id']}/posts/bulk-import"
        f"?confirm={'true' if confirm else 'false'}",
        headers=auth_header(ws["owner"]),
        files={"file": (name, io.BytesIO(body), "text/csv")},
    )


async def _post_count(db_session, ws):
    return (
        await db_session.execute(
            select(func.count()).select_from(Post).where(
                Post.account_id == ws["account_id"]
            )
        )
    ).scalar_one()


# ---------------------------------------------------------------------------
# The dry run
# ---------------------------------------------------------------------------

async def test_a_dry_run_reports_without_writing(
    client, auth_header, workspace, db_session
):
    ws = await workspace()
    body = _csv([f'"Hello there",{_future()},instagram,,'])

    response = await _upload(client, auth_header, ws, body)

    assert response.status_code == 200, response.text
    report = response.json()
    assert report["confirmed"] is False
    assert report["created"] == 0
    assert report["importable"] == 1
    assert await _post_count(db_session, ws) == 0, "the dry run created rows"


async def test_a_dry_run_spends_no_quota(
    client, auth_header, workspace, db_session
):
    """The user is approving on the basis that nothing has happened yet."""
    ws = await workspace()
    before = await ent.current_usage(db_session, ws["organization"], ent.POSTS_PER_MONTH)

    await _upload(client, auth_header, ws, _csv([f'"A post",{_future()},instagram,,']))

    after = await ent.current_usage(db_session, ws["organization"], ent.POSTS_PER_MONTH)
    assert after == before


# ---------------------------------------------------------------------------
# Partial failure
# ---------------------------------------------------------------------------

async def test_good_rows_import_while_bad_rows_are_reported(
    client, auth_header, workspace, db_session
):
    """Refusing fifty good rows over one bad one is not a service. The report
    has already told the user exactly which failed and why."""
    ws = await workspace()
    body = _csv([
        f'"Row two is fine",{_future()},instagram,,',
        f'"",{_future()},instagram,,',                      # no content
        f'"Row four has a bad date",not-a-date,instagram,,',
        f'"Row five names a platform we do not have",{_future()},tiktok,,',
        f'"Row six is fine too",{_future(11)},instagram,,',
    ])

    dry = (await _upload(client, auth_header, ws, body)).json()
    assert dry["total"] == 5
    assert dry["importable"] == 2
    assert dry["rejected"] == 3

    failing = {row["row_number"]: row for row in dry["rows"] if not row["importable"]}
    assert set(failing) == {3, 4, 5}
    assert "content" in failing[3]["errors"][0]["field"]
    assert "scheduled_at" in failing[4]["errors"][0]["field"]
    assert "platforms" in failing[5]["errors"][0]["field"]

    confirmed = (await _upload(client, auth_header, ws, body, confirm=True)).json()
    assert confirmed["created"] == 2
    assert await _post_count(db_session, ws) == 2


async def test_the_report_says_why_each_row_failed(client, auth_header, workspace):
    """A row number and a shrug is not a report."""
    ws = await workspace()
    body = _csv([f'"Text is here",yesterday,instagram,,'])

    row = (await _upload(client, auth_header, ws, body)).json()["rows"][0]

    assert row["importable"] is False
    message = row["errors"][0]["message"]
    assert "yesterday" in message
    assert "YYYY-MM-DD" in message, "the message does not say what to do instead"


async def test_a_past_date_is_refused_in_the_workspace_timezone(
    client, auth_header, workspace
):
    """A spreadsheet has no timezone, so its times are read on the workspace's
    clock -- the same contract the composer and recurring schedules use."""
    ws = await workspace(tz="Australia/Sydney")
    past = (datetime.now() - timedelta(days=2)).date().isoformat()
    body = _csv([f'"Backdated",{past} 09:00,instagram,,'])

    row = (await _upload(client, auth_header, ws, body)).json()["rows"][0]

    assert row["importable"] is False
    assert "Australia/Sydney" in row["errors"][0]["message"]


async def test_a_row_with_no_date_imports_as_a_draft(
    client, auth_header, workspace, db_session
):
    ws = await workspace()
    body = _csv(['"No date on this one",,instagram,,'])

    report = (await _upload(client, auth_header, ws, body, confirm=True)).json()

    assert report["created"] == 1
    assert report["drafts"] == 1
    post = (
        await db_session.execute(select(Post).where(Post.account_id == ws["account_id"]))
    ).scalar_one()
    assert post.status is PostStatus.DRAFT
    assert post.scheduled_at is None


async def test_validation_is_the_composers_own(client, auth_header, workspace):
    """Not a second implementation. An import must not accept content the
    composer would reject, or the two drift."""
    ws = await workspace(slugs=("twitter",))
    body = _csv([f'"{"x" * 400}",{_future()},twitter,,'])

    row = (await _upload(client, auth_header, ws, body)).json()["rows"][0]

    assert row["importable"] is False
    assert any("twitter" in e["field"] for e in row["errors"])


# ---------------------------------------------------------------------------
# The quota reservation
# ---------------------------------------------------------------------------

async def test_the_whole_set_is_reserved_at_once(
    client, auth_header, workspace, db_session, set_limit
):
    """Three rows against an allowance of three is exactly three increments,
    taken together."""
    ws = await workspace()
    await set_limit(ws["organization"], ent.POSTS_PER_MONTH, 3)
    body = _csv([f'"Row {n}",{_future(10 + n)},instagram,,' for n in range(3)])

    report = (await _upload(client, auth_header, ws, body, confirm=True)).json()

    assert report["created"] == 3
    usage = await ent.current_usage(db_session, ws["organization"], ent.POSTS_PER_MONTH)
    assert usage == 3


async def test_an_import_over_the_allowance_creates_nothing(
    client, auth_header, workspace, db_session, set_limit
):
    """All-or-nothing on the reservation. Importing the first two of five and
    then stopping leaves the user to work out which are missing."""
    ws = await workspace()
    await set_limit(ws["organization"], ent.POSTS_PER_MONTH, 2)
    body = _csv([f'"Row {n}",{_future(10 + n)},instagram,,' for n in range(5)])

    response = await _upload(client, auth_header, ws, body, confirm=True)

    assert response.status_code in (402, 403, 429), response.text
    assert await _post_count(db_session, ws) == 0, "a partial import was left behind"


async def test_a_rejected_import_spends_no_quota(
    client, auth_header, workspace, db_session, set_limit
):
    """A refused reservation must not consume the slots it asked for -- the
    next, smaller import has to still fit."""
    ws = await workspace()
    await set_limit(ws["organization"], ent.POSTS_PER_MONTH, 2)
    too_many = _csv([f'"Row {n}",{_future(10 + n)},instagram,,' for n in range(5)])

    await _upload(client, auth_header, ws, too_many, confirm=True)

    usage = await ent.current_usage(db_session, ws["organization"], ent.POSTS_PER_MONTH)
    assert usage == 0

    fits = _csv([f'"Row {n}",{_future(20 + n)},instagram,,' for n in range(2)])
    response = await _upload(client, auth_header, ws, fits, confirm=True)
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 2


async def test_only_importable_rows_are_charged(
    client, auth_header, workspace, db_session, set_limit
):
    """A row that cannot be created must not consume a slot."""
    ws = await workspace()
    await set_limit(ws["organization"], ent.POSTS_PER_MONTH, 2)
    body = _csv([
        f'"Fine",{_future()},instagram,,',
        '"",,,,',                                 # rejected
        f'"Also fine",{_future(11)},instagram,,',
    ])

    report = (await _upload(client, auth_header, ws, body, confirm=True)).json()

    assert report["created"] == 2
    usage = await ent.current_usage(db_session, ws["organization"], ent.POSTS_PER_MONTH)
    assert usage == 2, "a rejected row was charged"


# ---------------------------------------------------------------------------
# The file itself
# ---------------------------------------------------------------------------

async def test_a_missing_required_column_fails_the_file_not_the_rows(
    client, auth_header, workspace
):
    """A misnamed header is one mistake, not fifty."""
    ws = await workspace()
    body = _csv([f'"text",{_future()},instagram,,'], header="text,scheduled_at,platforms,media_urls,link")

    response = await _upload(client, auth_header, ws, body)

    assert response.status_code == 400
    assert "content" in response.json()["detail"]


async def test_an_excel_byte_order_mark_is_handled(
    client, auth_header, workspace
):
    """Excel writes a BOM. Without utf-8-sig the first column arrives named
    '\\ufeffcontent' and every row looks like it is missing its text."""
    ws = await workspace()
    body = b"\xef\xbb\xbf" + _csv([f'"With a BOM",{_future()},instagram,,'])

    report = (await _upload(client, auth_header, ws, body)).json()

    assert report["importable"] == 1


async def test_headers_are_matched_case_insensitively(client, auth_header, workspace):
    ws = await workspace()
    body = _csv(
        [f'"Mixed case header",{_future()},instagram,,'],
        header="Content,Scheduled At,Platforms,Media URLs,Link",
    )

    report = (await _upload(client, auth_header, ws, body)).json()

    assert report["importable"] == 1


async def test_list_columns_accept_pipes_and_semicolons(client, auth_header, workspace):
    """A comma inside a CSV cell is a fight nobody should have to win."""
    ws = await workspace(slugs=("instagram", "facebook"))
    body = _csv([f'"Two platforms",{_future()},instagram|facebook,,'])

    row = (await _upload(client, auth_header, ws, body)).json()["rows"][0]

    assert row["importable"] is True
    assert row["target_count"] == 2


async def test_an_empty_file_is_refused(client, auth_header, workspace):
    ws = await workspace()
    response = await _upload(client, auth_header, ws, b"")
    assert response.status_code == 400


async def test_a_header_with_no_rows_is_refused(client, auth_header, workspace):
    ws = await workspace()
    response = await _upload(client, auth_header, ws, _csv([]))
    assert response.status_code == 400
    assert "no rows" in response.json()["detail"]


async def test_too_many_rows_is_refused_before_any_work(client, auth_header, workspace):
    ws = await workspace()
    body = _csv([f'"Row {n}",,instagram,,' for n in range(bulk_import.MAX_ROWS + 5)])

    response = await _upload(client, auth_header, ws, body)

    assert response.status_code == 400
    assert str(bulk_import.MAX_ROWS) in response.json()["detail"]


async def test_a_link_becomes_a_variant(client, auth_header, workspace, db_session):
    """Post has no link column; PostVariant.link_url is where one lives."""
    ws = await workspace()
    body = _csv([f'"With a link",{_future()},instagram,,https://example.com/x'])

    await _upload(client, auth_header, ws, body, confirm=True)

    variant = (
        await db_session.execute(select(PostVariant))
    ).scalars().first()
    assert variant is not None
    assert variant.link_url == "https://example.com/x"
    assert variant.platform_slug == "instagram"


async def test_confirming_a_file_with_nothing_importable_is_refused(
    client, auth_header, workspace
):
    ws = await workspace()
    response = await _upload(client, auth_header, ws, _csv(['"",,,,']), confirm=True)
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Template and access
# ---------------------------------------------------------------------------

async def test_the_template_imports_cleanly_as_its_own_input(
    client, auth_header, workspace
):
    """Download it, upload it back, and every row must pass.

    The obvious first thing a user does with a template is send it straight
    back. The first version of this had fixed example dates, so by the time
    anyone used it every row failed on "that date is in the past" -- which
    teaches them the validator is broken rather than that the file needs
    editing. Dates and platforms are generated from the workspace now, and
    this test is what keeps them that way.
    """
    ws = await workspace()
    downloaded = await client.get(
        f"/api/v1/accounts/{ws['account_id']}/posts/bulk-import/template",
        headers=auth_header(ws["owner"]),
    )
    assert downloaded.status_code == 200
    assert "attachment" in downloaded.headers["content-disposition"]

    report = (await _upload(client, auth_header, ws, downloaded.content)).json()

    assert report["total"] == 3
    assert report["rejected"] == 0, [
        row["errors"] for row in report["rows"] if not row["importable"]
    ]


async def test_the_template_names_a_platform_the_workspace_has(
    client, auth_header, workspace
):
    """An example naming a platform the user has not connected teaches them
    the importer is broken."""
    ws = await workspace(slugs=("linkedin",))

    downloaded = await client.get(
        f"/api/v1/accounts/{ws['account_id']}/posts/bulk-import/template",
        headers=auth_header(ws["owner"]),
    )

    assert "linkedin" in downloaded.text
    assert "instagram" not in downloaded.text


async def test_a_viewer_cannot_import(client, auth_header, workspace, user_factory,
                                      member_factory):
    from app.models.team_member import InvitationStatus, TeamRole

    ws = await workspace()
    viewer = await user_factory(password=PASSWORD)
    await member_factory(
        viewer, ws["account"], role=TeamRole.VIEWER,
        invitation_status=InvitationStatus.ACCEPTED,
    )

    response = await client.post(
        f"/api/v1/accounts/{ws['account_id']}/posts/bulk-import",
        headers=auth_header(viewer),
        files={"file": ("posts.csv", io.BytesIO(_csv(['"x",,instagram,,'])), "text/csv")},
    )

    assert response.status_code == 403


async def test_another_workspace_cannot_be_imported_into(
    client, auth_header, workspace
):
    ws = await workspace()
    other = await workspace()

    response = await client.post(
        f"/api/v1/accounts/{other['account_id']}/posts/bulk-import",
        headers=auth_header(ws["owner"]),
        files={"file": ("posts.csv", io.BytesIO(_csv(['"x",,instagram,,'])), "text/csv")},
    )

    assert response.status_code in (403, 404)
