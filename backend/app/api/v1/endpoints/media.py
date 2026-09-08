"""The media library.

Uploads go straight to object storage: the client asks for a presigned URL,
PUTs the file to it, then tells us it landed. We never carry the bytes, which
is what makes a 500MB video upload possible without holding a worker for its
duration.

The two-step flow is also where validation lives. ``/presign`` checks what the
client *claims* -- type, declared size, the organization's remaining storage.
``/confirm`` checks what actually arrived: that the object exists, its real
size, and its real format read from the leading bytes. Nothing is recorded
until confirm succeeds, so a client that lies produces an orphaned object
rather than a library entry.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import verify_account_access as _verify_account_access
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.permissions import CONTENT_CREATE, CONTENT_DELETE, CONTENT_VIEW
from app.models.media import Media, MediaFolder, MediaKind, PostMedia
from app.schemas.common import MessageResponse
from app.schemas.media import (
    ConfirmRequest,
    FolderCreate,
    FolderResponse,
    FolderUpdate,
    MediaListResponse,
    MediaMove,
    MediaResponse,
    MediaUpdate,
    PresignRequest,
    PresignResponse,
)
from app.services import entitlement_service as ent
from app.services import media_service, storage

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_media_or_404(
    media_id: uuid.UUID, account_id: uuid.UUID, db: AsyncSession
) -> Media:
    """Scoped on account_id: that is the tenancy boundary, and a 404 rather
    than a 403 so the existence of another workspace's file is not disclosed."""
    media = (
        await db.execute(
            select(Media).where(
                Media.id == media_id,
                Media.account_id == account_id,
                Media.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if media is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media not found"
        )
    return media


async def _get_folder_or_404(
    folder_id: uuid.UUID, account_id: uuid.UUID, db: AsyncSession
) -> MediaFolder:
    folder = (
        await db.execute(
            select(MediaFolder).where(
                MediaFolder.id == folder_id, MediaFolder.account_id == account_id
            )
        )
    ).scalar_one_or_none()
    if folder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found"
        )
    return folder



async def _assert_name_free(
    db: AsyncSession,
    account_id: uuid.UUID,
    parent_id: Optional[uuid.UUID],
    name: str,
    *,
    exclude_id: Optional[uuid.UUID] = None,
) -> None:
    """Refuse a duplicate name among siblings.

    Checked here rather than relying on the unique constraint alone: SQL treats
    NULLs as distinct, so ``(account_id, NULL, 'Logos')`` twice does not violate
    it and two identically named folders appear at the library root. The
    constraint still backstops the non-root case.
    """
    conditions = [
        MediaFolder.account_id == account_id,
        func.lower(MediaFolder.name) == name.strip().lower(),
        MediaFolder.parent_id == parent_id
        if parent_id is not None
        else MediaFolder.parent_id.is_(None),
    ]
    if exclude_id is not None:
        conditions.append(MediaFolder.id != exclude_id)

    clash = (
        await db.execute(select(MediaFolder.id).where(and_(*conditions)).limit(1))
    ).scalar_one_or_none()
    if clash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A folder named '{name.strip()}' already exists here.",
        )


async def _usage_counts(db: AsyncSession, media_ids: list[uuid.UUID]) -> dict:
    """How many posts use each file, in one query rather than one per row."""
    if not media_ids:
        return {}
    rows = (
        await db.execute(
            select(PostMedia.media_id, func.count(PostMedia.post_id))
            .where(PostMedia.media_id.in_(media_ids))
            .group_by(PostMedia.media_id)
        )
    ).all()
    return {media_id: count for media_id, count in rows}


def _to_response(
    media: Media, *, used_in_posts: int = 0, download_url: Optional[str] = None
) -> MediaResponse:
    return MediaResponse(
        id=media.id,
        account_id=media.account_id,
        folder_id=media.folder_id,
        uploaded_by=media.uploaded_by,
        filename=media.filename,
        mime_type=media.mime_type,
        kind=media.kind.value,
        size_bytes=media.size_bytes,
        width=media.width,
        height=media.height,
        duration_seconds=media.duration_seconds,
        alt_text=media.alt_text,
        tags=list(media.tags or []),
        used_in_posts=used_in_posts,
        download_url=download_url,
        created_at=media.created_at,
        updated_at=media.updated_at,
    )


def _backend():
    try:
        return storage.get_storage()
    except storage.StorageError as exc:
        # A misconfigured deployment, not a bad request.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@router.post("/presign", response_model=PresignResponse)
async def presign_upload(
    account_id: uuid.UUID,
    payload: PresignRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Hand back a short-lived URL to upload straight to storage."""
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )

    canonical = media_service.validate_declared_upload(
        payload.filename, payload.mime_type, payload.size_bytes
    )
    if payload.folder_id is not None:
        await _get_folder_or_404(payload.folder_id, account_id, db)

    # Checked here so the user is refused before uploading, and again at
    # confirm because this size is only a claim.
    organization = await ent.get_organization_for_account(db, account_id)
    await media_service.enforce_storage_limit(db, organization, payload.size_bytes)

    backend = _backend()
    key = storage.build_key(account_id, payload.filename)
    try:
        presigned = backend.presign_upload(key, canonical)
    except storage.StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    return PresignResponse(
        upload_url=presigned.url,
        method=presigned.method,
        headers=presigned.headers,
        key=presigned.key,
        expires_in=presigned.expires_in,
        storage_backend=backend.name,
    )


@router.post(
    "/confirm", response_model=MediaResponse, status_code=status.HTTP_201_CREATED
)
async def confirm_upload(
    account_id: uuid.UUID,
    payload: ConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Record the upload, after verifying what actually landed."""
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )

    # The key is ours to generate, so a caller must not be able to confirm one
    # belonging to another workspace and adopt their file.
    if not payload.key.startswith(f"media/{account_id}/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That upload key does not belong to this workspace.",
        )

    existing = (
        await db.execute(select(Media.id).where(Media.s3_key == payload.key))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This upload has already been confirmed.",
        )

    if payload.folder_id is not None:
        await _get_folder_or_404(payload.folder_id, account_id, db)

    backend = _backend()
    try:
        info = backend.head(payload.key)
        header = backend.read_range(payload.key, length=media_service.HEADER_BYTES)
    except storage.ObjectNotFound:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No uploaded file was found for that key. The upload may not "
                "have completed."
            ),
        ) from None
    except storage.StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    mime_type, kind = media_service.verify_uploaded_object(
        info, header, payload.mime_type, payload.filename
    )

    # Re-checked against the measured size: the presign check used a number the
    # client supplied, and several uploads can be in flight at once.
    organization = await ent.get_organization_for_account(db, account_id)
    try:
        await media_service.enforce_storage_limit(db, organization, info.size_bytes)
    except ent.EntitlementExceeded:
        # The object is over the allowance, so it must not stay in the bucket
        # unreferenced -- nothing would ever clean it up.
        try:
            backend.delete(payload.key)
        except storage.StorageError:
            pass
        raise

    width = height = None
    if kind is MediaKind.IMAGE:
        width, height = media_service.image_dimensions(header)

    media = Media(
        id=uuid.uuid4(),
        account_id=account_id,
        folder_id=payload.folder_id,
        uploaded_by=current_user.id,
        filename=media_service.safe_filename(payload.filename, mime_type),
        s3_key=payload.key,
        mime_type=mime_type,
        kind=kind,
        size_bytes=info.size_bytes,
        width=width,
        height=height,
        alt_text=payload.alt_text,
        tags=[t.strip() for t in (payload.tags or []) if t and t.strip()][:32],
    )
    db.add(media)
    await db.flush()
    await db.refresh(media)
    return _to_response(media, download_url=backend.presign_download(media.s3_key))


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

_SORTS = {
    "date": Media.created_at,
    "name": Media.filename,
    "size": Media.size_bytes,
}


@router.get("/", response_model=MediaListResponse)
async def list_media(
    account_id: uuid.UUID,
    search: str | None = Query(None, description="Matches filename or tag"),
    kind: str | None = Query(None, description="image | video | document"),
    folder_id: uuid.UUID | None = Query(None),
    root_only: bool = Query(False, description="Only files not in any folder"),
    sort: str = Query("date", pattern="^(date|name|size)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)

    filters = [Media.account_id == account_id, Media.deleted_at.is_(None)]
    if folder_id is not None:
        filters.append(Media.folder_id == folder_id)
    elif root_only:
        filters.append(Media.folder_id.is_(None))

    if kind:
        try:
            filters.append(Media.kind == MediaKind(kind))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown media kind '{kind}'.",
            ) from None

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        # Tags are JSON, so they are matched as text. Good enough for a
        # library of this size and it avoids a dialect-specific JSON operator
        # that would not work on the SQLite test harness.
        filters.append(
            or_(
                func.lower(Media.filename).like(term),
                func.lower(cast(Media.tags, String)).like(term),
            )
        )

    total = (
        await db.execute(select(func.count(Media.id)).where(and_(*filters)))
    ).scalar() or 0

    column = _SORTS[sort]
    ordering = column.desc() if order == "desc" else column.asc()
    rows = (
        await db.execute(
            select(Media)
            .where(and_(*filters))
            .order_by(ordering)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).scalars().all()

    usage = await _usage_counts(db, [m.id for m in rows])
    backend = _backend()
    organization = await ent.get_organization_for_account(db, account_id)

    return MediaListResponse(
        items=[
            _to_response(
                m,
                used_in_posts=usage.get(m.id, 0),
                download_url=backend.presign_download(m.s3_key),
            )
            for m in rows
        ],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page else 1,
        storage_used_bytes=await media_service.storage_used_bytes(
            db, organization.id
        ),
        storage_limit_bytes=await ent.get_limit(db, organization, ent.STORAGE_BYTES),
    )


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------

@router.get("/folders/", response_model=list[FolderResponse])
async def list_folders(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Every folder in the workspace, flat. The client builds the tree -- it is
    small, and one query beats a recursive walk."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)

    folders = (
        await db.execute(
            select(MediaFolder)
            .where(MediaFolder.account_id == account_id)
            .order_by(MediaFolder.name)
        )
    ).scalars().all()

    counts = dict(
        (
            await db.execute(
                select(Media.folder_id, func.count(Media.id))
                .where(Media.account_id == account_id, Media.deleted_at.is_(None))
                .group_by(Media.folder_id)
            )
        ).all()
    )
    return [
        FolderResponse(
            id=f.id, account_id=f.account_id, name=f.name, parent_id=f.parent_id,
            media_count=counts.get(f.id, 0), created_at=f.created_at,
        )
        for f in folders
    ]


@router.post(
    "/folders/", response_model=FolderResponse, status_code=status.HTTP_201_CREATED
)
async def create_folder(
    account_id: uuid.UUID,
    payload: FolderCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )
    if payload.parent_id is not None:
        await _get_folder_or_404(payload.parent_id, account_id, db)
    await _assert_name_free(db, account_id, payload.parent_id, payload.name)

    folder = MediaFolder(
        id=uuid.uuid4(),
        account_id=account_id,
        name=payload.name.strip(),
        parent_id=payload.parent_id,
    )
    db.add(folder)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A folder named '{payload.name}' already exists here.",
        ) from None
    await db.refresh(folder)
    return FolderResponse(
        id=folder.id, account_id=folder.account_id, name=folder.name,
        parent_id=folder.parent_id, media_count=0, created_at=folder.created_at,
    )


@router.patch("/folders/{folder_id}", response_model=FolderResponse)
async def update_folder(
    account_id: uuid.UUID,
    folder_id: uuid.UUID,
    payload: FolderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )
    folder = await _get_folder_or_404(folder_id, account_id, db)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )

    if "name" in updates and updates["name"]:
        folder.name = updates["name"].strip()
    if "parent_id" in updates:
        new_parent = updates["parent_id"]
        if new_parent == folder.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A folder cannot be its own parent.",
            )
        if new_parent is not None:
            parent = await _get_folder_or_404(new_parent, account_id, db)
            # Walk up from the new parent: moving a folder inside its own
            # descendant would detach that whole subtree from the root, where
            # nothing could reach it again.
            seen = {folder.id}
            cursor = parent
            while cursor is not None:
                if cursor.id in seen:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="That move would put the folder inside itself.",
                    )
                seen.add(cursor.id)
                cursor = (
                    await _get_folder_or_404(cursor.parent_id, account_id, db)
                    if cursor.parent_id
                    else None
                )
        folder.parent_id = new_parent

    await _assert_name_free(
        db, account_id, folder.parent_id, folder.name, exclude_id=folder.id
    )
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A folder with that name already exists there.",
        ) from None
    await db.refresh(folder)
    return FolderResponse(
        id=folder.id, account_id=folder.account_id, name=folder.name,
        parent_id=folder.parent_id, media_count=0, created_at=folder.created_at,
    )


@router.delete("/folders/{folder_id}", response_model=MessageResponse)
async def delete_folder(
    account_id: uuid.UUID,
    folder_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Delete a folder. Its files move to the root rather than being deleted --
    removing a folder should not destroy what was filed in it."""
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_DELETE
    )
    folder = await _get_folder_or_404(folder_id, account_id, db)
    await db.delete(folder)
    await db.flush()
    return MessageResponse(message="Folder deleted; its files moved to the library root.")


# Folder routes are declared before /{media_id}: FastAPI matches in order,
# and a literal segment placed after a UUID parameter would be parsed as one.
@router.get("/{media_id}", response_model=MediaResponse)
async def get_media(
    account_id: uuid.UUID,
    media_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    media = await _get_media_or_404(media_id, account_id, db)
    usage = await _usage_counts(db, [media.id])
    return _to_response(
        media,
        used_in_posts=usage.get(media.id, 0),
        download_url=_backend().presign_download(media.s3_key),
    )


@router.get("/{media_id}/download")
async def download_media(
    account_id: uuid.UUID,
    media_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """A fresh presigned GET.

    Re-issued per request and short-lived, rather than stored, so revoking
    someone's access to the workspace revokes their access to its files.
    """
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    media = await _get_media_or_404(media_id, account_id, db)
    return {"download_url": _backend().presign_download(media.s3_key)}


# ---------------------------------------------------------------------------
# Mutating
# ---------------------------------------------------------------------------

@router.patch("/{media_id}", response_model=MediaResponse)
async def update_media(
    account_id: uuid.UUID,
    media_id: uuid.UUID,
    payload: MediaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Rename, retag, or set alt text. The stored object is untouched."""
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )
    media = await _get_media_or_404(media_id, account_id, db)

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )
    if "filename" in updates and updates["filename"]:
        media.filename = media_service.safe_filename(
            updates["filename"], media.mime_type
        )
    if "alt_text" in updates:
        media.alt_text = updates["alt_text"]
    if "tags" in updates and updates["tags"] is not None:
        media.tags = [t.strip() for t in updates["tags"] if t and t.strip()][:32]

    await db.flush()
    await db.refresh(media)
    usage = await _usage_counts(db, [media.id])
    return _to_response(media, used_in_posts=usage.get(media.id, 0))


@router.post("/{media_id}/move", response_model=MediaResponse)
async def move_media(
    account_id: uuid.UUID,
    media_id: uuid.UUID,
    payload: MediaMove,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )
    media = await _get_media_or_404(media_id, account_id, db)

    if payload.folder_id is not None:
        await _get_folder_or_404(payload.folder_id, account_id, db)
    media.folder_id = payload.folder_id
    await db.flush()
    await db.refresh(media)
    usage = await _usage_counts(db, [media.id])
    return _to_response(media, used_in_posts=usage.get(media.id, 0))


@router.delete("/{media_id}", response_model=MessageResponse)
async def delete_media(
    account_id: uuid.UUID,
    media_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Soft delete.

    Media attached to a post is never removed outright: the object stays so the
    post's history keeps working, and the row is only hidden. The response says
    so when the file was in use, because "deleted" meaning two different things
    is worse than a slightly longer message.
    """
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_DELETE
    )
    media = await _get_media_or_404(media_id, account_id, db)

    usage = (await _usage_counts(db, [media.id])).get(media.id, 0)
    media.deleted_at = datetime.now(timezone.utc)
    await db.flush()

    if usage:
        return MessageResponse(
            message=(
                f"Removed from the library. The file is still used by {usage} "
                f"post{'s' if usage != 1 else ''}, so it has been kept in "
                "storage and those posts are unaffected."
            )
        )
    return MessageResponse(message="Media deleted.")


# ---------------------------------------------------------------------------
# Local storage fallback (DEBUG only)
#
# S3 has no equivalent of these: the browser PUTs to AWS directly. They exist so
# the client-side flow is identical when no bucket is configured, which is the
# point -- a development path that differs from production hides bugs.
# ---------------------------------------------------------------------------

local_router = APIRouter()


def _local_backend_or_404(key: str, expires: int, signature: str):
    from app.core.config import settings

    if settings.S3_BUCKET or not settings.DEBUG:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if not storage.LocalStorageBackend.verify(key, expires, signature):
        # Unsigned or expired. Without this the endpoint would accept a PUT to
        # any path a caller invented.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This upload link is invalid or has expired.",
        )
    return storage.LocalStorageBackend()


@local_router.put("/local-upload")
async def local_upload(
    request: Request,
    key: str = Query(...),
    expires: int = Query(...),
    signature: str = Query(...),
):
    backend = _local_backend_or_404(key, expires, signature)
    body = await request.body()
    if not body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload."
        )
    backend.write(key, body)
    return {"key": key, "size_bytes": len(body)}


@local_router.get("/local-download")
async def local_download(
    key: str = Query(...),
    expires: int = Query(...),
    signature: str = Query(...),
):
    backend = _local_backend_or_404(key, expires, signature)
    try:
        info = backend.head(key)
        data = backend.path_for(key).read_bytes()
    except storage.ObjectNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        ) from None
    return Response(
        content=data,
        media_type=info.content_type or "application/octet-stream",
        # Never let a browser sniff a stored file into something executable.
        headers={"X-Content-Type-Options": "nosniff"},
    )
