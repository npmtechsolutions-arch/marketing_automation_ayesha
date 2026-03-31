"""API v1 router - aggregates all endpoint routers."""

from fastapi import APIRouter

from app.api.v1.endpoints.accounts import router as accounts_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.businesses import router as businesses_router
from app.api.v1.endpoints.teams import router as teams_router
from app.api.v1.endpoints.users import router as users_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(accounts_router)
api_v1_router.include_router(teams_router)
api_v1_router.include_router(businesses_router)
