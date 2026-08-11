"""User login session model.

Each row represents an authenticated session created at login. The session is
bound to the refresh token issued at login via ``refresh_jti`` (the token's
unique id). Revoking a session flips ``revoked`` so its refresh token can no
longer be exchanged for new access tokens — the session dies once the current
short-lived access token expires.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    # Unique id of the refresh token bound to this session.
    refresh_jti: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    device: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="sessions", foreign_keys=[user_id]
    )

    def __repr__(self) -> str:
        return f"<UserSession {self.id} user={self.user_id} revoked={self.revoked}>"
