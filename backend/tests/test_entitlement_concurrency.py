"""The metering race, tested against a real database.

The rest of the suite runs on in-memory SQLite through a single connection, so
it cannot exhibit the bug this guards: two requests arriving at limit-1, each
reading the same count, each concluding it fits. Reproducing that needs two
connections running two transactions at once, which means Postgres.

Skipped when no local Postgres is reachable; CI provides one.
"""

import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
)

from app.core.database import Base
from app.models.account import SubscriptionTier
from app.models.organization import Organization
from app.models.plan import Plan, PlanFeature, UsageRecord
from app.services import entitlement_service as ent

pytestmark = pytest.mark.asyncio

def _admin_url() -> str:
    """Where to create the scratch database.

    Derived from ``DATABASE_URL`` -- same server and credentials, but the
    ``postgres`` maintenance database -- so this runs against CI's Postgres
    service as well as the local dev instance, and never touches either one's
    data. ``TEST_POSTGRES_ADMIN_URL`` overrides it.
    """
    override = os.environ.get("TEST_POSTGRES_ADMIN_URL")
    if override:
        return override
    configured = os.environ.get("DATABASE_URL", "")
    if configured.startswith("postgresql"):
        return configured.rsplit("/", 1)[0] + "/postgres"
    return "postgresql+asyncpg://127.0.0.1:5433/postgres"


ADMIN_URL = _admin_url()
TEST_DB = "entitlement_concurrency_test"


async def _postgres_available() -> bool:
    engine = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect():
            return True
    except Exception:  # noqa: BLE001 - any connection failure means "skip"
        return False
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def pg_engine():
    # Function-scoped: a module-scoped async fixture would outlive the
    # per-test event loop the other fixtures run on.
    if not await _postgres_available():
        pytest.skip(f"no Postgres at {ADMIN_URL.rsplit('@', 1)[-1]}")

    from sqlalchemy import text

    admin = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
        await conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    await admin.dispose()

    url = ADMIN_URL.rsplit("/", 1)[0] + f"/{TEST_DB}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from tests.conftest import _load_plan_seed

    migration = _load_plan_seed()
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: migration.seed_plans(sync_conn))

    yield engine

    await engine.dispose()
    admin = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
    await admin.dispose()


@pytest_asyncio.fixture
async def sessions(pg_engine):
    """A factory for independent sessions -- each gets its own connection."""
    factory = async_sessionmaker(
        bind=pg_engine, class_=AsyncSession, expire_on_commit=False
    )
    opened = []

    async def _open() -> AsyncSession:
        session = factory()
        opened.append(session)
        return session

    yield _open
    for session in opened:
        await session.close()


@pytest_asyncio.fixture
async def organization(pg_engine, sessions):
    """A fresh organization on the Free plan, committed so both connections
    can see it."""
    from app.core.security import get_password_hash
    from app.models.user import User

    session = await sessions()
    user = User(
        id=uuid.uuid4(),
        email=f"race-{uuid.uuid4().hex[:10]}@example.com",
        password_hash=get_password_hash("hunter2-correct-horse"),
        full_name="Race Tester",
        is_active=True,
    )
    org = Organization(
        id=uuid.uuid4(),
        name="Race Org",
        slug=f"race-{uuid.uuid4().hex[:10]}",
        owner_id=user.id,
        subscription_tier=SubscriptionTier.FREE,
    )
    session.add_all([user, org])
    await session.commit()
    ent.invalidate_all()
    return org


async def _set_limit(session: AsyncSession, tier: SubscriptionTier, key: str, value):
    from sqlalchemy import select, update

    plan_id = (
        await session.execute(select(Plan.id).where(Plan.key == tier.value))
    ).scalar_one()
    await session.execute(
        update(PlanFeature)
        .where(PlanFeature.plan_id == plan_id, PlanFeature.feature_key == key)
        .values(limit_value=value)
    )
    await session.commit()
    ent.invalidate_all()


async def _usage(session: AsyncSession, org: Organization, key: str) -> int:
    from sqlalchemy import select

    session.expire_all()
    return (
        await session.execute(
            select(UsageRecord.count).where(
                UsageRecord.organization_id == org.id,
                UsageRecord.feature_key == key,
                UsageRecord.period_start == ent.period_start(),
            )
        )
    ).scalar() or 0


# ---------------------------------------------------------------------------

async def test_two_requests_at_the_limit_yield_exactly_one_winner(
    sessions, organization
):
    """The headline case. Limit 5, usage 4, two concurrent increments.

    Under the old read-then-write shape both would see used=4, both would
    decide 5 <= 5, and the organization would finish at 6. The guarded UPSERT
    makes the second transaction block on the row lock and re-evaluate the
    condition against the committed value, so it is refused.
    """
    setup = await sessions()
    await _set_limit(setup, SubscriptionTier.FREE, ent.POSTS_PER_MONTH, 5)
    for _ in range(4):
        await ent.check_and_increment(setup, organization, ent.POSTS_PER_MONTH)
    await setup.commit()
    assert await _usage(setup, organization, ent.POSTS_PER_MONTH) == 4

    async def attempt(session: AsyncSession):
        try:
            result = await ent.check_and_increment(
                session, organization, ent.POSTS_PER_MONTH
            )
            await session.commit()
            return result
        except ent.EntitlementExceeded:
            await session.rollback()
            return None

    a, b = await sessions(), await sessions()
    outcomes = await asyncio.gather(attempt(a), attempt(b))

    granted = [o for o in outcomes if o is not None]
    assert len(granted) == 1, (
        f"expected exactly one of two concurrent requests to succeed, got {outcomes}"
    )
    assert granted[0] == 5
    assert await _usage(setup, organization, ent.POSTS_PER_MONTH) == 5


async def test_many_concurrent_requests_never_exceed_the_limit(
    sessions, organization
):
    """Ten at once against a limit of 3: exactly three succeed, none over."""
    setup = await sessions()
    await _set_limit(setup, SubscriptionTier.FREE, ent.AI_REQUESTS_PER_MONTH, 3)

    async def attempt():
        session = await sessions()
        try:
            value = await ent.check_and_increment(
                session, organization, ent.AI_REQUESTS_PER_MONTH
            )
            await session.commit()
            return value
        except ent.EntitlementExceeded:
            await session.rollback()
            return None

    outcomes = await asyncio.gather(*(attempt() for _ in range(10)))

    granted = sorted(o for o in outcomes if o is not None)
    assert granted == [1, 2, 3], f"counter did not serialise cleanly: {outcomes}"
    assert await _usage(setup, organization, ent.AI_REQUESTS_PER_MONTH) == 3


async def test_concurrent_requests_under_an_unlimited_plan_all_succeed(
    sessions, organization
):
    """The unguarded path still has to be atomic -- no lost updates."""
    setup = await sessions()
    await _set_limit(setup, SubscriptionTier.FREE, ent.REPORTS_PER_MONTH, None)

    async def attempt():
        session = await sessions()
        value = await ent.check_and_increment(
            session, organization, ent.REPORTS_PER_MONTH
        )
        await session.commit()
        return value

    outcomes = await asyncio.gather(*(attempt() for _ in range(8)))

    assert sorted(outcomes) == list(range(1, 9)), f"lost update: {outcomes}"
    assert await _usage(setup, organization, ent.REPORTS_PER_MONTH) == 8


async def test_the_ai_meter_survives_a_rolled_back_request(sessions, organization):
    """A request that errors after metering must not refund its own increment.

    ``get_db`` rolls the session back on any exception, so an increment left
    uncommitted vanishes whenever the endpoint raises -- a 404, a provider
    timeout, a failure after the model was already billed. Live testing found
    exactly this: three failing AI calls moved the counter not at all. The
    check is made from a second connection, because the session that did the
    write would report the pending value either way.
    """
    from app.core.entitlement_deps import meter_ai_request

    setup = await sessions()
    await _set_limit(setup, SubscriptionTier.FREE, ent.AI_REQUESTS_PER_MONTH, 10)

    # The dependency resolves the organization from the workspace in the path.
    from app.models.account import Account

    account = Account(
        id=uuid.uuid4(),
        name="Race Workspace",
        slug=f"race-ws-{uuid.uuid4().hex[:10]}",
        owner_id=organization.owner_id,
        organization_id=organization.id,
    )
    setup.add(account)
    await setup.commit()

    worker = await sessions()
    await meter_ai_request(account_id=account.id, db=worker, current_user=None)
    # Whatever the endpoint does next must not be able to undo it.
    await worker.rollback()

    observer = await sessions()
    assert await _usage(observer, organization, ent.AI_REQUESTS_PER_MONTH) == 1, (
        "the AI meter was rolled back with the failing request"
    )
