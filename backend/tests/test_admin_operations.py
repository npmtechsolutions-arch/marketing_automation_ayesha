"""The operational admin surface: revenue, connection health, and API errors.

Two things are checked for every route. That a non-superadmin cannot reach it
-- these expose the whole customer book, so one unguarded handler is a data
breach rather than a bug. And that admin writes leave an audit trail, which
the plan endpoints shipped without.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.account import SubscriptionStatus, SubscriptionTier
from app.models.api_error import ApiError
from app.models.audit_log import ActivityLog as AuditLog
from app.models.platform import AccountHealth
from app.services import error_log

pytestmark = pytest.mark.asyncio

ADMIN = "/api/v1/admin"


@pytest.fixture
async def superadmin(user_factory):
    return await user_factory(is_superadmin=True)


# ---------------------------------------------------------------------------
# The gate, on every route added for scope 19
# ---------------------------------------------------------------------------

NEW_ROUTES = [
    ("get", f"{ADMIN}/revenue"),
    ("get", f"{ADMIN}/revenue/trend"),
    ("get", f"{ADMIN}/connection-health"),
    ("get", f"{ADMIN}/errors"),
    ("get", f"{ADMIN}/errors/summary"),
    ("get", f"{ADMIN}/errors/{uuid.uuid4()}"),
]


@pytest.mark.parametrize("method,path", NEW_ROUTES)
async def test_every_new_admin_route_requires_superadmin(
    client, auth_header, user_factory, method, path
):
    ordinary = await user_factory()

    response = await getattr(client, method)(path, headers=auth_header(ordinary))

    assert response.status_code == 403, (
        f"{method.upper()} {path} was reachable by a non-superadmin"
    )


@pytest.mark.parametrize("method,path", NEW_ROUTES)
async def test_every_new_admin_route_requires_authentication(client, method, path):
    response = await getattr(client, method)(path)
    assert response.status_code == 401, f"{method.upper()} {path} allowed anonymous access"


@pytest.mark.parametrize("method,path", NEW_ROUTES)
async def test_a_suspended_superadmin_cannot_reach_them(
    client, auth_header, user_factory, method, path
):
    """is_superadmin alone is not enough -- the account must still be active,
    which is what suspending a compromised operator relies on."""
    suspended = await user_factory(is_superadmin=True, is_active=False)

    response = await getattr(client, method)(path, headers=auth_header(suspended))

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Revenue endpoint
# ---------------------------------------------------------------------------

async def test_revenue_endpoint_returns_the_metrics(
    client, auth_header, superadmin, user_factory, organization_factory, db_session
):
    owner = await user_factory()
    await organization_factory(
        owner,
        subscription_tier=SubscriptionTier.PRO,
        subscription_status=SubscriptionStatus.ACTIVE,
    )
    await db_session.flush()

    response = await client.get(f"{ADMIN}/revenue", headers=auth_header(superadmin))

    assert response.status_code == 200
    body = response.json()
    assert body["mrr"] == 399.0
    assert body["arr"] == 399.0 * 12
    assert body["churn"]["days"] == 30
    assert "conversion_rate" in body["trials"]


async def test_revenue_trend_says_where_its_history_starts(
    client, auth_header, superadmin
):
    response = await client.get(
        f"{ADMIN}/revenue/trend?days=30", headers=auth_header(superadmin)
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["series"]) == 31, "a 30-day window is 31 inclusive days"
    # No events yet, so the client must be able to tell "no revenue recorded"
    # from "no records".
    assert body["has_history"] is False


# ---------------------------------------------------------------------------
# Connection health
# ---------------------------------------------------------------------------

async def test_connection_health_counts_and_lists_failures(
    client, auth_header, superadmin, db_session,
    user_factory, organization_factory, account_factory, social_account_factory,
):
    owner = await user_factory()
    organization = await organization_factory(owner)
    account = await account_factory(owner, organization=organization)

    broken = await social_account_factory(owner, account)
    broken.health = AccountHealth.FAILED
    broken.health_detail = "token revoked"
    broken.health_checked_at = datetime.now(timezone.utc)
    await db_session.flush()

    response = await client.get(
        f"{ADMIN}/connection-health", headers=auth_header(superadmin)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["counts"]["failed"] == 1
    row = next(item for item in body["failed"] if item["id"] == str(broken.id))
    # The context that makes the row actionable: support has to know whose
    # connection is broken, not just that one is.
    assert row["workspace"] == account.name
    assert row["organization"] == organization.name
    assert row["detail"] == "token revoked"


async def test_connection_health_reports_every_state_even_at_zero(
    client, auth_header, superadmin
):
    """A missing key reads as "unknown" in a UI; an explicit zero reads as
    "none", which is the true statement."""
    response = await client.get(
        f"{ADMIN}/connection-health", headers=auth_header(superadmin)
    )

    counts = response.json()["counts"]
    for state in AccountHealth:
        assert state.value in counts


# ---------------------------------------------------------------------------
# API errors
# ---------------------------------------------------------------------------

async def _error_row(db_session, *, path="/api/v1/posts", exc="ValueError", ago_days=0):
    row = ApiError(
        id=uuid.uuid4(),
        path=path,
        method="GET",
        status_code=500,
        exception_class=exc,
        message="boom",
        traceback="Traceback...\nValueError: boom",
        created_at=datetime.now(timezone.utc) - timedelta(days=ago_days),
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def test_errors_list_and_filters(client, auth_header, superadmin, db_session):
    await _error_row(db_session, path="/api/v1/posts", exc="ValueError")
    await _error_row(db_session, path="/api/v1/accounts/x/media", exc="KeyError")

    listed = await client.get(f"{ADMIN}/errors", headers=auth_header(superadmin))
    assert listed.json()["total"] == 2

    by_class = await client.get(
        f"{ADMIN}/errors?exception_class=KeyError", headers=auth_header(superadmin)
    )
    assert by_class.json()["total"] == 1

    # Prefix, not exact: filtering by a route family has to work without
    # knowing the workspace id in the middle of the path.
    by_path = await client.get(
        f"{ADMIN}/errors?path=/api/v1/accounts", headers=auth_header(superadmin)
    )
    assert by_path.json()["total"] == 1


async def test_the_error_list_omits_tracebacks(client, auth_header, superadmin, db_session):
    """Fifty multi-kilobyte tracebacks would make the list unusable; the detail
    route carries them."""
    row = await _error_row(db_session)

    listed = await client.get(f"{ADMIN}/errors", headers=auth_header(superadmin))
    assert "traceback" not in listed.json()["items"][0]

    detail = await client.get(f"{ADMIN}/errors/{row.id}", headers=auth_header(superadmin))
    assert "ValueError: boom" in detail.json()["traceback"]


async def test_error_summary_groups_by_exception(client, auth_header, superadmin, db_session):
    await _error_row(db_session, exc="ValueError")
    await _error_row(db_session, exc="ValueError")
    await _error_row(db_session, exc="KeyError")

    response = await client.get(
        f"{ADMIN}/errors/summary?days=7", headers=auth_header(superadmin)
    )

    body = response.json()
    assert body["total"] == 3
    # Most frequent first: the point of the view is what to fix next.
    assert body["by_exception"][0]["exception_class"] == "ValueError"
    assert body["by_exception"][0]["count"] == 2


async def test_pruning_drops_rows_past_the_window(db_session):
    await _error_row(db_session, ago_days=1)
    await _error_row(db_session, ago_days=120)

    deleted = await error_log.prune(db_session, days=90)

    assert deleted == 1
    remaining = (await db_session.execute(select(ApiError))).scalars().all()
    assert len(remaining) == 1


async def test_a_truncated_traceback_keeps_the_end(db_session):
    """The last frames are the ones that raised; the first are ASGI plumbing
    identical on every row."""
    long_trace = "filler\n" * 5000 + "ValueError: the actual cause"

    kept = error_log._truncate(long_trace, 200)

    assert kept.endswith("ValueError: the actual cause")
    assert kept.startswith("...[truncated]")


async def test_an_unknown_error_id_is_404(client, auth_header, superadmin):
    response = await client.get(
        f"{ADMIN}/errors/{uuid.uuid4()}", headers=auth_header(superadmin)
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Audit coverage (scope 19.5)
# ---------------------------------------------------------------------------

async def _audit_rows(db_session, action: str):
    return (
        await db_session.execute(select(AuditLog).where(AuditLog.action == action))
    ).scalars().all()


async def test_creating_a_plan_is_audited(client, auth_header, superadmin, db_session):
    response = await client.post(
        f"{ADMIN}/plans",
        headers=auth_header(superadmin),
        json={"key": "audited", "name": "Audited", "price_monthly": 10},
    )
    assert response.status_code == 201

    rows = await _audit_rows(db_session, "create_plan")
    assert len(rows) == 1
    assert rows[0].user_id == superadmin.id
    assert rows[0].resource_type == "plan"


async def test_updating_a_plan_records_both_ends_of_the_change(
    client, auth_header, superadmin, db_session
):
    created = await client.post(
        f"{ADMIN}/plans",
        headers=auth_header(superadmin),
        json={"key": "movable", "name": "Movable", "price_monthly": 10},
    )
    plan_id = created.json()["id"]

    await client.patch(
        f"{ADMIN}/plans/{plan_id}",
        headers=auth_header(superadmin),
        json={"price_monthly": 25},
    )

    rows = await _audit_rows(db_session, "update_plan")
    assert len(rows) == 1
    # Without the old value the log says a price is 25 now and nothing about
    # what it was, which is the question anyone reading it is asking.
    assert rows[0].old_values["price_monthly"] == 10.0
    assert rows[0].new_values["price_monthly"] == 25.0


async def test_changing_limits_is_audited(client, auth_header, superadmin, db_session):
    created = await client.post(
        f"{ADMIN}/plans",
        headers=auth_header(superadmin),
        json={"key": "limited", "name": "Limited", "price_monthly": 10},
    )
    plan_id = created.json()["id"]

    await client.put(
        f"{ADMIN}/plans/{plan_id}/limits",
        headers=auth_header(superadmin),
        json={"limits": {"posts_per_month": 500}},
    )

    rows = await _audit_rows(db_session, "update_plan_limits")
    assert len(rows) == 1
    assert rows[0].new_values["posts_per_month"] == 500


async def test_retiring_a_plan_is_audited(client, auth_header, superadmin, db_session):
    created = await client.post(
        f"{ADMIN}/plans",
        headers=auth_header(superadmin),
        json={"key": "retired", "name": "Retired", "price_monthly": 10},
    )
    plan_id = created.json()["id"]

    await client.delete(f"{ADMIN}/plans/{plan_id}", headers=auth_header(superadmin))

    rows = await _audit_rows(db_session, "deactivate_plan")
    assert len(rows) == 1
