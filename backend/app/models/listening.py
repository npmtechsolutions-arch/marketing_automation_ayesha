"""Social listening: saved searches, and what they found.

Scoped hard by what the platform actually feeds. X's pay-per-use tier includes
**recent search only — a rolling seven days**; full-archive search needs Pro or
Enterprise, neither of which is open to this deployment (docs/API-TIER-AUDIT.md).
So a mention older than seven days is not something this can find, and every
surface that shows these rows has to say the window rather than implying it has
looked at everything.

Two consequences are baked into the columns rather than left to the UI.

**Polling costs real money**, at roughly half a cent per post read on X's
pay-per-use tier. ``requests_made`` and ``posts_read`` accumulate on the query
so the spend is visible where the decision to keep polling is made, instead of
arriving as a surprise on a bill. That is the audit's own conclusion: any
listening feature needs a per-workspace read budget with a visible ceiling.

**A failed credential must never look like silence.** ``last_error`` and
``last_error_at`` sit beside ``last_success_at`` precisely so a query whose
token has no funding behind it reads as broken rather than as "no one is
talking about you" -- the same class of dishonesty as the connector that used
to invent metrics when its API call failed.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ListeningQuery(Base):
    """One saved search a workspace watches."""

    __tablename__ = "listening_queries"
    __table_args__ = (
        # The same phrase saved twice would poll twice and bill twice for one
        # answer. Case is not normalised here: X's search is case-insensitive
        # but its operators are not, so "AI OR ML" and "ai or ml" are two
        # genuinely different searches.
        UniqueConstraint(
            "account_id", "platform", "query_text", name="uq_listening_query"
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
    # Only "twitter" today. Stored rather than assumed because the audit found
    # Meta cannot feed this at all -- no public search, no hashtag streams --
    # so a second platform here would be a real event worth seeing in the data,
    # not a config change.
    platform: Mapped[str] = mapped_column(
        String(50), nullable=False, default="twitter"
    )
    query_text: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    last_polled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # The newest post id this query has seen, passed back as ``since_id`` so a
    # poll asks only for what is new. It moves forward only: a platform that
    # re-serves an older item on a later page must not drag the marker back and
    # make the whole window re-bill.
    last_result_cursor: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )

    # Health. A query with an error and no recent success is *broken*, and the
    # list says so; an empty stream on its own says nothing about whether the
    # search worked.
    last_success_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # What it has cost so far. Requests and posts are counted separately
    # because X bills per *post read*, not per request -- one request that
    # returns fifty posts costs fifty reads.
    requests_made: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    posts_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    mentions = relationship(
        "Mention",
        back_populates="query",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Mention(Base):
    """One post that matched a saved search.

    Never rewritten once stored. A platform can re-serve the same post with a
    different rendering of its author's display name, and updating the row on
    every poll would churn it and make "has anything actually happened here"
    unanswerable -- 2.5's rule, and the reason the inbox sync leaves existing
    messages alone.
    """

    __tablename__ = "listening_mentions"
    __table_args__ = (
        # Idempotency, and the only thing standing between a six-hourly poll
        # and a stream that duplicates itself four times a day.
        UniqueConstraint(
            "listening_query_id", "external_id", name="uq_listening_mention"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listening_query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listening_queries.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)

    author_handle: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # When the author posted it, from the platform. Distinct from matched_at:
    # a post can be found hours after it was written, and sorting a stream by
    # when *we* noticed would put a two-hour-old post above a two-minute-old one.
    posted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    query = relationship("ListeningQuery", back_populates="mentions")
