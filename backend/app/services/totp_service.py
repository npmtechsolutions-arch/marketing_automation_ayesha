"""TOTP two-factor authentication helpers.

Wraps ``pyotp`` for secret generation / code verification and renders an
enrollment QR code (as a base64 data URL) with ``qrcode``. Recovery codes are
generated in plaintext (shown to the user once) and stored elsewhere as SHA-256
hashes so a database leak never exposes usable codes.
"""

import base64
import hashlib
import io
import secrets

import pyotp
import qrcode

# Shown in the authenticator app as the account issuer.
ISSUER = "MarketEngine"


def generate_secret() -> str:
    """Return a new random base32 TOTP secret."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, account_label: str) -> str:
    """Build the otpauth:// URI used to enroll an authenticator app."""
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=account_label, issuer_name=ISSUER
    )


def qr_data_url(secret: str, account_label: str) -> str:
    """Render the provisioning URI as a base64 PNG data URL for <img src>."""
    uri = provisioning_uri(secret, account_label)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def verify_code(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code, allowing a +/- 1 step clock drift window."""
    if not secret or not code:
        return False
    return pyotp.TOTP(secret).verify(code.strip().replace(" ", ""), valid_window=1)


# ---------------------------------------------------------------------------
# Recovery codes
# ---------------------------------------------------------------------------

def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()


def generate_recovery_codes(count: int = 8) -> tuple[list[str], list[str]]:
    """Generate recovery codes.

    Returns ``(plaintext_codes, hashed_codes)``. Show the plaintext to the user
    exactly once; persist only the hashes.
    """
    plaintext: list[str] = []
    for _ in range(count):
        raw = secrets.token_hex(4).upper()  # 8 hex chars
        plaintext.append(f"{raw[:4]}-{raw[4:]}")
    hashed = [_hash_code(c) for c in plaintext]
    return plaintext, hashed


def consume_recovery_code(code: str, hashed_codes: list[str]) -> list[str] | None:
    """If ``code`` matches an unused hashed code, return the remaining hashes
    (with the used one removed). Returns ``None`` if the code is invalid.
    """
    if not code or not hashed_codes:
        return None
    target = _hash_code(code)
    if target not in hashed_codes:
        return None
    return [h for h in hashed_codes if h != target]
