"""One organization's connection to a CRM.

**Organization level, not workspace.** A CRM belongs to the company, not to one
of its brands: an agency running four workspaces has one HubSpot portal, and
making each workspace connect separately would mean four copies of the same
credential and four chances for three of them to go stale. It also matches how
the CRM sees it -- HubSpot has one portal per company, not per brand.

Tokens are encrypted at rest through ``EncryptedText``, the same as the social
account tokens and the Slack webhook. Anyone holding them can read and write a
company's customer records.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.db_types import EncryptedText


class CrmConnection(Base):
    __tablename__ = "crm_connections"
    __table_args__ = (
        # One connection per CRM per organization. A second row for the same
        # provider would mean two portals silently competing for the same
        # "Send to CRM" press; reconnecting updates this row in place instead,
        # which is 1.9's rule applied to credentials.
        UniqueConstraint("organization_id", "provider", name="uq_crm_connection"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)

    access_token: Mapped[Optional[str]] = mapped_column(EncryptedText, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(EncryptedText, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # The CRM's own identifiers, so settings can name the portal rather than
    # showing a bare "connected" that someone with three portals cannot act on.
    external_account_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    external_account_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # Who connected it. An org-wide credential that nobody remembers adding is
    # one nobody dares remove.
    connected_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
