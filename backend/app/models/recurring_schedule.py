"""Recurring schedules and the weekly posting queue.

Both store times as **local wall-clock plus a timezone name**, never as a UTC
interval. That is the whole design, and the reason is DST: "every Monday at
10:00" means 10:00 on the workspace's clock, and the UTC instant that
corresponds to it moves by an hour twice a year. A schedule stored as "every
604800 seconds from this UTC instant" is correct for about five months and then
publishes at 09:00 or 11:00 forever.

``next_run_at`` is UTC because that is what the worker compares against
``now()``. It is *derived* from the rule each time rather than advanced by
addition -- see ``app.services.recurrence``.
"""

import enum
import uuid
from datetime import datetime, time
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.post import Post


class RecurrenceStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    # Ran out its COUNT or passed its UNTIL. Kept rather than deleted so the
    # posts it produced still have something to point at.
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RecurringSchedule(Base):
    """A template post plus a rule for when to publish copies of it."""

    __tablename__ = "recurring_schedules"
    __table_args__ = (
        # The worker's only query: active schedules that are due.
        Index("ix_recurring_schedules_due", "status", "next_run_at"),
        Index("ix_recurring_schedules_account", "account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # The post whose content is copied for each occurrence. It is never
    # published itself -- publishing the template would give every occurrence
    # one shared row, one status and one permalink, and the second run would
    # overwrite the first one's results.
    template_post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # An iCalendar RRULE, e.g. "FREQ=WEEKLY;BYDAY=MO,WE,FR;BYHOUR=10;BYMINUTE=0".
    # Stored as text rather than decomposed into columns: RRULE is a standard
    # with an implementation we already depend on, and re-modelling BYSETPOS or
    # BYMONTHDAY in columns is how a scheduler ends up with its own subtly
    # different calendar.
    rrule: Mapped[str] = mapped_column(Text, nullable=False)

    # The zone the rule is expressed in. Copied from the workspace at creation
    # rather than read live, so moving the workspace's timezone does not
    # silently move every existing schedule.
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)

    # Local wall-clock start. Naive on purpose: it is a clock reading, and the
    # instant it denotes depends on the zone above.
    starts_at_local: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )

    # --- end conditions, either, both, or neither ------------------------
    until_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    max_occurrences: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[RecurrenceStatus] = mapped_column(
        Enum(RecurrenceStatus, name="recurrence_status_enum"),
        default=RecurrenceStatus.ACTIVE,
        nullable=False,
    )

    # UTC, because the worker compares it to now(). Recomputed from the rule
    # after every run, never advanced by adding an interval.
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    template_post: Mapped["Post"] = relationship("Post", foreign_keys=[template_post_id])


class QueueSlot(Base):
    """One recurring publishing slot in a workspace's week.

    "Add to queue" means: put this post in the next of these that is both in
    the future and not already taken. The slots are the schedule; the posts
    fill them in the order they are queued.
    """

    __tablename__ = "queue_slots"
    __table_args__ = (
        # One slot per weekday/time. Two identical slots would either
        # double-book or race, and neither is a feature.
        UniqueConstraint("account_id", "weekday", "time_local", name="uq_queue_slot"),
        Index("ix_queue_slots_account", "account_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )

    # 0 = Monday .. 6 = Sunday, matching Python's date.weekday() and RRULE's
    # MO..SU ordering. Not ISO weekday (1..7) and not cron (0=Sunday): both
    # were candidates, and mixing two of them is how a slot lands a day out.
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    time_local: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
