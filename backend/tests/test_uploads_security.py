"""Security regression tests for the file-upload endpoint.

Locks down three defects:

1. ``image/svg+xml`` was accepted. An SVG can carry ``<script>``, and uploads
   are served from the application's own origin, so that is stored XSS.
2. The client's ``Content-Type`` header was trusted outright, so any bytes
   could be stored under any extension.
3. The whole request body was read into memory before the size was checked,
   letting a client choose how much memory to allocate.
"""

import io
import uuid

import pytest
from PIL import Image

from app.api.v1.endpoints.uploads import (
    ALLOWED_CONTENT_TYPES,
    MAX_UPLOAD_BYTES,
    UPLOAD_DIR,
    _sniff_image_type,
)

pytestmark = pytest.mark.asyncio

UPLOAD_URL = "/api/v1/uploads/"


def _image_bytes(fmt: str, size=(8, 8), color="red") -> bytes:
    """Render a real image of the given format."""
    buf = io.BytesIO()
    mode = "RGB" if fmt in {"JPEG", "WEBP"} else "RGBA" if fmt == "PNG" else "P"
    Image.new(mode if fmt != "GIF" else "P", size, color).save(buf, format=fmt)
    return buf.getvalue()


SVG_WITH_SCRIPT = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
    b'<script>alert(document.domain)</script>'
    b'<circle cx="50" cy="50" r="40" fill="red"/>'
    b'</svg>'
)


@pytest.fixture
def cleanup_uploads():
    """Remove any files the test created, so the repo's uploads dir stays clean."""
    before = set(UPLOAD_DIR.glob("*")) if UPLOAD_DIR.exists() else set()
    yield
    if UPLOAD_DIR.exists():
        for path in set(UPLOAD_DIR.glob("*")) - before:
            path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 1. SVG is rejected
# ---------------------------------------------------------------------------

async def test_svg_is_rejected(client, auth_header, user_factory, cleanup_uploads):
    """An SVG carrying <script> must not be storable."""
    user = await user_factory()

    response = await client.post(
        UPLOAD_URL,
        headers=auth_header(user),
        files={"file": ("payload.svg", SVG_WITH_SCRIPT, "image/svg+xml")},
    )

    assert response.status_code == 400
    assert "unsupported file type" in response.json()["detail"].lower()


async def test_svg_not_in_allowlist():
    assert "image/svg+xml" not in ALLOWED_CONTENT_TYPES


async def test_svg_disguised_as_png_is_rejected(
    client, auth_header, user_factory, cleanup_uploads
):
    """Relabelling the SVG as PNG must not get it past the check either."""
    user = await user_factory()

    response = await client.post(
        UPLOAD_URL,
        headers=auth_header(user),
        files={"file": ("payload.png", SVG_WITH_SCRIPT, "image/png")},
    )

    assert response.status_code == 400
    assert "do not match" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 2. Declared Content-Type is not trusted
# ---------------------------------------------------------------------------

async def test_png_label_with_jpeg_bytes_is_rejected(
    client, auth_header, user_factory, cleanup_uploads
):
    """The exact case from the report: JPEG bytes declared as PNG."""
    user = await user_factory()

    response = await client.post(
        UPLOAD_URL,
        headers=auth_header(user),
        files={"file": ("shot.png", _image_bytes("JPEG"), "image/png")},
    )

    assert response.status_code == 400
    assert "do not match" in response.json()["detail"].lower()


@pytest.mark.parametrize(
    "declared,actual_fmt",
    [
        ("image/png", "JPEG"),
        ("image/jpeg", "PNG"),
        ("image/gif", "PNG"),
        ("image/webp", "JPEG"),
    ],
)
async def test_mismatched_type_is_rejected(
    client, auth_header, user_factory, cleanup_uploads, declared, actual_fmt
):
    user = await user_factory()

    response = await client.post(
        UPLOAD_URL,
        headers=auth_header(user),
        files={"file": (f"x{ALLOWED_CONTENT_TYPES[declared]}", _image_bytes(actual_fmt), declared)},
    )

    assert response.status_code == 400


async def test_non_image_bytes_are_rejected(
    client, auth_header, user_factory, cleanup_uploads
):
    """An executable/script payload labelled as an image is rejected."""
    user = await user_factory()

    response = await client.post(
        UPLOAD_URL,
        headers=auth_header(user),
        files={"file": ("evil.png", b"<html><script>alert(1)</script></html>", "image/png")},
    )

    assert response.status_code == 400


async def test_valid_magic_but_undecodable_is_rejected(
    client, auth_header, user_factory, cleanup_uploads
):
    """A correct PNG header followed by garbage passes the magic check but must
    still fail Pillow's decode -- this is why there are two checks."""
    user = await user_factory()
    payload = b"\x89PNG\r\n\x1a\n" + b"\x00" * 512

    response = await client.post(
        UPLOAD_URL,
        headers=auth_header(user),
        files={"file": ("broken.png", payload, "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["detail"].lower().startswith(
        ("file is not a readable image", "file contents do not match")
    )


async def test_sniff_recognises_each_format():
    assert _sniff_image_type(_image_bytes("JPEG")[:12]) == "image/jpeg"
    assert _sniff_image_type(_image_bytes("PNG")[:12]) == "image/png"
    assert _sniff_image_type(_image_bytes("GIF")[:12]) == "image/gif"
    assert _sniff_image_type(_image_bytes("WEBP")[:12]) == "image/webp"
    assert _sniff_image_type(SVG_WITH_SCRIPT[:12]) is None
    assert _sniff_image_type(b"") is None


# ---------------------------------------------------------------------------
# 3. Size is enforced while streaming
# ---------------------------------------------------------------------------

async def test_oversized_upload_is_rejected(
    client, auth_header, user_factory, cleanup_uploads
):
    """A body over the cap gets 413, and nothing is left on disk."""
    user = await user_factory()
    oversized = _image_bytes("JPEG") + b"\x00" * (MAX_UPLOAD_BYTES + 1024)

    before = set(UPLOAD_DIR.glob("*")) if UPLOAD_DIR.exists() else set()
    response = await client.post(
        UPLOAD_URL,
        headers=auth_header(user),
        files={"file": ("big.jpg", oversized, "image/jpeg")},
    )

    assert response.status_code == 413
    after = set(UPLOAD_DIR.glob("*")) if UPLOAD_DIR.exists() else set()
    assert after == before, "an oversized upload left a file behind"


async def test_oversized_content_length_rejected_without_reading_file(
    client, auth_header, user_factory, monkeypatch, cleanup_uploads
):
    """The Content-Length short-circuit fires before the endpoint reads the file.

    Patch the class the endpoint actually receives -- Starlette's UploadFile,
    not FastAPI's subclass; the multipart parser constructs the former, so
    patching the latter silently does nothing.

    Scope: this proves the *endpoint* never reads the upload. It does not prove
    the body never reached the process -- Starlette parses the multipart form
    during dependency resolution, before this handler runs. See the note on
    _MULTIPART_OVERHEAD_ALLOWANCE in uploads.py.
    """
    from starlette.datastructures import UploadFile as StarletteUploadFile

    user = await user_factory()

    async def _explode(*args, **kwargs):
        raise AssertionError("endpoint read the file despite an oversized Content-Length")

    monkeypatch.setattr(StarletteUploadFile, "read", _explode)

    response = await client.post(
        UPLOAD_URL,
        headers=auth_header(user),
        files={"file": ("big.jpg", b"\xff\xd8\xff" + b"\x00" * (MAX_UPLOAD_BYTES * 2), "image/jpeg")},
    )

    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()


async def test_streaming_limit_holds_without_content_length_hint(
    client, auth_header, user_factory, monkeypatch, cleanup_uploads
):
    """Size must still be enforced when Content-Length cannot be trusted.

    Neutralising the header short-circuit leaves only the running byte count in
    the streaming loop, which must still produce a 413.
    """
    import app.api.v1.endpoints.uploads as uploads_mod

    user = await user_factory()
    # Make the header check unreachable, forcing reliance on the chunk counter.
    monkeypatch.setattr(uploads_mod, "_MULTIPART_OVERHEAD_ALLOWANCE", 1024 ** 3)

    response = await client.post(
        UPLOAD_URL,
        headers=auth_header(user),
        files={"file": ("big.jpg", _image_bytes("JPEG") + b"\x00" * (MAX_UPLOAD_BYTES + 2048), "image/jpeg")},
    )

    assert response.status_code == 413


async def test_partial_file_is_cleaned_up_on_rejection(
    client, auth_header, user_factory, cleanup_uploads
):
    """A rejected upload must not leave a .part file behind."""
    user = await user_factory()

    await client.post(
        UPLOAD_URL,
        headers=auth_header(user),
        files={"file": ("x.png", _image_bytes("JPEG"), "image/png")},
    )

    leftovers = list(UPLOAD_DIR.glob("*.part")) if UPLOAD_DIR.exists() else []
    assert leftovers == [], f"partial files left behind: {leftovers}"


# ---------------------------------------------------------------------------
# 4. Valid uploads still work
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "fmt,content_type",
    [
        ("JPEG", "image/jpeg"),
        ("PNG", "image/png"),
        ("GIF", "image/gif"),
        ("WEBP", "image/webp"),
    ],
)
async def test_valid_image_round_trips(
    client, auth_header, user_factory, cleanup_uploads, fmt, content_type
):
    """A genuine image of each accepted format uploads and lands on disk."""
    user = await user_factory()
    payload = _image_bytes(fmt)

    response = await client.post(
        UPLOAD_URL,
        headers=auth_header(user),
        files={"file": (f"pic{ALLOWED_CONTENT_TYPES[content_type]}", payload, content_type)},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["filename"].startswith(str(user.id))
    assert body["url"].endswith(body["filename"])

    stored = UPLOAD_DIR / body["filename"]
    assert stored.exists(), "upload reported success but no file was written"
    assert stored.read_bytes() == payload, "stored bytes differ from what was sent"


async def test_jpeg_declared_as_image_jpg_is_accepted(
    client, auth_header, user_factory, cleanup_uploads
):
    """'image/jpg' is a common non-standard spelling of 'image/jpeg'."""
    user = await user_factory()

    response = await client.post(
        UPLOAD_URL,
        headers=auth_header(user),
        files={"file": ("pic.jpg", _image_bytes("JPEG"), "image/jpg")},
    )

    assert response.status_code == 200, response.text


async def test_upload_requires_authentication(client, cleanup_uploads):
    response = await client.post(
        UPLOAD_URL,
        files={"file": ("pic.jpg", _image_bytes("JPEG"), "image/jpeg")},
    )
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 5. Served files carry X-Content-Type-Options: nosniff
# ---------------------------------------------------------------------------

async def test_served_upload_has_nosniff_header(
    client, auth_header, user_factory, cleanup_uploads
):
    """Uploads are served from our origin, so the browser must not sniff them."""
    user = await user_factory()

    upload = await client.post(
        UPLOAD_URL,
        headers=auth_header(user),
        files={"file": ("pic.png", _image_bytes("PNG"), "image/png")},
    )
    assert upload.status_code == 200, upload.text
    filename = upload.json()["filename"]

    served = await client.get(f"/uploads/{filename}")
    assert served.status_code == 200
    assert served.headers.get("x-content-type-options") == "nosniff"


async def test_nosniff_static_files_class_is_mounted():
    from app.api.v1.endpoints.uploads import NoSniffStaticFiles
    from app.main import app

    mount = next(r for r in app.routes if getattr(r, "name", "") == "uploads")
    assert isinstance(mount.app, NoSniffStaticFiles)


async def test_missing_upload_still_404s(client):
    response = await client.get(f"/uploads/{uuid.uuid4().hex}.png")
    assert response.status_code == 404
