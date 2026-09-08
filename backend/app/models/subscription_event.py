"""A log of subscription transitions.

``Organization`` stores only the *current* tier and status. That is enough to
compute what is being billed right now, and not enough for any question with a
date in it: churn last 30 days, trial conversions, or a revenue trend. Those
need to know *when* a subscription changed, and ``updated_at`` cannot stand in
-- it moves on every write, so an organization that cancelled a year ago and
renamed itself yesterday would count as this month's churn.

One row per transition, written wherever tier or status changes: Stripe
webhooks, checkout confirmation, and a superadmin's manual change.

``mrr_amount`` is the organization's monthly value *at the time of the
transition*, copied rather than looked up later. A plan price change should
alter what customers pay next month, not silently rewrite what the business
earned last quarter -- and joining history to today's Plan row would do exactly
that.
"""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SubscriptionEventSource(str, enum.Enum):
    """Where the change came from, so an operator can tell a customer's own
    action from one of ours."""

    CHECKOUT = "checkout"
    WEBHOOK = "webhook"
    ADMIN = "admin"
    SYSTEM = "system"


class SubscriptionEvent(Base):
    __tablename__ = "subscription_events"
    __table_args__ = (
        # The revenue queries all filter by time, either across every
        # organization (trend, churn) or within one (its history).
        Index("ix_subscription_events_created", "created_at"),
        Index("ix_subscription_events_org_created", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Stored as plain strings rather than the SubscriptionTier/Status enums.
    # History has to survive a value being renamed or retired: an enum column
    # would reject a row describing a plan that no longer exists, which is
    # precisely the row a churn report needs.
    from_tier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_tier: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)

    # The organization's monthly value after this transition. Zero for free,
    # cancelled and enterprise -- see the module docstring for why it is copied
    # rather than derived at read time.
    mrr_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)

    source: Mapped[SubscriptionEventSource] = mapped_column(
        Enum(SubscriptionEventSource, name="subscription_event_source_enum"),
        default=SubscriptionEventSource.SYSTEM,
        nullable=False,
    )
    # Free text for the webhook event name or the admin's reason.
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # No index=True here: the explicit named index in __table_args__ already
    # covers created_at, and the two together produce duplicate indexes.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
