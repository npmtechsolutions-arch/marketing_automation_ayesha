"""Organization model — the billing entity above a Workspace.

The hierarchy is **Organization → Workspace → Social Accounts**, where a
"Workspace" is the :class:`~app.models.account.Account` class (the name is kept
because eleven foreign keys and most frontend URLs reference ``account_id``).

The subscription lives here rather than on the workspace. Previously every
`Account` carried its own tier and its own Stripe customer, so an agency running
five clients paid five times and nothing in the model represented the company
itself. Usage allowances are now spent across every workspace an organization
owns.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.account import SubscriptionStatus, SubscriptionTier
from app.models.team_member import InvitationStatus

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.user import User


class OrgRole(str, enum.Enum):
    """Roles within an organization.

    Deliberately coarser than :class:`~app.models.team_member.TeamRole`: an
    organization governs billing and which workspaces exist, not day-to-day
    content, so it needs far fewer distinctions.
    """

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class Organization(Base):
    """A company. Owns the subscription and one or more workspaces."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # --- Subscription (moved here from Account) ---------------------------
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier, name="subscription_tier_enum"),
        default=SubscriptionTier.FREE,
        nullable=False,
    )
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status_enum"),
        default=SubscriptionStatus.TRIALING,
        nullable=False,
    )
    # Indexed because the Stripe webhook looks organizations up by these two
    # columns on every event; on Account they were unindexed full scans.
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(
        String(255), index=True, nullable=True
    )
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(255), index=True, nullable=True
    )
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # No limit columns live here. They were denormalised from TIER_LIMITS and
    # are now plan_features rows, resolved through EntitlementService -- a copy
    # on this table would go stale the moment a superadmin edits a plan, and
    # would then contradict the usage endpoint and enforcement itself.

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
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    workspaces: Mapped[list["Account"]] = relationship(
        "Account", back_populates="organization", foreign_keys="Account.organization_id"
    )
    members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="organization",
        foreign_keys="OrganizationMember.organization_id",
    )

    def __repr__(self) -> str:
        return f"<Organization {self.name} ({self.slug})>"


class OrganizationMember(Base):
    """Membership of an organization.

    Mirrors :class:`~app.models.team_member.TeamMember` on purpose, invitation
    columns included, so the invite flow and the authorization checks are
    recognisably the same code.

    This is a **separate boundary** from workspace membership: holding a row here
    grants organization-level access (billing, the workspace list, org settings)
    and nothing else. Reading a workspace's content still requires a TeamMember
    row for that workspace.
    """

    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "organization_id", name="uq_org_member_user_organization"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Null until an emailed invitation is claimed, exactly as on TeamMember.
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), index=True, nullable=False
    )
    role: Mapped[OrgRole] = mapped_column(
        Enum(OrgRole, name="org_role_enum"),
        default=OrgRole.MEMBER,
        nullable=False,
    )
    invitation_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    invitation_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    invitation_status: Mapped[InvitationStatus] = mapped_column(
        Enum(InvitationStatus, name="invitation_status_enum"),
        default=InvitationStatus.PENDING,
        nullable=False,
    )
    invited_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="members", foreign_keys=[organization_id]
    )
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    inviter: Mapped[Optional["User"]] = relationship("User", foreign_keys=[invited_by])

    def __repr__(self) -> str:
        return f"<OrganizationMember user={self.user_id} org={self.organization_id} role={self.role}>"
