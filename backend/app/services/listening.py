"""Social listening: polling saved searches, and saying what the window is.

Everything here is shaped by one finding from the 2026-09-10 tier audit: X's
pay-per-use tier includes **recent search only, seven days back**, and bills
**per post read**. Two rules follow, and both are load-bearing rather than
stylistic.

**The window is part of every answer.** "No mentions" and "no mentions in the
last 7 days" are different claims, and only the second one is true. The label
is produced here, from the provider's own ``search_window_days``, so no
component can quietly render the friendlier version.

**A failed poll is never silence.** A search that could not run records the
reason on the query, and the query reads as broken. An empty stream from a
credential with no funding behind it would otherwise be indistinguishable from
a genuinely quiet week -- which is the shape of the fabrication this codebase
removed from the metrics connectors, arriving by a different road.

Polling costs money, so the interval is a workspace setting rather than a
constant, every poll's reads are counted onto the query, and a poll asks only
for what is new (``since_id``) rather than re-reading the window each time.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connectors.base import (
    NotSupportedError,
    PlatformRateLimited,
    ProviderAPIError,
)
from app.connectors.registry import get_provider
from app.models.account import Account
from app.models.listening import ListeningQuery, Mention
from app.models.platform import SocialAccount

logger = logging.getLogger(__name__)

# The only platform whose API can feed this. Meta has no public search on any
# tier -- no hashtag streams, no competitor timelines -- so a second entry here
# would be a genuine platform change, not a configuration one.
PLATFORM = "twitter"

# How often the worker *considers* polling. Whether a given query is due is
# decided per workspace from its own interval, because each poll spends money.
CHECK_INTERVAL_SECONDS = 15 * 60

# The workspace setting, and what it may be. A free-form number would let
# someone type 1 and quietly multiply their bill by six.
SETTINGS_KEY = "listening_interval_hours"
DEFAULT_INTERVAL_HOURS = 6
ALLOWED_INTERVALS = (1, 3, 6, 12, 24)

# Posts asked for per poll. X allows 10-100; this is deliberately near the
# floor because it is the multiplier on the bill -- at $0.005 a read, 25 posts
# four times a day is about $15 a month for one query, and 100 would be $60.
MAX_RESULTS_PER_POLL = 25

# The floor between two *manual* polls of one query. The scheduled sweep has
# the workspace's interval to hold it back; the button has nothing, and a
# button that spends money on every press needs something. Deliberately short:
# it exists to stop a leaning finger and a page that re-polls on focus, not to
# make someone wait for a legitimate second look.
MANUAL_POLL_MIN_SECONDS = 60


def manual_poll_allowed_in(query: ListeningQuery, now: Optional[datetime] = None) -> int:
    """Seconds until this query may be polled by hand again. 0 means now."""
    last = _aware(query.last_polled_at)
    if last is None:
        return 0
    elapsed = ((now or datetime.now(timezone.utc)) - last).total_seconds()
    return max(0, int(MANUAL_POLL_MIN_SECONDS - elapsed))


# Pay-per-use, "read someone else's post". Recorded as a constant with its
# source so the arithmetic shown to a user can be checked rather than trusted;
# docs/API-TIER-AUDIT.md carries the table and the date it was read.
READ_COST_USD = 0.005
COST_SOURCE = "X pay-per-use, $0.005 per post read (audited 2026-09-10)"


# ---------------------------------------------------------------------------
# The window, which every surface has to state
# ---------------------------------------------------------------------------

def window_days(platform: str = PLATFORM) -> Optional[int]:
    """How far back this platform's search reaches, from the connector."""
    return get_provider(platform).capabilities.search_window_days


def window_label(platform: str = PLATFORM) -> str:
    """The phrase every empty state and header uses.

    Built here rather than typed into a component so there is one place that
    can be wrong, and so a tier change moves every surface at once.
    """
    days = window_days(platform)
    if not days:
        return "this platform's search window"
    return f"the last {days} days" if days != 1 else "the last day"


def window_start(now: Optional[datetime] = None, platform: str = PLATFORM) -> Optional[datetime]:
    days = window_days(platform)
    if not days:
        return None
    return (now or datetime.now(timezone.utc)) - timedelta(days=days)


def estimated_cost_usd(posts_read: int) -> float:
    """What a number of reads cost, to the cent that matters."""
    return round((posts_read or 0) * READ_COST_USD, 4)


# ---------------------------------------------------------------------------
# The workspace's polling interval
# ---------------------------------------------------------------------------

def interval_hours(account: Account) -> int:
    """This workspace's poll interval, defaulted and bounded."""
    raw = (account.settings or {}).get(SETTINGS_KEY)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_HOURS
    return value if value in ALLOWED_INTERVALS else DEFAULT_INTERVAL_HOURS


def validate_interval(raw: Any) -> int:
    """Validate the setting on the way in.

    Refused rather than clamped: someone who asks for hourly polling and is
    silently given six-hourly will read the stream as broken. The settings
    writer's own rule -- accept-and-drop is the failure mode to avoid.
    """
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(
            f"settings.{SETTINGS_KEY} must be a number of hours "
            f"({', '.join(str(v) for v in ALLOWED_INTERVALS)})"
        )
    if value not in ALLOWED_INTERVALS:
        raise ValueError(
            f"settings.{SETTINGS_KEY} must be one of "
            f"{', '.join(str(v) for v in ALLOWED_INTERVALS)}. Each poll costs "
            "money, so the interval is a fixed set rather than free-form."
        )
    return value


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite hands back naive datetimes; Postgres does not."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def next_poll_at(query: ListeningQuery, hours: int) -> Optional[datetime]:
    """When this query may next be polled, or None if it never has been."""
    last = _aware(query.last_polled_at)
    return None if last is None else last + timedelta(hours=hours)


def is_due(query: ListeningQuery, hours: int, now: Optional[datetime] = None) -> bool:
    if not query.is_active:
        return False
    due_at = next_poll_at(query, hours)
    return due_at is None or (now or datetime.now(timezone.utc)) >= due_at


# ---------------------------------------------------------------------------
# The connection a query polls through
# ---------------------------------------------------------------------------

async def search_connection(
    db: AsyncSession, account_id: uuid.UUID
) -> Optional[SocialAccount]:
    """An active connection whose platform can actually search.

    Capability-gated rather than slug-matched: the question is not "is this X"
    but "can this connector search", which is what the UI needs to explain why
    the feature is idle.
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
        if get_provider(slug).capabilities.supports_recent_search:
            return connection
    return None


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------

def _newer_cursor(current: Optional[str], candidate: Optional[str]) -> Optional[str]:
    """The later of two platform ids. Forward only.

    X ids are numeric strings that increase with time. A poll that returned an
    older page must not drag the marker back -- doing so would re-read, and
    re-pay for, everything between.
    """
    if not candidate:
        return current
    if not current:
        return candidate
    try:
        return candidate if int(candidate) > int(current) else current
    except (TypeError, ValueError):
        # A platform that stops using numeric ids should not silently reorder
        # the marker; keeping what we have is the safe direction.
        return current


async def _store(
    db: AsyncSession, query: ListeningQuery, items: list[dict[str, Any]]
) -> int:
    """Insert what is new. Returns how many rows were genuinely created.

    Existing rows are left exactly as they are. A platform can re-serve the
    same post with a different rendering of the author's display name, and
    rewriting it on every poll would churn the row and make "is this new"
    unanswerable -- the inbox's rule, and the reason a re-poll is free of
    visible effect.
    """
    externals = [str(item["external_id"]) for item in items if item.get("external_id")]
    if not externals:
        return 0

    known = set(
        (
            await db.execute(
                select(Mention.external_id).where(
                    Mention.listening_query_id == query.id,
                    Mention.external_id.in_(externals),
                )
            )
        ).scalars().all()
    )

    created = 0
    for item in items:
        external = str(item.get("external_id") or "")
        # No external id means no way to recognise it next time, so storing it
        # would guarantee a duplicate on the next poll. Skipped, as in 2.5.
        if not external or external in known:
            continue
        known.add(external)
        posted = item.get("created_at")
        if isinstance(posted, datetime) and posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        db.add(
            Mention(
                id=uuid.uuid4(),
                listening_query_id=query.id,
                external_id=external,
                author_handle=item.get("author_handle"),
                author_name=item.get("author"),
                text=item.get("body") or "",
                posted_at=posted if isinstance(posted, datetime) else None,
                url=item.get("permalink"),
            )
        )
        created += 1
        query.last_result_cursor = _newer_cursor(query.last_result_cursor, external)

    await db.flush()
    return created


async def poll_query(
    db: AsyncSession,
    query: ListeningQuery,
    connection: SocialAccount,
    *,
    max_results: int = MAX_RESULTS_PER_POLL,
) -> dict[str, Any]:
    """Run one search and store what is new.

    Never raises. A failure is recorded **on the query**, which is the whole
    point: the reader has to be able to tell "nobody mentioned you" from "this
    search has not run since Tuesday".
    """
    slug = connection.platform.slug if connection.platform else None
    provider = get_provider(slug)
    now = datetime.now(timezone.utc)
    report: dict[str, Any] = {
        "query_id": str(query.id), "new": 0, "posts_read": 0,
        "requests": 0, "error": None,
    }

    try:
        result = await provider.search_recent(
            connection, query.query_text,
            since_id=query.last_result_cursor, max_results=max_results,
        )
    except NotSupportedError:
        # The capability said yes and the provider said no. A fact about the
        # connection, not a fault -- but still not silence.
        message = (
            f"{provider.name} cannot run this search on the connected account."
        )
        _record_failure(query, message, now)
        report["error"] = message
        return report
    except PlatformRateLimited as exc:
        message = f"X rate limited the search: {exc.detail}"[:500]
        _record_failure(query, message, now)
        report["error"] = message
        return report
    except ProviderAPIError as exc:
        _record_failure(query, exc.detail[:500], now)
        report["error"] = exc.detail
        return report
    except Exception as exc:  # noqa: BLE001 - a poll must not kill the sweep
        logger.exception("Listening poll failed for query %s", query.id)
        message = f"{type(exc).__name__}: {exc}"[:500]
        _record_failure(query, message, now)
        report["error"] = message
        return report

    items = result.get("items") or []
    report["requests"] = int(result.get("requests") or 0)
    report["posts_read"] = int(result.get("posts_read") or len(items))
    report["new"] = await _store(db, query, items)

    query.requests_made = (query.requests_made or 0) + report["requests"]
    query.posts_read = (query.posts_read or 0) + report["posts_read"]
    query.last_polled_at = now
    query.last_success_at = now
    query.last_error = None
    query.last_error_at = None
    await db.flush()
    return report


def _record_failure(query: ListeningQuery, message: str, now: datetime) -> None:
    """Mark the query broken, and still move the clock.

    ``last_polled_at`` advances on a failure too. Without that, a query whose
    credential has expired would retry on every single sweep -- which on a
    metered API is how a broken integration becomes an expensive one.
    """
    query.last_error = message
    query.last_error_at = now
    query.last_polled_at = now


async def sync_all(db: AsyncSession, *, limit: int = 25) -> dict[str, int]:
    """One pass over every active query that is due.

    Ordered by how long each has waited, and capped, so a workspace with forty
    queries cannot starve everyone else's -- and so one pass cannot spend an
    unbounded amount of money.
    """
    queries = (
        await db.execute(
            select(ListeningQuery)
            .where(ListeningQuery.is_active.is_(True))
            .order_by(ListeningQuery.last_polled_at.asc().nulls_first())
            .limit(limit * 4)
        )
    ).scalars().all()

    totals = {"polled": 0, "new": 0, "posts_read": 0, "errors": 0}
    now = datetime.now(timezone.utc)
    connections: dict[uuid.UUID, Optional[SocialAccount]] = {}
    intervals: dict[uuid.UUID, int] = {}

    for query in queries:
        if totals["polled"] >= limit:
            break

        if query.account_id not in intervals:
            account = (
                await db.execute(
                    select(Account).where(Account.id == query.account_id)
                )
            ).scalar_one_or_none()
            intervals[query.account_id] = (
                interval_hours(account) if account else DEFAULT_INTERVAL_HOURS
            )
        if not is_due(query, intervals[query.account_id], now):
            continue

        if query.account_id not in connections:
            connections[query.account_id] = await search_connection(
                db, query.account_id
            )
        connection = connections[query.account_id]
        if connection is None:
            # The connection was removed after the query was created. Recorded
            # on the query rather than skipped silently, or the stream just
            # stops with no explanation.
            _record_failure(
                query,
                "No X account is connected to this workspace, so this search "
                "cannot run. Reconnect X to resume listening.",
                now,
            )
            totals["errors"] += 1
            continue

        report = await poll_query(db, query, connection)
        totals["polled"] += 1
        totals["new"] += report["new"]
        totals["posts_read"] += report["posts_read"]
        if report["error"]:
            totals["errors"] += 1

    return totals
