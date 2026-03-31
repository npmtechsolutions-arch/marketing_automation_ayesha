"""Activity Log model - comprehensive user action tracking."""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ActivityLog(Base):
    """Tracks every significant user action in the system."""

    __tablename__ = "activity_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True, index=True
    )

    # Activity details
    action: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # e.g., "post.created", "post.published", "account.connected", "platform.created"
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # "post", "platform", "account", "ai", "billing", "auth", "settings"
    description: Mapped[str] = mapped_column(Text, nullable=False)  # Human-readable description

    # What was affected
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # "post", "social_account", "social_platform", etc.
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # UUID of the resource
    resource_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )  # Name for display

    # Change tracking
    old_values: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    new_values: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Request context
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="success", nullable=False
    )  # success, failed, warning

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ActivityLog {self.action} [{self.category}] user={self.user_id}>"
