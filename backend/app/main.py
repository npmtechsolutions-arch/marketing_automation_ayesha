import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from slowapi.errors import RateLimitExceeded

from app.core import ratelimit
from app.core.config import settings
from app.core.database import init_db

logger = logging.getLogger("app")


import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.core.scheduler import scheduled_post_worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    # Blocking work (bcrypt password hashing, ffmpeg video rendering, blocking
    # disk I/O around the ffmpeg render) runs via asyncio.to_thread on the
    # loop's default executor. Python's default pool is only ~min(32, cpu+4)
    # threads — on a small instance that's ~5, which bcrypt alone can saturate.
    # Give the loop an explicit, roomier pool sized from settings.
    #
    # Platform HTTP used to land here too, which was the original reason for
    # the size: an Instagram poll or a YouTube upload could hold a thread for
    # minutes. The connectors now await their requests, so that pressure is
    # gone; the pool is kept roomy for hashing.
    loop = asyncio.get_running_loop()
    loop.set_default_executor(
        ThreadPoolExecutor(
            max_workers=settings.PUBLISH_THREAD_POOL_SIZE,
            thread_name_prefix="blocking",
        )
    )
    await init_db()
    worker_task = asyncio.create_task(scheduled_post_worker())
    yield
    # Shutdown (cleanup resources if needed)
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered marketing automation platform for content creation, scheduling, and analytics.",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate limiting. The limiter is attached to app.state (slowapi reads it from
# there) and RateLimitExceeded is mapped to a 429 carrying Retry-After.
app.state.limiter = ratelimit.limiter
app.add_exception_handler(RateLimitExceeded, ratelimit.rate_limit_exceeded_handler)

# CORS middleware
# Credentials are now sent cross-origin (the refresh token rides in a cookie),
# so the allow-list must be exact. The previous allow_origin_regex matched every
# *.onrender.com host -- anyone can deploy there, and combined with
# allow_credentials that let an attacker-controlled origin make credentialed
# requests to this API and read the responses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# A registered Exception handler runs on Starlette's outermost error middleware,
# so its response bypasses CORSMiddleware and would otherwise ship WITHOUT the
# Access-Control-Allow-Origin header — making every 500 look like a CORS failure
# in the browser. Echo the CORS headers here so the frontend sees the real error.



def _cors_headers_for(request: Request) -> dict[str, str]:
    origin = request.headers.get("origin")
    if origin and origin in settings.CORS_ORIGINS:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return a JSON 500 (with CORS headers) instead of a header-less error."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    detail = f"{type(exc).__name__}: {exc}" if settings.DEBUG else "Internal server error"
    return JSONResponse(
        status_code=500,
        content={"detail": detail},
        headers=_cors_headers_for(request),
    )

# ---------------------------------------------------------------------------
# API v1 routers
# ---------------------------------------------------------------------------
from app.api.v1.router import api_v1_router
from app.api.v1.endpoints import (
    activity,
    admin,
    ai,
    analytics,
    billing,
    campaigns,
    facebook_oauth,
    instagram_oauth,
    linkedin_oauth,
    notifications,
    posts,
    settings as settings_routes,
    social_accounts,
    social_platforms,
    strategies,
    twitter_oauth,
    media,
    uploads,
    youtube_oauth,
    webhooks,
)

# Serve uploaded files (avatars, business logos) as static assets.
_uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
_uploads_dir.mkdir(parents=True, exist_ok=True)
# Served with X-Content-Type-Options: nosniff so a browser cannot MIME-sniff
# user-uploaded content into something executable on our own origin.
app.mount(
    "/uploads",
    uploads.NoSniffStaticFiles(directory=str(_uploads_dir)),
    name="uploads",
)

# Include the aggregated v1 router (auth, users, accounts, teams, businesses)
app.include_router(api_v1_router)

# Generic authenticated file uploads
app.include_router(uploads.router, prefix="/api/v1/uploads", tags=["Uploads"])

# Webhooks router
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])

# Additional routers with account-scoped prefixes
app.include_router(posts.router,            prefix="/api/v1/accounts/{account_id}/posts",       tags=["Content"])
app.include_router(ai.router,               prefix="/api/v1/accounts/{account_id}/ai",          tags=["AI Content Generation"])
app.include_router(analytics.router,        prefix="/api/v1/accounts/{account_id}/analytics",   tags=["Analytics"])
app.include_router(strategies.router,       prefix="/api/v1/accounts/{account_id}/strategies",  tags=["Strategies"])
app.include_router(campaigns.router,        prefix="/api/v1/accounts/{account_id}/campaigns",   tags=["Campaigns"])
app.include_router(notifications.router,    prefix="/api/v1/notifications",                     tags=["Notifications"])
app.include_router(billing.router,          prefix="/api/v1/accounts/{account_id}/billing",     tags=["Billing"])
app.include_router(settings_routes.router,  prefix="/api/v1/accounts/{account_id}/settings",    tags=["Settings"])
app.include_router(social_platforms.router,  prefix="/api/v1/accounts/{account_id}/social-platforms", tags=["Social Platforms"])
app.include_router(social_accounts.router,  prefix="/api/v1/accounts/{account_id}/social-accounts",  tags=["Social Accounts"])
app.include_router(linkedin_oauth.router,   prefix="/api/v1/accounts/{account_id}/linkedin",         tags=["LinkedIn OAuth"])
app.include_router(linkedin_oauth.callback_router, prefix="/api/v1",                                  tags=["LinkedIn OAuth"])
app.include_router(facebook_oauth.router,   prefix="/api/v1/accounts/{account_id}/facebook",         tags=["Facebook OAuth"])
app.include_router(facebook_oauth.callback_router, prefix="/api/v1",                                  tags=["Facebook OAuth"])
app.include_router(instagram_oauth.router,  prefix="/api/v1/accounts/{account_id}/instagram",        tags=["Instagram OAuth"])
app.include_router(instagram_oauth.callback_router, prefix="/api/v1",                                 tags=["Instagram OAuth"])
app.include_router(twitter_oauth.router,    prefix="/api/v1/accounts/{account_id}/twitter",          tags=["Twitter OAuth"])
app.include_router(twitter_oauth.callback_router,  prefix="/api/v1",                                  tags=["Twitter OAuth"])
app.include_router(youtube_oauth.router,    prefix="/api/v1/accounts/{account_id}/youtube",          tags=["YouTube OAuth"])
app.include_router(youtube_oauth.callback_router,  prefix="/api/v1",                                  tags=["YouTube OAuth"])
app.include_router(activity.router,         prefix="/api/v1/accounts/{account_id}/activity",          tags=["Activity"])
app.include_router(admin.router,            prefix="/api/v1/admin",                             tags=["Admin Panel"])
app.include_router(media.router,            prefix="/api/v1/accounts/{account_id}/media",        tags=["Media Library"])
# The local-storage upload/download shims are workspace-agnostic: the signed key
# carries the workspace, and the browser PUTs to them without an Authorization
# header, exactly as it would to S3.
app.include_router(media.local_router,      prefix="/api/v1/media",                              tags=["Media Library"])


# ---------------------------------------------------------------------------
# Root & health endpoints
# ---------------------------------------------------------------------------
@app.get("/", tags=["Root"])
async def root():
    return {"name": settings.APP_NAME, "version": settings.VERSION}


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}
