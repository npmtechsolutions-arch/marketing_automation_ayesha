"""Where the calendar is empty, and against what.

"Empty" only means something relative to an expectation, so this compares the
range against the two expectations the workspace has already expressed:

* **its queue slots** -- "we post Mon/Wed/Fri at 10:00" is a commitment, and a
  Wednesday with nothing in it is a gap the workspace itself defined;
* **its best posting times** -- observed from its own history where there is
  enough of it, and platform defaults where there is not.

Those are different strengths of claim and they stay labelled all the way out,
the same `observed` / `default` vocabulary :mod:`app.services.best_times` uses.
A queue gap is a missed commitment; a default-time gap is a suggestion from a
convention. Presenting them identically would make the second sound like the
first.

**Everything here is computed on the workspace's clock**, and occupancy is
compared as UTC *instants*. Both matter and for different reasons: a day
boundary in the viewer's timezone puts a gap on the wrong date, and during the
fall-back hour two different instants render as the same wall-clock reading, so
comparing local strings would call a genuinely free slot taken.
"""

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.platform import SocialAccount, SocialPlatform
from app.models.post import Post, PostStatus
from app.models.recurring_schedule import QueueSlot
from app.services import best_times
from app.services.dashboard import workspace_timezone
from app.services.recurrence import to_utc

logger = logging.getLogger(__name__)

# A post in one of these occupies its slot. A draft does not: it is not on the
# calendar, which is the whole reason a gap analysis is useful.
OCCUPYING_STATUSES = (
    PostStatus.SCHEDULED,
    PostStatus.PUBLISHING,
    PostStatus.PUBLISHED,
    PostStatus.PARTIALLY_PUBLISHED,
)

# A connected platform with nothing published or scheduled for this long is
# worth flagging. Two weeks is long enough not to nag over a quiet week and
# short enough that an account nobody noticed going silent still gets caught.
STALE_AFTER_DAYS = 14

# A range longer than this is refused rather than served slowly.
MAX_RANGE_DAYS = 92


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def _scheduled_posts(
    db: AsyncSession, account_id, *, since: datetime, until: datetime
) -> list[Post]:
    """Posts occupying calendar time in the window.

    Selected on ``scheduled_at`` OR ``published_at`` so a post that went out
    without ever being scheduled still counts as filling its day -- otherwise a
    workspace that publishes immediately would look permanently empty.
    """
    return list(
        (
            await db.execute(
                select(Post).where(
                    Post.account_id == account_id,
                    Post.deleted_at.is_(None),
                    Post.status.in_(OCCUPYING_STATUSES),
                    (
                        Post.scheduled_at.between(since, until)
                        | Post.published_at.between(since, until)
                    ),
                )
            )
        ).scalars().all()
    )


def _occupied_instants(posts: list[Post]) -> set[datetime]:
    instants = set()
    for post in posts:
        for value in (post.scheduled_at, post.published_at):
            aware = _as_utc(value)
            if aware is not None:
                instants.add(aware)
    return instants


def _occupied_days(posts: list[Post], tz) -> set[date]:
    """Which local days already have something on them."""
    days = set()
    for post in posts:
        for value in (post.scheduled_at, post.published_at):
            aware = _as_utc(value)
            if aware is not None:
                days.add(aware.astimezone(tz).date())
    return days


async def _queue_gaps(
    db: AsyncSession,
    account: Account,
    tz,
    start: date,
    end: date,
    occupied: set[datetime],
    now: datetime,
) -> list[dict[str, Any]]:
    """Queue slots in the range with nothing in them.

    The strongest kind of gap: the workspace said it posts at this time.
    """
    slots = (
        await db.execute(
            select(QueueSlot).where(
                QueueSlot.account_id == account.id,
                QueueSlot.is_active.is_(True),
            )
        )
    ).scalars().all()
    if not slots:
        return []

    by_weekday: dict[int, list[QueueSlot]] = {}
    for slot in slots:
        by_weekday.setdefault(slot.weekday, []).append(slot)

    gaps = []
    day = start
    while day <= end:
        for slot in sorted(by_weekday.get(day.weekday(), []), key=lambda s: s.time_local):
            local = datetime.combine(day, slot.time_local)
            instant = to_utc(local, tz)
            # A slot that has already passed is history, not a gap to fill.
            if instant <= now or instant in occupied:
                continue
            gaps.append({
                "local_datetime": local.isoformat(),
                "run_at": instant.isoformat(),
                "weekday": day.weekday(),
                "hour": slot.time_local.hour,
                "kind": "queue_slot",
                # A commitment the workspace made, not a suggestion.
                "slot_source": "queue",
                "platform": None,
                "social_account_id": None,
                "reason": (
                    f"This workspace's queue posts at "
                    f"{slot.time_local.isoformat(timespec='minutes')} on "
                    f"{best_times.WEEKDAYS[day.weekday()]}s, and this one is empty."
                ),
            })
        day += timedelta(days=1)
    return gaps


async def _best_time_gaps(
    db: AsyncSession,
    account: Account,
    tz,
    start: date,
    end: date,
    connections: list[tuple[SocialAccount, SocialPlatform]],
    settled_days: set[date],
    now: datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Best-time slots on days with nothing at all on them.

    Deliberately per *day* rather than per instant: proposing a second post two
    hours after a scheduled one because a heatmap cell is empty is noise. The
    question this answers is "you have nothing on Thursday and Thursday 18:00
    is when your audience is there".

    ``settled_days`` covers both ways a day can already be spoken for: a post
    on it, or a queue slot the workspace committed to. The second was missed at
    first, so an empty Wednesday with a 10:00 queue slot also collected
    suggestions at 12:00 and 13:00 -- one empty day, three rows. A commitment
    settles a day exactly as a scheduled post does, and the stronger claim
    should not be diluted by two weaker ones beside it.
    """
    gaps: list[dict[str, Any]] = []
    sources: dict[str, Any] = {}

    for social, platform in connections:
        slug = (platform.slug or "").lower()
        if slug in sources:
            continue
        try:
            analysis = await best_times.analyse(db, account, social_account_id=social.id)
        except Exception:  # noqa: BLE001 - one bad connection is not a failed report
            logger.exception("Best-time analysis failed for %s", slug)
            continue
        sources[slug] = {
            "source": analysis["source"],
            "explanation": analysis["explanation"],
            "sample_posts": analysis["sample"]["posts"],
        }
        suggestions = analysis["suggestions"][:3]

        day = start
        while day <= end:
            if day in settled_days:
                day += timedelta(days=1)
                continue
            for suggestion in suggestions:
                if suggestion["weekday"] != day.weekday():
                    continue
                local = datetime.combine(day, time(hour=int(suggestion["hour"])))
                instant = to_utc(local, tz)
                if instant <= now:
                    continue
                observed = bool(suggestion["observed"])
                gaps.append({
                    "local_datetime": local.isoformat(),
                    "run_at": instant.isoformat(),
                    "weekday": day.weekday(),
                    "hour": int(suggestion["hour"]),
                    "kind": "best_time",
                    # observed | default -- and they are not the same claim.
                    "slot_source": "observed" if observed else "default",
                    "platform": slug,
                    "social_account_id": str(social.id),
                    "account_name": social.account_name,
                    "reason": (
                        f"Nothing is scheduled on "
                        f"{best_times.WEEKDAYS[day.weekday()]} "
                        f"{day.isoformat()}, and "
                        + (
                            f"{best_times.WEEKDAYS[day.weekday()]} "
                            f"{int(suggestion['hour']):02d}:00 is an observed "
                            f"best slot for {social.account_name}."
                            if observed
                            else f"{int(suggestion['hour']):02d}:00 is a usual "
                                 f"{slug} posting time. {analysis['explanation']}"
                        )
                    ),
                })
            day += timedelta(days=1)
    return gaps, sources


async def _stale_platforms(
    db: AsyncSession,
    account_id,
    connections: list[tuple[SocialAccount, SocialPlatform]],
    now: datetime,
) -> list[dict[str, Any]]:
    """Connected accounts with nothing recent and nothing coming.

    Attribution is done in Python rather than in SQL. ``target_accounts`` is a
    JSON column, and querying inside one is dialect-specific -- the last time
    this project reached into JSON from SQL, it worked on SQLite and raised
    UndefinedFunctionError on Postgres.
    """
    since = now - timedelta(days=STALE_AFTER_DAYS)
    posts = list(
        (
            await db.execute(
                select(Post).where(
                    Post.account_id == account_id,
                    Post.deleted_at.is_(None),
                    Post.status.in_(OCCUPYING_STATUSES),
                    (
                        (Post.scheduled_at.is_not(None) & (Post.scheduled_at >= since))
                        | (Post.published_at.is_not(None) & (Post.published_at >= since))
                    ),
                )
            )
        ).scalars().all()
    )

    latest: dict[str, datetime] = {}
    for post in posts:
        stamps = [s for s in (_as_utc(post.scheduled_at), _as_utc(post.published_at)) if s]
        if not stamps:
            continue
        newest = max(stamps)
        for target in (post.target_accounts or []):
            target_id = str(
                target.get("social_account_id") or target.get("id") or ""
            ) if isinstance(target, dict) else str(target)
            if not target_id:
                continue
            if target_id not in latest or newest > latest[target_id]:
                latest[target_id] = newest

    stale = []
    for social, platform in connections:
        key = str(social.id)
        seen = latest.get(key)
        if seen is not None:
            continue
        stale.append({
            "social_account_id": key,
            "account_name": social.account_name,
            "platform": (platform.slug or "").lower(),
            "days": STALE_AFTER_DAYS,
            "reason": (
                f"{social.account_name} is connected but has nothing published "
                f"or scheduled in the last {STALE_AFTER_DAYS} days."
            ),
        })
    return stale


async def analyse(
    db: AsyncSession,
    account: Account,
    start: date,
    end: date,
    *,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """The gap picture for a range, on the workspace's clock."""
    if end < start:
        raise ValueError("The end of the range cannot be before its start.")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise ValueError(
            f"That range is longer than {MAX_RANGE_DAYS} days. Ask for less."
        )

    tz = workspace_timezone(account)
    now = _as_utc(now) or datetime.now(timezone.utc)

    window_start = to_utc(datetime.combine(start, time.min), tz)
    window_end = to_utc(datetime.combine(end + timedelta(days=1), time.min), tz)

    posts = await _scheduled_posts(
        db, account.id, since=window_start, until=window_end
    )
    occupied = _occupied_instants(posts)
    occupied_days = _occupied_days(posts, tz)

    connections = [
        (social, platform)
        for social, platform in (
            await db.execute(
                select(SocialAccount, SocialPlatform)
                .join(SocialPlatform, SocialPlatform.id == SocialAccount.platform_id)
                .where(SocialAccount.account_id == account.id)
                .order_by(SocialPlatform.slug)
            )
        ).all()
    ]

    queue_gaps = await _queue_gaps(
        db, account, tz, start, end, occupied, now
    )
    # A day is settled if something is on it *or* the queue already claims it.
    settled_days = occupied_days | {
        datetime.fromisoformat(gap["local_datetime"]).date() for gap in queue_gaps
    }
    best_gaps, slot_sources = await _best_time_gaps(
        db, account, tz, start, end, connections, settled_days, now
    )
    gaps = sorted(queue_gaps + best_gaps, key=lambda g: g["local_datetime"])

    total_days = (end - start).days + 1
    return {
        "window": {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "timezone": tz.key,
            "days": total_days,
        },
        "summary": {
            "scheduled_posts": len(posts),
            "days_with_nothing": total_days - len(
                {d for d in occupied_days if start <= d <= end}
            ),
            "queue_gaps": len(queue_gaps),
            "best_time_gaps": len(best_gaps),
        },
        # Per platform: whether its timing advice is observed or conventional.
        "slot_sources": slot_sources,
        "gaps": gaps,
        "stale_platforms": await _stale_platforms(db, account.id, connections, now),
    }
