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
    """Verify the database is reachable, retrying while the service starts up.

    This performs no DDL. The schema is owned entirely by Alembic --
    run ``alembic upgrade head`` (the Docker/compose entrypoints do this before
    starting the server). This function only waits for the database to accept
    connections, which matters when the API container starts alongside a
    Postgres container that is still initialising.

    Historically this also ran ``Base.metadata.create_all()`` plus a handful of
    ad-hoc ``ALTER TABLE ... IF NOT EXISTS`` statements. That was removed when
    Alembic was introduced: with create_all running on every boot, a model
    change could reach a database without a migration, leaving environments
    silently drifted and Alembic unable to tell.
    """
    from sqlalchemy import text
    import logging
    import asyncio

    logger = logging.getLogger(__name__)
    max_retries = 5
    retry_delay = 3

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Connecting to database (attempt %d/%d)...", attempt, max_retries)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection established.")
            return
        except Exception as e:
            if attempt == max_retries:
                logger.error(
                    "Could not connect to the database after %d attempts: %s",
                    max_retries, e,
                )
                raise
            logger.warning(
                "Database connection failed on attempt %d. Retrying in %d seconds: %s",
                attempt, retry_delay, e,
            )
            await asyncio.sleep(retry_delay)
