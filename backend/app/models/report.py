"""Generated performance reports.

A report is a row plus up to three rendered files. The row is created
immediately and the rendering happens in the worker, because a quarter's
aggregation plus a PDF render is seconds of work and a request that holds the
connection for it will time out behind a proxy long before it finishes.

The period is stored as two **dates**, not a type plus an offset. "Last month"
computed at read time answers a different question every month, so a report
downloaded in December would silently re-aggregate as November's -- the numbers
under a fixed title would change. The window a report covers is fixed when it
is created and never recomputed.
"""

import enum
import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base

_JSON = JSONB().with_variant(JSON(), "sqlite")


class ReportType(str, enum.Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    CUSTOM = "custom"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class ReportFormat(str, enum.Enum):
    PDF = "pdf"
    CSV = "csv"
    XLSX = "xlsx"


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_account_created", "account_id", "created_at"),
        # The worker's queue query.
        Index("ix_reports_status", "status"),
        # Answers "has this period already been reported?", which is what makes
        # scheduled generation idempotent without a next_run_at to drift.
        Index("ix_reports_period", "account_id", "type", "period_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    # Null for a report the scheduler produced rather than a person.
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    type: Mapped[ReportType] = mapped_column(
        Enum(ReportType, name="report_type_enum"), nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Inclusive start, inclusive end, in the workspace's own timezone. Fixed at
    # creation -- see the module docstring.
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status_enum"),
        default=ReportStatus.PENDING,
        nullable=False,
    )

    # The white-label settings *as applied to this report*, copied rather than
    # read live. A customer who rebrands should not find last quarter's PDF has
    # silently changed colours, and a workspace that loses the white_label
    # entitlement should not retroactively lose branding it had paid for when
    # the file was made.
    branding: Mapped[Optional[dict[str, Any]]] = mapped_column(_JSON, nullable=True)

    # {"pdf": "reports/<account>/<id>.pdf", "csv": ..., "xlsx": ...}
    # A format missing from the map was not produced -- which is how a PDF
    # renders as absent rather than broken on a host without pango.
    file_keys: Mapped[Optional[dict[str, str]]] = mapped_column(_JSON, nullable=True)

    # The aggregated numbers, kept so the API can show a summary without
    # re-reading analytics or re-downloading a file.
    summary: Mapped[Optional[dict[str, Any]]] = mapped_column(_JSON, nullable=True)

    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
