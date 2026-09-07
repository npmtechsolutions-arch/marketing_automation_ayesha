"""Durable, observable publishing.

Publishing used to happen inline: an endpoint flipped a post to PUBLISHING and
fired a background task that looped over the target accounts. Nothing about
that was recoverable or visible. If the process died mid-loop the post sat in
PUBLISHING until a sweeper reset the *whole post* and republished every target
-- including the ones that had already succeeded. A per-target failure was a
string in a JSON blob with no attempt count, no next-retry time, and no record
of what the platform actually said.

One job per (post, social account) makes each target independently
retryable, and each attempt leaves a log row carrying the platform's own
response.
"""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class JobStatus(str, enum.Enum):
    """Where a job is in its life.

    CLAIMED and RUNNING are separate on purpose. A worker claims a batch in one
    short transaction and only then starts executing, so a row stuck in CLAIMED
    means the process died between the two -- which is safe to requeue. A row
    stuck in RUNNING means it died mid-publish, where the platform may already
    have the post; the recovery sweep treats them the same but the distinction
    is preserved in the log so an operator can tell which happened.
    """

    QUEUED = "queued"
    CLAIMED = "claimed"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


# The statuses a job can still move out of. Used by the claim query and by the
# post-status derivation, so "is this finished?" has one definition.
TERMINAL_STATUSES = (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED)


class LogLevel(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class PublishingJob(Base):
    """One target account's share of publishing one post."""

    __tablename__ = "publishing_jobs"
    __table_args__ = (
        # The claim query's exact shape: due, still runnable, oldest first.
        Index("ix_publishing_jobs_claim", "status", "run_at"),
        Index("ix_publishing_jobs_post", "post_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    # No FK cascade to social_accounts: disconnecting an account must not erase
    # the record of what was published through it.
    social_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_accounts.id"), nullable=False
    )

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="publishing_job_status_enum"),
        default=JobStatus.QUEUED,
        nullable=False,
    )
    # When the job becomes eligible. Backoff is expressed by pushing this
    # forward rather than by sleeping, so a retry survives a restart.
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, default=3, server_default="3", nullable=False
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Which worker holds it, and since when. claimed_at is what the stale-claim
    # sweep reads; claimed_by is only for operators reading the table.
    claimed_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # The outcome, kept on the job so a post's results can be derived from its
    # jobs rather than from a parallel JSON blob that can disagree with them.
    # A YouTube Community post has no API. Such a job is FAILED -- retrying
    # cannot help -- but the UI shows a "publish by hand" helper rather than a
    # red error, so the distinction has to survive. Not in the status enum
    # because it is a *reason* for failing, not a state to be in.
    manual_required: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    external_post_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    post_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    post = relationship("Post", back_populates="publishing_jobs")
    social_account = relationship("SocialAccount", lazy="selectin")
    logs = relationship(
        "PublishingLog",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="PublishingLog.created_at",
    )

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def attempts_remaining(self) -> int:
        return max(0, (self.max_attempts or 0) - (self.attempts or 0))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<PublishingJob {self.id} {self.status.value} attempt {self.attempts}>"


class PublishingLog(Base):
    """One line in a job's history.

    ``platform_response`` holds whatever the platform sent back. It is the
    difference between "failed" and "failed because the page token was revoked
    on the 3rd of the month", and it is the first thing anyone asks for when a
    customer says their post did not go out.
    """

    __tablename__ = "publishing_logs"
    __table_args__ = (Index("ix_publishing_logs_job_created", "job_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publishing_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    level: Mapped[LogLevel] = mapped_column(
        Enum(LogLevel, name="publishing_log_level_enum"),
        default=LogLevel.INFO,
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # JSONB on Postgres, JSON on SQLite -- the test harness builds from the
    # models, so the type has to degrade rather than fail.
    platform_response: Mapped[Optional[dict]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    job = relationship("PublishingJob", back_populates="logs")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<PublishingLog {self.level.value} {self.message[:40]!r}>"
