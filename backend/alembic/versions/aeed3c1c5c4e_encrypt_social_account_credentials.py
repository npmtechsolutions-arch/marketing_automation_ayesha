"""encrypt social account credentials

Revision ID: aeed3c1c5c4e
Revises: 63f75cc5fbb2
Create Date: 2026-09-07 20:39:33.936202

Encrypts the credentials already stored in ``social_accounts``: ``api_key``,
``api_secret``, ``access_token`` and ``refresh_token``. These were written in
plaintext before ``EncryptedText`` was applied to the columns, so without this
step the ORM would try to decrypt plaintext and fail.

Data-only: the column types are unchanged. ``EncryptedText`` stores ciphertext
in the same ``TEXT`` column, so there is no DDL here.

Idempotent
----------
Every value is tested with ``looks_encrypted()`` (a trial decrypt) before being
touched, so re-running this migration -- or running it on a database that was
partly migrated before an interruption -- leaves already-encrypted values alone.

All SQL here is raw on purpose: going through the ORM would apply
``EncryptedText`` and re-encrypt on write or fail to decrypt on read.

Key
---
Uses ``TOKEN_ENCRYPTION_KEY`` (or, in development only, a key derived from
``SECRET_KEY``). Running this with a different key than the application will use
leaves values the application cannot read, so make sure the key is configured
before migrating.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.crypto import decrypt_secret, encrypt_secret, looks_encrypted

# revision identifiers, used by Alembic.
revision: str = 'aeed3c1c5c4e'
down_revision: Union[str, Sequence[str], None] = '63f75cc5fbb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CREDENTIAL_COLUMNS = ("api_key", "api_secret", "access_token", "refresh_token")

_SELECT = sa.text(
    "SELECT id, api_key, api_secret, access_token, refresh_token "
    "FROM social_accounts"
)
_UPDATE = sa.text(
    "UPDATE social_accounts SET "
    "api_key = :api_key, api_secret = :api_secret, "
    "access_token = :access_token, refresh_token = :refresh_token "
    "WHERE id = :id"
)


def rewrite_credentials(connection, transform, should_skip) -> int:
    """Apply ``transform`` to every credential column that needs it.

    ``should_skip(value)`` decides whether a value is already in the target
    form; those rows are left untouched, which is what makes this idempotent.
    Returns the number of rows rewritten.

    Takes the connection as an argument rather than calling ``op.get_bind()``
    internally so the logic can be exercised directly in tests.
    """
    rows = connection.execute(_SELECT).mappings().all()

    changed = 0
    for row in rows:
        updates = {}
        for column in CREDENTIAL_COLUMNS:
            value = row[column]
            if value is None or value == "":
                continue
            if should_skip(value):
                continue
            updates[column] = transform(value)

        if not updates:
            continue

        params = {"id": row["id"]}
        for column in CREDENTIAL_COLUMNS:
            params[column] = updates.get(column, row[column])
        connection.execute(_UPDATE, params)
        changed += 1

    print(f"  social_accounts: {changed} of {len(rows)} row(s) rewritten")
    return changed


def upgrade() -> None:
    """Encrypt any plaintext credentials."""
    # Skip values that already decrypt cleanly -- they are ciphertext already.
    rewrite_credentials(op.get_bind(), transform=encrypt_secret, should_skip=looks_encrypted)


def downgrade() -> None:
    """Decrypt credentials back to plaintext.

    The reverse is only meaningful with the same key the upgrade used. Values
    that are not decryptable are left as they are rather than corrupted.
    """
    rewrite_credentials(
        op.get_bind(),
        transform=decrypt_secret,
        should_skip=lambda v: not looks_encrypted(v),
    )
