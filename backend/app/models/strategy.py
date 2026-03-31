"""Strategy model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.business import Business
    from app.models.campaign import Campaign
    from app.models.post import Post
    from app.models.user import User


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str] = mapped_column(String(500), nullable=False)
    platform_mix: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    posting_frequency: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_themes: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    performance_summary: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    account: Mapped["Account"] = relationship("Account", foreign_keys=[account_id])
    business: Mapped["Business"] = relationship(
        "Business", back_populates="strategies", foreign_keys=[business_id]
    )
    posts: Mapped[list["Post"]] = relationship(
        "Post", back_populates="strategy", foreign_keys="Post.strategy_id"
    )
    campaigns: Mapped[list["Campaign"]] = relationship(
        "Campaign", back_populates="strategy", foreign_keys="Campaign.strategy_id"
    )

    def __repr__(self) -> str:
        return f"<Strategy {self.name}>"
