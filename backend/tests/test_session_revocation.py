"""Session revocation, refresh rotation, and single-use password reset links.

Three ways existed to keep using a session that should have ended:

* refresh tokens without a ``sid`` were accepted as "legacy", bypassing
  revocation entirely;
* a ``sid`` naming no session row still got a fresh token pair, because the
  lookup result was never required to be non-null;
* refresh tokens never rotated, so a stolen one worked for its whole lifetime
  alongside the victim's.

Logout was a no-op that returned success without touching anything, and
password reset links stayed valid for their full hour after being used.
"""

import uuid

import pytest
from sqlalchemy import select

from app.api.v1.endpoints.auth import REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH
from app.core.security import create_refresh_token, decode_token
from app.models.user_session import UserSession

pytestmark = pytest.mark.asyncio

LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
FORGOT_URL = "/api/v1/auth/forgot-password"
RESET_URL = "/api/v1/auth/reset-password"

PASSWORD = "hunter2-correct-horse"


async def _login(client, user) -> dict:
    response = await client.post(
        LOGIN_URL, json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# 1. sid-less refresh tokens are rejected
# ---------------------------------------------------------------------------

async def test_refresh_without_sid_is_rejected(client, user_factory):
    """The "legacy" path was a straight revocation bypass."""
    user = await user_factory(password=PASSWORD)
    legacy = create_refresh_token({"sub": str(user.id)})

    response = await client.post(REFRESH_URL, json={"refresh_token": legacy})

    assert response.status_code == 401
    assert "sign in again" in response.json()["detail"].lower()


async def test_refresh_with_sid_but_no_rjti_is_rejected(client, user_factory):
    """A session-bound token still needs the rotation id."""
    user = await user_factory(password=PASSWORD)
    token = create_refresh_token({"sub": str(user.id), "sid": uuid.uuid4().hex})

    response = await client.post(REFRESH_URL, json={"refresh_token": token})
    assert response.status_code == 401


async def test_refresh_with_unknown_session_is_rejected(client, user_factory):
    """A sid naming no session row used to be issued fresh tokens anyway."""
    user = await user_factory(password=PASSWORD)
    token = create_refresh_token(
        {"sub": str(user.id), "sid": uuid.uuid4().hex, "rjti": uuid.uuid4().hex}
    )

    response = await client.post(REFRESH_URL, json={"refresh_token": token})
    assert response.status_code == 401


async def test_access_token_is_not_accepted_as_a_refresh_token(client, user_factory):
    user = await user_factory(password=PASSWORD)
    tokens = await _login(client, user)

    response = await client.post(
        REFRESH_URL, json={"refresh_token": tokens["access_token"]}
    )
    assert response.status_code == 401
    assert "expected refresh token" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 2. Rotation, and reuse revoking the session
# ---------------------------------------------------------------------------

async def test_login_issues_session_bound_tokens(client, db_session, user_factory):
    user = await user_factory(password=PASSWORD)
    tokens = await _login(client, user)

    access = decode_token(tokens["access_token"])
    refresh = decode_token(tokens["refresh_token"])
    assert access["sid"] == refresh["sid"]
    assert refresh["rjti"], "refresh token carries a rotation id"

    session = (
        await db_session.execute(
            select(UserSession).where(UserSession.id == uuid.UUID(refresh["sid"]))
        )
    ).scalar_one()
    assert session.refresh_jti == refresh["rjti"]
    assert session.revoked is False


async def test_refresh_rotates_the_token(client, db_session, user_factory):
    user = await user_factory(password=PASSWORD)
    first = await _login(client, user)

    response = await client.post(
        REFRESH_URL, json={"refresh_token": first["refresh_token"]}
    )
    assert response.status_code == 200
    second = response.json()

    old = decode_token(first["refresh_token"])
    new = decode_token(second["refresh_token"])
    assert new["sid"] == old["sid"], "the session stays the same"
    assert new["rjti"] != old["rjti"], "the rotation id must change"

    session = (
        await db_session.execute(
            select(UserSession).where(UserSession.id == uuid.UUID(new["sid"]))
        )
    ).scalar_one()
    assert session.refresh_jti == new["rjti"]


async def test_reusing_a_rotated_token_revokes_the_session(
    client, db_session, user_factory
):
    """The headline case: presenting a superseded token means two parties hold
    it, so the session ends for both."""
    user = await user_factory(password=PASSWORD)
    first = await _login(client, user)
    stolen = first["refresh_token"]

    # The legitimate holder refreshes; `stolen` is now superseded.
    ok = await client.post(REFRESH_URL, json={"refresh_token": stolen})
    assert ok.status_code == 200
    rotated = ok.json()["refresh_token"]

    # The thief presents the old one.
    replay = await client.post(REFRESH_URL, json={"refresh_token": stolen})
    assert replay.status_code == 401
    assert "revoked" in replay.json()["detail"].lower()

    sid = decode_token(stolen)["sid"]
    session = (
        await db_session.execute(
            select(UserSession).where(UserSession.id == uuid.UUID(sid))
        )
    ).scalar_one()
    assert session.revoked is True, "reuse must revoke the session"

    # And the victim's freshly rotated token is dead too -- that is the point:
    # there is no way to tell which party is which.
    after = await client.post(REFRESH_URL, json={"refresh_token": rotated})
    assert after.status_code == 401


async def test_reuse_revocation_survives_the_request_rollback(
    client, db_engine, user_factory
):
    """The revocation must be committed, not just flushed.

    get_db rolls the session back whenever a request raises, and the reuse
    branch raises 401 immediately after setting `revoked`. Flushing alone meant
    the rollback quietly undid it and the session stayed usable -- caught
    against the live server, not here, because these tests share one session
    with the app and never exercise that rollback. Asserting through a fresh
    session is what makes this test see what the database actually holds.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    user = await user_factory(password=PASSWORD)
    tokens = await _login(client, user)
    stolen = tokens["refresh_token"]

    await client.post(REFRESH_URL, json={"refresh_token": stolen})
    replay = await client.post(REFRESH_URL, json={"refresh_token": stolen})
    assert replay.status_code == 401

    sid = uuid.UUID(decode_token(stolen)["sid"])
    factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as fresh:
        session = (
            await fresh.execute(select(UserSession).where(UserSession.id == sid))
        ).scalar_one()
        assert session.revoked is True, (
            "revocation was rolled back with the failed request"
        )


async def test_revoked_session_cannot_refresh(client, db_session, user_factory):
    user = await user_factory(password=PASSWORD)
    tokens = await _login(client, user)
    sid = decode_token(tokens["refresh_token"])["sid"]

    session = (
        await db_session.execute(
            select(UserSession).where(UserSession.id == uuid.UUID(sid))
        )
    ).scalar_one()
    session.revoked = True
    await db_session.flush()

    response = await client.post(
        REFRESH_URL, json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 3. Logout really revokes
# ---------------------------------------------------------------------------

async def test_logout_then_refresh_is_rejected(client, db_session, user_factory):
    user = await user_factory(password=PASSWORD)
    tokens = await _login(client, user)

    logout = await client.post(
        LOGOUT_URL, json={"refresh_token": tokens["refresh_token"]}
    )
    assert logout.status_code == 200

    response = await client.post(
        REFRESH_URL, json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 401
    assert "revoked" in response.json()["detail"].lower()


async def test_logout_via_access_token_revokes_the_session(
    client, db_session, user_factory
):
    """No refresh token to hand -- the sid in the bearer token identifies it."""
    user = await user_factory(password=PASSWORD)
    tokens = await _login(client, user)

    logout = await client.post(
        LOGOUT_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert logout.status_code == 200

    sid = decode_token(tokens["refresh_token"])["sid"]
    session = (
        await db_session.execute(
            select(UserSession).where(UserSession.id == uuid.UUID(sid))
        )
    ).scalar_one()
    assert session.revoked is True


async def test_logout_marks_only_that_session(client, db_session, user_factory):
    """Signing out of one device must not sign the user out everywhere."""
    user = await user_factory(password=PASSWORD)
    first = await _login(client, user)
    second = await _login(client, user)

    await client.post(LOGOUT_URL, json={"refresh_token": first["refresh_token"]})

    assert (
        await client.post(REFRESH_URL, json={"refresh_token": first["refresh_token"]})
    ).status_code == 401
    assert (
        await client.post(REFRESH_URL, json={"refresh_token": second["refresh_token"]})
    ).status_code == 200


async def test_logout_without_any_credential_still_succeeds(client):
    """Whether a session existed is not something a caller should learn."""
    response = await client.post(LOGOUT_URL)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# 4. The refresh token is delivered as a cookie
# ---------------------------------------------------------------------------

async def test_login_sets_an_httponly_refresh_cookie(client, user_factory):
    user = await user_factory(password=PASSWORD)
    response = await client.post(
        LOGIN_URL, json={"email": user.email, "password": PASSWORD}
    )

    assert response.status_code == 200
    cookie_header = response.headers.get("set-cookie", "")
    assert REFRESH_COOKIE_NAME in cookie_header
    assert "httponly" in cookie_header.lower()
    assert f"path={REFRESH_COOKIE_PATH}" in cookie_header.lower()
    assert "samesite=lax" in cookie_header.lower()


async def test_refresh_works_from_the_cookie_alone(client, user_factory):
    """No body at all -- the browser flow sends only the cookie."""
    user = await user_factory(password=PASSWORD)
    await _login(client, user)  # httpx keeps the cookie on the client

    response = await client.post(REFRESH_URL)
    assert response.status_code == 200, response.text
    assert response.json()["access_token"]


async def test_logout_clears_the_cookie(client, user_factory):
    user = await user_factory(password=PASSWORD)
    await _login(client, user)

    response = await client.post(LOGOUT_URL)
    assert response.status_code == 200
    assert REFRESH_COOKIE_NAME in response.headers.get("set-cookie", "")


# ---------------------------------------------------------------------------
# 5. Access token lifetime
# ---------------------------------------------------------------------------

async def test_access_token_expiry_is_thirty_minutes():
    """An access token cannot be revoked, so its lifetime is the exposure
    window after a logout or a revocation."""
    from app.core.config import Settings

    assert Settings(_env_file=None).ACCESS_TOKEN_EXPIRE_MINUTES == 30


# ---------------------------------------------------------------------------
# 6. Password reset links are single-use
# ---------------------------------------------------------------------------

async def test_reset_token_cannot_be_replayed(client, user_factory, monkeypatch):
    """Reset once, then the identical token is refused and the old password
    stays dead."""
    from app.core import challenge_store
    from app.core.security import create_password_reset_token

    user = await user_factory(password=PASSWORD)
    token, jti = create_password_reset_token(user.email)
    challenge_store.register_reset_token(jti)

    first = await client.post(
        RESET_URL, json={"token": token, "new_password": "FirstNewPassword1!"}
    )
    assert first.status_code == 200, first.text

    replay = await client.post(
        RESET_URL, json={"token": token, "new_password": "SecondNewPassword2!"}
    )
    assert replay.status_code == 400
    assert "invalid or expired" in replay.json()["detail"].lower()

    # The replay must not have taken effect, and the original password must
    # still be dead.
    assert (
        await client.post(
            LOGIN_URL, json={"email": user.email, "password": "SecondNewPassword2!"}
        )
    ).status_code == 401
    assert (
        await client.post(LOGIN_URL, json={"email": user.email, "password": PASSWORD})
    ).status_code == 401
    assert (
        await client.post(
            LOGIN_URL, json={"email": user.email, "password": "FirstNewPassword1!"}
        )
    ).status_code == 200


async def test_reset_token_never_registered_is_refused(client, user_factory):
    """A correctly signed token with no server-side record cannot be spent."""
    from app.core.security import create_password_reset_token

    user = await user_factory(password=PASSWORD)
    token, _jti = create_password_reset_token(user.email)

    response = await client.post(
        RESET_URL, json={"token": token, "new_password": "WhateverPass123!"}
    )
    assert response.status_code == 400


async def test_short_password_does_not_burn_the_link(client, user_factory):
    """A rejected password must leave the link usable -- otherwise a typo costs
    the user another round trip through their inbox."""
    from app.core import challenge_store
    from app.core.security import create_password_reset_token

    user = await user_factory(password=PASSWORD)
    token, jti = create_password_reset_token(user.email)
    challenge_store.register_reset_token(jti)

    too_short = await client.post(RESET_URL, json={"token": token, "new_password": "abc"})
    assert too_short.status_code == 400

    retry = await client.post(
        RESET_URL, json={"token": token, "new_password": "ProperPassword123!"}
    )
    assert retry.status_code == 200, retry.text


async def test_password_reset_revokes_existing_sessions(
    client, db_session, user_factory
):
    """Reset is how a compromised account is recovered, so live sessions must
    not survive it."""
    from app.core import challenge_store
    from app.core.security import create_password_reset_token

    user = await user_factory(password=PASSWORD)
    tokens = await _login(client, user)

    token, jti = create_password_reset_token(user.email)
    challenge_store.register_reset_token(jti)
    reset = await client.post(
        RESET_URL, json={"token": token, "new_password": "RecoveredPass123!"}
    )
    assert reset.status_code == 200, reset.text

    response = await client.post(
        REFRESH_URL, json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 401
