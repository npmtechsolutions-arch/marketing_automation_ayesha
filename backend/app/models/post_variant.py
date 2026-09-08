"""Per-platform overrides for a post.

One post, customised per platform. The base ``Post`` holds the master content
and a variant overrides it for one platform -- so an author writes once, then
trims the version that goes to X without touching what LinkedIn receives.

**Every override is nullable, and NULL means "inherit".** That distinction is
the whole design: a variant row with ``content = NULL`` follows the master as
it is edited, while ``content = ""`` is a deliberate (if odd) empty post. If
absence and emptiness were the same value, creating a variant to set a
first comment would silently freeze that platform's copy at whatever the master
said at the time.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

_JSON = JSONB().with_variant(JSON(), "sqlite")


class PostVariant(Base):
    __tablename__ = "post_variants"
    __table_args__ = (
        # One variant per platform per post: two would make "which one
        # publishes?" ambiguous at exactly the moment it matters.
        UniqueConstraint("post_id", "platform_slug", name="uq_post_variant_platform"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # Variants are meaningless without their post.
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The connector registry's slug, not a SocialPlatform id: a variant belongs
    # to a platform, not to one connected account. Two X accounts on one post
    # get the same variant, which is what an author means by "the X version".
    platform_slug: Mapped[str] = mapped_column(String(64), nullable=False)

    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Ordered media ids. A list rather than a set because carousel order is
    # part of the post, and ordered separately from the master because the
    # platform that gets four images may not be the one that gets them first.
    media: Mapped[Optional[list]] = mapped_column(_JSON, nullable=True)
    link_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    # media id -> alt text. Keyed by id rather than positional index so
    # reordering media does not silently reassign descriptions to the wrong
    # images.
    alt_texts: Mapped[Optional[dict]] = mapped_column(_JSON, nullable=True)
    # Which image represents a video. No FK cascade: losing the thumbnail
    # should not delete the variant.
    thumbnail_media_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media.id", ondelete="SET NULL"), nullable=True
    )
    # Posted as a reply immediately after publishing. Where hashtags and links
    # go on the platforms that penalise them in the body.
    first_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    post = relationship("Post", back_populates="variants")
    thumbnail = relationship("Media", lazy="selectin")

    @property
    def overrides(self) -> list[str]:
        """Which fields this variant actually overrides.

        Drives the composer's "inherited or overridden" indicator, so an author
        can see at a glance what they have changed for a platform.
        """
        names = ("content", "media", "link_url", "alt_texts",
                 "thumbnail_media_id", "first_comment")
        return [name for name in names if getattr(self, name) is not None]

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<PostVariant {self.platform_slug} overrides={self.overrides}>"
