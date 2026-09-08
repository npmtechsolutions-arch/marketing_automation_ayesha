"""Object storage for the media library.

Two backends behind one interface. S3 is the real one; the local backend keeps
development working when no bucket is configured, and is refused outside DEBUG
so a misconfigured production cannot silently start writing user media to a
container filesystem that disappears on the next deploy.

**Why presigned uploads at all.** The obvious design -- POST the file to us, we
forward it to S3 -- makes every upload cost twice the bandwidth and holds a
worker for the duration of a 100MB video. Presigning hands the client a
short-lived URL to PUT straight to the bucket; we only see the small confirm
call afterwards.

That splits validation in two, and the split is the security-relevant part.
Before the URL is issued we check what the client *says* it will upload (type,
declared size, the organization's remaining storage). After it lands we check
what it *actually* uploaded (the object exists, its real size, its real format
from the leading bytes). A client that lies at presign time is caught at
confirm time, and nothing is recorded until then.
"""

import hashlib
import hmac
import logging
import mimetypes
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# How long a presigned URL stays valid. Long enough for a large upload on a
# poor connection, short enough that a leaked URL is not a standing grant.
PRESIGN_EXPIRY_SECONDS = 15 * 60
# Presigned download links are re-issued per request, so they can be shorter.
DOWNLOAD_EXPIRY_SECONDS = 5 * 60


class StorageError(Exception):
    """The backend could not complete the operation."""


class ObjectNotFound(StorageError):
    """No object at that key. At confirm time this means the client never
    actually uploaded, which is the case worth telling them about."""


@dataclass(frozen=True)
class PresignedUpload:
    url: str
    method: str
    # Headers the client must send with the PUT. S3 signs Content-Type, so
    # sending a different one invalidates the signature.
    headers: dict[str, str]
    key: str
    expires_in: int


@dataclass(frozen=True)
class ObjectInfo:
    key: str
    size_bytes: int
    content_type: Optional[str] = None


class StorageBackend(ABC):
    """What the media endpoints need from storage, and nothing more."""

    name: str = "abstract"

    @abstractmethod
    def presign_upload(
        self, key: str, content_type: str, *, max_bytes: Optional[int] = None
    ) -> PresignedUpload:
        ...

    @abstractmethod
    def head(self, key: str) -> ObjectInfo:
        """Size and type of a stored object. Raises ObjectNotFound if absent."""

    @abstractmethod
    def read_range(self, key: str, *, length: int) -> bytes:
        """The first ``length`` bytes.

        Ranged so image dimensions can be read from the header without pulling
        a 100MB video through the API process.
        """

    @abstractmethod
    def put_object(
        self, key: str, data: bytes, *, content_type: str = "application/octet-stream"
    ) -> None:
        """Write bytes from the server.

        Distinct from ``presign_upload``, which hands the browser a URL and
        never sees the file. Reports are rendered in the worker, so their bytes
        exist in this process and have to be written from here.
        """

    @abstractmethod
    def presign_download(self, key: str) -> str:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        ...


# ---------------------------------------------------------------------------
# S3
# ---------------------------------------------------------------------------

class S3Backend(StorageBackend):
    name = "s3"

    def __init__(self) -> None:
        import boto3
        from botocore.config import Config

        self._bucket = settings.S3_BUCKET
        self._client = boto3.client(
            "s3",
            region_name=settings.S3_REGION or None,
            aws_access_key_id=settings.S3_ACCESS_KEY or None,
            aws_secret_access_key=settings.S3_SECRET_KEY or None,
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            # SigV4 so presigned URLs work in every region, including the ones
            # that refuse the older signature.
            config=Config(signature_version="s3v4"),
        )

    def presign_upload(
        self, key: str, content_type: str, *, max_bytes: Optional[int] = None
    ) -> PresignedUpload:
        try:
            url = self._client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=PRESIGN_EXPIRY_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Could not presign the upload: {exc}") from exc

        return PresignedUpload(
            url=url,
            method="PUT",
            headers={"Content-Type": content_type},
            key=key,
            expires_in=PRESIGN_EXPIRY_SECONDS,
        )

    def head(self, key: str) -> ObjectInfo:
        from botocore.exceptions import ClientError

        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                raise ObjectNotFound(key) from exc
            raise StorageError(f"Could not read the object: {exc}") from exc
        return ObjectInfo(
            key=key,
            size_bytes=int(response.get("ContentLength", 0)),
            content_type=response.get("ContentType"),
        )

    def read_range(self, key: str, *, length: int) -> bytes:
        from botocore.exceptions import ClientError

        try:
            response = self._client.get_object(
                Bucket=self._bucket, Key=key, Range=f"bytes=0-{length - 1}"
            )
            return response["Body"].read()
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                raise ObjectNotFound(key) from exc
            raise StorageError(f"Could not read the object: {exc}") from exc

    def put_object(
        self, key: str, data: bytes, *, content_type: str = "application/octet-stream"
    ) -> None:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            self._client.put_object(
                Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"Could not store {key}: {exc}") from exc

    def presign_download(self, key: str) -> str:
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=DOWNLOAD_EXPIRY_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Could not presign the download: {exc}") from exc

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Could not delete the object: {exc}") from exc


# ---------------------------------------------------------------------------
# Local (development only)
# ---------------------------------------------------------------------------

class LocalStorageBackend(StorageBackend):
    """Files on disk, with the same interface.

    There is no such thing as a presigned URL here, so one is simulated: the
    returned URL points at our own upload endpoint and carries an HMAC over the
    key and an expiry. That keeps the *client* flow identical to S3 -- PUT to a
    URL, then confirm -- which is the point, because a dev path that differs
    from production is a dev path that hides bugs.

    The signature is not decoration. Without it the endpoint would accept a PUT
    to any path a caller invents, which is an arbitrary file write.
    """

    name = "local"

    def __init__(self, root: Optional[Path] = None) -> None:
        # Rooted at uploads/, not uploads/media/: keys already begin with
        # "media/" and are identical to the ones S3 would use, which is the
        # point of the abstraction. Rooting a level deeper produced
        # uploads/media/media/<account>/...
        self._root = root or (Path(__file__).resolve().parent.parent / "uploads")
        self._root.mkdir(parents=True, exist_ok=True)

    # -- path safety ---------------------------------------------------------

    def path_for(self, key: str) -> Path:
        """Resolve a key to a path inside the root, or refuse.

        ``..`` in a key would otherwise write outside the media directory.
        Keys are generated server-side, but this is the last line before a
        filesystem write and cheap to hold.
        """
        candidate = (self._root / key).resolve()
        root = self._root.resolve()
        if root != candidate and root not in candidate.parents:
            raise StorageError("Refusing to access a path outside the media root")
        return candidate

    # -- signed URLs ---------------------------------------------------------

    @staticmethod
    def _sign(key: str, expires_at: int) -> str:
        message = f"{key}:{expires_at}".encode()
        return hmac.new(
            settings.SECRET_KEY.encode(), message, hashlib.sha256
        ).hexdigest()

    @classmethod
    def verify(cls, key: str, expires_at: int, signature: str) -> bool:
        if expires_at < int(time.time()):
            return False
        return hmac.compare_digest(cls._sign(key, expires_at), signature)

    def presign_upload(
        self, key: str, content_type: str, *, max_bytes: Optional[int] = None
    ) -> PresignedUpload:
        expires_at = int(time.time()) + PRESIGN_EXPIRY_SECONDS
        signature = self._sign(key, expires_at)
        base = (settings.BACKEND_URL or "").rstrip("/")
        return PresignedUpload(
            url=(
                f"{base}/api/v1/media/local-upload"
                f"?key={key}&expires={expires_at}&signature={signature}"
            ),
            method="PUT",
            headers={"Content-Type": content_type},
            key=key,
            expires_in=PRESIGN_EXPIRY_SECONDS,
        )

    def put_object(
        self, key: str, data: bytes, *, content_type: str = "application/octet-stream"
    ) -> None:
        # content_type is not stored on disk; head() sniffs it from the key.
        self.write(key, data)

    def write(self, key: str, data: bytes) -> None:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def head(self, key: str) -> ObjectInfo:
        path = self.path_for(key)
        if not path.is_file():
            raise ObjectNotFound(key)
        guessed, _ = mimetypes.guess_type(path.name)
        return ObjectInfo(
            key=key, size_bytes=path.stat().st_size, content_type=guessed
        )

    def read_range(self, key: str, *, length: int) -> bytes:
        path = self.path_for(key)
        if not path.is_file():
            raise ObjectNotFound(key)
        with path.open("rb") as handle:
            return handle.read(length)

    def presign_download(self, key: str) -> str:
        expires_at = int(time.time()) + DOWNLOAD_EXPIRY_SECONDS
        signature = self._sign(key, expires_at)
        base = (settings.BACKEND_URL or "").rstrip("/")
        return (
            f"{base}/api/v1/media/local-download"
            f"?key={key}&expires={expires_at}&signature={signature}"
        )

    def delete(self, key: str) -> None:
        path = self.path_for(key)
        if path.is_file():
            path.unlink()


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def storage_configured() -> bool:
    return bool(settings.S3_BUCKET)


def get_storage() -> StorageBackend:
    """The backend for this environment.

    S3 whenever a bucket is set. Otherwise local, but only in DEBUG -- a
    production process with no bucket configured is a misconfiguration, and
    writing user media to the container's disk would look like it worked right
    up until the next deploy threw it away.
    """
    if storage_configured():
        return S3Backend()
    if settings.DEBUG:
        return LocalStorageBackend()
    raise StorageError(
        "No S3 bucket is configured. Set S3_BUCKET (and credentials) to enable "
        "the media library."
    )


def build_key(account_id, filename: str) -> str:
    """Where an object lives in the bucket.

    Prefixed by workspace so a bucket policy or lifecycle rule can be written
    per tenant, and the random component means two people uploading
    ``logo.png`` do not collide -- and that a key cannot be guessed from the
    filename alone.
    """
    suffix = Path(filename).suffix.lower()[:16]
    return f"media/{account_id}/{uuid.uuid4().hex}{suffix}"
