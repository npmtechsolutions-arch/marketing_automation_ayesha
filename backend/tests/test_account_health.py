"""Connection health: notice a dying token before a post fails on it.

The behaviour that matters most is de-duplication. An hourly reminder that the
same account is still broken is how people learn to filter the notification
out, and then the one that matters gets filtered too.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.notification import Notification
from app.models.platform import AccountHealth, SocialAccount
from app.models.team_member import InvitationStatus, TeamRole
from app.services import account_health

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"
NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
async def workspace(
    db_session, user_factory, account_factory, organization_factory,
    social_account_factory, member_factory,
):
    async def _make():
        owner = await user_factory(password=PASSWORD, full_name="Olive Owner")
        organization = await organization_factory(owner)
        account = await account_factory(owner, organization=organization)
        # An editor: has content permissions but not accounts.manage, so they
        # should not be told to go and reconnect something.
        editor = await user_factory(password=PASSWORD, full_name="Ed Editor")
        await member_factory(
            editor, account, role=TeamRole.EDITOR,
            invitation_status=InvitationStatus.ACCEPTED,
        )
        return {
            "owner": owner, "editor": editor, "account": account,
            "account_id": account.id,
            "connect": lambda **kw: social_account_factory(owner, account, **kw),
        }

    return _make


async def _with_expiry(ws, delta, **kw):
    sa = await ws["connect"](**kw)
    sa.token_expires_at = NOW + delta if delta is not None else None
    return sa


# ---------------------------------------------------------------------------
# Health computation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "delta,expected",
    [
        (timedelta(days=90), AccountHealth.CONNECTED),
        (timedelta(days=8), AccountHealth.CONNECTED),
        # Exactly at the boundary counts as expiring: the warning should fire
        # on the day it becomes true, not the day after.
        (timedelta(days=7), AccountHealth.EXPIRING),
        (timedelta(days=1), AccountHealth.EXPIRING),
        (timedelta(hours=1), AccountHealth.EXPIRING),
        (timedelta(seconds=-1), AccountHealth.FAILED),
        (timedelta(days=-30), AccountHealth.FAILED),
    ],
)
async def test_health_from_expiry(db_session, workspace, delta, expected):
    ws = await workspace()
    sa = await _with_expiry(ws, delta)
    health, _ = account_health.compute_health(sa, now=NOW)
    assert health is expected


async def test_no_expiry_is_healthy(db_session, workspace):
    """Meta page tokens carry no expiry. Treating absence as a problem would
    mark healthy accounts EXPIRING forever."""
    ws = await workspace()
    sa = await _with_expiry(ws, None)
    assert account_health.compute_health(sa, now=NOW)[0] is AccountHealth.CONNECTED


async def test_a_missing_token_is_failed(db_session, workspace):
    ws = await workspace()
    sa = await ws["connect"]()
    sa.access_token = None
    health, detail = account_health.compute_health(sa, now=NOW)
    assert health is AccountHealth.FAILED
    assert "reconnect" in detail.lower()


async def test_the_detail_says_when(db_session, workspace):
    ws = await workspace()
    sa = await _with_expiry(ws, timedelta(days=3))
    _, detail = account_health.compute_health(sa, now=NOW)
    assert "3 days" in detail


# ---------------------------------------------------------------------------
# The sweep
# ---------------------------------------------------------------------------

async def test_sweep_records_health_and_the_check_time(db_session, workspace):
    ws = await workspace()
    await _with_expiry(ws, timedelta(days=2))
    await db_session.flush()

    summary = await account_health.sweep(db_session, now=NOW)
    assert summary["checked"] == 1
    assert summary["degraded"] == 1

    db_session.expire_all()
    sa = (await db_session.execute(select(SocialAccount))).scalars().one()
    assert sa.health is AccountHealth.EXPIRING
    assert sa.last_checked_at is not None


async def test_recovery_clears_the_detail(db_session, workspace):
    """A stale reason outliving the problem it described is worse than none."""
    ws = await workspace()
    sa = await _with_expiry(ws, timedelta(days=2))
    await db_session.flush()
    await account_health.sweep(db_session, now=NOW)

    db_session.expire_all()
    sa = (await db_session.execute(select(SocialAccount))).scalars().one()
    assert sa.health_detail

    sa.token_expires_at = NOW + timedelta(days=90)
    await db_session.flush()
    await account_health.sweep(db_session, now=NOW)

    db_session.expire_all()
    sa = (await db_session.execute(select(SocialAccount))).scalars().one()
    assert sa.health is AccountHealth.CONNECTED
    assert sa.health_detail is None


async def test_an_inactive_account_is_skipped(db_session, workspace):
    ws = await workspace()
    sa = await _with_expiry(ws, timedelta(days=-1))
    sa.is_active = False
    await db_session.flush()

    assert (await account_health.sweep(db_session, now=NOW))["checked"] == 0


# ---------------------------------------------------------------------------
# Notification de-duplication
# ---------------------------------------------------------------------------

async def _notifications(db_session):
    return (
        await db_session.execute(
            select(Notification).where(Notification.type.like("account.%"))
        )
    ).scalars().all()


async def test_a_degraded_account_notifies_once_not_every_sweep(
    db_session, workspace
):
    """The headline behaviour. Repeating the same warning hourly is how a
    notification stops being read."""
    ws = await workspace()
    await _with_expiry(ws, timedelta(days=2))
    await db_session.flush()

    first = await account_health.sweep(db_session, now=NOW)
    assert first["notified"] == 1

    for _ in range(4):
        again = await account_health.sweep(db_session, now=NOW)
        assert again["notified"] == 0, "a second warning went out for the same state"

    assert len(await _notifications(db_session)) == 1


async def test_a_worsening_state_notifies_again(db_session, workspace):
    """EXPIRING becoming FAILED is new information, not a repeat."""
    ws = await workspace()
    sa = await _with_expiry(ws, timedelta(days=2))
    await db_session.flush()
    await account_health.sweep(db_session, now=NOW)

    db_session.expire_all()
    sa = (await db_session.execute(select(SocialAccount))).scalars().one()
    sa.token_expires_at = NOW - timedelta(days=1)
    await db_session.flush()
    second = await account_health.sweep(db_session, now=NOW)

    assert second["notified"] == 1
    types = {n.type for n in await _notifications(db_session)}
    assert types == {"account.expiring", "account.failed"}


async def test_recovering_then_degrading_notifies_again(db_session, workspace):
    """The de-duplication is per state change, not a permanent mute."""
    ws = await workspace()
    sa = await _with_expiry(ws, timedelta(days=2))
    await db_session.flush()
    await account_health.sweep(db_session, now=NOW)

    for delta in (timedelta(days=90), timedelta(days=2)):
        db_session.expire_all()
        sa = (await db_session.execute(select(SocialAccount))).scalars().one()
        sa.token_expires_at = NOW + delta
        await db_session.flush()
        await account_health.sweep(db_session, now=NOW)

    assert len(await _notifications(db_session)) == 2


async def test_only_people_who_can_reconnect_are_told(db_session, workspace):
    """Telling a contributor is asking them to forward it."""
    ws = await workspace()
    await _with_expiry(ws, timedelta(days=-1))
    await db_session.flush()
    await account_health.sweep(db_session, now=NOW)

    recipients = {n.user_id for n in await _notifications(db_session)}
    assert ws["owner"].id in recipients
    assert ws["editor"].id not in recipients


async def test_a_healthy_account_notifies_nobody(db_session, workspace):
    ws = await workspace()
    await _with_expiry(ws, timedelta(days=200))
    await db_session.flush()
    await account_health.sweep(db_session, now=NOW)
    assert await _notifications(db_session) == []


# ---------------------------------------------------------------------------
# Auth failures seen while publishing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "error,is_auth",
    [
        ("Malformed access token EAAxyz", True),
        ("HTTP 401 Unauthorized", True),
        ("OAuthException: invalid_grant", True),
        ("The user revoked access", True),
        ("Request timed out", False),
        ("HTTP 503 Service Unavailable", False),
        ("429 Too Many Requests", False),
        (None, False),
    ],
)
async def test_auth_failures_are_told_apart_from_transient_ones(error, is_auth):
    """Marking an account FAILED on a timeout would send a false alarm and
    teach people to ignore the real ones."""
    from app.services.publishing import _looks_like_auth_failure

    assert _looks_like_auth_failure(error) is is_auth


async def test_a_publish_auth_failure_marks_the_account(db_session, workspace):
    """Stronger evidence than expiry arithmetic, and waiting up to an hour for
    the sweep would let the next scheduled post fail the same way."""
    ws = await workspace()
    sa = await _with_expiry(ws, timedelta(days=90))
    assert account_health.compute_health(sa, now=NOW)[0] is AccountHealth.CONNECTED

    account_health.mark_auth_failure(sa, "Publishing was rejected: 401")
    assert sa.health is AccountHealth.FAILED
    assert "401" in sa.health_detail


# ---------------------------------------------------------------------------
# Reconnect
# ---------------------------------------------------------------------------

async def test_reconnect_updates_in_place(db_session, workspace):
    """The whole point: a fresh row would orphan every post, publishing job and
    metric that pointed at the old one."""
    from app.api.v1.endpoints.oauth_common import apply_reconnect

    ws = await workspace()
    sa = await _with_expiry(ws, timedelta(days=-1), access_token="old_token")
    sa.health = AccountHealth.FAILED
    sa.health_detail = "expired"
    await db_session.flush()
    original_id, platform_id = sa.id, sa.platform_id

    applied = await apply_reconnect(
        db_session,
        reconnect_id=original_id,
        account_id=ws["account_id"],
        platform_id=platform_id,
        access_token="fresh_token",
        refresh_token="fresh_refresh",
        token_expires_at=NOW + timedelta(days=60),
    )
    assert applied is True

    rows = (await db_session.execute(select(SocialAccount))).scalars().all()
    assert len(rows) == 1, "a reconnect created a second row"
    assert rows[0].id == original_id, "the id changed, orphaning every foreign key"
    assert rows[0].access_token == "fresh_token"
    assert rows[0].health is AccountHealth.CONNECTED
    assert rows[0].health_detail is None


async def test_reconnect_keeps_the_refresh_token_when_none_is_returned(
    db_session, workspace
):
    """Google omits it on re-consent and Meta has none. Blanking it would break
    the next automatic refresh."""
    from app.api.v1.endpoints.oauth_common import apply_reconnect

    ws = await workspace()
    sa = await ws["connect"]()
    sa.refresh_token = "keep_me"
    await db_session.flush()

    await apply_reconnect(
        db_session, reconnect_id=sa.id, account_id=ws["account_id"],
        platform_id=sa.platform_id, access_token="new", refresh_token=None,
    )
    db_session.expire_all()
    refreshed = (await db_session.execute(select(SocialAccount))).scalars().one()
    assert refreshed.refresh_token == "keep_me"


async def test_reconnect_refuses_another_workspaces_account(
    db_session, workspace, user_factory, account_factory, social_account_factory
):
    """Without the scope check a caller could overwrite someone else's
    credentials."""
    from app.api.v1.endpoints.oauth_common import apply_reconnect

    ws = await workspace()
    other_owner = await user_factory()
    other = await account_factory(other_owner, name="Other")
    foreign = await social_account_factory(other_owner, other)
    await db_session.flush()
    # Captured before anything expires the instance.
    foreign_id, foreign_platform = foreign.id, foreign.platform_id

    applied = await apply_reconnect(
        db_session, reconnect_id=foreign_id, account_id=ws["account_id"],
        platform_id=foreign_platform, access_token="stolen",
    )
    assert applied is False

    db_session.expire_all()
    untouched = (
        await db_session.execute(
            select(SocialAccount).where(SocialAccount.id == foreign_id)
        )
    ).scalar_one()
    assert untouched.access_token != "stolen"


async def test_reconnect_refuses_a_mismatched_platform(db_session, workspace):
    """Pointing a LinkedIn reconnect at an Instagram row would overwrite it
    with credentials for the wrong service."""
    from app.api.v1.endpoints.oauth_common import apply_reconnect

    ws = await workspace()
    sa = await ws["connect"](slug="instagram")
    await db_session.flush()

    applied = await apply_reconnect(
        db_session, reconnect_id=sa.id, account_id=ws["account_id"],
        platform_id=uuid.uuid4(), access_token="wrong",
    )
    assert applied is False


async def test_health_summary_counts_by_state(db_session, workspace):
    ws = await workspace()
    for delta in (timedelta(days=90), timedelta(days=2), timedelta(days=-1)):
        await _with_expiry(ws, delta)
    await db_session.flush()
    await account_health.sweep(db_session, now=NOW)

    summary = await account_health.health_summary(db_session, ws["account_id"])
    assert summary["total"] == 3
    assert summary["connected"] == 1
    assert summary["expiring"] == 1
    assert summary["failed"] == 1
