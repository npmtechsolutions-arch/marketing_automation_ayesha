"""Competitor tracking: a follower and media-count history for named accounts.

**Named for exactly what it is.** Instagram's Business Discovery is the only
official route to another account's data, and it returns a deliberately thin
set: username, name, follower count, media count, and recent media. No
engagement, no posting cadence, no audience overlap, no "top content". Meta's
permission model restricts everything else to accounts that have authorised
this app, and tools appearing to offer more rely on scraping or licensed
third-party data (docs/API-TIER-AUDIT.md).

So this stores two numbers over time and calls itself competitor *tracking*.
The word "intelligence" would promise analysis of data nobody here can legally
obtain, which is a claim about a product rather than a feature name.

Both metric columns are **nullable, and null means "Discovery did not return
it"** -- not zero. A private account, a personal (non-business) account, or a
handle that has since been renamed all yield an absent field, and a stored 0
would draw a real, flat, wrong line through a follower chart. Same discipline
as ``analytics_daily``, for the same reason.
"""

import uuid
from datetime import date as date_type, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CompetitorAccount(Base):
    """One account a workspace watches."""

    __tablename__ = "competitor_accounts"
    __table_args__ = (
        # Discovery is capped per account per week, so the same handle twice
        # would spend half a workspace's allowance answering itself.
        UniqueConstraint(
            "account_id", "platform", "handle", name="uq_competitor_account"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Instagram only, and stored rather than assumed: the audit found Meta is
    # the *only* platform with any official competitor-data route at all, and X
    # has none. A second value here would be a real platform change.
    platform: Mapped[str] = mapped_column(
        String(50), nullable=False, default="instagram"
    )
    # Stored without the '@' and lowercased by the service, because Instagram
    # handles are case-insensitive and "@Nike" and "nike" are one account --
    # two rows would be two weekly lookups of the same thing.
    handle: Mapped[str] = mapped_column(String(120), nullable=False)
    # What Instagram calls them, captured at add time so the list reads as
    # names rather than handles. Nullable: Discovery does not always return it.
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    added_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Staleness is a first-class fact here. Discovery runs weekly at best, so a
    # number on screen is days old by definition and the UI has to say how old
    # -- "12,400 followers" and "12,400 followers as of 6 days ago" are
    # different claims.
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    snapshots = relationship(
        "CompetitorSnapshot",
        back_populates="competitor",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CompetitorSnapshot(Base):
    """What Discovery reported about one account on one day.

    Keyed by day, and upserted rather than appended -- the same shape as
    ``analytics_daily``. A second sync on the same day corrects that day
    instead of adding a second point, so a chart cannot show two different
    Tuesdays.
    """

    __tablename__ = "competitor_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "competitor_id", "date", name="uq_competitor_snapshot_day"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    competitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("competitor_accounts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)

    # Both nullable on purpose. Discovery omits a field for a private or
    # non-business account; a 0 here would be a measurement claiming the
    # account has no followers.
    followers: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    media_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    competitor = relationship("CompetitorAccount", back_populates="snapshots")
