"""Competitor tracking: two numbers a week, for accounts a workspace names.

The scope is set by what Meta actually offers, not by what a competitor
dashboard usually claims. Instagram's Business Discovery is the only official
route to another account's data on any platform here, it works only for public
**business and creator** accounts, it must be asked *as* an Instagram business
account, and it returns username, name, follower count and media count. There
is no engagement, no posting cadence, no audience overlap and no "top content"
anywhere in it, and Meta's permission model puts all of that out of reach for
accounts that have not authorised this app (docs/API-TIER-AUDIT.md).

So three rules run through this module:

* **The feature is named for what it does.** Tracking, not intelligence.
  ``NOT_TRACKED`` is served to the UI so the add dialog states the absences in
  the same breath as the offer, rather than leaving someone to discover them.
* **Absent is not zero.** A private account yields a name and no counts; the
  snapshot stores NULL and the chart shows a gap.
* **Every number is stale by design.** Discovery is capped at roughly one
  lookup per account per week, so a figure on screen is days old and the UI
  says how old. "12,400 followers" and "12,400 followers as of 6 days ago" are
  different claims.
"""

import logging
import uuid
from datetime import date as date_type, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connectors.base import (
    AccountNotFound,
    NotSupportedError,
    PlatformRateLimited,
    ProviderAPIError,
)
from app.connectors.registry import get_provider
from app.models.account import Account
from app.models.competitor import CompetitorAccount, CompetitorSnapshot
from app.models.platform import SocialAccount
from app.services.dashboard import workspace_timezone

logger = logging.getLogger(__name__)

# Instagram is the whole of it. X has no equivalent at any tier, and the other
# three have nothing at all -- the audit's finding, and the reason this is not
# a "cross-platform competitor" feature.
PLATFORM = "instagram"

# Meta caps Business Discovery per account per week. Polling harder does not
# get fresher numbers, it gets errors, so the cap is the schedule.
SYNC_INTERVAL_DAYS = 7

# How often the worker *looks*. Whether a competitor is due is a per-row
# question answered against the cap above.
CHECK_INTERVAL_SECONDS = 6 * 60 * 60

# A trend needs two points. One snapshot is a fact, not a line, and drawing a
# single-point chart invites reading a slope into it.
MIN_SNAPSHOTS_FOR_TREND = 2

# What the add dialog says, served from here so the UI cannot quietly promise
# more than the API returns.
TRACKED = ("Follower count", "Number of posts", "Account name")
NOT_TRACKED = (
    "Engagement (likes, comments) on their posts",
    "How often they post, or when",
    "Their top-performing content",
    "Their audience, or any overlap with yours",
)
NOT_TRACKED_REASON = (
    "Instagram's Business Discovery API returns only public counts for an "
    "account that has not connected itself to this app. Everything else is "
    "restricted by Meta to accounts that have authorised us, on every tier. "
    "Tools that appear to offer more are scraping or buying the data."
)
REQUIREMENT = (
    "Competitor tracking asks Instagram *as* your own Instagram business "
    "account, which is Meta's requirement rather than ours. Connect an "
    "Instagram business or creator account to switch it on."
)
ELIGIBILITY = (
    "Only public Instagram business and creator accounts can be looked up. A "
    "personal or private account is invisible to the API, so it cannot be "
    "tracked."
)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite hands back naive datetimes; Postgres does not."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def local_today(account: Account, now: Optional[datetime] = None) -> date_type:
    """Today on the *workspace's* clock, not the server's.

    A snapshot dated by the machine lands a day out for any workspace east or
    west of it, which is the bug six analytics tests carried for weeks.
    """
    moment = now or datetime.now(timezone.utc)
    return moment.astimezone(workspace_timezone(account)).date()


def normalise_handle(raw: str) -> str:
    """One canonical form. Instagram handles are case-insensitive, so '@Nike'
    and 'nike' are one account -- and two rows would be two weekly lookups of
    the same thing."""
    return (raw or "").strip().lstrip("@").lower()


# ---------------------------------------------------------------------------
# Staleness, which is part of every number here
# ---------------------------------------------------------------------------

def next_sync_at(competitor: CompetitorAccount) -> Optional[datetime]:
    last = _aware(competitor.last_synced_at)
    return None if last is None else last + timedelta(days=SYNC_INTERVAL_DAYS)


def is_due(competitor: CompetitorAccount, now: Optional[datetime] = None) -> bool:
    if not competitor.is_active:
        return False
    due_at = next_sync_at(competitor)
    return due_at is None or (now or datetime.now(timezone.utc)) >= due_at


def staleness_label(
    last_synced_at: Optional[datetime], now: Optional[datetime] = None
) -> str:
    """How old the number on screen is, in words.

    Never "up to date": the freshest possible figure here is one lookup old,
    and the cap means the next one is days away.
    """
    last = _aware(last_synced_at)
    if last is None:
        return "not checked yet"
    delta = (now or datetime.now(timezone.utc)) - last
    hours = int(delta.total_seconds() // 3600)
    if hours < 1:
        return "as of just now"
    if hours < 24:
        return f"as of {hours}h ago"
    days = delta.days
    return "as of yesterday" if days == 1 else f"as of {days} days ago"


def capability_notice() -> dict[str, Any]:
    """What this feature does and does not do, for the add dialog."""
    return {
        "tracked": list(TRACKED),
        "not_tracked": list(NOT_TRACKED),
        "not_tracked_reason": NOT_TRACKED_REASON,
        "eligibility": ELIGIBILITY,
        "cadence": (
            f"Checked about once a week — Instagram caps Business Discovery at "
            f"roughly one lookup per account per {SYNC_INTERVAL_DAYS} days."
        ),
    }


# ---------------------------------------------------------------------------
# The connection every lookup goes through
# ---------------------------------------------------------------------------

async def discovery_connection(
    db: AsyncSession, account_id: uuid.UUID
) -> Optional[SocialAccount]:
    """An active connection whose platform can look another account up.

    Capability-gated rather than slug-matched, and it also requires the
    Instagram business id: Meta's Discovery call is made *as* that account, so
    a connection without one cannot ask at all.
    """
    connections = (
        await db.execute(
            select(SocialAccount)
            .options(selectinload(SocialAccount.platform))
            .where(
                SocialAccount.account_id == account_id,
                SocialAccount.is_active.is_(True),
            )
        )
    ).scalars().all()

    for connection in connections:
        slug = connection.platform.slug if connection.platform else None
        if not get_provider(slug).capabilities.supports_competitor_lookup:
            continue
        config = connection.config or {}
        if config.get("instagram_business_account_id") or config.get("page_id"):
            return connection
    return None


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

async def upsert_snapshot(
    db: AsyncSession,
    competitor_id: uuid.UUID,
    day: date_type,
    data: dict[str, Any],
) -> None:
    """Write one competitor-day, correcting it if it already exists.

    The same shape as ``analytics_sync.upsert_day``, and for the same reason: a
    second sync on one day must *correct* that day rather than add a second
    point, or a chart shows two different Tuesdays.

    Only fields Discovery actually returned are written, so a week where the
    account went private does not overwrite last week's follower count with
    NULL -- absence means "not reported this time", not "erase what we knew".
    """
    values = {
        key: data[key]
        for key in ("followers", "media_count")
        if data.get(key) is not None
    }
    if not values:
        # Nothing measurable came back. A row of NULLs would say "we looked and
        # they have nothing", which is not what happened; the competitor's
        # last_error carries what did.
        return

    if db.bind.dialect.name == "postgresql":
        statement = pg_insert(CompetitorSnapshot).values(
            id=uuid.uuid4(), competitor_id=competitor_id, date=day, **values
        )
        await db.execute(
            statement.on_conflict_do_update(
                constraint="uq_competitor_snapshot_day",
                set_={**values, "updated_at": datetime.now(timezone.utc)},
            )
        )
        return

    # SQLite (the test harness) has no matching ON CONFLICT construct through
    # the postgresql dialect helper. Same semantics, two statements.
    existing = (
        await db.execute(
            select(CompetitorSnapshot).where(
                CompetitorSnapshot.competitor_id == competitor_id,
                CompetitorSnapshot.date == day,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            CompetitorSnapshot(
                id=uuid.uuid4(), competitor_id=competitor_id, date=day, **values
            )
        )
        return
    for key, value in values.items():
        setattr(existing, key, value)
    existing.updated_at = datetime.now(timezone.utc)


async def lookup(connection: SocialAccount, handle: str) -> dict[str, Any]:
    """One Discovery call. Raises AccountNotFound for a handle nobody can see."""
    slug = connection.platform.slug if connection.platform else None
    provider = get_provider(slug)
    return await provider.lookup_account(connection, normalise_handle(handle))


async def sync_competitor(
    db: AsyncSession,
    competitor: CompetitorAccount,
    connection: SocialAccount,
    account: Account,
    *,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Take one snapshot. Never raises.

    A failure is recorded on the competitor row -- a chart that simply stops
    growing new points looks like an account that stopped changing, which is
    the same confusion between silence and breakage that the listening work
    exists to prevent.
    """
    moment = now or datetime.now(timezone.utc)
    report: dict[str, Any] = {
        "competitor_id": str(competitor.id), "stored": False, "error": None,
    }

    try:
        data = await lookup(connection, competitor.handle)
    except AccountNotFound as exc:
        # Kept, not deleted. The account may have gone private or been renamed,
        # and throwing away the history we did collect would be worse than
        # showing it with a reason attached.
        _record_failure(competitor, exc.detail[:500], moment)
        report["error"] = exc.detail
        return report
    except NotSupportedError:
        message = "This connection cannot look up other accounts."
        _record_failure(competitor, message, moment)
        report["error"] = message
        return report
    except PlatformRateLimited as exc:
        message = f"Instagram rate limited the lookup: {exc.detail}"[:500]
        _record_failure(competitor, message, moment)
        report["error"] = message
        return report
    except ProviderAPIError as exc:
        _record_failure(competitor, exc.detail[:500], moment)
        report["error"] = exc.detail
        return report
    except Exception as exc:  # noqa: BLE001 - one bad row must not end the sweep
        logger.exception("Competitor sync failed for %s", competitor.id)
        message = f"{type(exc).__name__}: {exc}"[:500]
        _record_failure(competitor, message, moment)
        report["error"] = message
        return report

    await upsert_snapshot(db, competitor.id, local_today(account, moment), data)
    if data.get("display_name"):
        competitor.display_name = data["display_name"]
    competitor.last_synced_at = moment
    competitor.last_error = None
    competitor.last_error_at = None
    report["stored"] = True
    await db.flush()
    return report


def _record_failure(
    competitor: CompetitorAccount, message: str, now: datetime
) -> None:
    """Mark it broken, and still move the clock.

    ``last_synced_at`` advances on a failure too: Meta's cap counts attempts,
    not successes, so retrying a failing handle every six hours would spend the
    week's allowance and get the whole workspace throttled.
    """
    competitor.last_error = message
    competitor.last_error_at = now
    competitor.last_synced_at = now


async def sync_all(db: AsyncSession, *, limit: int = 25) -> dict[str, int]:
    """One pass over every active competitor that is due."""
    competitors = (
        await db.execute(
            select(CompetitorAccount)
            .where(CompetitorAccount.is_active.is_(True))
            .order_by(CompetitorAccount.last_synced_at.asc().nulls_first())
            .limit(limit * 4)
        )
    ).scalars().all()

    totals = {"checked": 0, "stored": 0, "errors": 0}
    now = datetime.now(timezone.utc)
    accounts: dict[uuid.UUID, Optional[Account]] = {}
    connections: dict[uuid.UUID, Optional[SocialAccount]] = {}

    for competitor in competitors:
        if totals["checked"] >= limit:
            break
        if not is_due(competitor, now):
            continue

        if competitor.account_id not in accounts:
            accounts[competitor.account_id] = (
                await db.execute(
                    select(Account).where(Account.id == competitor.account_id)
                )
            ).scalar_one_or_none()
        account = accounts[competitor.account_id]
        if account is None:
            continue

        if competitor.account_id not in connections:
            connections[competitor.account_id] = await discovery_connection(
                db, competitor.account_id
            )
        connection = connections[competitor.account_id]
        if connection is None:
            # The Instagram connection was removed after the competitor was
            # added. Said on the row rather than left as a chart that quietly
            # stopped growing.
            _record_failure(
                competitor,
                "No Instagram business account is connected to this workspace, "
                "so this competitor cannot be checked. " + REQUIREMENT,
                now,
            )
            totals["errors"] += 1
            continue

        report = await sync_competitor(db, competitor, connection, account, now=now)
        totals["checked"] += 1
        if report["stored"]:
            totals["stored"] += 1
        if report["error"]:
            totals["errors"] += 1

    return totals


async def history(
    db: AsyncSession, competitor_id: uuid.UUID, *, limit: int = 90
) -> list[CompetitorSnapshot]:
    """Snapshots oldest first, which is the order a chart draws them in."""
    rows = (
        await db.execute(
            select(CompetitorSnapshot)
            .where(CompetitorSnapshot.competitor_id == competitor_id)
            .order_by(CompetitorSnapshot.date.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(reversed(rows))
