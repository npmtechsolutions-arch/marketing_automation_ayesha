"""Authentication endpoints."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core import challenge_store
from app.core.ratelimit import enforce_limit, limiter, too_many_requests
from slowapi.util import get_remote_address
from app.core.security import (
    create_2fa_challenge_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash_async,
    verify_2fa_challenge_token,
    verify_password_async,
    create_password_reset_token,
    verify_password_reset_token,
)
from app.models.account import Account, SubscriptionStatus, SubscriptionTier
from app.models.team_member import InvitationStatus, TeamMember, TeamRole
from app.models.user import User
from app.models.user_session import UserSession
from app.services import totp_service
from app.services.email_service import EmailService
from app.services.firebase_auth import verify_firebase_id_token
from app.schemas.common import MessageResponse
from app.schemas.user import (
    FirebaseGoogleAuthRequest,
    GoogleAuthRequest,
    LoginResult,
    PasswordReset,
    PasswordResetConfirm,
    TokenRefresh,
    TwoFactorLogin,
    UserCreate,
    UserLogin,
    UserResponse,
    UserWithToken,
)
import httpx
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a name."""
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{slug}-{uuid.uuid4().hex[:8]}"


def _device_from_user_agent(ua: str | None) -> str:
    """Derive a short, human-friendly device label from a User-Agent string."""
    if not ua:
        return "Unknown device"
    ua_l = ua.lower()
    if "iphone" in ua_l:
        os_name = "iPhone"
    elif "ipad" in ua_l:
        os_name = "iPad"
    elif "android" in ua_l:
        os_name = "Android"
    elif "windows" in ua_l:
        os_name = "Windows"
    elif "mac os" in ua_l or "macintosh" in ua_l:
        os_name = "macOS"
    elif "linux" in ua_l:
        os_name = "Linux"
    else:
        os_name = "Unknown OS"

    if "edg/" in ua_l:
        browser = "Edge"
    elif "chrome" in ua_l and "chromium" not in ua_l:
        browser = "Chrome"
    elif "firefox" in ua_l:
        browser = "Firefox"
    elif "safari" in ua_l:
        browser = "Safari"
    else:
        browser = "Browser"
    return f"{browser} on {os_name}"


# The refresh token is delivered as a cookie rather than in the response body so
# that page scripts cannot read it: an XSS on the app can still call the API as
# the user, but it cannot exfiltrate a long-lived credential. Scoped to the auth
# path so it is not attached to every ordinary API call.
REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        # Secure cookies are dropped over plain http. Browsers treat localhost
        # as a secure context so development still works, but a dev server on a
        # LAN address would not -- hence relaxing it under DEBUG only.
        secure=not settings.DEBUG,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH, httponly=True,
        secure=not settings.DEBUG, samesite="lax",
    )


def _read_refresh_token(request: Request, payload: TokenRefresh | None) -> str | None:
    """Take an explicitly supplied token over the ambient cookie.

    Browsers send only the cookie, so they are unaffected. A client that names a
    token in the body means that one -- silently preferring whatever cookie
    happened to be attached would act on a different session than the caller
    asked for.
    """
    if payload is not None and payload.refresh_token:
        return payload.refresh_token
    return request.cookies.get(REFRESH_COOKIE_NAME)


async def _issue_session_tokens(
    db: AsyncSession, user: User, request: Request | None, response: Response
) -> UserWithToken:
    """Create a UserSession row and return access/refresh tokens bound to it.

    Both tokens carry the session id (``sid``). The refresh token additionally
    carries ``rjti``, the current rotation id: it changes on every refresh, so a
    refresh token can only be spent once. Called only after full authentication.
    """
    session_id = uuid.uuid4()
    sid = session_id.hex
    refresh_jti = uuid.uuid4().hex

    ua = request.headers.get("user-agent") if request else None
    ip = None
    if request is not None:
        fwd = request.headers.get("x-forwarded-for")
        ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)

    db.add(
        UserSession(
            id=session_id,
            user_id=user.id,
            refresh_jti=refresh_jti,
            device=_device_from_user_agent(ua),
            user_agent=ua,
            ip_address=ip,
        )
    )
    await db.flush()

    token_data = {"sub": str(user.id), "sid": sid}
    refresh = create_refresh_token({**token_data, "rjti": refresh_jti})
    _set_refresh_cookie(response, refresh)
    return UserWithToken(
        user=UserResponse.model_validate(user),
        access_token=create_access_token(token_data),
        refresh_token=refresh,
    )


@router.post(
    "/register",
    response_model=UserWithToken,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/hour")
async def register(
    payload: UserCreate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account.

    Creates the user, a default account, and an owner team membership.
    """
    # Check for existing email
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    # Create user
    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        full_name=payload.full_name,
        password_hash=await get_password_hash_async(payload.password),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Create default account
    account = Account(
        id=uuid.uuid4(),
        name=f"{payload.full_name}'s Workspace",
        slug=_generate_slug(payload.full_name),
        owner_id=user.id,
        subscription_tier=SubscriptionTier.FREE,
        subscription_status=SubscriptionStatus.TRIALING,
    )
    db.add(account)
    await db.flush()

    # Create owner team membership
    team_member = TeamMember(
        id=uuid.uuid4(),
        user_id=user.id,
        account_id=account.id,
        role=TeamRole.OWNER,
        invitation_status=InvitationStatus.ACCEPTED,
        accepted_at=datetime.now(timezone.utc),
    )
    db.add(team_member)
    await db.flush()

    # Generate tokens (register never requires 2FA — it's a brand new account)
    return await _issue_session_tokens(db, user, request, response)


@router.post("/login", response_model=LoginResult)
@limiter.limit("5/minute")
async def login(
    payload: UserLogin,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate a user.

    If the account has 2FA enabled, returns a short-lived challenge token that
    must be completed via ``/auth/login/2fa``. Otherwise returns tokens.
    """
    # Per-email limit on top of the per-IP decorator: stops a single account
    # being ground down from many addresses. Counted before the lookup so it
    # also covers addresses that do not exist, which would otherwise leave an
    # unlimited enumeration oracle.
    enforce_limit(
        "login:email",
        "10/hour",
        payload.email.strip().lower(),
        detail="Too many sign-in attempts for this account. Try again later.",
    )

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID / Email was not found. Please check your email or sign up.",
        )

    if not await verify_password_async(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password. Please verify your password and try again.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deleted",
        )

    # Password OK. If 2FA is on, defer token issuance to the 2FA step.
    if user.two_factor_enabled:
        challenge_token, jti = create_2fa_challenge_token(str(user.id))
        # Record it server-side so it can be consumed exactly once and its
        # wrong-code attempts counted.
        challenge_store.register_challenge(jti)
        return LoginResult(
            requires_2fa=True,
            challenge_token=challenge_token,
        )

    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)

    tokens = await _issue_session_tokens(db, user, request, response)
    return LoginResult(
        requires_2fa=False,
        user=tokens.user,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post("/login/2fa", response_model=LoginResult)
# Higher than /login's 5/minute on purpose: the binding constraint here is the
# per-challenge cap of 5 wrong codes (challenge_store.MAX_FAILED_ATTEMPTS). At
# 5/minute the IP limit fired first and shadowed it, and a user who fumbled
# their code then signed in again was blocked for a minute despite holding a
# fresh challenge. This still bounds a distributed attack while letting the
# per-challenge cap do the work it exists for.
@limiter.limit("15/minute")
async def login_2fa(
    payload: TwoFactorLogin,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Complete a 2FA login using a TOTP code or a recovery code."""
    decoded = verify_2fa_challenge_token(payload.challenge_token)
    if decoded is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your verification session expired. Please sign in again.",
        )
    user_id, jti = decoded

    # A valid signature is not enough: the challenge must still be outstanding.
    # This rejects a token that was already used to sign in, so capturing one
    # does not give an attacker a reusable credential.
    if not challenge_store.challenge_is_active(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your verification session expired. Please sign in again.",
        )

    # Cap wrong codes per challenge so a captured token cannot be used to
    # brute-force a six-digit TOTP.
    if challenge_store.failed_attempts(jti) >= challenge_store.MAX_FAILED_ATTEMPTS:
        raise too_many_requests(
            "Too many incorrect codes for this sign-in attempt. "
            "Please sign in again to get a new verification session.",
            retry_after=challenge_store.CHALLENGE_TTL_SECONDS,
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not verify your account.",
        )

    code = (payload.code or "").strip()
    verified = totp_service.verify_code(user.totp_secret, code)

    # Fall back to consuming a one-time recovery code.
    if not verified:
        remaining = totp_service.consume_recovery_code(
            code, user.totp_recovery_codes or []
        )
        if remaining is not None:
            user.totp_recovery_codes = remaining
            verified = True

    if not verified:
        # Record the miss and report it as an invalid code. The cap is enforced
        # by the pre-check above, so MAX_FAILED_ATTEMPTS wrong codes each get a
        # plain 400 and the *next* submission is the one refused with 429.
        challenge_store.record_failed_attempt(jti)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code.",
        )

    # Correct code: burn the challenge so it cannot be replayed. Losing the
    # race here means another request already consumed it.
    if not challenge_store.consume_challenge(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your verification session expired. Please sign in again.",
        )

    user.last_login_at = datetime.now(timezone.utc)
    tokens = await _issue_session_tokens(db, user, request, response)
    return LoginResult(
        requires_2fa=False,
        user=tokens.user,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post("/refresh", response_model=UserWithToken)
async def refresh_token(
    request: Request,
    response: Response,
    payload: TokenRefresh | None = Body(None),
    db: AsyncSession = Depends(get_db),
):
    """Exchange a refresh token for a new access/refresh pair.

    The token must be bound to a live session and must present that session's
    *current* rotation id. Three things are enforced here, each of which was a
    way to keep using a session that should have ended:

    * A token without ``sid`` is rejected. These used to be accepted as
      "legacy", which meant anyone holding one bypassed revocation entirely.
    * A ``sid`` with no matching session row is rejected. The old code looked
      the session up but issued fresh tokens anyway when it found nothing.
    * A stale ``rjti`` revokes the whole session. Refresh tokens rotate on every
      use, so a superseded one being presented means two parties hold the same
      token -- i.e. it was stolen. There is no way to tell victim from thief, so
      the session ends for both and the real user signs in again.
    """
    raw_token = _read_refresh_token(request, payload)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )

    token_payload = decode_token(raw_token)

    if token_payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type: expected refresh token",
        )

    user_id = token_payload.get("sub")
    sid = token_payload.get("sid")
    presented_jti = token_payload.get("rjti")

    if user_id is None or not sid or not presented_jti:
        # Pre-session tokens land here. They cannot be revoked, so they are no
        # longer honoured; the user signs in again once.
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This session is no longer valid. Please sign in again.",
        )

    try:
        session_uuid = uuid.UUID(sid)
    except (ValueError, AttributeError):
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This session is no longer valid. Please sign in again.",
        )

    session = (
        await db.execute(select(UserSession).where(UserSession.id == session_uuid))
    ).scalar_one_or_none()

    if session is None or session.revoked:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This session has been revoked. Please sign in again.",
        )

    if session.refresh_jti != presented_jti:
        # Reuse of a rotated token: the current holder and whoever spent it
        # before are not the same party. Kill the session rather than guess.
        session.revoked = True
        # Commit before raising. get_db rolls the session back when the request
        # raises, which would silently undo this revocation -- the whole point
        # of detecting the reuse.
        await db.commit()
        _clear_refresh_cookie(response)
        logger.warning(
            "Refresh token reuse detected; session revoked. session=%s user=%s",
            sid,
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This session has been revoked. Please sign in again.",
        )

    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None or not user.is_active or user.deleted_at is not None:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Rotate: the token just spent is now worthless, and presenting it again
    # trips the reuse branch above.
    new_jti = uuid.uuid4().hex
    session.refresh_jti = new_jti
    session.last_active_at = datetime.now(timezone.utc)

    token_data = {"sub": str(user.id), "sid": sid}
    new_refresh_token = create_refresh_token({**token_data, "rjti": new_jti})
    await db.flush()
    _set_refresh_cookie(response, new_refresh_token)

    return UserWithToken(
        user=UserResponse.model_validate(user),
        access_token=create_access_token(token_data),
        refresh_token=new_refresh_token,
    )


@router.get("/me", response_model=UserResponse)
async def get_auth_me(
    current_user: User = Depends(get_current_active_user),
):
    """Return current authenticated user profile."""
    return UserResponse.model_validate(current_user)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    payload: TokenRefresh | None = Body(None),
    db: AsyncSession = Depends(get_db),
):
    """End the current session.

    Identifies the session from the refresh token (cookie or body) or, failing
    that, from the ``sid`` in the bearer access token, and marks that
    UserSession revoked so no further refresh can succeed. The access token
    already issued stays valid until it expires -- that window is why
    ACCESS_TOKEN_EXPIRE_MINUTES is short.

    Always reports success: whether a given session existed is not something an
    unauthenticated caller should be able to probe.
    """
    sid = None

    raw_refresh = _read_refresh_token(request, payload)
    if raw_refresh:
        try:
            sid = decode_token(raw_refresh).get("sid")
        except HTTPException:
            sid = None

    if not sid:
        # Fall back to the access token's session id.
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            try:
                sid = decode_token(auth_header.split(" ", 1)[1]).get("sid")
            except HTTPException:
                sid = None

    if sid:
        try:
            session_uuid = uuid.UUID(sid)
        except (ValueError, AttributeError):
            session_uuid = None
        if session_uuid is not None:
            session = (
                await db.execute(
                    select(UserSession).where(UserSession.id == session_uuid)
                )
            ).scalar_one_or_none()
            if session is not None and not session.revoked:
                session.revoked = True
                await db.flush()

    _clear_refresh_cookie(response)
    return MessageResponse(message="Successfully logged out")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: PasswordReset,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset email."""
    # Keyed on IP *and* email together, so one address cannot be spammed with
    # reset mail and one client cannot walk a list of addresses.
    enforce_limit(
        "forgot-password",
        "3/hour",
        get_remote_address(request),
        payload.email.strip().lower(),
        detail="Too many password reset requests. Please try again later.",
    )

    # Look up user (but always return success to prevent enumeration)
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is not None and user.is_active:
        token, reset_jti = create_password_reset_token(user.email)
        # Recorded server-side so the link can be spent exactly once.
        challenge_store.register_reset_token(reset_jti)
        # Queued rather than awaited: the response must not depend on the mail
        # provider being reachable, and the timing must not differ between a
        # known and an unknown address (which would undo the generic response
        # below and turn this into an account-enumeration oracle).
        background_tasks.add_task(
            EmailService.send_password_reset_email, user.email, token
        )

    return MessageResponse(
        message="If an account with that email exists, a reset link has been sent"
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """Reset the password using a valid reset token."""
    decoded = verify_password_reset_token(payload.token)
    if decoded is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    email, reset_jti = decoded

    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found or inactive",
        )

    # Spend the link. The delete is atomic, so a replayed link -- or two
    # concurrent submissions of the same one -- succeeds at most once. Done
    # after validation so a rejected password does not burn the user's link.
    if not challenge_store.consume_reset_token(reset_jti):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.password_hash = await get_password_hash_async(payload.new_password)
    db.add(user)

    # A password reset is how someone recovers a compromised account, so every
    # existing session must end -- otherwise whoever prompted the reset keeps
    # their refresh token and simply carries on.
    existing_sessions = (
        await db.execute(
            select(UserSession).where(
                UserSession.user_id == user.id, UserSession.revoked.is_(False)
            )
        )
    ).scalars().all()
    for session in existing_sessions:
        session.revoked = True
    await db.flush()

    return MessageResponse(message="Password has been reset successfully")


@router.get("/google/url")
async def get_google_auth_url(redirect_uri: str | None = None):
    """Return Google OAuth 2.0 authorization URL for user login and signup."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured. Please set GOOGLE_CLIENT_ID in settings.",
        )

    cb_uri = redirect_uri or f"{settings.FRONTEND_URL}/auth/callback/google"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": cb_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return {"auth_url": auth_url}


@router.post("/google/callback", response_model=UserWithToken)
async def google_auth_callback(
    payload: GoogleAuthRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Exchange Google OAuth code for tokens, and log in or register user."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured on this server.",
        )

    cb_uri = payload.redirect_uri or f"{settings.FRONTEND_URL}/auth/callback/google"

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": payload.code,
                "grant_type": "authorization_code",
                "redirect_uri": cb_uri,
            },
        )
        if token_resp.status_code != 200:
            error_data = token_resp.json() if token_resp.headers.get("content-type", "").startswith("application/json") else {}
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_data.get("error_description") or "Failed to exchange authorization code with Google.",
            )

        token_data = token_resp.json()
        google_access_token = token_data.get("access_token")
        if not google_access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No access token received from Google.",
            )

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {google_access_token}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch profile information from Google.",
            )
        google_profile = userinfo_resp.json()

    email = google_profile.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account did not return an email address.",
        )

    full_name = google_profile.get("name") or email.split("@")[0]
    picture = google_profile.get("picture")

    # Find existing user by email
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is not None:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated.",
            )
        # Update user avatar / email verification if needed
        if not user.avatar_url and picture:
            user.avatar_url = picture
        user.email_verified = True
        user.last_login_at = datetime.now(timezone.utc)
        db.add(user)
        await db.flush()

        # Check if user has an account workspace; if not, create one
        account_member = await db.execute(
            select(TeamMember).where(TeamMember.user_id == user.id).limit(1)
        )
        if account_member.scalars().first() is None:
            account = Account(
                id=uuid.uuid4(),
                name=f"{user.full_name}'s Workspace",
                slug=_generate_slug(user.full_name),
                owner_id=user.id,
                subscription_tier=SubscriptionTier.FREE,
                subscription_status=SubscriptionStatus.TRIALING,
            )
            db.add(account)
            await db.flush()

            team_member = TeamMember(
                id=uuid.uuid4(),
                user_id=user.id,
                account_id=account.id,
                role=TeamRole.OWNER,
                invitation_status=InvitationStatus.ACCEPTED,
                accepted_at=datetime.now(timezone.utc),
            )
            db.add(team_member)
            await db.flush()
    else:
        # Create brand new user via Google Sign-In
        user = User(
            id=uuid.uuid4(),
            email=email,
            full_name=full_name,
            avatar_url=picture,
            password_hash=await get_password_hash_async(uuid.uuid4().hex + uuid.uuid4().hex),
            is_active=True,
            email_verified=True,
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()

        # Create default workspace
        account = Account(
            id=uuid.uuid4(),
            name=f"{full_name}'s Workspace",
            slug=_generate_slug(full_name),
            owner_id=user.id,
            subscription_tier=SubscriptionTier.FREE,
            subscription_status=SubscriptionStatus.TRIALING,
        )
        db.add(account)
        await db.flush()

        # Create owner team membership
        team_member = TeamMember(
            id=uuid.uuid4(),
            user_id=user.id,
            account_id=account.id,
            role=TeamRole.OWNER,
            invitation_status=InvitationStatus.ACCEPTED,
            accepted_at=datetime.now(timezone.utc),
        )
        db.add(team_member)
        await db.flush()

    return await _issue_session_tokens(db, user, request, response)


@router.get("/google/callback")
async def google_auth_callback_get(code: str | None = None, error: str | None = None, error_description: str | None = None):
    """Fallback GET callback if Google redirects directly to backend."""
    from fastapi.responses import RedirectResponse
    from urllib.parse import urlencode

    query_params = {}
    if code:
        query_params["code"] = code
    if error:
        query_params["error"] = error
    if error_description:
        query_params["error_description"] = error_description

    target_url = f"{settings.FRONTEND_URL}/auth/callback/google?{urlencode(query_params)}"
    return RedirectResponse(url=target_url)


@router.post("/google/firebase", response_model=UserWithToken)
async def google_firebase_auth(
    payload: FirebaseGoogleAuthRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate or register user via Firebase Google OAuth Popup token."""
    # SECURITY: never trust the client-supplied email. Verify the Firebase ID
    # token server-side and derive the identity from its signed claims. Without
    # this, anyone could POST an arbitrary email and be logged in as that user.
    claims = await verify_firebase_id_token(payload.id_token)
    email = claims.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account has no email address",
        )
    full_name = claims.get("name") or payload.full_name or email.split("@")[0]
    picture = claims.get("picture") or payload.avatar_url

    # Look up existing user by email
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is not None:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated.",
            )
        if not user.avatar_url and picture:
            user.avatar_url = picture
        user.email_verified = True
        user.last_login_at = datetime.now(timezone.utc)
        db.add(user)
        await db.flush()

        # Check if user has an account workspace; if not, create one
        account_member = await db.execute(
            select(TeamMember).where(TeamMember.user_id == user.id).limit(1)
        )
        if account_member.scalars().first() is None:
            account = Account(
                id=uuid.uuid4(),
                name=f"{user.full_name}'s Workspace",
                slug=_generate_slug(user.full_name),
                owner_id=user.id,
                subscription_tier=SubscriptionTier.FREE,
                subscription_status=SubscriptionStatus.TRIALING,
            )
            db.add(account)
            await db.flush()

            team_member = TeamMember(
                id=uuid.uuid4(),
                user_id=user.id,
                account_id=account.id,
                role=TeamRole.OWNER,
                invitation_status=InvitationStatus.ACCEPTED,
                accepted_at=datetime.now(timezone.utc),
            )
            db.add(team_member)
            await db.flush()
    else:
        # Create new user via Firebase Google Sign-In
        user = User(
            id=uuid.uuid4(),
            email=email,
            full_name=full_name,
            avatar_url=picture,
            password_hash=await get_password_hash_async(uuid.uuid4().hex + uuid.uuid4().hex),
            is_active=True,
            email_verified=True,
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()

        # Create default workspace
        account = Account(
            id=uuid.uuid4(),
            name=f"{full_name}'s Workspace",
            slug=_generate_slug(full_name),
            owner_id=user.id,
            subscription_tier=SubscriptionTier.FREE,
            subscription_status=SubscriptionStatus.TRIALING,
        )
        db.add(account)
        await db.flush()

        # Create owner team membership
        team_member = TeamMember(
            id=uuid.uuid4(),
            user_id=user.id,
            account_id=account.id,
            role=TeamRole.OWNER,
            invitation_status=InvitationStatus.ACCEPTED,
            accepted_at=datetime.now(timezone.utc),
        )
        db.add(team_member)
        await db.flush()

    return await _issue_session_tokens(db, user, request, response)

