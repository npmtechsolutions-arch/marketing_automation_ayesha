"""Post model."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.business import Business
    from app.models.campaign import Campaign
    from app.models.post_performance import PostPerformance
    from app.models.strategy import Strategy
    from app.models.user import User


class PostStatus(str, enum.Enum):
    DRAFT = "draft"
    PREVIEW = "preview"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    PARTIALLY_PUBLISHED = "partially_published"  # some accounts succeeded, some failed
    FAILED = "failed"


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    business_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=True
    )
    strategy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=True
    )
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True
    )

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # optional post title
    media_urls: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)  # list of uploaded media URLs
    hashtags: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)

    # AI generation fields
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ai_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ai_images: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    # e.g., [{"url": "...", "prompt": "...", "model": "dall-e-3"}]

    # Digital photography / assets
    digital_assets: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    # e.g., [{"url": "...", "type": "photo", "filters": {...}}]

    # Target accounts for posting (replaces old platforms JSON)
    target_accounts: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    # e.g., [{"social_account_id": "uuid", "platform_name": "Instagram", "account_name": "Acme Corp"}]

    # Posting results per account
    posting_results: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    # e.g., [{"social_account_id": "uuid", "status": "published/failed", "post_url": "...", "error": "..."}]

    # Status
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus, name="post_status_enum"),
        default=PostStatus.DRAFT,
        nullable=False,
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Approval
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Preview
    device_previews: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    # e.g., {"mobile": {...}, "tablet": {...}, "web": {...}}

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

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
    user: Mapped["User"] = relationship(
        "User", back_populates="posts", foreign_keys=[user_id]
    )
    account: Mapped["Account"] = relationship(
        "Account", back_populates="posts", foreign_keys=[account_id]
    )
    business: Mapped[Optional["Business"]] = relationship(
        "Business", back_populates="posts", foreign_keys=[business_id]
    )
    strategy: Mapped[Optional["Strategy"]] = relationship(
        "Strategy", back_populates="posts", foreign_keys=[strategy_id]
    )
    campaign: Mapped[Optional["Campaign"]] = relationship(
        "Campaign", back_populates="posts", foreign_keys=[campaign_id]
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[approved_by]
    )
    performances: Mapped[list["PostPerformance"]] = relationship(
        "PostPerformance", back_populates="post", foreign_keys="PostPerformance.post_id"
    )

    def __repr__(self) -> str:
        return f"<Post {self.id} status={self.status.value}>"
