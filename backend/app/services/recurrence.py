"""Turning a recurrence rule into UTC instants, correctly across DST.

Everything here follows one rule: **recurrence arithmetic happens in naive
local time, and the result is converted to UTC exactly once, at the end.**

The tempting alternative -- keep ``next_run_at`` in UTC and add seven days to
it each week -- is correct until the first DST transition and wrong for the six
months after it. A 10:00 Monday post starts arriving at 09:00 or 11:00, which
is the kind of bug nobody reports as a bug; they just quietly conclude the
scheduler drifts.

Two local times need a policy, because they are not ordinary:

* **Nonexistent** (spring forward). At 02:00 the clock jumps to 03:00, so
  02:30 never happens. The policy is to publish at the first instant that does
  exist, 03:00 -- an hour late once a year. The alternative is skipping the
  occurrence, which means a weekly post silently disappears one week in the
  year, and silence is the worse failure.

* **Ambiguous** (fall back). 01:30 happens twice, an hour apart. The policy is
  the *first* one. Publishing at both would post the same content twice, which
  a reader sees and an operator has to clean up.

``zoneinfo`` implements both via ``fold``: ``fold=0`` selects the earlier
offset, which gives exactly these two answers. The code below relies on that
rather than reimplementing it, and detects the two cases only so they can be
reported.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rrulestr

logger = logging.getLogger(__name__)

# A rule that produces nothing within this horizon is treated as exhausted
# rather than searched forever. dateutil will happily iterate a rule with no
# matches (BYMONTHDAY=30 in February, say) until it finds one; without a bound,
# a malformed rule becomes an infinite loop inside the worker.
SEARCH_HORIZON_DAYS = 366 * 5


class InvalidRecurrence(ValueError):
    """The rule, timezone, or start is not usable."""


def zone(name: Optional[str]) -> ZoneInfo:
    """The workspace's zone, falling back to UTC rather than failing."""
    try:
        return ZoneInfo((name or "UTC").strip())
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("Unusable timezone %r on a schedule; using UTC.", name)
        return ZoneInfo("UTC")


# ---------------------------------------------------------------------------
# Local <-> UTC, with the DST cases named
# ---------------------------------------------------------------------------

def is_nonexistent(local: datetime, tz: ZoneInfo) -> bool:
    """True if this wall-clock reading never happens (spring-forward gap).

    Detected by round-tripping: attach the zone, go to UTC, come back. A time
    inside the gap comes back as a *different* wall-clock reading, because the
    instant it names is on the other side of the jump.
    """
    attached = local.replace(tzinfo=tz)
    roundtrip = attached.astimezone(timezone.utc).astimezone(tz)
    return roundtrip.replace(tzinfo=None) != local


def is_ambiguous(local: datetime, tz: ZoneInfo) -> bool:
    """True if this wall-clock reading happens twice (fall-back overlap).

    The two candidate instants differ only in ``fold``; if they have different
    UTC offsets, the reading is ambiguous.
    """
    first = local.replace(tzinfo=tz, fold=0)
    second = local.replace(tzinfo=tz, fold=1)
    return first.utcoffset() != second.utcoffset()


def to_utc(local: datetime, tz: ZoneInfo) -> datetime:
    """A naive local wall-clock reading as a UTC instant.

    ``fold=0`` is what implements both policies in the module docstring: for an
    ambiguous reading it picks the earlier of the two instants, and for a
    nonexistent one it yields the instant that renders as the shifted-forward
    time.
    """
    if local.tzinfo is not None:
        raise InvalidRecurrence("expected a naive local datetime")
    return local.replace(tzinfo=tz, fold=0).astimezone(timezone.utc)


def to_local(instant: datetime, tz: ZoneInfo) -> datetime:
    """A UTC instant as a naive local wall-clock reading."""
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(tz).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------

def parse(rule: str, *, dtstart_local: datetime):
    """Compile an RRULE against a naive local start.

    Naive on purpose. dateutil does support aware datetimes, but then every
    occurrence it yields carries a fixed offset taken from ``dtstart`` -- so a
    weekly rule started in winter produces winter offsets all summer. Keeping
    the whole computation naive and localising once at the end is what makes
    the wall-clock time stable.
    """
    if dtstart_local.tzinfo is not None:
        raise InvalidRecurrence("dtstart must be naive local time")
    text = (rule or "").strip()
    if not text:
        raise InvalidRecurrence("an empty recurrence rule matches nothing")
    if "UNTIL" in text.upper() and "Z" in text.upper():
        # A UTC UNTIL inside the rule would be compared against naive local
        # occurrences, which dateutil refuses. End conditions belong in the
        # model's own columns, where they are interpreted in the workspace's
        # zone like everything else.
        raise InvalidRecurrence(
            "put the end date in until_local rather than inside the RRULE"
        )
    try:
        return rrulestr(text, dtstart=dtstart_local)
    except (ValueError, TypeError) as exc:
        raise InvalidRecurrence(f"unusable recurrence rule: {exc}") from exc


def next_occurrence(
    rule: str,
    *,
    timezone_name: str,
    dtstart_local: datetime,
    after: Optional[datetime] = None,
    until_local: Optional[datetime] = None,
    inclusive: bool = False,
) -> Optional[datetime]:
    """The next UTC instant this rule fires, strictly after ``after``.

    ``after`` is a UTC instant; it is converted into local wall-clock terms to
    ask the rule, and the answer is converted back. Both conversions are needed
    -- the rule speaks wall clock, the worker speaks UTC.
    """
    tz = zone(timezone_name)
    reference = after or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    rules = parse(rule, dtstart_local=dtstart_local)
    horizon = reference + timedelta(days=SEARCH_HORIZON_DAYS)
    cursor_local = to_local(reference, tz)

    # A loop rather than a single .after(): around fall-back, two distinct UTC
    # instants share one local reading, so the first candidate the rule offers
    # can convert to an instant at or before the one we already ran. Advancing
    # until the UTC value genuinely moves forward is what stops an occurrence
    # firing twice in the repeated hour.
    for _ in range(64):
        candidate_local = rules.after(cursor_local, inc=inclusive)
        if candidate_local is None:
            return None
        if until_local is not None and candidate_local > until_local:
            return None

        candidate_utc = to_utc(candidate_local, tz)
        if candidate_utc > reference or (inclusive and candidate_utc == reference):
            if candidate_utc > horizon:
                return None
            if is_nonexistent(candidate_local, tz):
                logger.info(
                    "Occurrence %s does not exist in %s (spring-forward gap); "
                    "publishing at %s instead.",
                    candidate_local, tz.key, to_local(candidate_utc, tz),
                )
            elif is_ambiguous(candidate_local, tz):
                logger.info(
                    "Occurrence %s happens twice in %s (fall-back overlap); "
                    "taking the first.", candidate_local, tz.key,
                )
            return candidate_utc

        # Candidate landed at or before the reference instant. Step the local
        # cursor past it and ask again.
        cursor_local = candidate_local
        inclusive = False

    logger.warning(
        "Gave up finding an occurrence after %s for rule %r in %s",
        reference, rule, timezone_name,
    )
    return None


def occurrences(
    rule: str,
    *,
    timezone_name: str,
    dtstart_local: datetime,
    after: Optional[datetime] = None,
    until_local: Optional[datetime] = None,
    limit: int = 10,
) -> list[datetime]:
    """The next ``limit`` UTC instants. Used for previewing a rule in the UI.

    A preview matters more than it looks: an RRULE is not readable, and the
    only honest way to show someone what "FREQ=MONTHLY;BYDAY=-1FR" does is to
    list the dates it produces.
    """
    found: list[datetime] = []
    cursor = after or datetime.now(timezone.utc)
    for _ in range(limit):
        nxt = next_occurrence(
            rule,
            timezone_name=timezone_name,
            dtstart_local=dtstart_local,
            after=cursor,
            until_local=until_local,
        )
        if nxt is None:
            break
        found.append(nxt)
        cursor = nxt
    return found


def describe(rule: str) -> str:
    """A short human reading of common rules, for lists and audit lines."""
    text = (rule or "").upper()
    days = {
        "MO": "Mon", "TU": "Tue", "WE": "Wed", "TH": "Thu",
        "FR": "Fri", "SA": "Sat", "SU": "Sun",
    }
    freq = "custom"
    for name in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
        if f"FREQ={name}" in text:
            freq = name.lower()
            break
    chosen = [label for code, label in days.items() if f"BYDAY={code}" in text
              or f",{code}" in text or f"BYDAY={code}," in text]
    return f"{freq} on {', '.join(chosen)}" if chosen else freq
