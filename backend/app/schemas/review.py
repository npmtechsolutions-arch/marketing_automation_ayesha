"""Schemas for the review workflow."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReviewAction(BaseModel):
    """A transition request. ``comment`` is required for request-changes."""

    comment: str | None = None


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)
    parent_id: UUID | None = None


class CommentUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)


class CommentAuthor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str
    avatar_url: str | None = None


class CommentResponse(BaseModel):
    id: UUID
    post_id: UUID
    author: CommentAuthor | None = None
    body: str
    mentions: list[UUID] = []
    parent_id: UUID | None = None
    created_at: datetime
    edited_at: datetime | None = None


class AssignmentUpdate(BaseModel):
    # None clears the assignment; omitted leaves it alone.
    assigned_to: UUID | None = None
    due_at: datetime | None = None


class ReviewState(BaseModel):
    """Everything the review panel needs in one call.

    ``allowed_actions`` is computed server-side so the UI offers exactly what
    the API will accept, rather than showing a button that 403s.
    """

    post_id: UUID
    status: str
    approvals_required: bool
    client_approval_required: bool
    allowed_actions: list[str] = []
    assigned_to: UUID | None = None
    due_at: datetime | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    comments: list[CommentResponse] = []
