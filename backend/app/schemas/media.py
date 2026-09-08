"""Schemas for the media library."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# --- upload ----------------------------------------------------------------

class PresignRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=128)
    # What the client believes it is about to upload. A claim: the real size is
    # measured after the object lands, and confirm re-checks it.
    size_bytes: int = Field(gt=0)
    folder_id: UUID | None = None


class PresignResponse(BaseModel):
    upload_url: str
    method: str
    headers: dict[str, str]
    # Returned so confirm can name the object. It is generated server-side --
    # a client-supplied key would let a caller write anywhere in the bucket.
    key: str
    expires_in: int
    storage_backend: str


class ConfirmRequest(BaseModel):
    key: str = Field(min_length=1, max_length=1024)
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=128)
    folder_id: UUID | None = None
    alt_text: str | None = None
    tags: list[str] = []


# --- media -----------------------------------------------------------------

class MediaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    folder_id: UUID | None = None
    uploaded_by: UUID | None = None
    filename: str
    mime_type: str
    kind: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    alt_text: str | None = None
    tags: list[str] = []
    # How many posts attach this file. Drives the delete warning, and is the
    # reason PostMedia exists rather than string-matching URLs.
    used_in_posts: int = 0
    # Short-lived, re-issued per request; never stored.
    download_url: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class MediaUpdate(BaseModel):
    """Rename, retag, move. All optional; only what is sent is changed."""

    filename: str | None = Field(default=None, min_length=1, max_length=255)
    alt_text: str | None = None
    tags: list[str] | None = None


class MediaMove(BaseModel):
    # None moves it to the library root.
    folder_id: UUID | None = None


class MediaListResponse(BaseModel):
    items: list[MediaResponse]
    total: int
    page: int
    per_page: int
    pages: int
    # So the UI can show "2.1GB of 10GB" without a second call.
    storage_used_bytes: int
    storage_limit_bytes: int | None = None


# --- folders ---------------------------------------------------------------

class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: UUID | None = None


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: UUID | None = None


class FolderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    name: str
    parent_id: UUID | None = None
    media_count: int = 0
    created_at: datetime
