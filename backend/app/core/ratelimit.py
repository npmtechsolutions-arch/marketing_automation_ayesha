"""Rate limiting.

Built on slowapi (a FastAPI wrapper around the ``limits`` package). Counters
live in Redis so limits hold across every worker and instance -- a per-process
counter is close to useless once the API runs more than one worker, since an
attacker's requests are spread across them.

Two ways to apply a limit:

* ``@limiter.limit(...)`` on an endpoint, for limits keyed on something visible
  in the request itself (the client IP).
* :func:`enforce_limit`, called inside the endpoint, for limits keyed on
  something only known after the body is parsed or the user is authenticated
  (an email address, a user id). slowapi's key functions receive only the
  ``Request`` and run before the body is available, so those cannot be
  expressed as decorators. Both paths share one storage backend and therefore
  one set of counters.

Client identity
---------------
The IP comes from the connection's peer address. Behind a reverse proxy (Render,
nginx, a load balancer) that is the *proxy's* address unless uvicorn is run with
``--proxy-headers``, in which case it resolves ``X-Forwarded-For`` for you.
Without that flag every client shares one bucket and legitimate traffic will
trip the limits. ``X-Forwarded-For`` is deliberately not read directly here:
trusting it unconditionally lets any client spoof its own identity and bypass
every IP-keyed limit.
"""

import logging
import time

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from limits import parse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.deps import get_current_active_user

logger = logging.getLogger(__name__)

# Per-user cap on AI generation endpoints. Temporary until database-backed
# entitlements land in Phase 1.3.
AI_GENERATION_LIMIT = "20/hour"

# How long to tell a blocked client to wait when the window cannot be read.
_DEFAULT_RETRY_AFTER = 60


def _storage_uri() -> str:
    """Return the limits storage URI, falling back to in-process memory.

    Redis is probed once at import. If it cannot be reached the limiter still
    works, but counters become per-process: limits then apply per worker rather
    than globally, which is a weaker guarantee than intended. That is a loud
    warning in production and expected in local development, where Redis is
    usually not running.
    """
    url = (settings.REDIS_URL or "").strip()
    if url:
        try:
            import redis

            client = redis.Redis.from_url(url, socket_connect_timeout=1)
            client.ping()
            client.close()
            return url
        except Exception as exc:  # noqa: BLE001 - any failure means "no Redis"
            message = (
                "Redis is not reachable at REDIS_URL (%s); rate-limit counters "
                "will be per-process, so limits apply per worker instead of "
                "globally."
            )
            if settings.DEBUG:
                logger.warning(message, exc)
            else:
                logger.error(message, exc)
    return "memory://"


limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri(),
    # Limits are declared per endpoint; nothing is limited by default.
    default_limits=[],
    # Off deliberately. With headers enabled slowapi injects X-RateLimit-* into
    # the endpoint's return value, which it requires to be a starlette Response
    # -- every endpoint here returns a Pydantic model, so enabling this breaks
    # each *successful* response on a limited route. Retry-After on the 429
    # itself is set by the handler below and by too_many_requests().
    headers_enabled=False,
)


def _retry_after(item, identifiers) -> int:
    """Seconds until the window resets, for the Retry-After header."""
    try:
        stats = limiter.limiter.get_window_stats(item, *identifiers)
        return max(1, int(stats.reset_time - time.time()))
    except Exception:  # noqa: BLE001 - never fail a request over a header
        return _DEFAULT_RETRY_AFTER


def too_many_requests(detail: str, retry_after: int) -> HTTPException:
    """Build a 429 carrying Retry-After."""
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detail,
        headers={"Retry-After": str(retry_after)},
    )


def enforce_limit(bucket: str, spec: str, *identifiers: str, detail: str) -> None:
    """Count one hit against ``bucket`` and raise 429 if the limit is exceeded.

    ``bucket`` namespaces the counter (e.g. ``"login:email"``) and
    ``identifiers`` are the values it is keyed on. ``spec`` is a limits
    expression such as ``"10/hour"``.

    Used for limits whose key is not derivable from the raw request -- an email
    from the parsed body, or an authenticated user id.
    """
    item = parse(spec)
    identifiers = tuple(str(i) for i in identifiers)
    if not limiter.limiter.hit(item, bucket, *identifiers):
        raise too_many_requests(detail, _retry_after(item, (bucket, *identifiers)))


def rate_limit_key_for_user(request: Request) -> str:
    """Key AI generation limits by user, falling back to IP.

    ``get_current_active_user`` stores the id on ``request.state``; it always
    runs first because these endpoints depend on it. The IP fallback only
    applies if the limit is ever attached to an unauthenticated route.
    """
    user_id = getattr(request.state, "rate_limit_user_id", None)
    return f"user:{user_id}" if user_id else f"ip:{get_remote_address(request)}"


async def rate_limit_exceeded_handler(request: Request, exc) -> JSONResponse:
    """Return slowapi's limit breaches as 429 + Retry-After, shaped like the
    app's other errors (``{"detail": ...}``)."""
    retry_after = _DEFAULT_RETRY_AFTER
    limit = getattr(exc, "limit", None)
    # slowapi wraps the parsed item differently across versions; try both.
    item = getattr(limit, "limit", None) or limit
    if item is not None:
        try:
            retry_after = _retry_after(item, (limiter._key_func(request),))
        except Exception:  # noqa: BLE001
            retry_after = _DEFAULT_RETRY_AFTER

    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": (
                "Too many requests. Please wait a moment and try again."
            )
        },
        headers={"Retry-After": str(retry_after)},
    )


async def ai_generation_rate_limit(
    request: Request,
    current_user=Depends(get_current_active_user),
):
    """Per-user cap on AI generation calls.

    Attached to the AI router so it covers every generation endpoint, including
    ones added later. Keyed on the user rather than the IP because these calls
    cost real money per request and a shared office IP should not throttle
    everyone at once.

    Temporary: superseded by database-backed entitlements in Phase 1.3.
    """
    # Also exposed for slowapi-decorated limits that key on the user.
    request.state.rate_limit_user_id = str(current_user.id)
    enforce_limit(
        "ai:generation",
        AI_GENERATION_LIMIT,
        str(current_user.id),
        detail=(
            "AI generation limit reached (20 per hour). "
            "Please wait before generating more content."
        ),
    )
    return current_user
