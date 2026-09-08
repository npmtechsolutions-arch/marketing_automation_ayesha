"""Media validation, inspection and accounting.

The security-relevant idea here is that presigned uploads split validation in
two. Before the URL is issued we can only check what the client *claims* --
its declared MIME type and size. After the object lands we check what it
actually is. A client that lies at presign time is caught at confirm time, and
no row is written until then, so a lie produces an orphaned object rather than
a library entry.
"""

import io
import logging
import mimetypes
import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.media import Media, MediaKind
from app.models.organization import Organization
from app.services import entitlement_service as ent
from app.services.storage import ObjectInfo

logger = logging.getLogger(__name__)

# What the library accepts. Deliberately narrower than "anything the platforms
# take": every entry here is a format we can identify from its leading bytes,
# which is what makes the confirm-time check meaningful.
#
# SVG is absent on purpose -- it is a document format that executes script, and
# it was removed from the old upload endpoint for exactly that reason.
ALLOWED_TYPES: dict[str, MediaKind] = {
    "image/jpeg": MediaKind.IMAGE,
    "image/png": MediaKind.IMAGE,
    "image/gif": MediaKind.IMAGE,
    "image/webp": MediaKind.IMAGE,
    "video/mp4": MediaKind.VIDEO,
    "video/quicktime": MediaKind.VIDEO,
    "video/webm": MediaKind.VIDEO,
}

# Spellings that mean the same format.
_CANONICAL = {"image/jpg": "image/jpeg", "image/pjpeg": "image/jpeg"}

# Per-file ceiling, independent of the plan's total storage. A plan with 10GB
# should still not accept one 10GB file: it would occupy the whole allowance and
# no platform would take it.
MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_VIDEO_BYTES = 512 * 1024 * 1024

# Enough for the header of every format we accept. PNG needs 24, JPEG needs to
# walk its segments, WEBP 30, MP4's ftyp box sits in the first few dozen. 64KB
# is generous and still a single small ranged GET rather than a full download.
HEADER_BYTES = 64 * 1024


def canonical_type(mime_type: str) -> str:
    value = (mime_type or "").split(";")[0].strip().lower()
    return _CANONICAL.get(value, value)


def kind_for(mime_type: str) -> MediaKind:
    return ALLOWED_TYPES.get(canonical_type(mime_type), MediaKind.DOCUMENT)


def max_bytes_for(mime_type: str) -> int:
    return (
        MAX_VIDEO_BYTES
        if kind_for(mime_type) is MediaKind.VIDEO
        else MAX_IMAGE_BYTES
    )


def validate_declared_upload(filename: str, mime_type: str, size_bytes: int) -> str:
    """Check what the client says it will upload. Returns the canonical type.

    Everything here is a claim -- the real file is checked at confirm time.
    Rejecting early still matters: it saves the user a long upload that would
    have been refused, and it keeps obvious junk out of the bucket.
    """
    canonical = canonical_type(mime_type)
    if canonical not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"'{mime_type}' is not an accepted media type. Allowed: "
                + ", ".join(sorted(ALLOWED_TYPES))
            ),
        )
    if not filename or not filename.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A filename is required.",
        )
    if size_bytes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The declared file size must be greater than zero.",
        )

    ceiling = max_bytes_for(canonical)
    if size_bytes > ceiling:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"That file is {size_bytes // (1024 * 1024)}MB; the limit for this "
                f"type is {ceiling // (1024 * 1024)}MB."
            ),
        )
    return canonical


# ---------------------------------------------------------------------------
# Identifying what actually landed
# ---------------------------------------------------------------------------

def sniff_type(header: bytes) -> Optional[str]:
    """The real format, from the leading bytes.

    Same approach as the old upload endpoint: a Content-Type header is a claim
    by the uploader and cannot be trusted to decide what a file is.
    """
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"GIF8"):
        return "image/gif"
    if len(header) >= 12 and header[0:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand in (b"qt  ",):
            return "video/quicktime"
        return "video/mp4"
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    return None


def image_dimensions(data: bytes) -> tuple[Optional[int], Optional[int]]:
    """Width and height from an image header.

    Pillow parses lazily -- opening reads the header and stops -- so this works
    on the ranged prefix without the whole file. A failure is not fatal:
    dimensions are metadata for the UI, and refusing an otherwise valid upload
    because they could not be read would be the wrong trade.
    """
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as img:
            return img.width, img.height
    except Exception:  # noqa: BLE001 - unreadable header, not a fatal error
        logger.info("Could not read image dimensions from the header.", exc_info=True)
        return None, None


def verify_uploaded_object(
    info: ObjectInfo, header: bytes, declared_type: str, filename: str
) -> tuple[str, MediaKind]:
    """Check the object that actually landed. Returns (mime_type, kind).

    This is the half of validation that a lying client cannot get past: the
    size is what S3 measured, and the type comes from the file's own bytes.
    """
    if info.size_bytes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    actual = sniff_type(header)
    if actual is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The uploaded file is not a recognised image or video. Its "
                "contents do not match any accepted format."
            ),
        )
    if actual not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{actual}' is not an accepted media type.",
        )

    declared = canonical_type(declared_type)
    if actual != declared:
        # Not merely a mismatch to log: this is a client that asked to upload
        # one thing and uploaded another.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"The uploaded file is {actual}, but the upload was requested "
                f"as {declared}."
            ),
        )

    ceiling = max_bytes_for(actual)
    if info.size_bytes > ceiling:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"The uploaded file is {info.size_bytes // (1024 * 1024)}MB; the "
                f"limit for this type is {ceiling // (1024 * 1024)}MB."
            ),
        )
    return actual, ALLOWED_TYPES[actual]


def safe_filename(filename: str, mime_type: str) -> str:
    """A display name that cannot be mistaken for a path.

    The object key is generated server-side, so this only affects what the user
    sees and what a download is named -- but a filename containing a path
    separator ends up in a Content-Disposition header, and that is worth
    stripping.
    """
    cleaned = (filename or "").replace("\\", "/").split("/")[-1].strip()
    cleaned = "".join(c for c in cleaned if c.isprintable() and c not in '"\r\n')
    cleaned = cleaned[:255] or "upload"
    if "." not in cleaned:
        guessed = mimetypes.guess_extension(canonical_type(mime_type)) or ""
        cleaned += guessed
    return cleaned


# ---------------------------------------------------------------------------
# Storage accounting
# ---------------------------------------------------------------------------

async def storage_used_bytes(db: AsyncSession, organization_id) -> int:
    """Bytes stored across every workspace in an organization.

    Soft-deleted media is excluded. That is a deliberate choice with a cost:
    the object is still in the bucket, so what is billed by AWS and what is
    charged to the customer's plan diverge until a cleanup job removes it. The
    alternative -- counting files a user believes they deleted -- is worse.
    """
    stmt = (
        select(func.coalesce(func.sum(Media.size_bytes), 0))
        .join(Account, Account.id == Media.account_id)
        .where(
            Account.organization_id == organization_id,
            Media.deleted_at.is_(None),
        )
    )
    return int((await db.execute(stmt)).scalar() or 0)


async def enforce_storage_limit(
    db: AsyncSession, organization: Organization, additional_bytes: int
) -> None:
    """Refuse an upload that would take the organization over its allowance.

    Checked at presign time so the user is told before they spend minutes
    uploading, and again at confirm time because the declared size is a claim
    and several uploads can be in flight at once.
    """
    limit = await ent.get_limit(db, organization, ent.STORAGE_BYTES)
    if limit is None:  # unlimited
        return

    used = await storage_used_bytes(db, organization.id)
    if used + additional_bytes > limit:
        plan = organization.subscription_tier.value.title()
        raise ent.EntitlementExceeded(
            detail=(
                f"This upload would use {_human(used + additional_bytes)} of your "
                f"{plan} plan's {_human(limit)} of storage. Delete some files or "
                "upgrade your plan to continue."
            ),
            feature_key=ent.STORAGE_BYTES,
            limit=limit,
        )


def _human(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f}{unit}" if unit == "B" else f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}TB"


async def sync_post_media(
    db: AsyncSession, post_id, account_id, media_ids: Optional[list]
) -> None:
    """Make PostMedia match the ids the composer sent.

    ``None`` means "not mentioned", which leaves existing links alone -- a
    PATCH that only changes the caption must not detach the post's images. An
    empty list means "no attachments", which clears them.

    Ids are re-checked against the workspace rather than trusted: a post could
    otherwise claim usage of another tenant's file, which would both leak its
    existence and block that tenant from deleting it.
    """
    from app.models.media import Media as MediaModel
    from app.models.media import PostMedia

    if media_ids is None:
        return

    wanted = {mid for mid in media_ids if mid}
    if wanted:
        valid = set(
            (
                await db.execute(
                    select(MediaModel.id).where(
                        MediaModel.id.in_(wanted),
                        MediaModel.account_id == account_id,
                        MediaModel.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
        )
        rejected = wanted - valid
        if rejected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Some attached media could not be found in this workspace's "
                    "library."
                ),
            )
        wanted = valid

    existing = {
        link.media_id: link
        for link in (
            await db.execute(
                select(PostMedia).where(PostMedia.post_id == post_id)
            )
        ).scalars().all()
    }

    for media_id in wanted - set(existing):
        db.add(PostMedia(id=uuid.uuid4(), post_id=post_id, media_id=media_id))
    for media_id in set(existing) - wanted:
        await db.delete(existing[media_id])
    await db.flush()
