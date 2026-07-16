from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db


import asyncio
from app.core.scheduler import scheduled_post_worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    youtube_oauth,
)

# Include the aggregated v1 router (auth, users, accounts, teams, businesses)
app.include_router(api_v1_router)

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


# ---------------------------------------------------------------------------
# Root & health endpoints
# ---------------------------------------------------------------------------
@app.get("/", tags=["Root"])
async def root():
    return {"name": settings.APP_NAME, "version": settings.VERSION}


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}
