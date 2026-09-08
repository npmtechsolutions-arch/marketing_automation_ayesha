"""Recurrence and queue slots across daylight-saving transitions.

This file is mostly about one class of bug. A schedule that stores "every
Monday at 10:00" as a UTC instant plus a 604800-second interval is correct
until the clocks change and then publishes at 09:00 or 11:00 for the next six
months. Nobody reports that as a bug; they conclude the product drifts.

So: wall-clock stability is asserted directly, in both directions, in both
hemispheres, and at the two local times that are not ordinary -- the hour that
does not exist and the hour that happens twice.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.services import recurrence

pytestmark = pytest.mark.asyncio

NY = "America/New_York"          # spring forward 2026-03-08, back 2026-11-01
BERLIN = "Europe/Berlin"         # forward 2026-03-29, back 2026-10-25
SYDNEY = "Australia/Sydney"      # southern hemisphere: back 2026-04-05, forward 2026-10-04
PHOENIX = "America/Phoenix"      # no DST at all


def _local(instant, tz_name):
    return recurrence.to_local(instant, ZoneInfo(tz_name))


# ---------------------------------------------------------------------------
# The core promise: the wall clock does not move
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "tz_name, start, hour",
    [
        # Northern spring forward.
        (NY, datetime(2026, 2, 23, 10, 0), 10),
        # Northern autumn back.
        (NY, datetime(2026, 10, 19, 10, 0), 10),
        (BERLIN, datetime(2026, 3, 16, 9, 30), 9),
        # Southern hemisphere, where the transitions run the other way.
        (SYDNEY, datetime(2026, 3, 23, 14, 0), 14),
        (SYDNEY, datetime(2026, 9, 21, 14, 0), 14),
        # A zone with no DST, as the control.
        (PHOENIX, datetime(2026, 3, 2, 8, 0), 8),
    ],
)
async def test_weekly_time_survives_the_transition(tz_name, start, hour):
    """Eight consecutive weekly occurrences all land on the same wall clock."""
    cursor = recurrence.to_utc(start - timedelta(days=1), ZoneInfo(tz_name))
    seen = []
    for _ in range(8):
        nxt = recurrence.next_occurrence(
            "FREQ=WEEKLY", timezone_name=tz_name, dtstart_local=start, after=cursor
        )
        assert nxt is not None
        seen.append(_local(nxt, tz_name))
        cursor = nxt

    assert {moment.hour for moment in seen} == {hour}, (
        f"the posting hour drifted across a DST boundary: "
        f"{sorted({m.hour for m in seen})}"
    )
    assert {moment.minute for moment in seen} == {start.minute}


async def test_the_utc_instant_does_move():
    """The other half of the same promise.

    Holding the wall clock steady *requires* the UTC instant to shift by an
    hour. A test that only checked local time would also pass against a
    fixed-offset implementation that had frozen the whole zone.
    """
    start = datetime(2026, 2, 23, 10, 0)
    before = recurrence.next_occurrence(
        "FREQ=WEEKLY", timezone_name=NY, dtstart_local=start,
        after=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    after = recurrence.next_occurrence(
        "FREQ=WEEKLY", timezone_name=NY, dtstart_local=start,
        after=datetime(2026, 3, 8, 12, tzinfo=timezone.utc),
    )

    assert before.hour == 15, "EST: 10:00 New York is 15:00 UTC"
    assert after.hour == 14, "EDT: 10:00 New York is 14:00 UTC"


# ---------------------------------------------------------------------------
# The hour that does not exist
# ---------------------------------------------------------------------------

async def test_a_nonexistent_local_time_is_detected():
    assert recurrence.is_nonexistent(datetime(2026, 3, 8, 2, 30), ZoneInfo(NY))
    assert not recurrence.is_nonexistent(datetime(2026, 3, 9, 2, 30), ZoneInfo(NY))


async def test_a_nonexistent_occurrence_shifts_forward_rather_than_vanishing():
    """02:30 does not happen on the spring-forward date.

    The occurrence publishes at 03:30 instead. Skipping it would mean a daily
    post silently missing one day a year, and silence is the worse failure --
    an hour late is visible and explicable, a missing post is neither.
    """
    start = datetime(2026, 3, 6, 2, 30)
    nxt = recurrence.next_occurrence(
        "FREQ=DAILY", timezone_name=NY, dtstart_local=start,
        after=datetime(2026, 3, 7, 12, tzinfo=timezone.utc),
    )

    local = _local(nxt, NY)
    assert local.date() == datetime(2026, 3, 8).date(), "the occurrence was skipped"
    assert (local.hour, local.minute) == (3, 30)


async def test_the_day_after_a_shift_returns_to_the_configured_time():
    """The shift applies to the one impossible occurrence, not to the rest."""
    start = datetime(2026, 3, 6, 2, 30)
    cursor = datetime(2026, 3, 7, 12, tzinfo=timezone.utc)
    times = []
    for _ in range(3):
        nxt = recurrence.next_occurrence(
            "FREQ=DAILY", timezone_name=NY, dtstart_local=start, after=cursor
        )
        times.append(_local(nxt, NY))
        cursor = nxt

    assert [(t.hour, t.minute) for t in times] == [(3, 30), (2, 30), (2, 30)]


# ---------------------------------------------------------------------------
# The hour that happens twice
# ---------------------------------------------------------------------------

async def test_an_ambiguous_local_time_is_detected():
    assert recurrence.is_ambiguous(datetime(2026, 11, 1, 1, 30), ZoneInfo(NY))
    assert not recurrence.is_ambiguous(datetime(2026, 11, 2, 1, 30), ZoneInfo(NY))


async def test_a_doubled_hour_publishes_once_not_twice():
    """01:30 occurs twice on the fall-back date, an hour apart.

    Publishing at both would put the same content on the customer's feed
    twice, which their audience sees.
    """
    start = datetime(2026, 10, 30, 1, 30)
    cursor = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
    instants = []
    for _ in range(3):
        nxt = recurrence.next_occurrence(
            "FREQ=DAILY", timezone_name=NY, dtstart_local=start, after=cursor
        )
        instants.append(nxt)
        cursor = nxt

    local_dates = [_local(i, NY).date() for i in instants]
    assert len(set(local_dates)) == 3, "the repeated hour fired twice on one day"
    # And it took the earlier of the two instants: EDT, offset -04:00.
    fallback_day = instants[0]
    assert fallback_day.astimezone(ZoneInfo(NY)).utcoffset() == timedelta(hours=-4)


async def test_an_occurrence_inside_the_repeated_hour_never_goes_backwards():
    """Asking for the next occurrence after an instant in the repeated hour
    must move forward in UTC, not return the same local reading again."""
    start = datetime(2026, 10, 30, 1, 30)
    first = recurrence.next_occurrence(
        "FREQ=DAILY", timezone_name=NY, dtstart_local=start,
        after=datetime(2026, 10, 31, 12, tzinfo=timezone.utc),
    )
    second = recurrence.next_occurrence(
        "FREQ=DAILY", timezone_name=NY, dtstart_local=start, after=first
    )

    assert second > first
    assert (second - first) >= timedelta(hours=23)


# ---------------------------------------------------------------------------
# Rules, ends and refusals
# ---------------------------------------------------------------------------

async def test_byday_rules_pick_the_right_days():
    start = datetime(2026, 6, 1, 10, 0)          # a Monday
    instants = recurrence.occurrences(
        "FREQ=WEEKLY;BYDAY=MO,WE,FR", timezone_name=NY,
        dtstart_local=start,
        after=datetime(2026, 5, 31, tzinfo=timezone.utc), limit=6,
    )
    weekdays = [_local(i, NY).weekday() for i in instants]
    assert weekdays == [0, 2, 4, 0, 2, 4]


async def test_until_stops_the_series():
    start = datetime(2026, 6, 1, 10, 0)
    instants = recurrence.occurrences(
        "FREQ=DAILY", timezone_name=NY, dtstart_local=start,
        after=datetime(2026, 5, 31, tzinfo=timezone.utc),
        until_local=datetime(2026, 6, 4, 23, 59), limit=10,
    )
    assert len(instants) == 4


async def test_an_unparseable_rule_is_refused():
    with pytest.raises(recurrence.InvalidRecurrence):
        recurrence.parse("FREQ=NEVER", dtstart_local=datetime(2026, 6, 1, 10, 0))


async def test_an_empty_rule_is_refused():
    with pytest.raises(recurrence.InvalidRecurrence):
        recurrence.parse("   ", dtstart_local=datetime(2026, 6, 1, 10, 0))


async def test_a_utc_until_inside_the_rule_is_refused():
    """A UTC UNTIL cannot be compared against naive local occurrences, and
    silently accepting one would compare a local reading to an instant."""
    with pytest.raises(recurrence.InvalidRecurrence):
        recurrence.parse(
            "FREQ=DAILY;UNTIL=20260701T000000Z",
            dtstart_local=datetime(2026, 6, 1, 10, 0),
        )


async def test_an_aware_dtstart_is_refused():
    with pytest.raises(recurrence.InvalidRecurrence):
        recurrence.parse(
            "FREQ=DAILY",
            dtstart_local=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        )


async def test_an_unknown_timezone_falls_back_to_utc_rather_than_failing():
    """A bad zone must not stop a schedule running; it runs in UTC and logs."""
    nxt = recurrence.next_occurrence(
        "FREQ=DAILY", timezone_name="Mars/Olympus",
        dtstart_local=datetime(2026, 6, 1, 10, 0),
        after=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    assert nxt is not None and nxt.hour == 10


async def test_asking_from_inside_the_repeated_hour_moves_forward():
    """The case the forward-progress guard exists for.

    06:00 UTC on the fall-back date is 01:00 local for the *second* time --
    01:00 already happened an hour earlier at 05:00 UTC. Converting that
    reference to a local reading and asking the rule for the next occurrence
    yields 01:30 local, which converts back (fold=0) to 05:30 UTC: half an
    hour *before* the reference.

    Returned as-is, the worker would see a due instant in the past, publish,
    store the same next_run_at, and publish again on the next pass. The guard
    is what turns that into "tomorrow" instead of a publish loop.
    """
    after = datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc)

    nxt = recurrence.next_occurrence(
        "FREQ=DAILY", timezone_name=NY,
        dtstart_local=datetime(2026, 10, 30, 1, 30), after=after,
    )

    assert nxt > after, "returned an instant at or before the reference"
    assert _local(nxt, NY).date() == datetime(2026, 11, 2).date()


async def test_repeated_asks_never_return_the_same_instant_twice():
    """Chaining next_occurrence across the fall-back night must strictly
    increase -- the worker feeds each answer back in as the next reference."""
    cursor = datetime(2026, 10, 31, 20, tzinfo=timezone.utc)
    seen = []
    for _ in range(6):
        cursor = recurrence.next_occurrence(
            "FREQ=DAILY", timezone_name=NY,
            dtstart_local=datetime(2026, 10, 30, 1, 30), after=cursor,
        )
        seen.append(cursor)

    assert seen == sorted(seen)
    assert len(set(seen)) == len(seen), "an instant repeated"
