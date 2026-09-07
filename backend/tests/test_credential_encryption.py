"""Tests for encryption at rest of social-platform credentials.

``social_accounts`` stored ``api_key``, ``api_secret``, ``access_token`` and
``refresh_token`` in plaintext -- the model comment claimed "encrypted in
production" but nothing encrypted anything. These tests cover both halves of
the fix: the ``EncryptedText`` column type, and the data migration that
converts rows written before it existed.
"""

import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import select

from app.core.crypto import (
    SecretDecryptionError,
    decrypt_secret,
    encrypt_secret,
    looks_encrypted,
)
from app.models.platform import SocialAccount, SocialPlatform

pytestmark = pytest.mark.asyncio

CREDENTIAL_COLUMNS = ("api_key", "api_secret", "access_token", "refresh_token")


def _sql(query: str, **params):
    """text() with UUID-typed binds.

    Raw SQL must bind UUIDs through sa.Uuid so the value matches what the ORM
    stored -- SQLite keeps them as bare hex while ``str(uuid)`` has dashes.
    Typed binds keep these tests dialect-agnostic.
    """
    binds = [
        sa.bindparam(key, value, type_=sa.Uuid) if isinstance(value, uuid.UUID)
        else sa.bindparam(key, value)
        for key, value in params.items()
    ]
    return sa.text(query).bindparams(*binds)


def _load_migration():
    """Import the data migration by path (alembic/versions is not a package)."""
    path = (
        Path(__file__).resolve().parent.parent
        / "alembic"
        / "versions"
        / "aeed3c1c5c4e_encrypt_social_account_credentials.py"
    )
    spec = importlib.util.spec_from_file_location("encrypt_credentials_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _make_platform(db_session, user, account) -> SocialPlatform:
    platform = SocialPlatform(
        id=uuid.uuid4(),
        user_id=user.id,
        account_id=account.id,
        name="Testgram",
        slug=f"testgram-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(platform)
    await db_session.flush()
    return platform


# ---------------------------------------------------------------------------
# The crypto helpers
# ---------------------------------------------------------------------------

async def test_encrypt_decrypt_round_trip():
    secret = "ya29.a0AfH6SMB-super-secret-oauth-token"
    ciphertext = encrypt_secret(secret)

    assert ciphertext != secret
    assert secret not in ciphertext
    assert decrypt_secret(ciphertext) == secret


async def test_none_and_empty_pass_through():
    """None means 'no credential' and must not become ciphertext."""
    assert encrypt_secret(None) is None
    assert decrypt_secret(None) is None
    assert encrypt_secret("") == ""
    assert decrypt_secret("") == ""


async def test_encryption_is_non_deterministic():
    """Fernet embeds a timestamp and IV, so the same input differs each time.

    This matters: identical ciphertext would leak that two accounts share a
    credential.
    """
    assert encrypt_secret("same-value") != encrypt_secret("same-value")


async def test_tampered_ciphertext_is_rejected():
    """Fernet is authenticated -- a modified token must not decrypt."""
    ciphertext = encrypt_secret("secret")
    tampered = ciphertext[:-4] + ("AAAA" if not ciphertext.endswith("AAAA") else "BBBB")

    with pytest.raises(SecretDecryptionError):
        decrypt_secret(tampered)


async def test_plaintext_fails_to_decrypt():
    """Decrypting an unmigrated plaintext value fails loudly rather than
    returning garbage that would be sent to a platform API as a credential."""
    with pytest.raises(SecretDecryptionError):
        decrypt_secret("plaintext_access_token")


async def test_looks_encrypted_discriminates():
    assert looks_encrypted(encrypt_secret("x")) is True
    assert looks_encrypted("plaintext_access_token") is False
    assert looks_encrypted(None) is False
    assert looks_encrypted("") is False


# ---------------------------------------------------------------------------
# The EncryptedText column type
# ---------------------------------------------------------------------------

async def test_credentials_round_trip_through_the_model(
    db_session, user_factory, account_factory
):
    """The ORM sees plaintext; the database holds ciphertext."""
    user = await user_factory()
    account = await account_factory(user)
    platform = await _make_platform(db_session, user, account)

    secrets = {
        "api_key": "AK-123456",
        "api_secret": "AS-abcdef",
        "access_token": "ya29.super-secret",
        "refresh_token": "1//refresh-secret",
    }
    social = SocialAccount(
        id=uuid.uuid4(),
        user_id=user.id,
        account_id=account.id,
        platform_id=platform.id,
        account_name="Acme Testgram",
        **secrets,
    )
    db_session.add(social)
    await db_session.flush()
    db_session.expunge_all()

    # Read back through the ORM: plaintext.
    loaded = (
        await db_session.execute(
            select(SocialAccount).where(SocialAccount.id == social.id)
        )
    ).scalar_one()
    for column, expected in secrets.items():
        assert getattr(loaded, column) == expected, f"{column} did not round-trip"

    # Read the same row as raw SQL: ciphertext, and none of the plaintext.
    raw = (
        await db_session.execute(
            _sql(
                "SELECT api_key, api_secret, access_token, refresh_token "
                "FROM social_accounts WHERE id = :id",
                id=social.id,
            )
        )
    ).mappings().one()

    for column, plaintext in secrets.items():
        stored = raw[column]
        assert stored != plaintext, f"{column} was stored in plaintext"
        assert plaintext not in stored, f"{column} plaintext leaked into storage"
        assert looks_encrypted(stored), f"{column} is not a valid ciphertext"


async def test_null_credentials_stay_null(db_session, user_factory, account_factory):
    """A social account with no credentials stores NULL, not ciphertext."""
    user = await user_factory()
    account = await account_factory(user)
    platform = await _make_platform(db_session, user, account)

    social = SocialAccount(
        id=uuid.uuid4(),
        user_id=user.id,
        account_id=account.id,
        platform_id=platform.id,
        account_name="No creds",
    )
    db_session.add(social)
    await db_session.flush()

    raw = (
        await db_session.execute(
            _sql("SELECT access_token, api_key FROM social_accounts WHERE id = :id",
                 id=social.id)
        )
    ).mappings().one()
    assert raw["access_token"] is None
    assert raw["api_key"] is None


async def test_update_re_encrypts(db_session, user_factory, account_factory):
    """Rotating a token stores new ciphertext, not the new plaintext."""
    user = await user_factory()
    account = await account_factory(user)
    platform = await _make_platform(db_session, user, account)

    social = SocialAccount(
        id=uuid.uuid4(),
        user_id=user.id,
        account_id=account.id,
        platform_id=platform.id,
        account_name="Rotates",
        access_token="original-token",
    )
    db_session.add(social)
    await db_session.flush()

    social.access_token = "rotated-token"
    await db_session.flush()

    raw = (
        await db_session.execute(
            _sql("SELECT access_token FROM social_accounts WHERE id = :id",
                 id=social.id)
        )
    ).scalar_one()
    assert "rotated-token" not in raw
    assert decrypt_secret(raw) == "rotated-token"


# ---------------------------------------------------------------------------
# The data migration
# ---------------------------------------------------------------------------

async def _insert_plaintext_row(db_session, user, account, platform, **creds):
    """Insert a row the way the pre-encryption code did: raw SQL, plaintext.

    Going through the ORM would encrypt on write, which is exactly what this
    fixture must avoid.
    """
    row_id = uuid.uuid4()
    await db_session.execute(
        _sql(
            "INSERT INTO social_accounts "
            "(id, user_id, account_id, platform_id, account_name, "
            " api_key, api_secret, access_token, refresh_token, is_active, is_verified) "
            "VALUES (:id, :user_id, :account_id, :platform_id, :account_name, "
            " :api_key, :api_secret, :access_token, :refresh_token, :is_active, :is_verified)",
            id=row_id,
            user_id=user.id,
            account_id=account.id,
            platform_id=platform.id,
            account_name="Legacy account",
            api_key=creds.get("api_key"),
            api_secret=creds.get("api_secret"),
            access_token=creds.get("access_token"),
            refresh_token=creds.get("refresh_token"),
            is_active=True,
            is_verified=False,
        )
    )
    return row_id


async def test_migration_encrypts_plaintext_row(
    db_session, user_factory, account_factory
):
    """The migration converts a legacy plaintext row to ciphertext."""
    migration = _load_migration()
    user = await user_factory()
    account = await account_factory(user)
    platform = await _make_platform(db_session, user, account)

    plaintext = {
        "api_key": "legacy-key",
        "api_secret": "legacy-secret",
        "access_token": "legacy-access-token",
        "refresh_token": "legacy-refresh-token",
    }
    row_id = await _insert_plaintext_row(db_session, user, account, platform, **plaintext)

    # Sanity: it really is plaintext before the migration runs.
    before = (
        await db_session.execute(
            _sql("SELECT access_token FROM social_accounts WHERE id = :id",
                 id=row_id)
        )
    ).scalar_one()
    assert before == "legacy-access-token"

    changed = await db_session.run_sync(
        lambda sync_conn: migration.rewrite_credentials(
            sync_conn, transform=encrypt_secret, should_skip=looks_encrypted
        )
    )
    assert changed == 1

    raw = (
        await db_session.execute(
            _sql(
                "SELECT api_key, api_secret, access_token, refresh_token "
                "FROM social_accounts WHERE id = :id",
                id=row_id,
            )
        )
    ).mappings().one()
    for column, value in plaintext.items():
        assert raw[column] != value, f"{column} left in plaintext"
        assert decrypt_secret(raw[column]) == value, f"{column} did not survive"

    # And the ORM can now read the migrated row.
    db_session.expunge_all()
    loaded = (
        await db_session.execute(
            select(SocialAccount).where(SocialAccount.id == row_id)
        )
    ).scalar_one()
    assert loaded.access_token == "legacy-access-token"


async def test_migration_is_idempotent(db_session, user_factory, account_factory):
    """Re-running must not double-encrypt already-migrated values."""
    migration = _load_migration()
    user = await user_factory()
    account = await account_factory(user)
    platform = await _make_platform(db_session, user, account)
    row_id = await _insert_plaintext_row(
        db_session, user, account, platform, access_token="legacy-token"
    )

    async def _run():
        return await db_session.run_sync(
            lambda c: migration.rewrite_credentials(
                c, transform=encrypt_secret, should_skip=looks_encrypted
            )
        )

    assert await _run() == 1, "first run should encrypt the plaintext row"
    assert await _run() == 0, "second run should skip already-encrypted values"
    assert await _run() == 0, "third run should still be a no-op"

    raw = (
        await db_session.execute(
            _sql("SELECT access_token FROM social_accounts WHERE id = :id",
                 id=row_id)
        )
    ).scalar_one()
    # Decrypting once must yield the original -- proving it was not encrypted twice.
    assert decrypt_secret(raw) == "legacy-token"


async def test_migration_leaves_nulls_alone(db_session, user_factory, account_factory):
    migration = _load_migration()
    user = await user_factory()
    account = await account_factory(user)
    platform = await _make_platform(db_session, user, account)
    row_id = await _insert_plaintext_row(
        db_session, user, account, platform, access_token="only-this-one"
    )

    await db_session.run_sync(
        lambda c: migration.rewrite_credentials(
            c, transform=encrypt_secret, should_skip=looks_encrypted
        )
    )

    raw = (
        await db_session.execute(
            _sql(
                "SELECT api_key, api_secret, refresh_token FROM social_accounts "
                "WHERE id = :id",
                id=row_id,
            )
        )
    ).mappings().one()
    assert raw["api_key"] is None
    assert raw["api_secret"] is None
    assert raw["refresh_token"] is None


async def test_migration_downgrade_restores_plaintext(
    db_session, user_factory, account_factory
):
    migration = _load_migration()
    user = await user_factory()
    account = await account_factory(user)
    platform = await _make_platform(db_session, user, account)
    row_id = await _insert_plaintext_row(
        db_session, user, account, platform, access_token="round-trip-me"
    )

    await db_session.run_sync(
        lambda c: migration.rewrite_credentials(
            c, transform=encrypt_secret, should_skip=looks_encrypted
        )
    )
    await db_session.run_sync(
        lambda c: migration.rewrite_credentials(
            c, transform=decrypt_secret, should_skip=lambda v: not looks_encrypted(v)
        )
    )

    raw = (
        await db_session.execute(
            _sql("SELECT access_token FROM social_accounts WHERE id = :id",
                 id=row_id)
        )
    ).scalar_one()
    assert raw == "round-trip-me"


# ---------------------------------------------------------------------------
# Configuration guard
# ---------------------------------------------------------------------------

async def test_production_requires_token_encryption_key(monkeypatch):
    """DEBUG=false with no TOKEN_ENCRYPTION_KEY must refuse to boot."""
    from app.core.config import Settings

    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("SECRET_KEY", "a-real-secret-key-for-this-test-0123456789")
    monkeypatch.setenv("JWT_SECRET_KEY", "another-real-secret-key-0123456789abcdef")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "")

    with pytest.raises(RuntimeError, match="TOKEN_ENCRYPTION_KEY"):
        Settings(_env_file=None)


async def test_production_boots_with_token_encryption_key(monkeypatch):
    from cryptography.fernet import Fernet

    from app.core.config import Settings

    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("SECRET_KEY", "a-real-secret-key-for-this-test-0123456789")
    monkeypatch.setenv("JWT_SECRET_KEY", "another-real-secret-key-0123456789abcdef")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())

    settings = Settings(_env_file=None)
    assert settings.TOKEN_ENCRYPTION_KEY
