"""One row per connected account per day.

Analytics were previously computed on demand from ``post_performances``, which
answers "how did this post do" but not "how did the audience grow" -- nothing
recorded a follower count at a point in time, so growth could not be shown at
all. That is why the dashboard's follower growth has been returning null.

**Every metric is nullable, and null means "the platform does not report it",
not "zero".** X exposes no reach on the tier we use; LinkedIn reports no saves;
profile visits exist on Instagram and nowhere else. Storing 0 for those would
make a chart show a real, flat, wrong line -- and averaging across platforms
would silently drag every figure down.
"""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# The metric columns, in one place. The sync writes them, the endpoints
# aggregate them, and the CSV export names them -- three copies of this list
# would drift the first time a metric is added.
METRIC_FIELDS = (
    "followers",
    "following",
    "posts_count",
    "likes",
    "comments",
    "shares",
    "saves",
    "reach",
    "impressions",
    "video_views",
    "profile_visits",
    "clicks",
)

# Metrics that are a running total rather than a daily amount. Summing these
# across a range would be meaningless -- 1,000 followers on Monday plus 1,010
# on Tuesday is not 2,010 -- so aggregates take the latest value instead.
CUMULATIVE_FIELDS = frozenset({"followers", "following", "posts_count"})


class AnalyticsDaily(Base):
    __tablename__ = "analytics_daily"
    __table_args__ = (
        # The sync upserts on this: one row per account per day, so a re-run
        # corrects the day rather than duplicating it.
        UniqueConstraint("social_account_id", "date", name="uq_analytics_daily_day"),
        # The range queries' shape: this account, these dates, in order.
        Index("ix_analytics_daily_account_date", "social_account_id", "date"),
        # Retention pruning scans by date alone across every account.
        Index("ix_analytics_daily_date", "date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    social_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    # A calendar date in the workspace's timezone, not a timestamp: platforms
    # report daily buckets, and storing an instant would invite comparing
    # buckets that do not line up.
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # BigInteger throughout: a large account's lifetime impressions exceed
    # int32, and discovering that through an overflow in production is not the
    # way to find out.
    followers: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    following: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    posts_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    likes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    comments: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    shares: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    saves: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    reach: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    impressions: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    video_views: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    profile_visits: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    clicks: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    social_account = relationship("SocialAccount", lazy="selectin")

    def as_metrics(self) -> dict:
        return {name: getattr(self, name) for name in METRIC_FIELDS}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AnalyticsDaily {self.social_account_id} {self.date}>"
