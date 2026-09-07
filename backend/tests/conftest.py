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
async def account_factory(db_session):
    """Create an ``Account`` owned by ``owner``, plus the owner's ACCEPTED membership."""

    async def _make(owner: User, *, name: str = "Test Account") -> Account:
        account = Account(
            id=uuid.uuid4(),
            name=name,
            slug=f"acct-{uuid.uuid4().hex[:12]}",
            owner_id=owner.id,
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
