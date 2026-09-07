"""Authentication: register, login, 2FA, refresh, logout.

Happy paths and the failure paths that matter. The revocation and rotation
edge cases live in test_session_revocation.py; the enumeration and timing
properties in test_security_hardening.py. This module covers the flows
themselves end to end.
"""

import uuid

import pytest
import pyotp

from app.services import totp_service

pytestmark = pytest.mark.asyncio

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
TWOFA_URL = "/api/v1/auth/login/2fa"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/auth/me"

PASSWORD = "hunter2-correct-horse"


def _unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

async def test_register_creates_a_usable_account(client):
    email = _unique_email()
    response = await client.post(
        REGISTER_URL,
        json={"email": email, "password": PASSWORD, "full_name": "New Person"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == email

    login = await client.post(LOGIN_URL, json={"email": email, "password": PASSWORD})
    assert login.status_code == 200


async def test_register_gives_the_user_an_owned_account(client, auth_header):
    """Registration provisions a workspace; without it the app has nothing to
    show after sign-up."""
    email = _unique_email()
    response = await client.post(
        REGISTER_URL,
        json={"email": email, "password": PASSWORD, "full_name": "Owner"},
    )
    token = response.json()["access_token"]

    accounts = await client.get(
        "/api/v1/accounts/", headers={"Authorization": f"Bearer {token}"}
    )
    assert accounts.status_code == 200
    assert len(accounts.json()["items"]) == 1


async def test_duplicate_registration_is_rejected(client, user_factory):
    user = await user_factory(password=PASSWORD)
    response = await client.post(
        REGISTER_URL,
        json={"email": user.email, "password": PASSWORD, "full_name": "Impostor"},
    )
    assert response.status_code in (400, 409)


async def test_register_rejects_a_malformed_email(client):
    response = await client.post(
        REGISTER_URL,
        json={"email": "not-an-email", "password": PASSWORD, "full_name": "X"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

async def test_login_returns_tokens_and_the_user(client, user_factory):
    user = await user_factory(password=PASSWORD)
    response = await client.post(
        LOGIN_URL, json={"email": user.email, "password": PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requires_2fa"] is False
    assert body["access_token"] and body["refresh_token"]
    assert body["user"]["email"] == user.email


async def test_login_with_wrong_password_is_refused(client, user_factory):
    user = await user_factory(password=PASSWORD)
    response = await client.post(
        LOGIN_URL, json={"email": user.email, "password": "not-the-password"}
    )
    assert response.status_code == 401


async def test_inactive_user_cannot_log_in(client, user_factory):
    user = await user_factory(password=PASSWORD, is_active=False)
    response = await client.post(
        LOGIN_URL, json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code in (401, 403)


async def test_access_token_authenticates_a_request(client, user_factory):
    user = await user_factory(password=PASSWORD)
    tokens = (
        await client.post(LOGIN_URL, json={"email": user.email, "password": PASSWORD})
    ).json()

    me = await client.get(
        ME_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == user.email


async def test_me_requires_a_token(client):
    assert (await client.get(ME_URL)).status_code in (401, 403)


async def test_garbage_token_is_refused(client):
    response = await client.get(
        ME_URL, headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


async def test_refresh_token_cannot_be_used_as_an_access_token(client, user_factory):
    """They are both JWTs signed with the same key; only the `type` claim keeps
    a refresh token from authenticating requests directly."""
    user = await user_factory(password=PASSWORD)
    tokens = (
        await client.post(LOGIN_URL, json={"email": user.email, "password": PASSWORD})
    ).json()

    response = await client.get(
        ME_URL, headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Two-factor
# ---------------------------------------------------------------------------

async def _enable_2fa(db_session, user) -> str:
    secret = totp_service.generate_secret()
    user.totp_secret = secret
    user.two_factor_enabled = True
    await db_session.flush()
    return secret


async def test_login_with_2fa_returns_a_challenge_not_tokens(
    client, db_session, user_factory
):
    user = await user_factory(password=PASSWORD)
    await _enable_2fa(db_session, user)

    response = await client.post(
        LOGIN_URL, json={"email": user.email, "password": PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requires_2fa"] is True
    assert body["challenge_token"]
    assert not body.get("access_token"), "tokens must wait for the second factor"


async def test_2fa_completes_with_a_valid_code(client, db_session, user_factory):
    user = await user_factory(password=PASSWORD)
    secret = await _enable_2fa(db_session, user)
    challenge = (
        await client.post(LOGIN_URL, json={"email": user.email, "password": PASSWORD})
    ).json()["challenge_token"]

    response = await client.post(
        TWOFA_URL,
        json={"challenge_token": challenge, "code": pyotp.TOTP(secret).now()},
    )

    assert response.status_code == 200, response.text
    assert response.json()["access_token"]


async def test_2fa_rejects_a_wrong_code(client, db_session, user_factory):
    user = await user_factory(password=PASSWORD)
    await _enable_2fa(db_session, user)
    challenge = (
        await client.post(LOGIN_URL, json={"email": user.email, "password": PASSWORD})
    ).json()["challenge_token"]

    response = await client.post(
        TWOFA_URL, json={"challenge_token": challenge, "code": "000000"}
    )
    assert response.status_code == 400


async def test_2fa_rejects_a_garbage_challenge(client):
    response = await client.post(
        TWOFA_URL, json={"challenge_token": "nonsense", "code": "000000"}
    )
    assert response.status_code == 401


async def test_recovery_code_completes_2fa(client, db_session, user_factory):
    """The escape hatch when the authenticator is gone."""
    user = await user_factory(password=PASSWORD)
    await _enable_2fa(db_session, user)
    plain, hashed = totp_service.generate_recovery_codes(2)
    user.totp_recovery_codes = hashed
    await db_session.flush()

    challenge = (
        await client.post(LOGIN_URL, json={"email": user.email, "password": PASSWORD})
    ).json()["challenge_token"]

    response = await client.post(
        TWOFA_URL, json={"challenge_token": challenge, "code": plain[0]}
    )
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# Refresh and logout
# ---------------------------------------------------------------------------

async def test_refresh_returns_a_new_access_token(client, user_factory):
    user = await user_factory(password=PASSWORD)
    tokens = (
        await client.post(LOGIN_URL, json={"email": user.email, "password": PASSWORD})
    ).json()

    response = await client.post(
        REFRESH_URL, json={"refresh_token": tokens["refresh_token"]}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_refreshed_token_authenticates(client, user_factory):
    user = await user_factory(password=PASSWORD)
    tokens = (
        await client.post(LOGIN_URL, json={"email": user.email, "password": PASSWORD})
    ).json()
    refreshed = (
        await client.post(REFRESH_URL, json={"refresh_token": tokens["refresh_token"]})
    ).json()

    me = await client.get(
        ME_URL, headers={"Authorization": f"Bearer {refreshed['access_token']}"}
    )
    assert me.status_code == 200


async def test_refresh_with_garbage_is_refused(client):
    response = await client.post(REFRESH_URL, json={"refresh_token": "nonsense"})
    assert response.status_code == 401


async def test_logout_then_refresh_fails(client, user_factory):
    user = await user_factory(password=PASSWORD)
    tokens = (
        await client.post(LOGIN_URL, json={"email": user.email, "password": PASSWORD})
    ).json()

    assert (
        await client.post(LOGOUT_URL, json={"refresh_token": tokens["refresh_token"]})
    ).status_code == 200
    assert (
        await client.post(REFRESH_URL, json={"refresh_token": tokens["refresh_token"]})
    ).status_code == 401


async def test_logging_in_again_after_logout_works(client, user_factory):
    """Logout ends a session, not the account."""
    user = await user_factory(password=PASSWORD)
    tokens = (
        await client.post(LOGIN_URL, json={"email": user.email, "password": PASSWORD})
    ).json()
    await client.post(LOGOUT_URL, json={"refresh_token": tokens["refresh_token"]})

    again = await client.post(
        LOGIN_URL, json={"email": user.email, "password": PASSWORD}
    )
    assert again.status_code == 200
    assert again.json()["access_token"]
