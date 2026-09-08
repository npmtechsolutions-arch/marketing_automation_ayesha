"""When this account's posts have actually done well, by weekday and hour.

The predecessor of this feature was a heatmap drawn from ``Math.random()`` with
a caption claiming a 22% reach uplift. It was removed because a fabricated
number in an analytics product is worse than an empty state: a user cannot tell
it from a measurement. Everything here is built so that distinction survives to
the pixel -- **every cell says whether it was observed or defaulted**, and the
response says which of the two the suggestions came from.

Where the data comes from, and where it does not:

* ``analytics_daily`` stores a **date and no hour**, so it cannot contribute to
  an hour-of-day analysis at all. It is not consulted.
* ``post_performance`` carries the engagement, and the hour comes from the
  post's ``published_at``. That join is the whole dataset.

Attribution is per connected account, not merely per platform: posts are
filtered by the connection listed in ``target_accounts`` *and* by the
performance row's ``platform_type``, so a post sent to Instagram and Facebook
contributes its Instagram numbers to the Instagram account only.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.platform import SocialAccount, SocialPlatform
from app.models.post import Post, PostStatus
from app.models.post_performance import PostPerformance
from app.services.dashboard import workspace_timezone

logger = logging.getLogger(__name__)

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# How far back to look. A year would cover more posts and describe an audience
# that has since changed; twelve weeks is recent enough to still be true.
DEFAULT_WINDOW_DAYS = 84

# Below this many measured posts the account's own history is not evidence, it
# is anecdote: three posts that happened to land on a Tuesday would otherwise
# make Tuesday the recommendation forever.
MIN_SAMPLE_POSTS = 12

# And a single cell needs its own support before it is treated as measured
# rather than as noise.
MIN_CELL_POSTS = 2

SUGGESTION_COUNT = 3


# Platform conventions, used only when an account has too little history of its
# own. These are **not measurements** -- they are the widely published posting
# conventions for each network, and they are labelled as defaults everywhere
# they surface so nobody mistakes them for this account's data.
DEFAULT_SLOTS: dict[str, tuple[tuple[int, int], ...]] = {
    "instagram": ((1, 11), (2, 11), (3, 14)),
    "facebook":  ((1, 9), (2, 13), (4, 9)),
    "linkedin":  ((1, 8), (2, 10), (3, 8)),
    "twitter":   ((1, 9), (2, 12), (3, 9)),
    "youtube":   ((4, 15), (5, 10), (6, 10)),
}
GENERIC_SLOTS = ((1, 10), (2, 13), (3, 10))


@dataclass
class Cell:
    weekday: int
    hour: int
    posts: int = 0
    engagement: int = 0
    reach: int = 0

    @property
    def score(self) -> Optional[float]:
        """Average interactions per post in this slot.

        An average rather than a total: a slot used twenty times will out-total
        a better one used twice, and the question is "where should the next
        post go", not "where have we posted most".
        """
        return round(self.engagement / self.posts, 2) if self.posts else None


def default_slots(platform: Optional[str]) -> tuple[tuple[int, int], ...]:
    return DEFAULT_SLOTS.get((platform or "").lower(), GENERIC_SLOTS)


async def _connection(
    db: AsyncSession, account_id: uuid.UUID, social_account_id: Optional[uuid.UUID]
) -> tuple[Optional[SocialAccount], Optional[str]]:
    if social_account_id is None:
        return None, None
    row = (
        await db.execute(
            select(SocialAccount, SocialPlatform.slug)
            .join(SocialPlatform, SocialPlatform.id == SocialAccount.platform_id)
            .where(
                SocialAccount.id == social_account_id,
                SocialAccount.account_id == account_id,
            )
        )
    ).first()
    if row is None:
        return None, None
    return row[0], row[1]


async def analyse(
    db: AsyncSession,
    account: Account,
    *,
    social_account_id: Optional[uuid.UUID] = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    min_sample: int = MIN_SAMPLE_POSTS,
) -> dict:
    """The weekday x hour picture for one connection, or for the workspace."""
    connection, platform = await _connection(db, account.id, social_account_id)
    if social_account_id is not None and connection is None:
        raise ValueError("That connection does not belong to this workspace.")

    tz = workspace_timezone(account)
    since = datetime.now(timezone.utc) - timedelta(days=window_days)

    rows = (
        await db.execute(
            select(
                Post.id,
                Post.published_at,
                Post.target_accounts,
                PostPerformance.platform_type,
                PostPerformance.likes,
                PostPerformance.comments,
                PostPerformance.shares,
                PostPerformance.saves,
                PostPerformance.reach,
            )
            .join(PostPerformance, PostPerformance.post_id == Post.id)
            .where(
                Post.account_id == account.id,
                Post.deleted_at.is_(None),
                Post.status == PostStatus.PUBLISHED,
                Post.published_at.is_not(None),
                Post.published_at >= since,
            )
        )
    ).all()

    cells: dict[tuple[int, int], Cell] = {}
    counted_posts: set[uuid.UUID] = set()

    for row in rows:
        # Per-connection attribution. Filtered here rather than in SQL because
        # target_accounts is a JSON column and containment operators differ
        # between Postgres and the SQLite test harness; the row set is one
        # workspace's twelve weeks, which is small.
        if connection is not None:
            targets = row.target_accounts or []
            if not any(
                str(t.get("social_account_id")) == str(connection.id)
                for t in targets
                if isinstance(t, dict)
            ):
                continue
            if (row.platform_type or "").lower() != (platform or "").lower():
                continue

        published = row.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        # The reader's clock, not the server's: "post at 9am" means 9am where
        # the audience is, and a UTC hour would be wrong for most workspaces.
        local = published.astimezone(tz)

        key = (local.weekday(), local.hour)
        cell = cells.setdefault(key, Cell(weekday=key[0], hour=key[1]))
        cell.posts += 1
        cell.engagement += sum(
            value or 0
            for value in (row.likes, row.comments, row.shares, row.saves)
        )
        cell.reach += row.reach or 0
        counted_posts.add(row.id)

    sample = len(counted_posts)
    sufficient = sample >= min_sample

    heatmap = []
    for weekday in range(7):
        for hour in range(24):
            cell = cells.get((weekday, hour))
            observed = bool(cell and cell.posts >= MIN_CELL_POSTS and sufficient)
            heatmap.append({
                "weekday": weekday,
                "hour": hour,
                "posts": cell.posts if cell else 0,
                # Null, not zero, for a slot never tried. Zero would say "we
                # posted here and nobody engaged", which is a different and
                # false claim.
                "score": cell.score if observed else None,
                "observed": observed,
            })

    suggestions = _suggest(cells, sufficient, platform, tz)

    return {
        "scope": {
            "social_account_id": str(social_account_id) if social_account_id else None,
            "platform": platform,
            "account_name": connection.account_name if connection else None,
            "timezone": tz.key,
            "window_days": window_days,
        },
        "sample": {
            "posts": sample,
            "threshold": min_sample,
            "sufficient": sufficient,
        },
        # The single field a caller must read before presenting any of this.
        "source": "observed" if sufficient else "default",
        "explanation": (
            f"Based on {sample} published post"
            f"{'s' if sample != 1 else ''} in the last {window_days} days."
            if sufficient
            else (
                f"Only {sample} post{'s' if sample != 1 else ''} with performance "
                f"data in the last {window_days} days — fewer than the "
                f"{min_sample} needed to read a pattern. Showing the usual "
                f"{platform or 'social media'} posting times instead."
            )
        ),
        "heatmap": heatmap,
        "suggestions": suggestions,
    }


def _suggest(
    cells: dict[tuple[int, int], Cell],
    sufficient: bool,
    platform: Optional[str],
    tz,
) -> list[dict]:
    """The top slots, measured if we can and conventional if we cannot."""
    if sufficient:
        ranked = sorted(
            (c for c in cells.values() if c.posts >= MIN_CELL_POSTS),
            key=lambda c: (c.score or 0, c.posts),
            reverse=True,
        )
        if ranked:
            return [
                {
                    "weekday": cell.weekday,
                    "hour": cell.hour,
                    "label": f"{WEEKDAYS[cell.weekday]} {cell.hour:02d}:00",
                    "score": cell.score,
                    "posts": cell.posts,
                    "observed": True,
                }
                for cell in ranked[:SUGGESTION_COUNT]
            ]
        # Enough posts overall but none in any single slot often enough to be
        # more than noise. Fall through to the defaults rather than promoting
        # a one-off.

    return [
        {
            "weekday": weekday,
            "hour": hour,
            "label": f"{WEEKDAYS[weekday]} {hour:02d}:00",
            "score": None,
            "posts": 0,
            # The flag every caller must respect: this is a convention, not
            # this account's data.
            "observed": False,
        }
        for weekday, hour in default_slots(platform)
    ]


def next_occurrence(weekday: int, hour: int, tz, *, after: Optional[datetime] = None) -> datetime:
    """The next time this slot comes round, as a UTC instant.

    So a suggestion chip can fill the scheduler directly. Resolved on the
    workspace's clock and converted once, the same contract the composer and
    recurring schedules use.
    """
    from app.services.recurrence import to_utc

    reference = (after or datetime.now(timezone.utc)).astimezone(tz)
    days_ahead = (weekday - reference.weekday()) % 7
    candidate = (reference + timedelta(days=days_ahead)).replace(
        hour=hour, minute=0, second=0, microsecond=0, tzinfo=None
    )
    if to_utc(candidate, tz) <= (after or datetime.now(timezone.utc)):
        candidate = candidate + timedelta(days=7)
    return to_utc(candidate, tz)
