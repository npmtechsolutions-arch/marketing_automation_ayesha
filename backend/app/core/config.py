from pathlib import Path
from typing import ClassVar

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # General
    APP_NAME: str = "MarketEngine AI"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Auth / JWT
    SECRET_KEY: str = "change-me-in-production"
    JWT_SECRET_KEY: str = "change-me-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:MyNewPassword123@localhost:5432/marketing_automation"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Data retention: number of days a soft-deleted user is kept before the
    # scheduled hard-purge permanently removes them and their owned workspaces.
    SOFT_DELETE_RETENTION_DAYS: int = 30

    # AI
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_STARTER: str = ""
    STRIPE_PRICE_GROWTH: str = ""
    STRIPE_PRICE_PRO: str = ""

    # Social OAuth
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_CONFIG_ID: str = ""
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    # Must EXACTLY match the "Authorized redirect URL" configured in the LinkedIn app.
    LINKEDIN_REDIRECT_URI: str = "http://localhost:8000/api/v1/linkedin/callback"
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    # Must EXACTLY match an "Authorized redirect URI" in the Google Cloud OAuth client.
    YOUTUBE_REDIRECT_URI: str = "http://localhost:8000/api/v1/youtube/callback"
    TWITTER_CLIENT_ID: str = ""
    TWITTER_CLIENT_SECRET: str = ""
    # Must EXACTLY match a "Callback URI" in the X app's User authentication settings.
    TWITTER_REDIRECT_URI: str = "http://localhost:8000/api/v1/twitter/callback"

    # AWS S3
    S3_BUCKET: str = ""
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_ENDPOINT_URL: str = ""

    # Email
    SENDGRID_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@marketengine.ai"

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Load .env from the repository root (three levels above this file: backend/app/core)
    env_path: ClassVar[Path] = Path(__file__).resolve().parents[3] / ".env"

    model_config = {
        "env_file": str(env_path),
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Strip whitespaces from URLs and clean trailing slashes
        self.DATABASE_URL = self.DATABASE_URL.strip() if self.DATABASE_URL else ""
        
        if self.FRONTEND_URL:
            self.FRONTEND_URL = self.FRONTEND_URL.strip().rstrip("/")
            
        if self.LINKEDIN_REDIRECT_URI:
            self.LINKEDIN_REDIRECT_URI = self.LINKEDIN_REDIRECT_URI.strip()
        if self.YOUTUBE_REDIRECT_URI:
            self.YOUTUBE_REDIRECT_URI = self.YOUTUBE_REDIRECT_URI.strip()
        if self.TWITTER_REDIRECT_URI:
            self.TWITTER_REDIRECT_URI = self.TWITTER_REDIRECT_URI.strip()

        if self.DATABASE_URL.startswith("postgresql://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)


settings = Settings()
