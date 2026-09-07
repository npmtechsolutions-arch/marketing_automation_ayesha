"""Workspace settings and usage.

These endpoints report limits, so they are a place where a stale copy of a
limit would be visible to a user. They resolve them through the entitlement
service for that reason, and these tests pin that the numbers agree with what
enforcement would actually do.
"""

import pytest

from app.services import entitlement_service as ent

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


@pytest.fixture
async def workspace(user_factory, account_factory, organization_factory):
    owner = await user_factory(password=PASSWORD)
    organization = await organization_factory(owner)
    account = await account_factory(owner, organization=organization)
    return {"owner": owner, "organization": organization, "account": account}


def _url(account_id, suffix=""):
    return f"/api/v1/accounts/{account_id}/settings/{suffix}"


async def test_get_settings_reports_plan_limits(client, auth_header, workspace):
    response = await client.get(
        _url(workspace["account"].id), headers=auth_header(workspace["owner"])
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["subscription_tier"] == "free"
    assert body["monthly_post_limit"] == 10
    assert body["max_team_members"] == 1
    assert body["max_platforms"] == 2


async def test_renaming_a_workspace_succeeds(client, auth_header, workspace):
    """This returned 500.

    The PUT built its response from ``account.subscription_tier`` and the three
    limit columns -- all of which moved to Organization in the 1.1 migration --
    so every rename raised AttributeError. The GET had been updated and the PUT
    had not, because each built the payload itself.
    """
    response = await client.put(
        _url(workspace["account"].id),
        headers=auth_header(workspace["owner"]),
        json={"name": "Renamed Workspace"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Renamed Workspace"
    # And it still carries the subscription fields the GET returns.
    assert response.json()["subscription_tier"] == "free"
    assert response.json()["monthly_post_limit"] == 10


async def test_get_and_put_agree(client, auth_header, workspace):
    """One builder serves both, so their payloads cannot drift apart."""
    headers = auth_header(workspace["owner"])
    before = (await client.get(_url(workspace["account"].id), headers=headers)).json()
    after = (
        await client.put(
            _url(workspace["account"].id), headers=headers, json={"settings": {"a": 1}}
        )
    ).json()

    assert before.keys() == after.keys()
    for field in ("subscription_tier", "subscription_status", "monthly_post_limit",
                  "max_team_members", "max_platforms"):
        assert before[field] == after[field]


async def test_limit_change_is_reflected(client, auth_header, workspace, set_limit):
    """A raised cap must show here too, or the page reports one number while
    enforcement applies another."""
    await set_limit(workspace["organization"], ent.POSTS_PER_MONTH, 250)

    body = (
        await client.get(
            _url(workspace["account"].id), headers=auth_header(workspace["owner"])
        )
    ).json()
    assert body["monthly_post_limit"] == 250


async def test_unlimited_is_null_not_a_sentinel(client, auth_header, workspace, set_limit):
    await set_limit(workspace["organization"], ent.POSTS_PER_MONTH, None)

    body = (
        await client.get(
            _url(workspace["account"].id), headers=auth_header(workspace["owner"])
        )
    ).json()
    assert body["monthly_post_limit"] is None


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

async def test_usage_matches_the_metered_counter(
    client, auth_header, workspace, db_session
):
    """Posts are metered, so this must read usage_records rather than counting
    rows -- the two diverge as soon as a post is deleted."""
    headers = auth_header(workspace["owner"])
    for i in range(3):
        assert (
            await client.post(
                f"/api/v1/accounts/{workspace['account'].id}/posts/",
                headers=headers,
                json={"content": f"post {i}", "target_accounts": []},
            )
        ).status_code == 201

    body = (await client.get(_url(workspace["account"].id, "usage"), headers=headers)).json()
    assert body["posts_this_month"] == 3
    assert body["posts_limit"] == 10
    assert body["posts_remaining"] == 7
    assert body["team_members"] == 1
    assert body["team_members_limit"] == 1


async def test_usage_reports_no_remainder_when_unlimited(
    client, auth_header, workspace, set_limit
):
    await set_limit(workspace["organization"], ent.POSTS_PER_MONTH, None)

    body = (
        await client.get(
            _url(workspace["account"].id, "usage"),
            headers=auth_header(workspace["owner"]),
        )
    ).json()
    assert body["posts_limit"] is None
    assert body["posts_remaining"] is None


async def test_settings_denied_to_a_non_member(
    client, auth_header, user_factory, workspace
):
    stranger = await user_factory()
    response = await client.get(
        _url(workspace["account"].id), headers=auth_header(stranger)
    )
    assert response.status_code == 403
