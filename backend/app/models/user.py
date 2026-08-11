"""User model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, DateTime, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.notification import Notification
    from app.models.platform import SocialPlatform
    from app.models.post import Post
    from app.models.team_member import TeamMember
    from app.models.user_session import UserSession


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Per-user preferences (notification toggles, appearance choices, etc.).
    # Free-form JSON so new preference keys don't require a schema change.
    preferences: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Two-factor authentication (TOTP). ``totp_pending_secret`` holds a secret
    # during setup, before the user has confirmed a code; on confirmation it is
    # promoted to ``totp_secret`` and ``two_factor_enabled`` is set. Recovery
    # codes are stored as one-way hashes (never plaintext).
    totp_secret: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    totp_pending_secret: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    two_factor_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    totp_recovery_codes: Mapped[Optional[list[str]]] = mapped_column(
        JSON, nullable=True
    )

    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
    accounts: Mapped[list["TeamMember"]] = relationship(
        "TeamMember",
        back_populates="user",
        foreign_keys="TeamMember.user_id",
        lazy="selectin",
    )
    owned_accounts: Mapped[list["Account"]] = relationship(
        "Account", back_populates="owner", foreign_keys="Account.owner_id"
    )
    posts: Mapped[list["Post"]] = relationship(
        "Post", back_populates="user", foreign_keys="Post.user_id"
    )
    social_platforms: Mapped[list["SocialPlatform"]] = relationship(
        "SocialPlatform", back_populates="user", foreign_keys="SocialPlatform.user_id", lazy="selectin"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="user", foreign_keys="Notification.user_id"
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession",
        back_populates="user",
        foreign_keys="UserSession.user_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
