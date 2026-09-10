from pathlib import Path
from typing import ClassVar

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # General
    APP_NAME: str = "MarketEngine AI"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Encryption at rest for third-party credentials (social platform tokens).
    # A urlsafe-base64 32-byte Fernet key. Generate one with:
    #     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Required when DEBUG=false; see the boot guard at the bottom of this class.
    # Rotating this value makes every stored token undecryptable, so the
    # affected accounts must reconnect.
    TOKEN_ENCRYPTION_KEY: str = ""

    # Auth / JWT
    SECRET_KEY: str = "change-me-in-production"
    JWT_SECRET_KEY: str = "change-me-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    # Short-lived on purpose: an access token cannot be revoked once issued,
    # so its lifetime is the window an attacker keeps a stolen one. Session
    # continuity comes from the rotating refresh token instead.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database
    # Matches the docker-compose postgres service. A default that names a
    # real-looking password invites someone to reuse it.
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/marketengine"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Concurrency / performance
    # Max number of posts that may be published to the social platforms at the
    # same time. Keeps a spike of simultaneous publishes (e.g. many users firing
    # scheduled posts at once) from saturating CPU, threads and DB connections.
    MAX_CONCURRENT_PUBLISHES: int = 5
    # Size of the thread pool used for blocking work: bcrypt hashing, and the
    # small disk operations around the ffmpeg render. Platform HTTP no longer
    # runs here -- the connectors await it -- so this pool is far less
    # contended than it was, but it is still shared with password hashing.
    PUBLISH_THREAD_POOL_SIZE: int = 16

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
    # Allows an account admin to switch subscription tier directly, without a
    # Stripe payment. Intended for development/demo deployments that have no
    # Stripe keys — never enable this in production, it hands out paid tiers
    # for free. Must be set explicitly: there is no longer any combination of
    # other settings that turns it on by itself.
    BILLING_ALLOW_MANUAL_PLAN_CHANGE: bool = False

    # Social OAuth & AI Keys
    GEMINI_API_KEY: str = ""
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_CONFIG_ID: str = ""
    META_REDIRECT_URI: str = "http://localhost:8000/api/v1/facebook/callback"
    META_WEBHOOK_VERIFY_TOKEN: str = "marketengine_verify_token"
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    # Must EXACTLY match the "Authorized redirect URL" configured in the LinkedIn app.
    LINKEDIN_REDIRECT_URI: str = "http://localhost:8000/api/v1/linkedin/callback"
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    # Firebase project used by the frontend Google sign-in popup. The backend
    # verifies the ID token's signature/issuer/audience against this project.
    FIREBASE_PROJECT_ID: str = "marketengine-ai"
    # Must EXACTLY match an "Authorized redirect URI" in the Google Cloud OAuth client.
    YOUTUBE_REDIRECT_URI: str = "http://localhost:8000/api/v1/youtube/callback"
    # HubSpot, the v1 CRM. Free developer portal, public OAuth, and the two
    # contact scopes need no app review.
    HUBSPOT_CLIENT_ID: str = ""
    HUBSPOT_CLIENT_SECRET: str = ""
    HUBSPOT_REDIRECT_URI: str = "http://localhost:8000/api/v1/integrations/hubspot/callback"

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

    # This service's own public base URL. Needed because the local storage
    # backend hands the browser a URL to PUT to, and a relative one would
    # resolve against the frontend's origin, not ours. Unused when S3 is
    # configured -- those URLs come from AWS.
    BACKEND_URL: str = "http://localhost:8000"

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

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
        if self.BACKEND_URL:
            self.BACKEND_URL = self.BACKEND_URL.strip().rstrip("/")
            
        if self.LINKEDIN_REDIRECT_URI:
            self.LINKEDIN_REDIRECT_URI = self.LINKEDIN_REDIRECT_URI.strip()
        if self.GOOGLE_CLIENT_ID:
            self.GOOGLE_CLIENT_ID = self.GOOGLE_CLIENT_ID.strip()
        if self.GOOGLE_CLIENT_SECRET:
            self.GOOGLE_CLIENT_SECRET = self.GOOGLE_CLIENT_SECRET.strip()
        if self.YOUTUBE_REDIRECT_URI:
            self.YOUTUBE_REDIRECT_URI = self.YOUTUBE_REDIRECT_URI.strip()
        if self.TWITTER_REDIRECT_URI:
            self.TWITTER_REDIRECT_URI = self.TWITTER_REDIRECT_URI.strip()

        if self.DATABASE_URL.startswith("postgresql://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

        # Build list of allowed origins
        # Production origins come from CORS_ORIGINS / FRONTEND_URL in the
        # environment. Nothing is hardcoded here: an origin baked into the
        # source is one nobody remembers to remove when it stops being ours.
        allowed_set = set(self.CORS_ORIGINS)
        allowed_set.add("http://localhost:5173")
        allowed_set.add("http://localhost:3000")
        allowed_set.add("http://127.0.0.1:5173")
        
        if self.FRONTEND_URL:
            allowed_set.add(self.FRONTEND_URL)
            allowed_set.add(f"{self.FRONTEND_URL}/")

        self.CORS_ORIGINS = list(allowed_set)

        # SECURITY: refuse to boot a non-debug (production) instance that is
        # still signing tokens with a publicly-known placeholder secret. Doing
        # so would let anyone forge access tokens for any user. Local/dev runs
        # (DEBUG=true) are exempt so the defaults remain convenient.
        _insecure_secrets = {
            "change-me-in-production",
            "change-me-jwt-secret",
            "dev-secret-key-change-in-production",
            "dev-jwt-secret-change-in-production",
        }
        if not self.DEBUG and (
            self.SECRET_KEY in _insecure_secrets
            or self.JWT_SECRET_KEY in _insecure_secrets
        ):
            raise RuntimeError(
                "SECRET_KEY and JWT_SECRET_KEY must be set to strong, unique "
                "values in production (DEBUG=false). Refusing to start with a "
                "known placeholder secret."
            )

        # SECURITY: third-party access/refresh tokens are encrypted at rest with
        # TOKEN_ENCRYPTION_KEY. Without it a production instance would fall back
        # to a key derived from SECRET_KEY, which is a development convenience
        # and must never guard real users' platform credentials.
        if not self.DEBUG and not self.TOKEN_ENCRYPTION_KEY.strip():
            raise RuntimeError(
                "TOKEN_ENCRYPTION_KEY must be set in production (DEBUG=false). "
                "It encrypts stored social-platform credentials at rest. "
                "Generate one with:\n"
                '    python -c "from cryptography.fernet import Fernet; '
                "print(Fernet.generate_key().decode())\""
            )


settings = Settings()
