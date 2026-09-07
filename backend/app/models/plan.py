"""Plans, features and metered usage.

Replaces the hard-coded ``TIER_LIMITS`` / ``TIER_PRICING`` dictionaries. A limit
in a Python dict cannot be changed without a deploy, cannot differ for one
customer who negotiated a higher cap, and drifts from whatever Stripe actually
bills. These tables make an entitlement data.

Two kinds of feature, and the difference decides how a limit is enforced:

* **Stateful** -- workspaces, team members, connected social accounts, storage.
  The limit applies to what currently exists, so usage is a COUNT and deleting
  something frees the slot again.
* **Metered** -- posts, AI requests and reports per month. The limit applies to
  what was consumed during a period, so usage accumulates in ``UsageRecord``
  and deleting the artefact does not refund the quota. An AI request costs real
  money whether or not the result is kept.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class FeatureUnit(str, enum.Enum):
    """How a feature's limit is expressed."""

    COUNT = "count"
    BOOLEAN = "boolean"
    BYTES = "bytes"


class Plan(Base):
    """A sellable plan. ``key`` matches the old SubscriptionTier values."""

    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Nullable: FREE and ENTERPRISE are not bought through Stripe checkout.
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    price_monthly: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    features: Mapped[list["PlanFeature"]] = relationship(
        "PlanFeature", back_populates="plan", foreign_keys="PlanFeature.plan_id"
    )

    def __repr__(self) -> str:
        return f"<Plan {self.key}>"


class Feature(Base):
    """A metered or gated capability. Keyed by string, not id, so plan rows and
    call sites reference something readable."""

    __tablename__ = "features"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit: Mapped[FeatureUnit] = mapped_column(
        Enum(FeatureUnit, name="feature_unit_enum"),
        default=FeatureUnit.COUNT,
        nullable=False,
    )
    # Metered features accumulate per period; stateful ones are counted live.
    is_metered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<Feature {self.key}>"


class PlanFeature(Base):
    """What one plan grants for one feature.

    ``limit_value`` NULL means unlimited. For a boolean feature, 1 is on and 0
    is off -- an absent row means the plan does not grant the feature at all.
    """

    __tablename__ = "plan_features"
    __table_args__ = (
        UniqueConstraint("plan_id", "feature_key", name="uq_plan_feature"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id"), index=True, nullable=False
    )
    feature_key: Mapped[str] = mapped_column(
        String(64), ForeignKey("features.key"), index=True, nullable=False
    )
    # BigInteger, not Integer: a storage limit in bytes overflows int32 at 2GB.
    limit_value: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    plan: Mapped["Plan"] = relationship(
        "Plan", back_populates="features", foreign_keys=[plan_id]
    )
    feature: Mapped["Feature"] = relationship("Feature", foreign_keys=[feature_key])

    def __repr__(self) -> str:
        return f"<PlanFeature {self.feature_key}={self.limit_value}>"


class UsageRecord(Base):
    """Consumption of a metered feature by one organization in one period.

    The unique constraint is what makes enforcement safe: the check and the
    increment are a single ``INSERT ... ON CONFLICT DO UPDATE ... WHERE`` that
    the database serialises. Reading the count and then writing it back would
    let two requests at the limit both succeed.
    """

    __tablename__ = "usage_records"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "feature_key", "period_start", name="uq_usage_period"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), index=True, nullable=False
    )
    feature_key: Mapped[str] = mapped_column(
        String(64), ForeignKey("features.key"), nullable=False
    )
    # Start of the billing period this usage falls in. Stateful features never
    # get a row here.
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Same reason as limit_value: byte counts exceed int32.
    count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped["Organization"] = relationship(
        "Organization", foreign_keys=[organization_id]
    )

    def __repr__(self) -> str:
        return f"<UsageRecord {self.feature_key}={self.count}>"
