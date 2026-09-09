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
