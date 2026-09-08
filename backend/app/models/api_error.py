"""Unhandled 5xx responses, kept so they can be looked at later.

The exception handler already logs to stderr. That is fine on a laptop and
useless in production: nobody reads a log stream continuously, the interesting
line has scrolled away by the time a customer reports the problem, and there is
no way to ask "how often does this happen" or "is it only this one workspace".

Only *unhandled* exceptions land here. A deliberate ``HTTPException`` -- a 403,
a 404, a validation error -- is the application working, and storing those
would bury the real failures under a mountain of expected ones.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Postgres has no practical row limit, but a runaway recursion produces a trace
# megabytes long, and a thousand of those is a table nobody can query. The tail
# is the useful half -- it holds the frame that actually raised.
MAX_TRACEBACK_CHARS = 8_000
MAX_MESSAGE_CHARS = 1_000


class ApiError(Base):
    __tablename__ = "api_errors"
    __table_args__ = (
        Index("ix_api_errors_created", "created_at"),
        # The two filters the admin page offers, each of which would otherwise
        # scan the whole table.
        Index("ix_api_errors_class_created", "exception_class", "created_at"),
        Index("ix_api_errors_path_created", "path", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    path: Mapped[str] = mapped_column(String(500), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    exception_class: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # No foreign keys. An error row must outlive whatever it refers to -- the
    # point of keeping it is to investigate afterwards, and a cascade from a
    # deleted user would erase exactly the evidence of what went wrong for
    # them. Null means the request was unauthenticated or the identity could
    # not be read.
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
