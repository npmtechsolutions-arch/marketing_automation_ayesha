"""Shared pytest fixtures for the backend test-suite.

The suite runs against an in-memory SQLite database (aiosqlite) so it needs no
Postgres service. Two details make that work:

* ``app.core.database`` builds its engine at import time with Postgres-only
  pool arguments, so we never point ``DATABASE_URL`` at SQLite. Instead we
  create our own engine here and override the ``get_db`` dependency.
* ``httpx``'s ASGITransport does not run lifespan events, so the app's
  ``init_db()`` and the background scheduler task never start during tests.

All models use the dialect-agnostic ``sqlalchemy.Uuid`` (via
``postgresql.UUID``, which subclasses it in SQLAlchemy 2.x), so the schema
creates cleanly on SQLite.
"""

import os
import uuid
from datetime import datetime, timezone

# Must be set before app.core.config is imported: a non-DEBUG instance refuses
# to boot while the JWT secrets are still the shipped placeholders.
os.environ.setdefault("DEBUG", "true")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import sqltypes

# ---------------------------------------------------------------------------
# Make SQLite accept string UUIDs, the way Postgres does.
#
# get_current_user filters `User.id == user_id` where user_id is the JWT's
# `sub` claim -- a *string*. asyncpg coerces that to a uuid transparently, but
# SQLAlchemy's non-native Uuid bind processor calls `value.hex` and blows up on
# a str. Without this shim the tests would fail on a difference between the
# test backend and production, not on application behaviour.
# ---------------------------------------------------------------------------
_original_uuid_bind_processor = sqltypes.Uuid.bind_processor


def _lenient_uuid_bind_processor(self, dialect):
    processor = _original_uuid_bind_processor(self, dialect)
    if processor is None:
        return None

    def process(value):
        if isinstance(value, str):
            value = uuid.UUID(value)
        return processor(value)

    return process


sqltypes.Uuid.bind_processor = _lenient_uuid_bind_processor

from app.core.database import Base, get_db
from app.core.security import create_access_token, get_password_hash
from app.main import app as fastapi_app
from app.models.account import Account
from app.models.organization import Organization, OrganizationMember, OrgRole
from app.models.team_member import InvitationStatus, TeamMember, TeamRole
from app.models.user import User

# Importing the package registers every model on Base.metadata.
import app.models  # noqa: F401


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def db_engine():
    """A fresh in-memory SQLite engine with the full schema, per test.

    StaticPool keeps every connection pointed at the same in-memory database;
    without it each connection would get its own empty one.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncSession:
    """An AsyncSession bound to the test database."""
    session_factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def _redirect_independent_sessions(db_engine, monkeypatch):
    """Point ``AsyncSessionLocal`` at the test database.

    Most code takes its session from the ``get_db`` dependency, which the
    client fixture overrides. A few places deliberately open their own --
    ``error_log.record`` must, because the request's session is in a failed
    transaction by the time a 500 handler runs. Without this those writes go
    to the real database configured in the environment: the suite would
    quietly accumulate rows in a developer's Postgres, and any error raised
    inside a test would try to use a different event loop's connection and
    fail with an unrelated message.
    """
    import app.core.database as database

    factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr(database, "AsyncSessionLocal", factory)
    yield


@pytest_asyncio.fixture
async def client(db_engine, db_session) -> AsyncClient:
    """An HTTP client for the real FastAPI app, wired to the test database.

    The override yields the *same* session the test uses, so rows a test
    creates are visible to the request handlers without an explicit commit.
    """

    async def _override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def user_factory(db_session):
    """Create persisted ``User`` rows.

    Usage::

        user = await user_factory()
        other = await user_factory(email="someone@example.com")
    """
    created: list[User] = []

    async def _make(
        email: str | None = None,
        *,
        full_name: str = "Test User",
        password: str = "hunter2-correct-horse",
        is_active: bool = True,
        **extra,
    ) -> User:
        user = User(
            id=uuid.uuid4(),
            email=email or f"user-{uuid.uuid4().hex[:12]}@example.com",
            password_hash=get_password_hash(password),
            full_name=full_name,
            is_active=is_active,
            email_verified=True,
            **extra,
        )
        db_session.add(user)
        await db_session.flush()
        created.append(user)
        return user

    return _make


@pytest_asyncio.fixture
async def organization_factory(db_session):
    """Create an ``Organization`` owned by ``owner``, with an OWNER membership.

    ``extra`` overrides any column. Limits are not among them -- they live in
    plan_features; use the ``set_limit`` fixture to change one.
    """

    async def _make(owner: User, *, name: str = "Test Org", **extra) -> Organization:
        organization = Organization(
            id=uuid.uuid4(),
            name=name,
            slug=f"org-{uuid.uuid4().hex[:12]}",
            owner_id=owner.id,
            **extra,
        )
        db_session.add(organization)
        await db_session.flush()

        db_session.add(
            OrganizationMember(
                id=uuid.uuid4(),
                user_id=owner.id,
                organization_id=organization.id,
                role=OrgRole.OWNER,
                invitation_status=InvitationStatus.ACCEPTED,
                accepted_at=datetime.now(timezone.utc),
            )
        )
        await db_session.flush()
        return organization

    return _make


@pytest_asyncio.fixture
async def org_member_factory(db_session):
    """Create an ``OrganizationMember`` at a given role and invitation status.

    Defaults to PENDING, mirroring ``member_factory``: the unaccepted case is
    what the authorization tests care about.
    """

    async def _make(
        user: User,
        organization: Organization,
        *,
        role: OrgRole = OrgRole.MEMBER,
        invitation_status: InvitationStatus = InvitationStatus.PENDING,
    ) -> OrganizationMember:
        member = OrganizationMember(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=organization.id,
            role=role,
            invitation_email=user.email,
            invitation_token=uuid.uuid4().hex,
            invitation_status=invitation_status,
            accepted_at=(
                datetime.now(timezone.utc)
                if invitation_status is InvitationStatus.ACCEPTED
                else None
            ),
        )
        db_session.add(member)
        await db_session.flush()
        return member

    return _make


@pytest_asyncio.fixture
async def account_factory(db_session, organization_factory):
    """Create an ``Account`` (workspace) plus the owner's ACCEPTED membership.

    Creates an owning Organization automatically unless one is passed as
    ``organization=``, so the ~30 existing call sites keep working unchanged.
    Tests that need to control a limit pass their own organization.
    """

    async def _make(
        owner: User,
        *,
        name: str = "Test Account",
        organization: Organization | None = None,
        **extra,
    ) -> Account:
        """``extra`` overrides any Account column."""
        if organization is None:
            organization = await organization_factory(owner, name=f"{name} Org")
        account = Account(
            id=uuid.uuid4(),
            name=name,
            slug=f"acct-{uuid.uuid4().hex[:12]}",
            owner_id=owner.id,
            organization_id=organization.id,
            **extra,
        )
        db_session.add(account)
        await db_session.flush()

        db_session.add(
            TeamMember(
                id=uuid.uuid4(),
                user_id=owner.id,
                account_id=account.id,
                role=TeamRole.OWNER,
                invitation_status=InvitationStatus.ACCEPTED,
                accepted_at=datetime.now(timezone.utc),
            )
        )
        await db_session.flush()
        return account

    return _make


@pytest_asyncio.fixture
async def member_factory(db_session):
    """Create a ``TeamMember`` row at a given role and invitation status.

    Defaults to ``PENDING`` because that is the state the authorization
    regression tests care about — an invitation that has not been accepted.
    """

    async def _make(
        user: User,
        account: Account,
        *,
        role: TeamRole = TeamRole.ADMIN,
        invitation_status: InvitationStatus = InvitationStatus.PENDING,
    ) -> TeamMember:
        member = TeamMember(
            id=uuid.uuid4(),
            user_id=user.id,
            account_id=account.id,
            role=role,
            invitation_email=user.email,
            invitation_token=uuid.uuid4().hex,
            invitation_status=invitation_status,
            accepted_at=(
                datetime.now(timezone.utc)
                if invitation_status is InvitationStatus.ACCEPTED
                else None
            ),
        )
        db_session.add(member)
        await db_session.flush()
        return member

    return _make


@pytest.fixture
def auth_header():
    """Build an ``Authorization`` header carrying a valid access token."""

    def _make(user: User) -> dict[str, str]:
        token = create_access_token({"sub": str(user.id)})
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Give every test a clean rate-limit and 2FA-challenge state.

    Counters are process-global, so without this one test's requests would
    consume another's budget and the order tests run in would change results.
    """
    from app.core import challenge_store
    from app.core.ratelimit import limiter

    limiter.reset()
    challenge_store.reset()
    yield
    limiter.reset()
    challenge_store.reset()


def _load_migration(filename: str):
    """A migration module, imported by path.

    Seeds are reused rather than duplicated so the tests exercise the same rows
    a real database gets -- a second copy here would drift from the migration.
    """
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parent.parent / "alembic" / "versions" / filename
    )
    spec = importlib.util.spec_from_file_location(f"migration_{filename}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_plan_seed():
    return _load_migration("d5b28a71f3c6_plans_and_entitlements.py")


@pytest_asyncio.fixture(autouse=True)
async def seeded_plans(db_engine, db_session):
    """Every test gets the standard plans and features.

    The schema comes from create_all, which creates tables but no rows, so
    without this every entitlement lookup would find no plan and treat the
    feature as ungranted.
    """
    from app.services import entitlement_service

    migration = _load_plan_seed()
    await db_session.run_sync(lambda conn: migration.seed_plans(conn))
    # Features added after the original plans migration seed themselves, the
    # same way: a plan with no row for a feature resolves as *not granted*, so
    # without this every listening test would meet a 402 instead of the rule
    # it was written for.
    listening = _load_migration("a2f7c1d4e908_listening_queries.py")
    await db_session.run_sync(lambda conn: listening.seed_listening_feature(conn))
    competitors = _load_migration("d3e6b9a71c25_competitor_tracking.py")
    await db_session.run_sync(lambda conn: competitors.seed_competitor_feature(conn))
    await db_session.flush()
    # Limits are cached for 60s; a previous test's numbers must not leak.
    entitlement_service.invalidate_all()
    yield
    entitlement_service.invalidate_all()


@pytest_asyncio.fixture
async def set_limit(db_session):
    """Override one feature's limit for an organization's plan.

    Limits are plan-level, so this edits the plan row the organization is on.
    Each test gets its own database, so there is no bleed between them.
    """
    from sqlalchemy import select as sa_select

    from app.models.plan import Plan, PlanFeature
    from app.services import entitlement_service

    async def _set(organization, feature_key: str, limit_value):
        plan = (
            await db_session.execute(
                sa_select(Plan).where(Plan.key == organization.subscription_tier.value)
            )
        ).scalar_one()
        row = (
            await db_session.execute(
                sa_select(PlanFeature).where(
                    PlanFeature.plan_id == plan.id,
                    PlanFeature.feature_key == feature_key,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = PlanFeature(
                id=uuid.uuid4(), plan_id=plan.id, feature_key=feature_key
            )
            db_session.add(row)
        row.limit_value = limit_value
        await db_session.flush()
        entitlement_service.invalidate_all()

    return _set


@pytest_asyncio.fixture
async def social_platform_factory(db_session):
    """Create a ``SocialPlatform`` row.

    These are per-workspace catalogue rows rather than a global enum, so a test
    that wants a connected account needs one of these first.
    """
    from app.models.platform import SocialPlatform

    async def _make(owner, account, *, slug: str = "instagram", name: str | None = None):
        platform = SocialPlatform(
            id=uuid.uuid4(),
            user_id=owner.id,
            account_id=account.id,
            name=name or slug.title(),
            slug=slug,
            is_active=True,
            sort_order=0,
        )
        db_session.add(platform)
        await db_session.flush()
        await db_session.refresh(platform)
        return platform

    return _make


@pytest_asyncio.fixture
async def social_account_factory(db_session, social_platform_factory):
    """Create a connected ``SocialAccount``, with its platform if needed."""
    from app.models.platform import SocialAccount

    async def _make(
        owner,
        account,
        *,
        slug: str = "instagram",
        platform=None,
        access_token: str = "mock_token_for_tests",
        **extra,
    ):
        platform = platform or await social_platform_factory(owner, account, slug=slug)
        social_account = SocialAccount(
            id=uuid.uuid4(),
            user_id=owner.id,
            account_id=account.id,
            platform_id=platform.id,
            account_name=extra.pop("account_name", f"{slug} account"),
            access_token=access_token,
            is_active=True,
            is_verified=True,
            **extra,
        )
        db_session.add(social_account)
        await db_session.flush()
        await db_session.refresh(social_account)
        return social_account

    return _make
