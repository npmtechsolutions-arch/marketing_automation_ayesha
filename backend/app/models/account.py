"""Account model — a **Workspace** in the Organization → Workspace hierarchy.

The class name is retained deliberately: eleven foreign keys across ten models
and most frontend URLs reference ``account_id``, so renaming would be churn
without benefit. Read every ``Account`` below as "Workspace".

An Account is the container for one client's content. The billing entity above
it is :class:`~app.models.organization.Organization`, which owns the
subscription and whose allowances are spent across all of its workspaces.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.organization import Organization
    from app.models.post import Post
    from app.models.team_member import TeamMember
    from app.models.user import User


class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    STARTER = "starter"
    GROWTH = "growth"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    TRIALING = "trialing"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # The billing entity this workspace belongs to. Subscription tier, Stripe
    # ids and every usage limit live on the Organization, not here.
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), index=True, nullable=False
    )
    settings: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    owner: Mapped["User"] = relationship(
        "User", back_populates="owned_accounts", foreign_keys=[owner_id]
    )
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="workspaces", foreign_keys=[organization_id]
    )
    team_members: Mapped[list["TeamMember"]] = relationship(
        "TeamMember", back_populates="account", foreign_keys="TeamMember.account_id"
    )
    businesses: Mapped[list["Business"]] = relationship(
        "Business", back_populates="account", foreign_keys="Business.account_id"
    )
    posts: Mapped[list["Post"]] = relationship(
        "Post", back_populates="account", foreign_keys="Post.account_id"
    )

    def __repr__(self) -> str:
        return f"<Account {self.name} ({self.slug})>"
