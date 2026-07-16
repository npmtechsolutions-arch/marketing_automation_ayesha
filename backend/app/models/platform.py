"""User-defined social media platforms and their accounts."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.account import Account


class SocialPlatform(Base):
    """A social media platform created/defined by the user (agency)."""

    __tablename__ = "social_platforms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "Facebook", "Instagram", "TikTok"
    slug: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "facebook", "instagram"
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # icon identifier
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # hex color e.g., "#1877F2"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Platform API configuration template (what fields are needed for accounts)
    api_config_template: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    # e.g., {"fields": [{"key": "app_id", "label": "App ID", "type": "text", "required": true}, ...]}

    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # e.g., "https://graph.facebook.com/v18.0"

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User", back_populates="social_platforms", foreign_keys=[user_id], lazy="selectin"
    )
    account: Mapped["Account"] = relationship("Account", foreign_keys=[account_id], lazy="selectin")
    social_accounts: Mapped[list["SocialAccount"]] = relationship(
        back_populates="platform", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<SocialPlatform {self.name} ({self.slug})>"


class SocialAccount(Base):
    """A specific social media account on a platform (e.g., a client's Instagram account)."""

    __tablename__ = "social_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    platform_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_platforms.id"), nullable=False
    )

    # Account identification
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g., "Acme Corp Instagram"
    account_handle: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # e.g., "@acmecorp"
    profile_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    profile_image_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # API credentials (encrypted in production)
    api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Additional config (flexible JSON for platform-specific settings)
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    # e.g., {"page_id": "123", "app_id": "456", "webhook_url": "..."}

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # connection tested successfully
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_posted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata", JSON, nullable=True
    )  # follower count, etc.

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], lazy="selectin")
    account: Mapped["Account"] = relationship("Account", foreign_keys=[account_id], lazy="selectin")
    platform: Mapped["SocialPlatform"] = relationship(
        back_populates="social_accounts", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<SocialAccount {self.account_name} on {self.platform_id}>"
