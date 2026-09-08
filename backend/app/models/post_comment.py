"""Review conversation on a post.

An approval workflow without a record of *why* something was sent back is a
workflow that generates "can you look at this again?" messages in another
tool. Comments live on the post so the reason travels with the work.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

_JSON = JSONB().with_variant(JSON(), "sqlite")


class PostComment(Base):
    __tablename__ = "post_comments"
    __table_args__ = (
        Index("ix_post_comments_post_created", "post_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # User ids extracted from @[uuid] tokens at write time. Stored rather than
    # re-parsed on read so a later edit to the body cannot retroactively change
    # who was notified -- the notification already went out.
    mentions: Mapped[Optional[list]] = mapped_column(_JSON, nullable=True, default=list)
    # Threading. One level is what a review conversation needs; deeper nesting
    # makes a timeline unreadable without buying anything.
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("post_comments.id", ondelete="CASCADE"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    edited_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Soft delete: a review thread that silently loses a message reads as if
    # the objection was never raised.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    post = relationship("Post", back_populates="comments")
    author = relationship("User", lazy="selectin")
    replies = relationship(
        "PostComment",
        back_populates="parent",
        cascade="all, delete-orphan",
        single_parent=True,
    )
    parent = relationship("PostComment", remote_side=[id], back_populates="replies")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<PostComment {self.id} on {self.post_id}>"
