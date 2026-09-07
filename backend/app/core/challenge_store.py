"""Server-side state for single-use auth artefacts.

Covers in-flight 2FA login challenges and password reset tokens. Both are
stateless JWTs, which means that without a record of use they stay valid for
their whole lifetime no matter how often they are presented.

A challenge token proves the password step succeeded and the user still owes a
second factor. As a bare JWT it is replayable until it expires, and it offers
no way to count wrong codes -- an attacker who captured one could brute-force
a six-digit TOTP at whatever rate the API allows.

This module gives each challenge server-side state, so it can be:

* **single-use** -- consumed on success and rejected afterwards, and
* **attempt-capped** -- a bounded number of wrong codes per challenge.

Backed by Redis (shared across workers, with TTLs that expire the state
automatically). When Redis is unavailable it falls back to an in-process dict,
which is correct for a single worker and is what local development and the test
suite use. That fallback is weaker: with several workers an attacker's attempts
spread across separate counters, so Redis should be present in production.
"""

import logging
import time
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Challenge tokens are valid for 5 minutes (see create_2fa_challenge_token), so
# the server-side state expires alongside them.
CHALLENGE_TTL_SECONDS = 5 * 60

# Wrong codes allowed per challenge before it is refused outright.
MAX_FAILED_ATTEMPTS = 5

_CHALLENGE_PREFIX = "2fa:challenge:"
_ATTEMPTS_PREFIX = "2fa:attempts:"
_RESET_PREFIX = "pwreset:"

# Password reset tokens are valid for 1 hour (create_password_reset_token),
# so their record expires with them.
RESET_TTL_SECONDS = 60 * 60


class _MemoryStore:
    """Minimal expiring key/value store used when Redis is unavailable."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[float, int]] = {}

    def _purge(self) -> None:
        now = time.time()
        for key in [k for k, (exp, _) in self._data.items() if exp <= now]:
            self._data.pop(key, None)

    def set(self, key: str, value: int, ttl: int) -> None:
        self._purge()
        self._data[key] = (time.time() + ttl, value)

    def get(self, key: str) -> Optional[int]:
        self._purge()
        entry = self._data.get(key)
        return None if entry is None else entry[1]

    def delete(self, key: str) -> bool:
        self._purge()
        return self._data.pop(key, None) is not None

    def incr(self, key: str, ttl: int) -> int:
        self._purge()
        entry = self._data.get(key)
        if entry is None:
            self._data[key] = (time.time() + ttl, 1)
            return 1
        expires_at, value = entry
        self._data[key] = (expires_at, value + 1)
        return value + 1

    def clear(self) -> None:
        self._data.clear()


class _RedisStore:
    """Redis-backed store. Deletes are atomic, which is what makes a challenge
    single-use even with concurrent requests."""

    def __init__(self, client) -> None:
        self._client = client

    def set(self, key: str, value: int, ttl: int) -> None:
        self._client.setex(key, ttl, value)

    def get(self, key: str) -> Optional[int]:
        raw = self._client.get(key)
        return None if raw is None else int(raw)

    def delete(self, key: str) -> bool:
        # DEL returns the number of keys removed; exactly one caller can see 1.
        return bool(self._client.delete(key))

    def incr(self, key: str, ttl: int) -> int:
        pipe = self._client.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl, nx=True)
        value, _ = pipe.execute()
        return int(value)

    def clear(self) -> None:
        for prefix in (_CHALLENGE_PREFIX, _ATTEMPTS_PREFIX, _RESET_PREFIX):
            for key in self._client.scan_iter(match=f"{prefix}*"):
                self._client.delete(key)


def _build_store():
    url = (settings.REDIS_URL or "").strip()
    if url:
        try:
            import redis

            client = redis.Redis.from_url(
                url, socket_connect_timeout=1, decode_responses=True
            )
            client.ping()
            return _RedisStore(client)
        except Exception as exc:  # noqa: BLE001 - any failure means "no Redis"
            message = (
                "Redis is not reachable at REDIS_URL (%s); 2FA challenge state "
                "is per-process, so single-use and attempt caps only hold "
                "within one worker."
            )
            if settings.DEBUG:
                logger.warning(message, exc)
            else:
                logger.error(message, exc)
    return _MemoryStore()


_store = _build_store()


def register_challenge(jti: str) -> None:
    """Record a newly issued challenge as unused."""
    _store.set(f"{_CHALLENGE_PREFIX}{jti}", 1, CHALLENGE_TTL_SECONDS)


def challenge_is_active(jti: str) -> bool:
    """True if the challenge exists and has not been consumed."""
    return _store.get(f"{_CHALLENGE_PREFIX}{jti}") is not None


def consume_challenge(jti: str) -> bool:
    """Consume a challenge. Returns True for the caller that got it.

    The delete is atomic, so two concurrent requests replaying the same token
    cannot both succeed.
    """
    _store.delete(f"{_ATTEMPTS_PREFIX}{jti}")
    return _store.delete(f"{_CHALLENGE_PREFIX}{jti}")


def failed_attempts(jti: str) -> int:
    """How many wrong codes have been submitted for this challenge."""
    return _store.get(f"{_ATTEMPTS_PREFIX}{jti}") or 0


def record_failed_attempt(jti: str) -> int:
    """Count a wrong code and return the new total."""
    return _store.incr(f"{_ATTEMPTS_PREFIX}{jti}", CHALLENGE_TTL_SECONDS)


def register_reset_token(jti: str) -> None:
    """Record a freshly issued password reset token as unused."""
    _store.set(f"{_RESET_PREFIX}{jti}", 1, RESET_TTL_SECONDS)


def consume_reset_token(jti: str) -> bool:
    """Consume a password reset token. True only for the caller that got it.

    The delete is atomic, so a replayed link -- including two concurrent
    submissions of the same one -- succeeds at most once.
    """
    return _store.delete(f"{_RESET_PREFIX}{jti}")


def reset() -> None:
    """Clear all stored state. For tests."""
    _store.clear()
