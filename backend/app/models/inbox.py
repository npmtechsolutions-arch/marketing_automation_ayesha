"""The unified inbox: threads and their messages.

A thread is one conversation with one person on one platform -- a comment
thread under a post, a DM conversation, or a single mention. Messages hang off
it in time order, including the ones the team writes.

Everything is keyed on the platform's own ``external_id``. Polling re-fetches
the same items every pass by design, so the id is what makes a sync idempotent:
without a unique constraint on it, every poll would duplicate the inbox.
"""

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base

_JSON = JSONB().with_variant(JSON(), "sqlite")


class ThreadType(str, enum.Enum):
    COMMENT = "comment"
    DM = "dm"
    MENTION = "mention"


class ThreadStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class MessageDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    # A note the team writes to each other. Never sent anywhere -- which is
    # why it is a direction rather than a flag: every query that means "what
    # did the customer see" filters on direction already, so a note cannot
    # leak into one by being forgotten.
    INTERNAL = "internal"


class InboxThread(Base):
    __tablename__ = "inbox_threads"
    __table_args__ = (
        # One thread per platform conversation. The connection is part of the
        # key because two workspaces can follow the same public post, and a
        # workspace can connect two accounts on one platform.
        UniqueConstraint(
            "social_account_id", "external_id", name="uq_inbox_thread_external"
        ),
        Index("ix_inbox_threads_account_activity", "account_id", "last_message_at"),
        Index("ix_inbox_threads_status", "account_id", "status"),
        Index("ix_inbox_threads_assignee", "assigned_to"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    social_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    type: Mapped[ThreadType] = mapped_column(
        Enum(ThreadType, name="inbox_thread_type_enum"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # The post or conversation this hangs off, when there is one. Null for a
    # mention, which lives on someone else's content.
    parent_external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    participant: Mapped[str] = mapped_column(String(200), nullable=False)
    participant_handle: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    permalink: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    status: Mapped[ThreadStatus] = mapped_column(
        Enum(ThreadStatus, name="inbox_thread_status_enum"),
        default=ThreadStatus.OPEN,
        nullable=False,
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    tags: Mapped[Optional[list[str]]] = mapped_column(_JSON, nullable=True)

    # Denormalised so the list can sort and preview without loading messages.
    # The inbox is read far more often than it is written.
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_message_preview: Mapped[Optional[str]] = mapped_column(String(280), nullable=True)
    unread_count: Mapped[int] = mapped_column(default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["InboxMessage"]] = relationship(
        "InboxMessage", back_populates="thread", cascade="all, delete-orphan",
        order_by="InboxMessage.created_at",
    )


class InboxMessage(Base):
    __tablename__ = "inbox_messages"
    __table_args__ = (
        # What makes the poll idempotent. Internal notes have no platform id,
        # so they carry a locally generated one rather than NULL: in SQL two
        # NULLs are distinct, so a nullable column here would not constrain
        # anything and would quietly let duplicates through.
        UniqueConstraint("thread_id", "external_id", name="uq_inbox_message_external"),
        Index("ix_inbox_messages_thread_time", "thread_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inbox_threads.id", ondelete="CASCADE"),
        nullable=False,
    )

    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection, name="inbox_message_direction_enum"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    author: Mapped[str] = mapped_column(String(200), nullable=False)
    author_handle: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # Set for anything a team member wrote, so a note or a reply can be
    # attributed to a person rather than to the workspace.
    author_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)
    media: Mapped[Optional[list[Any]]] = mapped_column(_JSON, nullable=True)

    # The platform's timestamp, not ours: ordering by when we happened to poll
    # would shuffle a conversation.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    thread: Mapped["InboxThread"] = relationship("InboxThread", back_populates="messages")
