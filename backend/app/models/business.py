"""Business model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.post import Post
    from app.models.strategy import Strategy


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    target_audience: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    brand_voice: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    goals: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    competitors: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    account: Mapped["Account"] = relationship(
        "Account", back_populates="businesses", foreign_keys=[account_id]
    )
    posts: Mapped[list["Post"]] = relationship(
        "Post", back_populates="business", foreign_keys="Post.business_id"
    )
    strategies: Mapped[list["Strategy"]] = relationship(
        "Strategy", back_populates="business", foreign_keys="Strategy.business_id"
    )

    def __repr__(self) -> str:
        return f"<Business {self.name}>"
