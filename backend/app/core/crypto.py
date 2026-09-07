"""Symmetric encryption for secrets stored at rest.

Third-party platform credentials (OAuth access/refresh tokens, API keys and
secrets) are encrypted with Fernet before they reach the database, so a leaked
dump, an errant backup, or read access to a replica does not hand over every
connected account.

Fernet gives authenticated encryption: a value that has been tampered with
fails to decrypt rather than decrypting to something else.

Key management
--------------
The key is ``settings.TOKEN_ENCRYPTION_KEY``, a urlsafe-base64 32-byte Fernet
key. Generate one with::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Production (``DEBUG=false``) refuses to boot without it -- see the guard in
``app.core.config``. For local development the key may be omitted, in which case
one is derived deterministically from ``SECRET_KEY`` so that stored values stay
readable across restarts without any extra setup. That fallback is a
convenience, never a security control: it is only as strong as SECRET_KEY, which
in development is a well-known placeholder.

Rotation
--------
Changing the key makes every previously stored value undecryptable; those
accounts must reconnect. Re-encrypting under a new key would need a migration
that decrypts with the old key and encrypts with the new one, which is why the
key is treated as long-lived.
"""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class SecretDecryptionError(RuntimeError):
    """A stored secret could not be decrypted with the configured key."""


def _derive_dev_key(secret: str) -> bytes:
    """Derive a valid Fernet key from SECRET_KEY, for development only.

    Deterministic so values written before a restart can still be read after it.
    """
    digest = hashlib.sha256(f"token-encryption:{secret}".encode()).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    """Build the Fernet instance once, from configuration."""
    configured = settings.TOKEN_ENCRYPTION_KEY.strip()
    if configured:
        try:
            return Fernet(configured.encode())
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                "TOKEN_ENCRYPTION_KEY is not a valid Fernet key. Generate one "
                'with: python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            ) from exc
    # No key configured. config.py has already refused to boot if this is
    # production, so this path is development only.
    return Fernet(_derive_dev_key(settings.SECRET_KEY))


def encrypt_secret(value: str | None) -> str | None:
    """Encrypt ``value`` for storage. ``None`` passes through unchanged.

    An empty string is preserved as an empty string rather than encrypted, so
    "no credential" stays distinguishable from "a credential that is blank".
    """
    if value is None:
        return None
    if value == "":
        return ""
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str | None:
    """Decrypt a stored value. ``None`` and ``""`` pass through unchanged.

    Raises :class:`SecretDecryptionError` if the value is not a valid token for
    the configured key -- which means either the data predates encryption (the
    baseline data migration was not run) or the key changed. Failing loudly
    beats returning ciphertext, which would be sent to a platform API as if it
    were a credential and surface as a confusing auth error.
    """
    if value is None:
        return None
    if value == "":
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError, TypeError) as exc:
        raise SecretDecryptionError(
            "Stored secret could not be decrypted with the configured "
            "TOKEN_ENCRYPTION_KEY. The value may predate encryption (run "
            "`alembic upgrade head`) or the key may have changed."
        ) from exc


def looks_encrypted(value: str | None) -> bool:
    """Return True if ``value`` is a Fernet token this key can decrypt.

    Used by the data migration to stay idempotent: re-running it must not
    double-encrypt values that are already ciphertext.
    """
    if not value:
        return False
    try:
        _fernet().decrypt(value.encode())
        return True
    except (InvalidToken, ValueError, TypeError):
        return False


def reset_cache() -> None:
    """Drop the cached Fernet instance. For tests that change the key."""
    _fernet.cache_clear()
