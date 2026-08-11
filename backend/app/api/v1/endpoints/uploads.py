"""Generic authenticated file-upload endpoint.

Stores uploaded images on local disk under ``settings``-configured uploads dir
and returns an absolute URL (built from the request host) that the frontend can
save straight into fields like ``avatar_url`` or a business ``logo_url``. Files
are served back as static assets mounted at ``/uploads`` in ``app.main``.
"""

import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from app.core.deps import get_current_active_user
from app.models.user import User

router = APIRouter()

# Where uploaded files land on disk. Kept next to the backend package so it
# survives restarts and is easy to mount as static files.
UPLOAD_DIR = Path(__file__).resolve().parents[4] / "uploads"

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


class UploadResponse(BaseModel):
    url: str
    filename: str


@router.post("/", response_model=UploadResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Upload an image and return a public URL to it."""
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{file.content_type}'. Upload a JPG, PNG, GIF, WEBP, or SVG image.",
        )

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 5 MB.",
        )

    ext = ALLOWED_CONTENT_TYPES[file.content_type]
    filename = f"{current_user.id}_{uuid.uuid4().hex}{ext}"

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / filename
    async with aiofiles.open(dest, "wb") as out:
        await out.write(contents)

    # Absolute URL against the backend host (e.g. http://localhost:8000/uploads/xyz.png)
    base = str(request.base_url).rstrip("/")
    return UploadResponse(url=f"{base}/uploads/{filename}", filename=filename)
