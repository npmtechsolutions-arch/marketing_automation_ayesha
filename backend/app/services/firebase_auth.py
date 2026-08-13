"""Server-side verification of Firebase / Google Identity Platform ID tokens.

The frontend signs users in with the Firebase Google popup and posts the
resulting ID token to ``/auth/google/firebase``. That token is a JWT signed by
Google's Secure Token service. We MUST verify its signature and claims here
before trusting the identity it asserts — trusting a client-supplied email
without this verification is a complete authentication bypass.
"""

import time

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.x509 import load_pem_x509_certificate
from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings

# Google's public X.509 certs for the Secure Token service that signs Firebase
# ID tokens.
_CERTS_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)

# In-process cache of the signing certs, keyed by ``kid``. Google rotates these
# roughly daily and advertises the lifetime via the Cache-Control header.
_certs_cache: dict[str, str] = {}
_certs_expiry: float = 0.0


async def _get_signing_certs() -> dict[str, str]:
    global _certs_cache, _certs_expiry
    now = time.time()
    if _certs_cache and now < _certs_expiry:
        return _certs_cache

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(_CERTS_URL)
        resp.raise_for_status()
        certs = resp.json()

    # Honour the advertised max-age, defaulting to one hour.
    max_age = 3600
    for part in resp.headers.get("Cache-Control", "").split(","):
        part = part.strip()
        if part.startswith("max-age="):
            try:
                max_age = int(part.split("=", 1)[1])
            except ValueError:
                pass

    _certs_cache = certs
    _certs_expiry = now + max_age
    return certs


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


async def verify_firebase_id_token(id_token: str) -> dict:
    """Verify a Firebase ID token and return its validated claims.

    Raises ``HTTPException(401)`` if the token is missing, malformed, expired,
    or fails signature / issuer / audience validation, and ``503`` if Firebase
    auth is not configured on the server.
    """
    project_id = settings.FIREBASE_PROJECT_ID
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured",
        )
    if not id_token:
        raise _unauthorized("Missing Google credential")

    try:
        kid = jwt.get_unverified_header(id_token).get("kid")
    except JWTError:
        raise _unauthorized("Invalid Google credential")

    certs = await _get_signing_certs()
    cert_pem = certs.get(kid) if kid else None
    if not cert_pem:
        raise _unauthorized("Invalid Google credential")

    public_key_pem = (
        load_pem_x509_certificate(cert_pem.encode())
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )

    try:
        claims = jwt.decode(
            id_token,
            public_key_pem,
            algorithms=["RS256"],
            audience=project_id,
            issuer=f"https://securetoken.google.com/{project_id}",
        )
    except JWTError:
        raise _unauthorized("Invalid or expired Google credential")

    if not claims.get("email"):
        raise _unauthorized("Google account has no email address")

    return claims
