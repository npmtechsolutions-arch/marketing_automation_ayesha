"""Superadmin plan administration and the organization usage endpoint.

These two are the point of moving limits into the database: an operator can
change what a plan allows without a deploy, and a customer can see how much of
it they have spent.
"""

import pytest

pytestmark = pytest.mark.asyncio

ADMIN = "/api/v1/admin"


@pytest.fixture
async def superadmin(user_factory):
    return await user_factory(is_superadmin=True)


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

PLAN_ROUTES = [
    ("get", f"{ADMIN}/plans", None),
    ("get", f"{ADMIN}/features", None),
    ("post", f"{ADMIN}/plans", {"key": "sneaky", "name": "Sneaky"}),
]


@pytest.mark.parametrize("method,path,body", PLAN_ROUTES)
async def test_plan_administration_requires_superadmin(
    client, auth_header, user_factory, method, path, body
):
    ordinary = await user_factory()
    response = await getattr(client, method)(
        path, headers=auth_header(ordinary), **({"json": body} if body else {})
    )
    assert response.status_code == 403, (
        f"{method.upper()} {path} was reachable by a non-superadmin"
    )


@pytest.mark.parametrize("method,path,body", PLAN_ROUTES)
async def test_plan_administration_requires_authentication(
    client, method, path, body
):
    response = await getattr(client, method)(
        path, **({"json": body} if body else {})
    )
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

async def test_list_plans_returns_the_seeded_catalogue(
    client, auth_header, superadmin
):
    response = await client.get(f"{ADMIN}/plans", headers=auth_header(superadmin))
    assert response.status_code == 200, response.text

    plans = {p["key"]: p for p in response.json()}
    assert {"free", "starter", "growth", "pro", "enterprise"} <= set(plans)

    free = {f["feature_key"]: f for f in plans["free"]["features"]}
    assert free["posts_per_month"]["limit_value"] == 10
    assert free["white_label"]["limit_value"] == 0

    enterprise = {f["feature_key"]: f for f in plans["enterprise"]["features"]}
    assert enterprise["posts_per_month"]["unlimited"] is True
    assert enterprise["posts_per_month"]["limit_value"] is None
    assert enterprise["white_label"]["limit_value"] == 1


async def test_list_features_returns_the_catalogue(client, auth_header, superadmin):
    response = await client.get(f"{ADMIN}/features", headers=auth_header(superadmin))
    assert response.status_code == 200

    features = {f["key"]: f for f in response.json()}
    assert {
        "workspaces", "team_members", "social_accounts", "posts_per_month",
        "ai_requests_per_month", "storage_bytes", "analytics_history_days",
        "reports_per_month", "white_label",
    } <= set(features)
    assert features["white_label"]["unit"] == "boolean"
    assert features["storage_bytes"]["unit"] == "bytes"
    assert features["posts_per_month"]["is_metered"] is True


# ---------------------------------------------------------------------------
# Editing limits -- the reason this exists
# ---------------------------------------------------------------------------

async def _plan_id(client, auth_header, superadmin, key: str) -> str:
    plans = (await client.get(f"{ADMIN}/plans", headers=auth_header(superadmin))).json()
    return next(p["id"] for p in plans if p["key"] == key)


async def test_raising_a_limit_takes_effect_immediately(
    client, auth_header, superadmin, user_factory, account_factory,
    organization_factory,
):
    """The cache must not outlive the change -- see update_plan_limits."""
    owner = await user_factory()
    organization = await organization_factory(owner)
    account = await account_factory(owner, organization=organization)
    headers = auth_header(owner)

    body = {"content": "post", "target_accounts": []}
    for _ in range(10):  # the Free plan's allowance
        assert (
            await client.post(
                f"/api/v1/accounts/{account.id}/posts/", headers=headers, json=body
            )
        ).status_code == 201
    assert (
        await client.post(
            f"/api/v1/accounts/{account.id}/posts/", headers=headers, json=body
        )
    ).status_code == 402

    plan_id = await _plan_id(client, auth_header, superadmin, "free")
    response = await client.put(
        f"{ADMIN}/plans/{plan_id}/limits",
        headers=auth_header(superadmin),
        json={"limits": {"posts_per_month": 12}},
    )
    assert response.status_code == 200, response.text

    assert (
        await client.post(
            f"/api/v1/accounts/{account.id}/posts/", headers=headers, json=body
        )
    ).status_code == 201


async def test_null_limit_grants_unlimited(client, auth_header, superadmin):
    plan_id = await _plan_id(client, auth_header, superadmin, "free")
    response = await client.put(
        f"{ADMIN}/plans/{plan_id}/limits",
        headers=auth_header(superadmin),
        json={"limits": {"posts_per_month": None}},
    )
    assert response.status_code == 200

    features = {f["feature_key"]: f for f in response.json()["features"]}
    assert features["posts_per_month"]["unlimited"] is True
    assert features["posts_per_month"]["limit_value"] is None


async def test_a_partial_limits_update_leaves_the_rest_alone(
    client, auth_header, superadmin
):
    plan_id = await _plan_id(client, auth_header, superadmin, "starter")
    before = (
        await client.get(f"{ADMIN}/plans/{plan_id}", headers=auth_header(superadmin))
    ).json()
    original = {f["feature_key"]: f["limit_value"] for f in before["features"]}

    response = await client.put(
        f"{ADMIN}/plans/{plan_id}/limits",
        headers=auth_header(superadmin),
        json={"limits": {"team_members": 99}},
    )
    after = {f["feature_key"]: f["limit_value"] for f in response.json()["features"]}

    assert after["team_members"] == 99
    assert {k: v for k, v in after.items() if k != "team_members"} == {
        k: v for k, v in original.items() if k != "team_members"
    }


async def test_unknown_feature_key_is_rejected(client, auth_header, superadmin):
    """A typo must not silently create a limit nothing reads."""
    plan_id = await _plan_id(client, auth_header, superadmin, "free")
    response = await client.put(
        f"{ADMIN}/plans/{plan_id}/limits",
        headers=auth_header(superadmin),
        json={"limits": {"psots_per_month": 50}},
    )
    assert response.status_code == 400
    assert "psots_per_month" in response.json()["detail"]


async def test_negative_limit_is_rejected(client, auth_header, superadmin):
    """-1 used to mean unlimited; null does now, and -1 must not sneak back in
    as a limit that compares below every usage count."""
    plan_id = await _plan_id(client, auth_header, superadmin, "free")
    response = await client.put(
        f"{ADMIN}/plans/{plan_id}/limits",
        headers=auth_header(superadmin),
        json={"limits": {"posts_per_month": -1}},
    )
    assert response.status_code == 400
    assert "null" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Creating and retiring plans
# ---------------------------------------------------------------------------

async def test_create_plan_populates_every_feature(client, auth_header, superadmin):
    response = await client.post(
        f"{ADMIN}/plans",
        headers=auth_header(superadmin),
        json={
            "key": "agency",
            "name": "Agency",
            "price_monthly": "499.00",
            "sort_order": 90,
            "limits": {"workspaces": 50, "posts_per_month": None},
        },
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["key"] == "agency"
    assert body["price_monthly"] == 499.0

    features = {f["feature_key"]: f for f in body["features"]}
    assert len(features) == 9, "every known feature should get a row"
    assert features["workspaces"]["limit_value"] == 50
    assert features["posts_per_month"]["unlimited"] is True
    # Unmentioned features default to 0 -- not granted, never unlimited.
    assert features["white_label"]["limit_value"] == 0


async def test_duplicate_plan_key_is_rejected(client, auth_header, superadmin):
    response = await client.post(
        f"{ADMIN}/plans",
        headers=auth_header(superadmin),
        json={"key": "free", "name": "Free Again"},
    )
    assert response.status_code == 409


async def test_update_plan_metadata(client, auth_header, superadmin):
    plan_id = await _plan_id(client, auth_header, superadmin, "pro")
    response = await client.patch(
        f"{ADMIN}/plans/{plan_id}",
        headers=auth_header(superadmin),
        json={"name": "Pro (renamed)", "price_monthly": "149.00"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Pro (renamed)"
    assert response.json()["price_monthly"] == 149.0


async def test_delete_deactivates_rather_than_removes(
    db_session, client, auth_header, superadmin
):
    """Deleting the row would leave every organization on that tier with no
    limits at all, which reads as 'nothing granted'."""
    from sqlalchemy import select

    from app.models.plan import Plan

    plan_id = await _plan_id(client, auth_header, superadmin, "starter")
    response = await client.delete(
        f"{ADMIN}/plans/{plan_id}", headers=auth_header(superadmin)
    )
    assert response.status_code == 204

    plan = (
        await db_session.execute(select(Plan).where(Plan.key == "starter"))
    ).scalar_one()
    assert plan is not None
    assert plan.is_active is False


async def test_unknown_plan_is_404(client, auth_header, superadmin):
    import uuid

    response = await client.get(
        f"{ADMIN}/plans/{uuid.uuid4()}", headers=auth_header(superadmin)
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Usage endpoint
# ---------------------------------------------------------------------------

async def test_usage_reports_used_against_limit(
    client, auth_header, user_factory, account_factory, organization_factory
):
    owner = await user_factory()
    organization = await organization_factory(owner)
    account = await account_factory(owner, organization=organization)
    headers = auth_header(owner)

    for i in range(3):
        await client.post(
            f"/api/v1/accounts/{account.id}/posts/",
            headers=headers,
            json={"content": f"post {i}", "target_accounts": []},
        )

    response = await client.get(
        f"/api/v1/organizations/{organization.id}/usage", headers=headers
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["plan_key"] == "free"
    assert body["plan_name"] == "Free"

    features = {f["key"]: f for f in body["features"]}
    assert features["posts_per_month"]["used"] == 3
    assert features["posts_per_month"]["limit"] == 10
    assert features["posts_per_month"]["metered"] is True
    # Stateful: counted live, not metered.
    assert features["workspaces"]["used"] == 1
    assert features["workspaces"]["limit"] == 1
    assert features["workspaces"]["metered"] is False
    assert features["white_label"]["enabled"] is False


async def test_usage_reflects_an_unlimited_plan(
    client, auth_header, user_factory, account_factory, organization_factory,
    set_limit,
):
    owner = await user_factory()
    organization = await organization_factory(owner)
    await account_factory(owner, organization=organization)
    await set_limit(organization, "posts_per_month", None)

    response = await client.get(
        f"/api/v1/organizations/{organization.id}/usage", headers=auth_header(owner)
    )
    features = {f["key"]: f for f in response.json()["features"]}
    assert features["posts_per_month"]["limit"] is None
    assert features["posts_per_month"]["unlimited"] is True


async def test_usage_is_denied_to_a_non_member(
    client, auth_header, user_factory, account_factory, organization_factory
):
    owner = await user_factory()
    organization = await organization_factory(owner)
    await account_factory(owner, organization=organization)
    stranger = await user_factory()

    response = await client.get(
        f"/api/v1/organizations/{organization.id}/usage",
        headers=auth_header(stranger),
    )
    assert response.status_code == 403
