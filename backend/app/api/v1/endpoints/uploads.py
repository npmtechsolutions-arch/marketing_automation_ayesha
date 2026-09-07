"""Generic authenticated file-upload endpoint.

Stores uploaded images on local disk under ``settings``-configured uploads dir
and returns an absolute URL (built from the request host) that the frontend can
save straight into fields like ``avatar_url`` or a business ``logo_url``. Files
are served back as static assets mounted at ``/uploads`` in ``app.main``.

Security notes
--------------
Uploaded files are served from the application's own origin, so anything the
browser will execute in that origin is effectively stored XSS. Three rules
follow from that, and all three are enforced below:

* **No SVG.** An SVG is an XML document that may contain ``<script>``; served
  from our origin it runs with our origin's privileges. There is no way to make
  a served SVG safe short of sanitising it, so the format is not accepted.
* **The client's ``Content-Type`` is a hint, not evidence.** It is attacker
  controlled, so the file's own bytes decide what it is: a magic-number check
  on the header, then a Pillow decode as a second opinion.
* **Size is enforced while streaming**, not after buffering. Reading the body
  first and checking the length afterwards means an attacker sets the memory
  cost, not us.
"""

import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

from app.core.deps import get_current_active_user
from app.models.user import User

router = APIRouter()

# Where uploaded files land on disk. Kept next to the backend package so it
# survives restarts and is easy to mount as static files.
UPLOAD_DIR = Path(__file__).resolve().parents[4] / "uploads"

# Declared content types we accept, and the extension each maps to.
# SVG is deliberately absent -- see the module docstring.
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

# Several spellings can mean the same format; compare canonical names.
_CANONICAL_TYPE = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/gif": "image/gif",
    "image/webp": "image/webp",
}

# The format Pillow should report for each canonical type.
_PILLOW_FORMAT = {
    "image/jpeg": {"JPEG"},
    "image/png": {"PNG"},
    "image/gif": {"GIF"},
    "image/webp": {"WEBP"},
}

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

# Read the body in chunks rather than all at once, so a huge upload is rejected
# after one chunk instead of after it is fully resident in memory.
CHUNK_SIZE = 64 * 1024

# Bytes needed before the format can be identified: WEBP needs the 'WEBP' tag
# at offset 8..12.
_MAGIC_PREFIX_BYTES = 12

# A multipart body is slightly larger than the file it carries (boundaries and
# part headers). Allow for that when short-circuiting on Content-Length, so a
# file just under the limit is not rejected because of envelope overhead.
#
# Scope of this guard: FastAPI resolves the ``UploadFile`` dependency -- which
# parses the multipart body -- before this handler runs, so by the time we look
# at Content-Length the body has already been received and spooled by Starlette
# (to a temp file once it exceeds its spool threshold, not held wholly in RAM).
# The check therefore saves the disk write and the decode, not the transfer.
# Rejecting before the body is read at all would need ASGI middleware that
# inspects the header ahead of routing; that is a larger change than this fix.
# What the streaming loop below does fix is the endpoint materialising the whole
# file as one bytes object on top of that spool -- it never holds more than
# CHUNK_SIZE.
_MULTIPART_OVERHEAD_ALLOWANCE = 8 * 1024


def _sniff_image_type(header: bytes) -> str | None:
    """Identify an image format from its magic number, or None if unrecognised."""
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"GIF8"):
        return "image/gif"
    if len(header) >= 12 and header[0:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    return None


def _verify_decodable(path: Path, expected_type: str) -> None:
    """Second check: Pillow must parse the file and agree on the format.

    The magic-number test only reads a handful of bytes, so it passes for a file
    with a valid header and arbitrary trailing content. Decoding rejects that,
    and also catches truncated or corrupt images.
    """
    try:
        with Image.open(path) as img:
            img.verify()
            detected = img.format
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not a readable image.",
        )

    if detected not in _PILLOW_FORMAT[expected_type]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File contents do not match the declared image type.",
        )


class UploadResponse(BaseModel):
    url: str
    filename: str


class NoSniffStaticFiles(StaticFiles):
    """StaticFiles that sends ``X-Content-Type-Options: nosniff``.

    Stops a browser from MIME-sniffing an uploaded file into something
    executable regardless of the Content-Type we serve it with.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


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
            detail=(
                f"Unsupported file type '{file.content_type}'. "
                "Upload a JPG, PNG, GIF, or WEBP image."
            ),
        )
    declared_type = _CANONICAL_TYPE[file.content_type]

    # Cheapest possible rejection: the client already told us it is too big.
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_UPLOAD_BYTES + _MULTIPART_OVERHEAD_ALLOWANCE:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="File too large. Maximum size is 5 MB.",
                )
        except ValueError:
            # Malformed header: ignore it and rely on the streaming counter.
            pass

    ext = ALLOWED_CONTENT_TYPES[file.content_type]
    filename = f"{current_user.id}_{uuid.uuid4().hex}{ext}"

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / filename
    # Stream to a partial file so a rejected upload never appears at the final
    # name, even briefly.
    partial = dest.with_suffix(dest.suffix + ".part")

    total = 0
    header = b""
    try:
        async with aiofiles.open(partial, "wb") as out:
            while chunk := await file.read(CHUNK_SIZE):
                total += len(chunk)
                # Enforce the limit as the bytes arrive: stop at the first chunk
                # that crosses it rather than buffering the whole body.
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="File too large. Maximum size is 5 MB.",
                    )

                # Check the magic number as soon as enough bytes have arrived,
                # so a mismatched file is rejected without reading the rest.
                if len(header) < _MAGIC_PREFIX_BYTES:
                    header += chunk[: _MAGIC_PREFIX_BYTES - len(header)]
                    if len(header) >= _MAGIC_PREFIX_BYTES:
                        sniffed = _sniff_image_type(header)
                        if sniffed is None or sniffed != declared_type:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=(
                                    "File contents do not match the declared "
                                    "image type."
                                ),
                            )

                await out.write(chunk)

        if total == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        # A file shorter than the magic prefix never reached the check above.
        if len(header) < _MAGIC_PREFIX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File contents do not match the declared image type.",
            )

        # Second opinion: the bytes must actually decode as that format.
        _verify_decodable(partial, declared_type)

        partial.replace(dest)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    # Absolute URL against the backend host (e.g. http://localhost:8000/uploads/xyz.png)
    base = str(request.base_url).rstrip("/")
    return UploadResponse(url=f"{base}/uploads/{filename}", filename=filename)
