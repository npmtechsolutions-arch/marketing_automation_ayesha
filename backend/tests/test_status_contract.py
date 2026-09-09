"""The UI's status vocabulary must match the backend's.

`CalendarPage` used to narrow twelve statuses to five, falling through to
"draft" for anything it did not recognise -- so an approved post sat in the
Drafts filter and a partial publish got a green "Published" pill. The fix was
to stop discarding statuses, which only holds while the two lists agree.

Adding a member to PostStatus without adding it to POST_STATUSES would put the
UI straight back into silently calling it a draft, and nothing else in either
suite would notice. This is the seam, so this is where it is pinned.
"""

import pathlib
import re
import uuid

from sqlalchemy import select

from app.models.post import PostStatus

FRONTEND = pathlib.Path("../frontend/src")
STATUS_MODULE = FRONTEND / "lib" / "postStatus.ts"
STATUS_TEST = FRONTEND / "lib" / "postStatus.test.ts"


def _string_list(source: str, after: str) -> list[str]:
    """The quoted strings in the first [...] block following a marker."""
    start = source.index(after)
    block = source[start : source.index("]", start)]
    return re.findall(r'"([a-z_]+)"', block)


def test_frontend_knows_every_post_status():
    statuses = {s.value for s in PostStatus}
    declared = set(_string_list(STATUS_MODULE.read_text(), "export const POST_STATUSES = ["))

    missing = statuses - declared
    extra = declared - statuses

    assert not missing, (
        f"the UI does not know these statuses and will show them as drafts: "
        f"{sorted(missing)}. Add them to POST_STATUSES in {STATUS_MODULE.name}."
    )
    assert not extra, f"the UI expects statuses the backend cannot send: {sorted(extra)}"


def test_the_frontend_contract_test_lists_them_too():
    """The UI test spells the list out to state the contract; keep it true."""
    statuses = {s.value for s in PostStatus}
    declared = set(_string_list(STATUS_TEST.read_text(), "const BACKEND_STATUSES = ["))
    assert declared == statuses


def test_a_partial_publish_is_a_distinct_status():
    """Not an alias for success.

    The whole of defect #15 was the UI folding this into `published`. If the
    backend ever stops distinguishing them, the UI's separate bucket becomes
    dead code and the fix silently unwinds.
    """
    assert PostStatus.PARTIALLY_PUBLISHED.value == "partially_published"
    assert PostStatus.PARTIALLY_PUBLISHED is not PostStatus.PUBLISHED


def test_the_review_states_are_not_drafts():
    """Each is a distinct member, so the UI can tell them apart."""
    review = {
        PostStatus.PENDING_APPROVAL, PostStatus.IN_REVIEW,
        PostStatus.CLIENT_REVIEW, PostStatus.CHANGES_REQUESTED,
        PostStatus.APPROVED,
    }
    assert PostStatus.DRAFT not in review
    assert len({s.value for s in review}) == 5


# ---------------------------------------------------------------------------
# The seat meter must agree with the refusal (#13)
# ---------------------------------------------------------------------------

async def test_the_settings_endpoint_reports_the_limit_that_is_enforced(
    client, auth_header, user_factory, account_factory, organization_factory,
    set_limit,
):
    """The team page reads its seat meter from here.

    It used to hardcode `planLimit = 10` and the string "Growth Plan", so a
    brand-new Free workspace was told "1 of 10 team members used - Growth Plan"
    and then refused on the very next click with "your Free plan's limit for
    team members (1)". Two contradicting numbers on one screen.

    This pins the half the UI depends on: the number the endpoint reports is
    the number the invite endpoint enforces. One source of truth per number.
    """
    from app.services import entitlement_service as ent

    owner = await user_factory()
    organization = await organization_factory(owner)
    await set_limit(organization, ent.TEAM_MEMBERS, 2)
    account = await account_factory(owner, organization=organization)

    settings = await client.get(
        f"/api/v1/accounts/{account.id}/settings/", headers=auth_header(owner)
    )
    assert settings.status_code == 200, settings.text
    reported = settings.json()["max_team_members"]
    assert reported == 2

    # The owner already holds one seat, so exactly one invitation fits.
    first = await client.post(
        f"/api/v1/accounts/{account.id}/team/invite",
        headers=auth_header(owner),
        json={"email": f"a-{uuid.uuid4().hex[:8]}@example.com", "role": "editor"},
    )
    second = await client.post(
        f"/api/v1/accounts/{account.id}/team/invite",
        headers=auth_header(owner),
        json={"email": f"b-{uuid.uuid4().hex[:8]}@example.com", "role": "editor"},
    )

    assert first.status_code == 201, first.text
    assert second.status_code in (402, 403, 429), second.text
    # The refusal names the same number the meter showed.
    assert str(reported) in second.json()["detail"]


async def test_an_unlimited_plan_reports_null_rather_than_a_number(
    client, auth_header, user_factory, account_factory, organization_factory,
    set_limit,
):
    """Null is how "unlimited" is expressed, and the UI must not read it as 0."""
    from app.services import entitlement_service as ent

    owner = await user_factory()
    organization = await organization_factory(owner)
    await set_limit(organization, ent.TEAM_MEMBERS, None)
    account = await account_factory(owner, organization=organization)

    settings = await client.get(
        f"/api/v1/accounts/{account.id}/settings/", headers=auth_header(owner)
    )

    assert settings.json()["max_team_members"] is None


def _without_comments(source: str) -> str:
    """Code only.

    A comment naming the old hardcoded value is worth keeping -- it is the
    record of why this guard exists -- and must not trip the guard itself.
    """
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"//[^\n]*", "", source)


def test_the_team_page_does_not_hardcode_a_plan():
    """A structural guard, because this is how the defect got in.

    Someone pasted the middle tier's numbers in as a placeholder and they
    stayed. The values now come from the settings endpoint above.
    """
    source = _without_comments((FRONTEND / "pages" / "team" / "TeamPage.tsx").read_text())

    assert "planLimit = " not in source, "seat limit is hardcoded again"
    for literal in ("Growth Plan", "Free Plan", "Pro Plan", "Starter Plan"):
        assert literal not in source, f"plan name {literal!r} is hardcoded again"


# ---------------------------------------------------------------------------
# The approval workflow has to be reachable (#18/#19)
# ---------------------------------------------------------------------------

async def test_approvals_can_be_switched_on_and_read_back(
    client, auth_header, user_factory, account_factory, organization_factory,
):
    """The whole approval workflow was unreachable.

    `approvals_required` was read by approvals.settings_for and enforced by
    assert_publishable, but the string appeared nowhere in the frontend -- no
    toggle, no settings row. The only way to turn it on was a hand-written PUT
    with the right nested blob. There is a Workspace settings tab now; this
    pins the contract it depends on.
    """
    owner = await user_factory()
    organization = await organization_factory(owner)
    account = await account_factory(owner, organization=organization)
    url = f"/api/v1/accounts/{account.id}/settings/"

    written = await client.put(
        url, headers=auth_header(owner),
        json={"settings": {"approvals_required": True}},
    )
    assert written.status_code == 200, written.text
    assert written.json()["settings"]["approvals_required"] is True

    read_back = await client.get(url, headers=auth_header(owner))
    assert read_back.json()["settings"]["approvals_required"] is True


async def test_setting_one_workspace_flag_does_not_drop_the_others(
    client, auth_header, user_factory, account_factory, organization_factory,
):
    """The tab saves one key at a time, so the merge has to hold.

    A replace rather than a merge would mean flipping the approvals toggle
    silently discarded the workspace's timezone -- and every scheduled time in
    it would move.
    """
    owner = await user_factory()
    organization = await organization_factory(owner)
    account = await account_factory(owner, organization=organization)
    url = f"/api/v1/accounts/{account.id}/settings/"

    await client.put(url, headers=auth_header(owner),
                     json={"settings": {"timezone": "Australia/Sydney"}})
    await client.put(url, headers=auth_header(owner),
                     json={"settings": {"approvals_required": True}})

    settings = (await client.get(url, headers=auth_header(owner))).json()["settings"]
    assert settings["timezone"] == "Australia/Sydney"
    assert settings["approvals_required"] is True


async def test_the_composer_can_comply_with_the_gate_it_hits(
    client, auth_header, db_session, user_factory, account_factory,
    organization_factory, social_platform_factory, social_account_factory,
):
    """With approvals on, publishing 409s and tells the user to submit for
    review. That instruction has to be followable.

    The composer offered Queue / Post Now / Schedule and nothing else, so every
    route out of it was refused and the only way forward was to know that the
    action lived on a different page. It now offers "Submit for review", which
    is this endpoint.
    """
    from app.models.post import Post, PostStatus

    owner = await user_factory()
    organization = await organization_factory(owner)
    account = await account_factory(owner, organization=organization)
    await client.put(
        f"/api/v1/accounts/{account.id}/settings/", headers=auth_header(owner),
        json={"settings": {"approvals_required": True}},
    )
    platform = await social_platform_factory(owner, account, slug="facebook")
    social = await social_account_factory(owner, account, slug="facebook")

    created = await client.post(
        f"/api/v1/accounts/{account.id}/posts/", headers=auth_header(owner),
        json={"content": "needs review", "target_account_ids": [str(social.id)]},
    )
    assert created.status_code == 201, created.text
    post_id = created.json()["id"]

    # The gate the composer runs into.
    refused = await client.post(
        f"/api/v1/accounts/{account.id}/posts/{post_id}/publish",
        headers=auth_header(owner),
    )
    assert refused.status_code == 409
    assert "review" in refused.json()["detail"].lower()

    # ...and the action it now offers instead.
    submitted = await client.post(
        f"/api/v1/accounts/{account.id}/posts/{post_id}/submit-for-review",
        headers=auth_header(owner),
    )
    assert submitted.status_code == 200, submitted.text

    post = (
        await db_session.execute(select(Post).where(Post.id == uuid.UUID(post_id)))
    ).scalar_one()
    await db_session.refresh(post)
    assert post.status is not PostStatus.DRAFT


def test_the_workspace_settings_tab_writes_every_setting_that_is_read():
    """Anything approvals.settings_for reads must be settable somewhere.

    That was the defect: three keys drove real behaviour and no screen wrote
    any of them.
    """
    tab = (FRONTEND / "pages" / "settings" / "SettingsPage.tsx").read_text()
    for key in ("timezone", "approvals_required", "client_approval_required"):
        assert key in tab, f"{key} is read by the server and set by no screen"
