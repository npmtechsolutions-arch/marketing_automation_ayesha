from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)



async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all database tables with retry logic to wait for database service startup."""
    from sqlalchemy import text
    import logging
    import asyncio
    
    logger = logging.getLogger(__name__)
    max_retries = 5
    retry_delay = 3
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Initializing database (attempt %d/%d)...", attempt, max_retries)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                # Lightweight self-healing migrations for columns added after a table
                # already exists (create_all does not ALTER existing tables).
                await conn.execute(
                    text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS instagram_music_url TEXT")
                )
                await conn.execute(
                    text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS instagram_music_end_offset INTEGER")
                )
            logger.info("Database initialized successfully.")
            return
        except Exception as e:
            if attempt == max_retries:
                logger.error("Failed to initialize database after %d attempts: %s", max_retries, e)
                raise
            logger.warning("Database connection failed on attempt %d. Retrying in %d seconds: %s", attempt, retry_delay, e)
            await asyncio.sleep(retry_delay)
