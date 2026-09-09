"""The analytics queries, executed against real Postgres.

The rest of the analytics suite runs on the in-memory SQLite harness, which is
fast and covers the logic -- but SQLite accepts SQL that Postgres rejects. The
posts query originally rounded a ``double precision``; SQLite computed it
happily and every one of the 600-odd tests passed, while the endpoint was a
hard 500 in production because Postgres only has ``round(numeric, int)``.

So these execute each query function once, on the database the product
actually runs on. They assert very little about the numbers -- the SQLite
tests do that -- and exist to prove the SQL runs at all.

Skipped when no Postgres is reachable; CI runs one.
"""

import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.services import analytics_query
from app.services.dashboard import resolve_range

pytestmark = pytest.mark.asyncio

TEST_DB = "analytics_sql_test"


def _admin_url() -> str:
    override = os.environ.get("TEST_POSTGRES_ADMIN_URL")
    if override:
        return override
    configured = os.environ.get("DATABASE_URL", "")
    if configured.startswith("postgresql"):
        return configured.rsplit("/", 1)[0] + "/postgres"
    return "postgresql+asyncpg://127.0.0.1:5433/postgres"


ADMIN_URL = _admin_url()


async def _postgres_available() -> bool:
    engine = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect():
            return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def pg_session():
    if not await _postgres_available():
        pytest.skip(f"no Postgres at {ADMIN_URL.rsplit('@', 1)[-1]}")

    admin = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
        await conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    await admin.dispose()

    engine = create_async_engine(ADMIN_URL.rsplit("/", 1)[0] + f"/{TEST_DB}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()
        admin = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
        await admin.dispose()


@pytest_asyncio.fixture
async def seeded(pg_session):
    """One workspace, one connection, a day of metrics and a measured post."""
    from app.core.security import get_password_hash
    from app.models.account import Account
    from app.models.organization import Organization
    from app.models.platform import SocialAccount, SocialPlatform
    from app.models.post import Post, PostStatus
    from app.models.post_performance import PostPerformance
    from app.models.user import User
    from app.services import analytics_sync

    user = User(
        id=uuid.uuid4(), email=f"pg-{uuid.uuid4().hex[:10]}@example.com",
        password_hash=get_password_hash("hunter2-correct-horse"),
        full_name="PG Tester", is_active=True, two_factor_enabled=False,
    )
    org = Organization(
        id=uuid.uuid4(), name="PG Org", slug=f"pg-{uuid.uuid4().hex[:8]}",
        owner_id=user.id,
    )
    account = Account(
        id=uuid.uuid4(), name="PG Workspace", slug=f"pgw-{uuid.uuid4().hex[:8]}",
        owner_id=user.id, organization_id=org.id, settings={},
    )
    platform = SocialPlatform(
        id=uuid.uuid4(), account_id=account.id, user_id=user.id,
        name="Instagram", slug="instagram", is_active=True,
    )
    connection = SocialAccount(
        id=uuid.uuid4(), account_id=account.id, user_id=user.id,
        platform_id=platform.id, account_name="pg ig", access_token="mock_token",
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    post = Post(
        id=uuid.uuid4(), account_id=account.id, user_id=user.id,
        title="Measured", content="body", status=PostStatus.PUBLISHED, published_at=now,
    )
    pg_session.add_all([user, org, account, platform, connection, post])
    await pg_session.flush()
    pg_session.add(PostPerformance(
        id=uuid.uuid4(), post_id=post.id, platform_type="instagram",
        likes=120, comments=30, shares=10, saves=0,
        reach=4000, impressions=9000, clicks=45, video_views=0,
    ))

    yesterday = date.today() - timedelta(days=1)
    await analytics_sync.upsert_day(
        pg_session, connection.id, yesterday,
        {"followers": 5000, "reach": 4000, "impressions": 9000},
    )
    await pg_session.commit()
    return account


async def test_every_analytics_query_runs_on_postgres(pg_session, seeded):
    """Each of the four views, executed once. A dialect error here is the whole
    point of the file."""
    window = resolve_range(seeded, "30d", None, None)

    overview = await analytics_query.overview(pg_session, seeded, window)
    assert overview["metrics"]["followers"]["value"] == 5000

    platforms = await analytics_query.platforms(pg_session, seeded, window)
    assert [row["platform"] for row in platforms] == ["instagram"]

    audience = await analytics_query.audience(pg_session, seeded, window)
    assert audience["current"] == 5000

    posts = await analytics_query.posts(pg_session, seeded, window)
    # round(numeric, int): (120+30+10+0)/4000*100. On a Float cast Postgres
    # raises UndefinedFunctionError here instead.
    assert [p["engagement_rate"] for p in posts] == [4.0]


async def test_csv_rendering_runs_on_postgres(pg_session, seeded):
    """The CSV path re-renders the same rows, so a Decimal coming back from
    Postgres where SQLite returned a float must still serialise."""
    window = resolve_range(seeded, "30d", None, None)

    overview = await analytics_query.overview(pg_session, seeded, window)
    body = analytics_query.overview_csv(overview)
    assert "followers,5000" in body

    posts = await analytics_query.posts(pg_session, seeded, window)
    assert "4.0" in analytics_query.to_csv(posts)


async def test_the_plan_grounding_queries_run_on_postgres(pg_session, seeded):
    """The monthly plan's grounding, executed once on the real dialect.

    Its topic query grouped by ``posts.hashtags`` -- a ``json`` column, which
    Postgres has no equality operator for, so the GROUP BY raised
    UndefinedFunctionError. SQLite grouped it happily, the whole suite passed,
    and the first live call was a 500. The same shape as the
    ``round(double precision, int)`` bug this file was created for.
    """
    from app.services import content_plan

    grounding = await content_plan.gather_grounding(pg_session, seeded)

    assert grounding["connections"], "the seeded connection should be listed"
    # It runs; what it found is the SQLite suite's business.
    assert "topics" in grounding["past_performance"]
    assert "explanation" in grounding["past_performance"]
