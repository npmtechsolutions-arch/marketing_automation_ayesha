"""The media library.

Uploads previously went to a single ``uploads/`` directory, were referenced by
URL strings in ``Post.media_urls``, and were never tracked: nobody could tell
what a workspace was storing, whether a file was still in use, or how much of
its storage allowance it had spent -- ``storage_bytes`` was an entitlement that
always reported zero because nothing counted anything.

These tables make media a first-class object: owned by a workspace, organised
into folders, attributed to an uploader, and linked to the posts that use it.
"""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Tags are a small array of short strings; JSONB on Postgres so they can be
# indexed and searched, plain JSON on SQLite for the test harness.
_JSON = JSONB().with_variant(JSON(), "sqlite")


class MediaKind(str, enum.Enum):
    """Coarse type, derived from the MIME type at confirm time.

    Stored rather than computed on read so the list endpoint can filter on it
    in SQL instead of pulling every row and filtering in Python.
    """

    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"


class MediaFolder(Base):
    """A folder in one workspace's library.

    Self-referential and unconstrained in depth. Names are unique among
    siblings so "New folder" twice in the same place is an error rather than
    two indistinguishable folders.
    """

    __tablename__ = "media_folders"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "parent_id", "name", name="uq_media_folder_sibling_name"
        ),
        Index("ix_media_folders_account_parent", "account_id", "parent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # NULL means the library root.
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_folders.id", ondelete="CASCADE"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    account = relationship("Account")
    parent = relationship("MediaFolder", remote_side=[id], back_populates="children")
    children = relationship(
        "MediaFolder", back_populates="parent", cascade="all, delete-orphan"
    )
    media = relationship("Media", back_populates="folder")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<MediaFolder {self.name!r}>"


class Media(Base):
    """One stored file."""

    __tablename__ = "media"
    __table_args__ = (
        # The list endpoint's default query: this workspace, not deleted,
        # newest first.
        Index("ix_media_account_created", "account_id", "created_at"),
        Index("ix_media_account_folder", "account_id", "folder_id"),
        # The object key is the identity in the bucket; two rows pointing at
        # one object would make deletion unsafe.
        UniqueConstraint("s3_key", name="uq_media_s3_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        # Deleting a folder must not delete the files in it; they fall back to
        # the root, where the user can still find them.
        ForeignKey("media_folders.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # Named s3_key even under the local backend: it is the object key in
    # whichever store is configured, and renaming it per backend would mean two
    # names for one concept.
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[MediaKind] = mapped_column(
        Enum(MediaKind, name="media_kind_enum"),
        default=MediaKind.IMAGE,
        nullable=False,
    )
    # BigInteger: a plan's storage allowance is measured in gigabytes, and a
    # single video can exceed int32 on its own.
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    alt_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(_JSON, nullable=True, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Soft delete. Media that a published post points at cannot be removed
    # outright without breaking the post's history, so deletion hides the row
    # and leaves the object in place.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    account = relationship("Account")
    folder = relationship("MediaFolder", back_populates="media")
    uploader = relationship("User")
    post_links = relationship(
        "PostMedia", back_populates="media", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Media {self.filename!r} {self.size_bytes}B>"


class PostMedia(Base):
    """Which posts use which media.

    Without this, "is this file still in use?" could only be answered by
    string-matching URLs inside ``Post.media_urls`` -- which misses a file
    referenced under a presigned URL that has since expired, and cannot tell a
    library file from a pasted external link.
    """

    __tablename__ = "post_media"
    __table_args__ = (
        # One link per pair: attaching the same image twice is one usage.
        UniqueConstraint("post_id", "media_id", name="uq_post_media"),
        Index("ix_post_media_media", "media_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    post = relationship("Post", back_populates="media_links")
    media = relationship("Media", back_populates="post_links")
