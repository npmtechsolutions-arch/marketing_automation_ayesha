"""Connection health: notice a token is dying before a post fails on it.

A social connection degrades silently. The token has an expiry nobody watches,
or a customer revokes access in the platform's own settings, and the first
anyone hears about it is a scheduled post failing at 9am with an auth error --
by which time the slot is gone.

The sweep runs hourly, tries to refresh what it can, and reports what it
cannot. The important design constraint is **notify once per state change, not
once per sweep**: an hourly reminder that the same account is still broken is
how people learn to ignore the notification.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connectors.base import NotSupportedError
from app.connectors.registry import get_provider
from app.models.platform import AccountHealth, SocialAccount

logger = logging.getLogger(__name__)

# How far ahead a token counts as expiring. A week is long enough for someone
# to notice and act during a normal working pattern, and short enough that the
# warning still means something when it appears.
EXPIRY_WARNING_DAYS = 7

# How often the sweep runs. Tokens do not degrade minute to minute, and each
# pass may make a network call per account.
SWEEP_INTERVAL_SECONDS = 60 * 60

# Refresh anything expiring within this window rather than waiting for it to
# reach the warning threshold -- a refresh that succeeds is better than a
# warning nobody has to act on.
REFRESH_WHEN_WITHIN = timedelta(days=EXPIRY_WARNING_DAYS)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite drops tzinfo on read where Postgres keeps it."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def compute_health(
    account: SocialAccount, *, now: Optional[datetime] = None
) -> tuple[AccountHealth, Optional[str]]:
    """The account's health from what is already known about it.

    Pure: no network, no database. The sweep calls this after attempting a
    refresh, and the accounts endpoint can call it to show a live answer
    without waiting for the next pass.
    """
    now = now or datetime.now(timezone.utc)

    if not account.access_token:
        return (
            AccountHealth.FAILED,
            "No access token is stored for this account. Reconnect it to publish.",
        )

    expires_at = _aware(account.token_expires_at)
    if expires_at is None:
        # Meta page tokens and some others carry no expiry. Absence is not a
        # problem; treating it as one would mark healthy accounts EXPIRING
        # forever.
        return AccountHealth.CONNECTED, None

    if expires_at <= now:
        return (
            AccountHealth.FAILED,
            f"The access token expired on {expires_at.date().isoformat()}. "
            "Reconnect the account to publish again.",
        )
    if expires_at - now <= timedelta(days=EXPIRY_WARNING_DAYS):
        days = max(1, (expires_at - now).days)
        return (
            AccountHealth.EXPIRING,
            f"The access token expires in {days} day{'s' if days != 1 else ''}.",
        )
    return AccountHealth.CONNECTED, None


async def try_refresh(db: AsyncSession, account: SocialAccount) -> bool:
    """Refresh the token if the platform supports it. True when it worked.

    A failure here is not fatal to the sweep: it means this account needs a
    human, which is exactly what health is for.
    """
    provider = get_provider(account.platform.slug if account.platform else None)
    try:
        result = await provider.refresh_token(account)
    except NotSupportedError:
        # Nothing to do for this platform. Not an error -- Meta page tokens
        # have no refresh grant, they are re-exchanged instead.
        return False
    except Exception as exc:  # noqa: BLE001 - a refusal is information, not a crash
        logger.info(
            "Could not refresh %s account %s: %s", provider.slug, account.id, exc
        )
        account.health_detail = f"Automatic refresh failed: {exc}"
        return False

    account.access_token = result.access_token
    if result.refresh_token:
        account.refresh_token = result.refresh_token
    if result.expires_at:
        account.token_expires_at = result.expires_at
    account.last_verified_at = datetime.now(timezone.utc)
    logger.info("Refreshed %s account %s automatically.", provider.slug, account.id)
    return True


def mark_auth_failure(account: SocialAccount, detail: str) -> None:
    """Record that a live call rejected these credentials.

    Called from the publish path: a 401 from the platform is stronger evidence
    than any expiry arithmetic, and waiting up to an hour for the sweep to
    notice would let the next scheduled post fail the same way.
    """
    account.health = AccountHealth.FAILED
    account.health_detail = detail
    account.health_changed_at = datetime.now(timezone.utc)
    account.last_checked_at = datetime.now(timezone.utc)


async def sweep_account(
    db: AsyncSession, account: SocialAccount, *, now: Optional[datetime] = None
) -> tuple[AccountHealth, bool]:
    """Check one account. Returns (health, changed).

    ``changed`` is what gates notification: without it the same warning goes
    out every hour and stops being read.
    """
    now = now or datetime.now(timezone.utc)
    previous = account.health

    expires_at = _aware(account.token_expires_at)
    if expires_at is not None and expires_at - now <= REFRESH_WHEN_WITHIN:
        # Try to fix it before reporting it. A silent successful refresh is a
        # better outcome than a warning someone has to act on.
        await try_refresh(db, account)

    health, detail = compute_health(account, now=now)
    account.last_checked_at = now
    if health is not previous:
        account.health = health
        account.health_changed_at = now
    # The detail is refreshed either way, so a stale reason does not outlive
    # the problem it described.
    account.health_detail = detail if health is not AccountHealth.CONNECTED else None
    return health, health is not previous


async def sweep(db: AsyncSession, *, now: Optional[datetime] = None) -> dict:
    """Check every active connection and notify on the ones that changed.

    Returns a small summary for the worker log, so an operator can see the
    sweep ran and what it found without reading the table.
    """
    now = now or datetime.now(timezone.utc)
    accounts = (
        await db.execute(
            select(SocialAccount)
            .options(selectinload(SocialAccount.platform))
            .where(SocialAccount.is_active.is_(True))
        )
    ).scalars().all()

    summary = {"checked": 0, "changed": 0, "degraded": 0, "notified": 0}
    for account in accounts:
        try:
            health, changed = await sweep_account(db, account, now=now)
        except Exception:  # noqa: BLE001 - one bad account must not stop the sweep
            logger.exception("Health sweep failed for account %s", account.id)
            continue

        summary["checked"] += 1
        if changed:
            summary["changed"] += 1
        if health in (AccountHealth.EXPIRING, AccountHealth.FAILED):
            summary["degraded"] += 1
            if changed:
                # Only on the transition. An account that has been broken for
                # a week does not need a seventh identical notification.
                summary["notified"] += await notify_degraded(db, account, health)

    await db.commit()
    if summary["checked"]:
        logger.info("Account health sweep: %s", summary)
    return summary


async def notify_degraded(
    db: AsyncSession, account: SocialAccount, health: AccountHealth
) -> int:
    """Tell the people who can fix it.

    Workspace admins rather than everyone: reconnecting requires managing the
    account, so telling a contributor is asking them to forward it.
    """
    import uuid as _uuid

    from app.core.permissions import ACCOUNTS_MANAGE, role_has_permission
    from app.models.notification import Notification
    from app.models.team_member import InvitationStatus, TeamMember
    from app.services.email_service import EmailService

    members = (
        await db.execute(
            select(TeamMember).where(
                TeamMember.account_id == account.account_id,
                TeamMember.invitation_status == InvitationStatus.ACCEPTED,
                TeamMember.user_id.is_not(None),
            )
        )
    ).scalars().all()
    managers = [m for m in members if role_has_permission(m.role, ACCOUNTS_MANAGE)]
    if not managers:
        return 0

    platform = account.platform.name if account.platform else "A social account"
    if health is AccountHealth.FAILED:
        title = f"{platform} disconnected"
        message = (
            f"'{account.account_name}' can no longer publish. "
            + (account.health_detail or "Reconnect it to resume publishing.")
        )
    else:
        title = f"{platform} connection expiring"
        message = (
            f"'{account.account_name}' will stop publishing soon. "
            + (account.health_detail or "Reconnect it to avoid interruption.")
        )

    from app.models.user import User

    users = (
        await db.execute(
            select(User).where(User.id.in_([m.user_id for m in managers]))
        )
    ).scalars().all()

    for user in users:
        db.add(
            Notification(
                id=_uuid.uuid4(),
                user_id=user.id,
                account_id=account.account_id,
                type=f"account.{health.value}",
                title=title,
                message=message,
                action_url="/social-accounts",
            )
        )
        try:
            await EmailService.send_account_health_email(
                user.email,
                user_name=user.full_name,
                account_name=account.account_name,
                platform=platform,
                health=health.value,
                detail=account.health_detail or "",
            )
        except Exception:  # noqa: BLE001 - a mail failure must not fail the sweep
            logger.exception("Could not email %s about account health", user.email)

    await db.flush()

    # Slack too, if routed. Reached only on a transition -- the sweep calls
    # this behind `if changed`, which is what keeps a broken account from
    # producing an hourly reminder that it is still broken.
    from app.models.account import Account as _Account
    from app.services import notifications as _notifications

    workspace = (
        await db.execute(
            select(_Account).where(_Account.id == account.account_id)
        )
    ).scalar_one_or_none()
    if workspace is not None:
        await _notifications.to_slack(
            db, workspace, _notifications.Event.ACCOUNT_HEALTH_CHANGED,
            title=title, message=message,
            fields={
                "Account": account.account_name or "(unnamed)",
                "Platform": platform,
                "Health": health.value,
            },
        )

    return len(users)


async def health_summary(db: AsyncSession, account_id) -> dict:
    """Counts by health for one workspace, for the dashboard's warning strip."""
    from sqlalchemy import func as sa_func

    rows = (
        await db.execute(
            select(SocialAccount.health, sa_func.count(SocialAccount.id))
            .where(
                SocialAccount.account_id == account_id,
                SocialAccount.is_active.is_(True),
            )
            .group_by(SocialAccount.health)
        )
    ).all()
    counts = {health.value: count for health, count in rows}
    return {
        "total": sum(counts.values()),
        "connected": counts.get("connected", 0),
        "expiring": counts.get("expiring", 0),
        "failed": counts.get("failed", 0),
        "unknown": counts.get("unknown", 0),
    }
