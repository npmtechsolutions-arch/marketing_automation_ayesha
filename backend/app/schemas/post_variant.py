"""Schemas for per-platform post variants."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PostVariantUpsert(BaseModel):
    """Create or replace a platform's variant.

    Every field is optional and ``None`` means *inherit from the master post* --
    not "clear". Clearing an override is done by deleting the variant, or by
    sending an explicit empty value (``""`` / ``[]``), which is a deliberate
    choice to publish nothing there.
    """

    content: str | None = None
    # Ordered media ids. Order matters: it is the carousel order.
    media: list[UUID] | None = None
    link_url: str | None = Field(default=None, max_length=2048)
    # media id -> alt text, keyed by id so reordering cannot reassign them.
    alt_texts: dict[str, str] | None = None
    thumbnail_media_id: UUID | None = None
    first_comment: str | None = None


class PostVariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    platform_slug: str
    content: str | None = None
    media: list[UUID] = []
    link_url: str | None = None
    alt_texts: dict[str, str] = {}
    thumbnail_media_id: UUID | None = None
    first_comment: str | None = None
    # Which fields this variant actually overrides, so the composer can show
    # "inherited" against the rest.
    overrides: list[str] = []
    created_at: datetime
    updated_at: datetime | None = None


class ResolvedPreview(BaseModel):
    """What a platform would actually publish, master and variant combined."""

    platform: str
    content: str
    media: list[UUID] = []
    link_url: str | None = None
    first_comment: str | None = None
    overrides: list[str] = []


class ValidationErrorItem(BaseModel):
    platform: str
    field: str
    message: str
    severity: str = "error"


class PlatformValidationResult(BaseModel):
    platform: str
    accounts: list[str] = []
    ok: bool
    character_count: int
    character_limit: int | None = None
    media_count: int
    errors: list[ValidationErrorItem] = []


class PostValidationResponse(BaseModel):
    valid: bool
    platforms: list[PlatformValidationResult] = []
    # Flattened, for a caller that just wants to know what is wrong.
    errors: list[ValidationErrorItem] = []
