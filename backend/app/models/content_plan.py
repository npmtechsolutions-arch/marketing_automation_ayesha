"""A month of proposed posts, awaiting a human.

The AI manager **proposes**. It does not publish, and it does not schedule.
Accepting a plan creates drafts — or posts in review, where the workspace
requires approval — and a person still has to put every one of them out.

That is the whole shape of the feature, and it is why the plan is a row rather
than a response body: a proposal you cannot come back to is a proposal nobody
reviews properly.

Every item records **what grounded it**. A plan that says "Wednesday 18:00"
must be able to say whether that came from this workspace's own posting history
or from a platform default, because those are different claims and only one of
them is about the customer. See ``source`` on the item and ``grounding`` on the
plan.
"""

import enum
import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# JSONB on Postgres, JSON on SQLite, exactly as the report model does it.
_JSON = JSON().with_variant(JSONB(), "postgresql")


class PlanGoal(str, enum.Enum):
    """What the month is for.

    A closed set, and the only free-form thing the caller controls that reaches
    the *system* prompt. Topic hints are user text and go in the user message —
    the rule from 2.3, kept here because this prompt is much larger and the
    temptation to interpolate is correspondingly greater.
    """

    AWARENESS = "awareness"
    ENGAGEMENT = "engagement"
    TRAFFIC = "traffic"
    LEADS = "leads"


class PlanStatus(str, enum.Enum):
    PROPOSED = "proposed"
    PARTIALLY_ACCEPTED = "partially_accepted"
    ACCEPTED = "accepted"
    DISCARDED = "discarded"


class PlanItemStatus(str, enum.Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DISCARDED = "discarded"


class ContentPlan(Base):
    __tablename__ = "content_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    # Null when the campaign is deleted: a plan already reviewed should not
    # vanish with it, the same reasoning as reports.campaign_id.
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # The first of the month this plan covers, on the workspace's clock.
    month: Mapped[date] = mapped_column(Date, nullable=False)
    goal: Mapped[PlanGoal] = mapped_column(
        Enum(PlanGoal, name="plan_goal_enum"), nullable=False
    )
    status: Mapped[PlanStatus] = mapped_column(
        Enum(PlanStatus, name="plan_status_enum"),
        default=PlanStatus.PROPOSED, nullable=False,
    )

    # What the generator was given to work from, frozen at generation time so a
    # reviewer can see the basis of a proposal rather than today's version of
    # it. Carries the per-platform best-time source, the sample sizes behind
    # it, and the topics drawn from real performance.
    grounding: Mapped[Optional[dict[str, Any]]] = mapped_column(_JSON, nullable=True)

    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    items: Mapped[list["ContentPlanItem"]] = relationship(
        "ContentPlanItem",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="ContentPlanItem.scheduled_at",
    )


class ContentPlanItem(Base):
    __tablename__ = "content_plan_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_plans.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Both readings are stored. The local one is what the reviewer sees and
    # what a rationale quotes ("Wednesday 18:00"); the UTC instant is what a
    # post would be scheduled at. Deriving one from the other at read time is
    # how the calendar ended up showing a Sydney post in London hours.
    scheduled_local: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # The social accounts this proposal is for, as a list of ids. Validated
    # against the workspace at accept time, not trusted from the model.
    target_account_ids: Mapped[list[str]] = mapped_column(_JSON, nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[Optional[list[str]]] = mapped_column(_JSON, nullable=True)

    # One sentence saying why this slot, in the reviewer's language.
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # "observed" or "default" -- whether the slot came from this workspace's
    # own history or from a platform convention. The single field a reader must
    # see before believing the timing, and the same vocabulary best_times uses.
    slot_source: Mapped[str] = mapped_column(String(16), nullable=False)

    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[PlanItemStatus] = mapped_column(
        Enum(PlanItemStatus, name="plan_item_status_enum"),
        default=PlanItemStatus.PROPOSED, nullable=False,
    )
    # Set when the item is accepted and a real post exists for it. SET NULL so
    # deleting the post does not delete the record that it was proposed.
    post_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    plan: Mapped["ContentPlan"] = relationship("ContentPlan", back_populates="items")
