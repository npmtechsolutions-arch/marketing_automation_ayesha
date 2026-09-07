"""Rate limiting and 2FA challenge hardening.

Before this, nothing in the API was rate limited: passwords, TOTP codes and
password-reset mail could all be hammered as fast as the client could send
requests. A 2FA challenge token was also replayable until it expired and put no
ceiling on wrong codes, so capturing one turned a six-digit second factor into
a short brute-force.
"""

import uuid

import pytest

import pyotp

from app.core import challenge_store
from app.services import totp_service

pytestmark = pytest.mark.asyncio

LOGIN_URL = "/api/v1/auth/login"
TWOFA_URL = "/api/v1/auth/login/2fa"
FORGOT_URL = "/api/v1/auth/forgot-password"
REGISTER_URL = "/api/v1/auth/register"

PASSWORD = "hunter2-correct-horse"


def _current_code(secret: str) -> str:
    """The TOTP code the app would accept right now."""
    return pyotp.TOTP(secret).now()


async def _enable_2fa(db_session, user) -> str:
    """Turn on TOTP for a user and return the shared secret."""
    secret = totp_service.generate_secret()
    user.totp_secret = secret
    user.two_factor_enabled = True
    await db_session.flush()
    return secret


async def _start_challenge(client, user) -> str:
    """Log in with the right password and return the 2FA challenge token."""
    response = await client.post(
        LOGIN_URL, json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["requires_2fa"] is True
    return body["challenge_token"]


# ---------------------------------------------------------------------------
# Login rate limits
# ---------------------------------------------------------------------------

async def test_sixth_rapid_login_attempt_is_rate_limited(client, user_factory):
    """5/minute per IP: the sixth attempt in a burst is refused."""
    user = await user_factory(password=PASSWORD)

    statuses = []
    for _ in range(6):
        response = await client.post(
            LOGIN_URL, json={"email": user.email, "password": "wrong-password"}
        )
        statuses.append(response.status_code)

    assert statuses[:5] == [401] * 5, f"first five should be auth failures: {statuses}"
    assert statuses[5] == 429, f"sixth should be rate limited: {statuses}"


async def test_rate_limited_response_carries_retry_after(client, user_factory):
    user = await user_factory(password=PASSWORD)
    for _ in range(5):
        await client.post(LOGIN_URL, json={"email": user.email, "password": "nope"})

    response = await client.post(
        LOGIN_URL, json={"email": user.email, "password": "nope"}
    )

    assert response.status_code == 429
    retry_after = response.headers.get("retry-after")
    assert retry_after is not None, "429 must tell the client when to retry"
    assert retry_after.isdigit() and int(retry_after) > 0
    assert "detail" in response.json()


async def test_correct_password_still_blocked_once_limited(client, user_factory):
    """The limit applies to the endpoint, not just to failures -- otherwise an
    attacker who guesses correctly on attempt six is unaffected by it."""
    user = await user_factory(password=PASSWORD)
    for _ in range(5):
        await client.post(LOGIN_URL, json={"email": user.email, "password": "nope"})

    response = await client.post(
        LOGIN_URL, json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 429


async def test_login_email_limit_counts_unknown_addresses(client):
    """The per-email limit is applied before the user lookup, so probing an
    address that does not exist is limited too."""
    email = f"ghost-{uuid.uuid4().hex[:8]}@example.com"

    statuses = [
        (await client.post(LOGIN_URL, json={"email": email, "password": "x"})).status_code
        for _ in range(6)
    ]
    assert 429 in statuses


async def test_register_is_rate_limited(client):
    """5/hour per IP on registration."""
    statuses = []
    for i in range(6):
        response = await client.post(
            REGISTER_URL,
            json={
                "email": f"new-{uuid.uuid4().hex[:10]}@example.com",
                "password": "SomeStrongPassword123!",
                "full_name": f"New User {i}",
            },
        )
        statuses.append(response.status_code)

    assert statuses[-1] == 429, f"sixth registration should be limited: {statuses}"


async def test_forgot_password_is_rate_limited(client, user_factory):
    """3/hour per IP+email, so reset mail cannot be used to spam an inbox."""
    user = await user_factory(password=PASSWORD)

    statuses = [
        (await client.post(FORGOT_URL, json={"email": user.email})).status_code
        for _ in range(4)
    ]

    assert statuses[:3] == [200] * 3, statuses
    assert statuses[3] == 429, statuses


async def test_forgot_password_limit_is_per_email(client, user_factory):
    """A different address from the same IP has its own budget."""
    first = await user_factory(password=PASSWORD)
    second = await user_factory(password=PASSWORD)

    for _ in range(3):
        await client.post(FORGOT_URL, json={"email": first.email})

    assert (
        await client.post(FORGOT_URL, json={"email": first.email})
    ).status_code == 429
    assert (
        await client.post(FORGOT_URL, json={"email": second.email})
    ).status_code == 200


# ---------------------------------------------------------------------------
# 2FA challenge: single use
# ---------------------------------------------------------------------------

async def test_consumed_2fa_challenge_cannot_be_replayed(
    client, db_session, user_factory
):
    """The headline case: a challenge token is good for exactly one sign-in."""
    user = await user_factory(password=PASSWORD)
    secret = await _enable_2fa(db_session, user)
    challenge = await _start_challenge(client, user)

    first = await client.post(
        TWOFA_URL,
        json={"challenge_token": challenge, "code": _current_code(secret)},
    )
    assert first.status_code == 200, first.text
    assert first.json()["access_token"]

    replay = await client.post(
        TWOFA_URL,
        json={"challenge_token": challenge, "code": _current_code(secret)},
    )
    assert replay.status_code == 401, (
        f"a consumed challenge must not work twice (got {replay.status_code})"
    )


async def test_unknown_challenge_jti_is_rejected(client, db_session, user_factory):
    """A correctly signed token whose challenge was never registered (or has
    already expired server-side) is refused."""
    from app.core.security import create_2fa_challenge_token

    user = await user_factory(password=PASSWORD)
    secret = await _enable_2fa(db_session, user)
    # Signed correctly, but never registered in the challenge store.
    token, _jti = create_2fa_challenge_token(str(user.id))

    response = await client.post(
        TWOFA_URL,
        json={"challenge_token": token, "code": _current_code(secret)},
    )
    assert response.status_code == 401


async def test_challenge_token_carries_a_jti():
    from app.core.security import create_2fa_challenge_token, verify_2fa_challenge_token

    token, jti = create_2fa_challenge_token(str(uuid.uuid4()))
    decoded = verify_2fa_challenge_token(token)

    assert decoded is not None
    assert decoded[1] == jti


# ---------------------------------------------------------------------------
# 2FA challenge: attempt cap
# ---------------------------------------------------------------------------

async def test_sixth_wrong_totp_code_is_rate_limited(
    client, db_session, user_factory
):
    """Five wrong codes are rejected as invalid; the sixth is refused outright.

    The IP-keyed 5/minute limit on this endpoint would also produce a 429 on the
    sixth request, which would pass this test for the wrong reason. Clearing the
    IP counters between submissions isolates the per-challenge cap, and the
    assertion on the message confirms which limit fired.
    """
    from app.core.ratelimit import limiter

    user = await user_factory(password=PASSWORD)
    await _enable_2fa(db_session, user)
    challenge = await _start_challenge(client, user)

    statuses = []
    for _ in range(6):
        limiter.reset()  # keep the IP limit out of the way
        response = await client.post(
            TWOFA_URL, json={"challenge_token": challenge, "code": "000000"}
        )
        statuses.append(response.status_code)

    assert statuses[:5] == [400] * 5, f"first five are invalid-code: {statuses}"
    assert statuses[5] == 429, f"sixth should be refused: {statuses}"

    body = response.json()
    assert "incorrect codes" in body["detail"].lower(), (
        f"429 came from the wrong limit: {body['detail']}"
    )
    assert response.headers.get("retry-after") is not None


async def test_2fa_endpoint_is_ip_rate_limited(client):
    """Independently of the per-challenge cap, the endpoint is 15/minute per IP.

    Uses a bogus challenge token so every request is rejected early without
    touching any challenge's attempt counter -- what accumulates here is purely
    the IP-keyed limit.
    """
    statuses = [
        (
            await client.post(
                TWOFA_URL, json={"challenge_token": "not-a-real-token", "code": "000000"}
            )
        ).status_code
        for _ in range(16)
    ]

    assert statuses[:15] == [401] * 15, f"first fifteen are rejected tokens: {statuses}"
    assert statuses[15] == 429, f"sixteenth should be IP rate limited: {statuses}"


async def test_per_challenge_cap_binds_before_the_ip_limit(
    client, db_session, user_factory
):
    """The per-challenge cap is the binding constraint on wrong codes.

    No isolation here on purpose: with the IP limit at 15/minute and the cap at
    5 attempts, six wrong codes in a row must be stopped by the *cap*. When the
    IP limit was 5/minute it fired first and the cap never got to act.
    """
    user = await user_factory(password=PASSWORD)
    await _enable_2fa(db_session, user)
    challenge = await _start_challenge(client, user)

    statuses = []
    for _ in range(6):
        response = await client.post(
            TWOFA_URL, json={"challenge_token": challenge, "code": "000000"}
        )
        statuses.append(response.status_code)

    assert statuses == [400] * 5 + [429], statuses
    assert "incorrect codes" in response.json()["detail"].lower(), (
        f"the IP limit shadowed the per-challenge cap: {response.json()['detail']}"
    )


async def test_fresh_challenge_works_after_exhausting_a_previous_one(
    client, db_session, user_factory
):
    """A user who fumbles five codes can sign in again immediately.

    At 5/minute this was impossible -- the IP limit blocked the retry for a
    full minute even with a brand-new challenge.
    """
    user = await user_factory(password=PASSWORD)
    secret = await _enable_2fa(db_session, user)
    first = await _start_challenge(client, user)

    for _ in range(6):
        await client.post(TWOFA_URL, json={"challenge_token": first, "code": "000000"})

    second = await _start_challenge(client, user)
    response = await client.post(
        TWOFA_URL, json={"challenge_token": second, "code": _current_code(secret)}
    )
    assert response.status_code == 200, response.text


async def test_correct_code_rejected_after_attempt_cap(
    client, db_session, user_factory
):
    """Once the cap is hit the challenge is dead even for the right code --
    otherwise the cap would only slow an attacker down, not stop them."""
    user = await user_factory(password=PASSWORD)
    secret = await _enable_2fa(db_session, user)
    challenge = await _start_challenge(client, user)

    from app.core.ratelimit import limiter

    for _ in range(5):
        limiter.reset()  # isolate the per-challenge cap from the per-IP limit
        await client.post(
            TWOFA_URL, json={"challenge_token": challenge, "code": "000000"}
        )

    limiter.reset()
    response = await client.post(
        TWOFA_URL,
        json={"challenge_token": challenge, "code": _current_code(secret)},
    )
    assert response.status_code == 429
    assert "incorrect codes" in response.json()["detail"].lower()


async def test_attempt_cap_is_per_challenge(client, db_session, user_factory):
    """Signing in again gives a fresh challenge with its own attempt budget, so
    a user who fumbles their code is not locked out of the account."""
    user = await user_factory(password=PASSWORD)
    secret = await _enable_2fa(db_session, user)

    from app.core.ratelimit import limiter

    first_challenge = await _start_challenge(client, user)
    for _ in range(6):
        limiter.reset()  # isolate the per-challenge cap from the per-IP limit
        last = await client.post(
            TWOFA_URL, json={"challenge_token": first_challenge, "code": "000000"}
        )
    assert last.status_code == 429
    assert "incorrect codes" in last.json()["detail"].lower()

    limiter.reset()
    second_challenge = await _start_challenge(client, user)
    limiter.reset()
    assert second_challenge != first_challenge

    response = await client.post(
        TWOFA_URL,
        json={
            "challenge_token": second_challenge,
            "code": _current_code(secret),
        },
    )
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# The challenge store itself
# ---------------------------------------------------------------------------

async def test_challenge_store_consume_is_single_use():
    jti = uuid.uuid4().hex
    challenge_store.register_challenge(jti)

    assert challenge_store.challenge_is_active(jti) is True
    assert challenge_store.consume_challenge(jti) is True
    assert challenge_store.consume_challenge(jti) is False, "second consume must fail"
    assert challenge_store.challenge_is_active(jti) is False


async def test_challenge_store_counts_attempts():
    jti = uuid.uuid4().hex
    challenge_store.register_challenge(jti)

    assert challenge_store.failed_attempts(jti) == 0
    for expected in range(1, 4):
        assert challenge_store.record_failed_attempt(jti) == expected
    assert challenge_store.failed_attempts(jti) == 3


async def test_consuming_a_challenge_clears_its_attempts():
    jti = uuid.uuid4().hex
    challenge_store.register_challenge(jti)
    challenge_store.record_failed_attempt(jti)
    challenge_store.consume_challenge(jti)

    assert challenge_store.failed_attempts(jti) == 0


# ---------------------------------------------------------------------------
# AI generation limit
# ---------------------------------------------------------------------------

async def test_ai_generation_limit_is_per_user():
    """20/hour, keyed on the user so one client cannot exhaust another's quota."""
    from app.core.ratelimit import AI_GENERATION_LIMIT, enforce_limit
    from fastapi import HTTPException

    assert AI_GENERATION_LIMIT == "20/hour"

    user_a, user_b = str(uuid.uuid4()), str(uuid.uuid4())
    for _ in range(20):
        enforce_limit("ai:generation", AI_GENERATION_LIMIT, user_a, detail="x")

    with pytest.raises(HTTPException) as exc:
        enforce_limit("ai:generation", AI_GENERATION_LIMIT, user_a, detail="x")
    assert exc.value.status_code == 429
    assert exc.value.headers.get("Retry-After")

    # A different user is unaffected.
    enforce_limit("ai:generation", AI_GENERATION_LIMIT, user_b, detail="x")


async def test_ai_router_has_the_rate_limit_dependency():
    """Attached router-wide so new generation endpoints are covered too."""
    from app.api.v1.endpoints.ai import router
    from app.core.ratelimit import ai_generation_rate_limit

    assert any(
        dep.dependency is ai_generation_rate_limit for dep in router.dependencies
    ), "AI router is missing the per-user generation limit"
