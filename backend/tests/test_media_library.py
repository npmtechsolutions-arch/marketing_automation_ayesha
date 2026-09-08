"""The media library: presign, confirm, CRUD, usage and isolation.

Uploads go straight to object storage, so validation is split in two: presign
checks what the client *claims* it will upload, and confirm checks what
actually landed. Most of what is worth testing lives in that gap -- a client
that declares a small PNG and uploads a large video is the case the design has
to survive.

Storage is a real in-memory :class:`StorageBackend` subclass rather than a
mock, so the endpoints exercise the same interface S3 implements. The S3
backend itself is covered separately with botocore's Stubber.
"""

import io
import uuid

import pytest
from sqlalchemy import select

from app.models.media import Media, PostMedia
from app.services import media_service, storage

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


def png_bytes(width: int = 120, height: int = 80) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), "purple").save(buf, "PNG")
    return buf.getvalue()


def jpeg_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), "red").save(buf, "JPEG")
    return buf.getvalue()


class FakeStorage(storage.StorageBackend):
    """An in-memory bucket implementing the real interface.

    A subclass rather than a MagicMock: it has to actually store bytes, because
    the confirm path reads them back to determine the file's real type and
    dimensions. A mock would let a broken confirm pass.
    """

    name = "fake"

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def presign_upload(self, key, content_type, *, max_bytes=None):
        return storage.PresignedUpload(
            url=f"https://fake-bucket.example/{key}?signed=1",
            method="PUT",
            headers={"Content-Type": content_type},
            key=key,
            expires_in=900,
        )

    def put(self, key: str, data: bytes) -> None:
        """Stands in for the client's PUT to the presigned URL."""
        self.objects[key] = data

    def put_object(self, key: str, data: bytes, *, content_type: str = "") -> None:
        """A server-side write. The media library never uses this -- browsers
        upload straight to the presigned URL -- but the interface requires it,
        which is what stops a backend shipping without it."""
        self.objects[key] = data

    def head(self, key):
        if key not in self.objects:
            raise storage.ObjectNotFound(key)
        return storage.ObjectInfo(key=key, size_bytes=len(self.objects[key]))

    def read_range(self, key, *, length):
        if key not in self.objects:
            raise storage.ObjectNotFound(key)
        return self.objects[key][:length]

    def presign_download(self, key):
        return f"https://fake-bucket.example/{key}?download=1"

    def delete(self, key):
        self.deleted.append(key)
        self.objects.pop(key, None)


@pytest.fixture
def fake_storage(monkeypatch):
    backend = FakeStorage()
    monkeypatch.setattr(storage, "get_storage", lambda: backend)
    return backend


@pytest.fixture
async def workspace(user_factory, account_factory, organization_factory):
    owner = await user_factory(password=PASSWORD)
    organization = await organization_factory(owner)
    account = await account_factory(owner, organization=organization)
    return {
        "owner": owner, "organization": organization, "account": account,
        # Captured before anything expires these instances.
        "account_id": account.id,
    }


def _url(account_id, suffix=""):
    return f"/api/v1/accounts/{account_id}/media{suffix}"


async def _upload(client, auth_header, ws, fake_storage, *, data=None,
                  filename="photo.png", mime="image/png", folder_id=None, tags=None):
    """The whole client flow: presign, PUT, confirm."""
    data = png_bytes() if data is None else data
    headers = auth_header(ws["owner"])

    presign = await client.post(
        _url(ws["account"].id, "/presign"), headers=headers,
        json={
            "filename": filename, "mime_type": mime, "size_bytes": len(data),
            **({"folder_id": str(folder_id)} if folder_id else {}),
        },
    )
    if presign.status_code != 200:
        return presign, None

    key = presign.json()["key"]
    fake_storage.put(key, data)  # the browser's PUT

    confirm = await client.post(
        _url(ws["account"].id, "/confirm"), headers=headers,
        json={
            "key": key, "filename": filename, "mime_type": mime,
            **({"folder_id": str(folder_id)} if folder_id else {}),
            **({"tags": tags} if tags else {}),
        },
    )
    return confirm, key


# ---------------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------------

async def test_presign_then_confirm_creates_the_row(
    client, auth_header, workspace, fake_storage, db_session
):
    response, key = await _upload(client, auth_header, workspace, fake_storage)
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["filename"] == "photo.png"
    assert body["mime_type"] == "image/png"
    assert body["kind"] == "image"
    assert body["size_bytes"] == len(png_bytes())
    # Read from the file's own header, not from anything the client sent.
    assert (body["width"], body["height"]) == (120, 80)
    assert body["used_in_posts"] == 0
    assert body["download_url"]

    rows = (await db_session.execute(select(Media))).scalars().all()
    assert len(rows) == 1 and rows[0].s3_key == key


async def test_presign_returns_a_server_generated_key(
    client, auth_header, workspace, fake_storage
):
    """The client must not choose the key: it decides where in the bucket the
    object lands, and a client-supplied one could target another workspace."""
    response = await client.post(
        _url(workspace["account_id"], "/presign"),
        headers=auth_header(workspace["owner"]),
        json={"filename": "x.png", "mime_type": "image/png", "size_bytes": 100},
    )
    key = response.json()["key"]
    assert key.startswith(f"media/{workspace['account'].id}/")
    assert "x.png" not in key, "the key should not be guessable from the filename"


async def test_confirm_reads_dimensions_from_the_header_only(
    client, auth_header, workspace, fake_storage
):
    """Pillow parses lazily, so a ranged prefix is enough -- the endpoint never
    pulls the whole object through the API process."""
    response, _ = await _upload(
        client, auth_header, workspace, fake_storage, data=png_bytes(1000, 250)
    )
    assert (response.json()["width"], response.json()["height"]) == (1000, 250)


# ---------------------------------------------------------------------------
# What a lying client gets
# ---------------------------------------------------------------------------

async def test_confirm_rejects_a_file_that_is_not_what_was_declared(
    client, auth_header, workspace, fake_storage, db_session
):
    """The point of confirming against the stored bytes.

    Declaring a PNG and uploading a JPEG is benign; declaring an image and
    uploading something else entirely is not, and only the post-upload check
    can tell.
    """
    headers = auth_header(workspace["owner"])
    presign = await client.post(
        _url(workspace["account_id"], "/presign"), headers=headers,
        json={"filename": "photo.png", "mime_type": "image/png", "size_bytes": 500},
    )
    key = presign.json()["key"]
    fake_storage.put(key, jpeg_bytes())  # not the declared type

    confirm = await client.post(
        _url(workspace["account_id"], "/confirm"), headers=headers,
        json={"key": key, "filename": "photo.png", "mime_type": "image/png"},
    )
    assert confirm.status_code == 400
    assert "image/jpeg" in confirm.json()["detail"]
    assert (await db_session.execute(select(Media))).scalars().all() == []


async def test_confirm_rejects_content_that_is_not_media(
    client, auth_header, workspace, fake_storage
):
    headers = auth_header(workspace["owner"])
    presign = await client.post(
        _url(workspace["account_id"], "/presign"), headers=headers,
        json={"filename": "a.png", "mime_type": "image/png", "size_bytes": 40},
    )
    key = presign.json()["key"]
    fake_storage.put(key, b"<?php system($_GET['c']); ?>")

    confirm = await client.post(
        _url(workspace["account_id"], "/confirm"), headers=headers,
        json={"key": key, "filename": "a.png", "mime_type": "image/png"},
    )
    assert confirm.status_code == 400
    assert "not a recognised" in confirm.json()["detail"]


async def test_confirm_without_an_upload_is_refused(
    client, auth_header, workspace, fake_storage
):
    """Nothing was ever PUT, so there is no object to record."""
    headers = auth_header(workspace["owner"])
    presign = await client.post(
        _url(workspace["account_id"], "/presign"), headers=headers,
        json={"filename": "a.png", "mime_type": "image/png", "size_bytes": 40},
    )
    confirm = await client.post(
        _url(workspace["account_id"], "/confirm"), headers=headers,
        json={"key": presign.json()["key"], "filename": "a.png",
              "mime_type": "image/png"},
    )
    assert confirm.status_code == 400
    assert "may not have completed" in confirm.json()["detail"]


async def test_confirm_cannot_adopt_another_workspaces_key(
    client, auth_header, workspace, user_factory, account_factory, fake_storage
):
    """Otherwise a caller could confirm a key they observed and take ownership
    of someone else's uploaded file."""
    other_owner = await user_factory()
    other = await account_factory(other_owner, name="Other")
    foreign_key = f"media/{other.id}/{uuid.uuid4().hex}.png"
    fake_storage.put(foreign_key, png_bytes())

    response = await client.post(
        _url(workspace["account_id"], "/confirm"),
        headers=auth_header(workspace["owner"]),
        json={"key": foreign_key, "filename": "x.png", "mime_type": "image/png"},
    )
    assert response.status_code == 400
    assert "does not belong to this workspace" in response.json()["detail"]


async def test_confirming_twice_is_refused(
    client, auth_header, workspace, fake_storage
):
    """A replayed confirm would create a second row for one object, and then
    deleting either would break the other."""
    first, key = await _upload(client, auth_header, workspace, fake_storage)
    assert first.status_code == 201

    again = await client.post(
        _url(workspace["account_id"], "/confirm"),
        headers=auth_header(workspace["owner"]),
        json={"key": key, "filename": "photo.png", "mime_type": "image/png"},
    )
    assert again.status_code == 409


@pytest.mark.parametrize(
    "mime,detail",
    [
        ("image/svg+xml", "not an accepted media type"),
        ("application/pdf", "not an accepted media type"),
        ("text/html", "not an accepted media type"),
    ],
)
async def test_presign_refuses_types_the_library_does_not_take(
    client, auth_header, workspace, fake_storage, mime, detail
):
    """SVG is absent deliberately: it is a document format that executes
    script, and it was removed from the old upload endpoint for that reason."""
    response = await client.post(
        _url(workspace["account_id"], "/presign"),
        headers=auth_header(workspace["owner"]),
        json={"filename": "x", "mime_type": mime, "size_bytes": 100},
    )
    assert response.status_code == 400
    assert detail in response.json()["detail"]


async def test_presign_refuses_a_file_over_the_per_type_ceiling(
    client, auth_header, workspace, fake_storage
):
    """Independent of the plan: one 25MB+ image would occupy an allowance and
    no platform would take it."""
    response = await client.post(
        _url(workspace["account_id"], "/presign"),
        headers=auth_header(workspace["owner"]),
        json={
            "filename": "huge.png", "mime_type": "image/png",
            "size_bytes": media_service.MAX_IMAGE_BYTES + 1,
        },
    )
    assert response.status_code == 413


# ---------------------------------------------------------------------------
# Storage entitlement
# ---------------------------------------------------------------------------

async def test_presign_refuses_when_the_plan_is_out_of_storage(
    client, auth_header, workspace, fake_storage, set_limit
):
    await set_limit(workspace["organization"], "storage_bytes", 1000)

    response = await client.post(
        _url(workspace["account_id"], "/presign"),
        headers=auth_header(workspace["owner"]),
        json={"filename": "x.png", "mime_type": "image/png", "size_bytes": 5000},
    )
    assert response.status_code == 402
    assert "storage" in response.json()["detail"].lower()


async def test_storage_is_counted_across_uploads(
    client, auth_header, workspace, fake_storage, set_limit, db_session
):
    """storage_bytes used to always report zero -- nothing counted anything."""
    from app.services import entitlement_service as ent

    await set_limit(workspace["organization"], "storage_bytes", 10_000)
    first, _ = await _upload(client, auth_header, workspace, fake_storage)
    assert first.status_code == 201

    used = await ent.current_usage(
        db_session, workspace["organization"], ent.STORAGE_BYTES
    )
    assert used == first.json()["size_bytes"] > 0


async def test_confirm_rechecks_the_limit_against_the_real_size(
    client, auth_header, workspace, fake_storage, set_limit, db_session
):
    """The presign check used a number the client supplied. A client that
    declares 10 bytes and uploads a megabyte is caught here, and the object is
    deleted rather than left orphaned in the bucket.
    """
    await set_limit(workspace["organization"], "storage_bytes", 500)
    headers = auth_header(workspace["owner"])

    presign = await client.post(
        _url(workspace["account_id"], "/presign"), headers=headers,
        json={"filename": "small.png", "mime_type": "image/png", "size_bytes": 10},
    )
    assert presign.status_code == 200, "a 10-byte claim fits the allowance"
    key = presign.json()["key"]
    fake_storage.put(key, png_bytes(400, 400))  # far larger than declared

    confirm = await client.post(
        _url(workspace["account_id"], "/confirm"), headers=headers,
        json={"key": key, "filename": "small.png", "mime_type": "image/png"},
    )
    assert confirm.status_code == 402
    assert key in fake_storage.deleted, "the oversized object must not be left behind"
    assert (await db_session.execute(select(Media))).scalars().all() == []


# ---------------------------------------------------------------------------
# Listing, search, filter, sort
# ---------------------------------------------------------------------------

async def test_list_search_filter_and_sort(
    client, auth_header, workspace, fake_storage
):
    headers = auth_header(workspace["owner"])
    await _upload(client, auth_header, workspace, fake_storage,
                  filename="alpha.png", tags=["brand", "hero"])
    await _upload(client, auth_header, workspace, fake_storage,
                  filename="beta.png", data=png_bytes(400, 400))

    listing = (await client.get(_url(workspace["account_id"], "/"), headers=headers)).json()
    assert listing["total"] == 2
    assert listing["storage_used_bytes"] > 0

    by_name = await client.get(
        _url(workspace["account_id"], "/?search=alpha"), headers=headers
    )
    assert [m["filename"] for m in by_name.json()["items"]] == ["alpha.png"]

    by_tag = await client.get(
        _url(workspace["account_id"], "/?search=hero"), headers=headers
    )
    assert [m["filename"] for m in by_tag.json()["items"]] == ["alpha.png"]

    by_size = await client.get(
        _url(workspace["account_id"], "/?sort=size&order=desc"), headers=headers
    )
    sizes = [m["size_bytes"] for m in by_size.json()["items"]]
    assert sizes == sorted(sizes, reverse=True)

    videos = await client.get(
        _url(workspace["account_id"], "/?kind=video"), headers=headers
    )
    assert videos.json()["total"] == 0


# ---------------------------------------------------------------------------
# Rename, move, folders
# ---------------------------------------------------------------------------

async def test_rename_and_retag(client, auth_header, workspace, fake_storage):
    created, _ = await _upload(client, auth_header, workspace, fake_storage)
    media_id = created.json()["id"]

    response = await client.patch(
        _url(workspace["account_id"], f"/{media_id}"),
        headers=auth_header(workspace["owner"]),
        json={"filename": "renamed.png", "tags": ["a", "b"], "alt_text": "A logo"},
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "renamed.png"
    assert response.json()["tags"] == ["a", "b"]
    assert response.json()["alt_text"] == "A logo"


async def test_a_filename_cannot_carry_a_path(
    client, auth_header, workspace, fake_storage
):
    created, _ = await _upload(client, auth_header, workspace, fake_storage)
    response = await client.patch(
        _url(workspace["account_id"], f"/{created.json()['id']}"),
        headers=auth_header(workspace["owner"]),
        json={"filename": "../../etc/passwd"},
    )
    # Path segments stripped. The extension is appended because the name had
    # none -- what matters is that no separator survives into a
    # Content-Disposition header.
    assert "/" not in response.json()["filename"]
    assert response.json()["filename"].startswith("passwd")


async def test_folder_crud_and_move(
    client, auth_header, workspace, fake_storage, db_session
):
    headers = auth_header(workspace["owner"])

    folder = await client.post(
        _url(workspace["account_id"], "/folders/"), headers=headers,
        json={"name": "Campaign assets"},
    )
    assert folder.status_code == 201
    folder_id = folder.json()["id"]

    created, _ = await _upload(client, auth_header, workspace, fake_storage)
    moved = await client.post(
        _url(workspace["account_id"], f"/{created.json()['id']}/move"),
        headers=headers, json={"folder_id": folder_id},
    )
    assert moved.status_code == 200
    assert moved.json()["folder_id"] == folder_id

    folders = (
        await client.get(_url(workspace["account_id"], "/folders/"), headers=headers)
    ).json()
    assert folders[0]["media_count"] == 1

    in_folder = await client.get(
        _url(workspace["account_id"], f"/?folder_id={folder_id}"), headers=headers
    )
    assert in_folder.json()["total"] == 1


async def test_duplicate_sibling_folder_name_is_refused(
    client, auth_header, workspace
):
    headers = auth_header(workspace["owner"])
    body = {"name": "Logos"}
    assert (
        await client.post(_url(workspace["account_id"], "/folders/"), headers=headers, json=body)
    ).status_code == 201
    second = await client.post(
        _url(workspace["account_id"], "/folders/"), headers=headers, json=body
    )
    assert second.status_code == 409


async def test_a_folder_cannot_be_moved_inside_itself(
    client, auth_header, workspace
):
    """That would detach the whole subtree from the root, where nothing could
    reach it again."""
    headers = auth_header(workspace["owner"])
    parent = (await client.post(
        _url(workspace["account_id"], "/folders/"), headers=headers, json={"name": "P"}
    )).json()
    child = (await client.post(
        _url(workspace["account_id"], "/folders/"), headers=headers,
        json={"name": "C", "parent_id": parent["id"]},
    )).json()

    response = await client.patch(
        _url(workspace["account_id"], f"/folders/{parent['id']}"),
        headers=headers, json={"parent_id": child["id"]},
    )
    assert response.status_code == 400
    assert "inside itself" in response.json()["detail"]


async def test_deleting_a_folder_keeps_its_files(
    client, auth_header, workspace, fake_storage, db_session
):
    headers = auth_header(workspace["owner"])
    folder = (await client.post(
        _url(workspace["account_id"], "/folders/"), headers=headers, json={"name": "Temp"}
    )).json()
    created, _ = await _upload(
        client, auth_header, workspace, fake_storage, folder_id=folder["id"]
    )

    response = await client.delete(
        _url(workspace["account_id"], f"/folders/{folder['id']}"), headers=headers
    )
    assert response.status_code == 200

    db_session.expire_all()
    media = (await db_session.execute(select(Media))).scalars().one()
    assert media.deleted_at is None, "the file must survive its folder"
    assert media.folder_id is None, "and fall back to the root"


# ---------------------------------------------------------------------------
# Usage tracking and deletion
# ---------------------------------------------------------------------------

async def test_attaching_media_to_a_post_counts_as_usage(
    client, auth_header, workspace, fake_storage, db_session
):
    created, _ = await _upload(client, auth_header, workspace, fake_storage)
    media_id = created.json()["id"]
    headers = auth_header(workspace["owner"])

    post = await client.post(
        f"/api/v1/accounts/{workspace['account_id']}/posts/", headers=headers,
        json={"content": "With a picture", "target_accounts": [],
              "media_ids": [media_id]},
    )
    assert post.status_code == 201, post.text

    detail = await client.get(
        _url(workspace["account_id"], f"/{media_id}"), headers=headers
    )
    assert detail.json()["used_in_posts"] == 1

    links = (await db_session.execute(select(PostMedia))).scalars().all()
    assert len(links) == 1


async def test_detaching_media_drops_the_usage(
    client, auth_header, workspace, fake_storage
):
    created, _ = await _upload(client, auth_header, workspace, fake_storage)
    media_id = created.json()["id"]
    headers = auth_header(workspace["owner"])

    post = (await client.post(
        f"/api/v1/accounts/{workspace['account_id']}/posts/", headers=headers,
        json={"content": "x", "target_accounts": [], "media_ids": [media_id]},
    )).json()

    await client.put(
        f"/api/v1/accounts/{workspace['account_id']}/posts/{post['id']}",
        headers=headers, json={"media_ids": []},
    )
    detail = await client.get(
        _url(workspace["account_id"], f"/{media_id}"), headers=headers
    )
    assert detail.json()["used_in_posts"] == 0


async def test_an_edit_that_does_not_mention_media_leaves_it_attached(
    client, auth_header, workspace, fake_storage
):
    """None means "not mentioned". A caption-only edit must not silently
    detach the post's images."""
    created, _ = await _upload(client, auth_header, workspace, fake_storage)
    media_id = created.json()["id"]
    headers = auth_header(workspace["owner"])

    post = (await client.post(
        f"/api/v1/accounts/{workspace['account_id']}/posts/", headers=headers,
        json={"content": "x", "target_accounts": [], "media_ids": [media_id]},
    )).json()

    await client.put(
        f"/api/v1/accounts/{workspace['account_id']}/posts/{post['id']}",
        headers=headers, json={"content": "a new caption"},
    )
    detail = await client.get(
        _url(workspace["account_id"], f"/{media_id}"), headers=headers
    )
    assert detail.json()["used_in_posts"] == 1


async def test_a_post_cannot_attach_another_workspaces_media(
    client, auth_header, workspace, user_factory, account_factory,
    organization_factory, fake_storage
):
    """It would both disclose that the file exists and block its owner from
    deleting it."""
    other_owner = await user_factory(password=PASSWORD)
    other_org = await organization_factory(other_owner)
    other = await account_factory(other_owner, organization=other_org, name="Other")
    foreign, _ = await _upload(
        client, auth_header,
        {"owner": other_owner, "organization": other_org, "account": other},
        fake_storage,
    )

    response = await client.post(
        f"/api/v1/accounts/{workspace['account_id']}/posts/",
        headers=auth_header(workspace["owner"]),
        json={"content": "x", "target_accounts": [],
              "media_ids": [foreign.json()["id"]]},
    )
    assert response.status_code == 400
    assert "library" in response.json()["detail"].lower()


async def test_delete_is_soft_and_warns_when_in_use(
    client, auth_header, workspace, fake_storage, db_session
):
    """The object stays so the post's history keeps working, and the message
    says so -- "deleted" meaning two different things is worse than a longer
    sentence."""
    created, key = await _upload(client, auth_header, workspace, fake_storage)
    media_id = created.json()["id"]
    headers = auth_header(workspace["owner"])
    await client.post(
        f"/api/v1/accounts/{workspace['account_id']}/posts/", headers=headers,
        json={"content": "x", "target_accounts": [], "media_ids": [media_id]},
    )

    response = await client.delete(_url(workspace["account_id"], f"/{media_id}"), headers=headers)
    assert response.status_code == 200
    assert "still used by 1 post" in response.json()["message"]

    db_session.expire_all()
    media = (await db_session.execute(select(Media))).scalars().one()
    assert media.deleted_at is not None
    assert key in fake_storage.objects, "the stored object must be kept"

    gone = await client.get(_url(workspace["account_id"], f"/{media_id}"), headers=headers)
    assert gone.status_code == 404


async def test_deleted_media_stops_counting_against_storage(
    client, auth_header, workspace, fake_storage, db_session
):
    from app.services import entitlement_service as ent

    created, _ = await _upload(client, auth_header, workspace, fake_storage)
    await client.delete(
        _url(workspace["account_id"], f"/{created.json()['id']}"),
        headers=auth_header(workspace["owner"]),
    )
    used = await ent.current_usage(
        db_session, workspace["organization"], ent.STORAGE_BYTES
    )
    assert used == 0


# ---------------------------------------------------------------------------
# Tenancy and permissions
# ---------------------------------------------------------------------------

async def test_another_workspace_cannot_see_or_touch_the_library(
    client, auth_header, workspace, user_factory, account_factory, fake_storage
):
    created, _ = await _upload(client, auth_header, workspace, fake_storage)
    media_id = created.json()["id"]

    stranger = await user_factory()
    stranger_account = await account_factory(stranger, name="Stranger")

    # Not a member of this workspace at all.
    assert (await client.get(
        _url(workspace["account_id"], "/"), headers=auth_header(stranger)
    )).status_code == 403

    # A member of their own workspace, reaching for a file id from another.
    for method, suffix in (
        ("get", f"/{media_id}"), ("delete", f"/{media_id}"),
    ):
        response = await getattr(client, method)(
            _url(stranger_account.id, suffix), headers=auth_header(stranger)
        )
        assert response.status_code == 404, (
            f"{method} {suffix} leaked another workspace's media"
        )


async def test_a_viewer_can_browse_but_not_upload_or_delete(
    client, auth_header, workspace, user_factory, member_factory, fake_storage
):
    from app.models.team_member import InvitationStatus, TeamRole

    created, _ = await _upload(client, auth_header, workspace, fake_storage)
    viewer = await user_factory()
    await member_factory(
        viewer, workspace["account"], role=TeamRole.VIEWER,
        invitation_status=InvitationStatus.ACCEPTED,
    )
    headers = auth_header(viewer)
    account_id = workspace["account"].id

    assert (await client.get(_url(account_id, "/"), headers=headers)).status_code == 200
    assert (await client.post(
        _url(account_id, "/presign"), headers=headers,
        json={"filename": "x.png", "mime_type": "image/png", "size_bytes": 10},
    )).status_code == 403
    assert (await client.delete(
        _url(account_id, f"/{created.json()['id']}"), headers=headers
    )).status_code == 403


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def test_local_backend_only_outside_production(monkeypatch):
    """Writing user media to a container filesystem looks like it works right
    up until the next deploy throws it away."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "S3_BUCKET", "")
    monkeypatch.setattr(settings, "DEBUG", True)
    assert storage.get_storage().name == "local"

    monkeypatch.setattr(settings, "DEBUG", False)
    with pytest.raises(storage.StorageError) as exc:
        storage.get_storage()
    assert "S3_BUCKET" in str(exc.value)


def test_local_backend_refuses_a_key_that_escapes_its_root(tmp_path):
    """Keys are generated server-side, but this is the last line before a
    filesystem write."""
    backend = storage.LocalStorageBackend(root=tmp_path)
    with pytest.raises(storage.StorageError):
        backend.path_for("../../etc/passwd")


def test_local_presigned_urls_are_signed_and_expire(monkeypatch, tmp_path):
    """Without the signature the shim would accept a PUT to any path a caller
    invented, which is an arbitrary file write."""
    import time

    backend = storage.LocalStorageBackend(root=tmp_path)
    upload = backend.presign_upload("media/abc/x.png", "image/png")
    params = dict(
        pair.split("=", 1) for pair in upload.url.split("?", 1)[1].split("&")
    )

    assert storage.LocalStorageBackend.verify(
        params["key"], int(params["expires"]), params["signature"]
    )
    assert not storage.LocalStorageBackend.verify(
        params["key"], int(params["expires"]), "0" * 64
    )
    assert not storage.LocalStorageBackend.verify(
        params["key"], int(time.time()) - 1,
        storage.LocalStorageBackend._sign(params["key"], int(time.time()) - 1),
    )


# ---------------------------------------------------------------------------
# The S3 backend itself
#
# FakeStorage above proves the endpoints use the interface correctly; these
# prove S3Backend implements it correctly. botocore's Stubber asserts the exact
# API calls without a network or a moto dependency.
# ---------------------------------------------------------------------------

@pytest.fixture
def s3_backend(monkeypatch):
    from botocore.stub import Stubber

    from app.core.config import settings

    monkeypatch.setattr(settings, "S3_BUCKET", "test-bucket")
    monkeypatch.setattr(settings, "S3_REGION", "us-east-1")
    monkeypatch.setattr(settings, "S3_ACCESS_KEY", "AKIATEST")
    monkeypatch.setattr(settings, "S3_SECRET_KEY", "secret")
    monkeypatch.setattr(settings, "S3_ENDPOINT_URL", "")

    backend = storage.S3Backend()
    stubber = Stubber(backend._client)
    stubber.activate()
    yield backend, stubber
    stubber.deactivate()


def test_s3_head_returns_the_real_size(s3_backend):
    backend, stubber = s3_backend
    stubber.add_response(
        "head_object",
        {"ContentLength": 4096, "ContentType": "image/png"},
        {"Bucket": "test-bucket", "Key": "media/a/b.png"},
    )
    info = backend.head("media/a/b.png")
    assert info.size_bytes == 4096
    assert info.content_type == "image/png"
    stubber.assert_no_pending_responses()


def test_s3_missing_object_raises_object_not_found(s3_backend):
    """Confirm depends on telling "never uploaded" apart from "S3 is down"."""
    backend, stubber = s3_backend
    stubber.add_client_error("head_object", service_error_code="404", http_status_code=404)
    with pytest.raises(storage.ObjectNotFound):
        backend.head("media/a/missing.png")


def test_s3_other_errors_are_not_mistaken_for_missing(s3_backend):
    backend, stubber = s3_backend
    stubber.add_client_error("head_object", service_error_code="AccessDenied", http_status_code=403)
    with pytest.raises(storage.StorageError) as exc:
        backend.head("media/a/b.png")
    assert not isinstance(exc.value, storage.ObjectNotFound)


def test_s3_reads_only_the_requested_prefix(s3_backend):
    """A ranged GET is what keeps a 500MB video from being pulled through the
    API process just to read its header."""
    backend, stubber = s3_backend
    stubber.add_response(
        "get_object",
        {"Body": io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)},
        {"Bucket": "test-bucket", "Key": "media/a/b.png", "Range": "bytes=0-1023"},
    )
    data = backend.read_range("media/a/b.png", length=1024)
    assert data.startswith(b"\x89PNG")
    stubber.assert_no_pending_responses()


def test_s3_presigned_upload_is_a_put_that_pins_the_content_type(s3_backend):
    """S3 signs Content-Type, so the client must send the one we signed --
    which is also what stops it uploading a different kind of file to a URL
    issued for an image."""
    backend, _ = s3_backend
    presigned = backend.presign_upload("media/a/b.png", "image/png")

    assert presigned.method == "PUT"
    assert presigned.headers["Content-Type"] == "image/png"
    assert "test-bucket" in presigned.url
    assert "media/a/b.png" in presigned.url
    assert "X-Amz-Signature" in presigned.url
    assert f"X-Amz-Expires={storage.PRESIGN_EXPIRY_SECONDS}" in presigned.url


def test_s3_presigned_download_expires(s3_backend):
    backend, _ = s3_backend
    url = backend.presign_download("media/a/b.png")
    assert "X-Amz-Signature" in url
    assert f"X-Amz-Expires={storage.DOWNLOAD_EXPIRY_SECONDS}" in url


def test_s3_is_chosen_whenever_a_bucket_is_configured(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "S3_BUCKET", "prod-bucket")
    monkeypatch.setattr(settings, "DEBUG", True)
    # Even in DEBUG: a configured bucket means someone meant to use it.
    assert storage.get_storage().name == "s3"
