"""Custom SQLAlchemy column types."""

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core.crypto import decrypt_secret, encrypt_secret


class EncryptedText(TypeDecorator):
    """A Text column whose value is encrypted at rest.

    Encryption happens on the way to the database and decryption on the way
    back, so application code and the ORM see plaintext and nothing else needs
    to change.

    Because the stored form is ciphertext, these columns cannot be compared,
    filtered, sorted, or indexed meaningfully in SQL -- ``WHERE access_token =
    :value`` will never match. Nothing in this codebase does that (audited when
    the type was introduced); anything that needs to must load the row and
    compare in Python.
    """

    impl = Text
    # Safe to cache: the type carries no per-instance configuration.
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_secret(value)

    def process_result_value(self, value, dialect):
        return decrypt_secret(value)
