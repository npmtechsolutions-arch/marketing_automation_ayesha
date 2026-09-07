"""Two workers, one queue: no job may be claimed twice.

This is the guarantee that lets the app run more than one instance. It cannot
be tested on the in-memory SQLite harness: ``with_for_update(skip_locked=True)``
is a no-op there, so a single-connection test would pass against a claim query
with no locking at all. It needs two real transactions, which means Postgres.

Skipped when none is reachable; CI runs one.
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.post import Post, PostStatus
from app.models.publishing_job import JobStatus, PublishingJob
from app.services import publishing

pytestmark = pytest.mark.asyncio

TEST_DB = "publishing_concurrency_test"


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
async def pg_engine():
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
    yield engine
    await engine.dispose()

    admin = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
    await admin.dispose()


@pytest_asyncio.fixture
async def sessions(pg_engine):
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
async def queued_jobs(sessions):
    """A post with N queued, due jobs, committed so every worker can see them."""
    from app.core.security import get_password_hash
    from app.models.account import Account
    from app.models.organization import Organization
    from app.models.platform import SocialAccount, SocialPlatform
    from app.models.user import User

    async def _make(count: int):
        session = await sessions()
        user = User(
            id=uuid.uuid4(), email=f"claim-{uuid.uuid4().hex[:10]}@example.com",
            password_hash=get_password_hash("hunter2-correct-horse"),
            full_name="Claim Tester", is_active=True, two_factor_enabled=False,
        )
        org = Organization(
            id=uuid.uuid4(), name="Claim Org",
            slug=f"claim-{uuid.uuid4().hex[:10]}", owner_id=user.id,
        )
        account = Account(
            id=uuid.uuid4(), name="Claim WS",
            slug=f"claim-ws-{uuid.uuid4().hex[:10]}",
            owner_id=user.id, organization_id=org.id,
        )
        platform = SocialPlatform(
            id=uuid.uuid4(), user_id=user.id, account_id=account.id,
            name="Instagram", slug="instagram", is_active=True, sort_order=0,
        )
        session.add_all([user, org, account, platform])
        await session.flush()

        accounts = []
        for i in range(count):
            sa = SocialAccount(
                id=uuid.uuid4(), user_id=user.id, account_id=account.id,
                platform_id=platform.id, account_name=f"acct {i}",
                access_token="mock_token", is_active=True, is_verified=True,
            )
            session.add(sa)
            accounts.append(sa)
        await session.flush()

        post = Post(
            id=uuid.uuid4(), user_id=user.id, account_id=account.id,
            content="Claim me", status=PostStatus.PUBLISHING,
            target_accounts=[{"social_account_id": str(sa.id)} for sa in accounts],
        )
        session.add(post)
        await session.flush()
        jobs = await publishing.create_jobs_for_post(session, post)
        await session.commit()
        return post.id, [j.id for j in jobs]

    return _make


# ---------------------------------------------------------------------------

async def test_two_workers_never_claim_the_same_job(sessions, queued_jobs):
    """The headline guarantee.

    Without FOR UPDATE SKIP LOCKED both workers read the same queued rows and
    both publish them -- the post goes out twice on every platform, which is
    the failure users notice and cannot undo.
    """
    post_id, job_ids = await queued_jobs(8)

    worker_a, worker_b = await sessions(), await sessions()

    async def claim(session, name):
        return await publishing.claim_due_jobs(session, limit=8, claimant=name)

    a, b = await asyncio.gather(claim(worker_a, "a"), claim(worker_b, "b"))

    overlap = set(a) & set(b)
    assert overlap == set(), f"both workers claimed {len(overlap)} job(s): {overlap}"
    assert sorted(a + b) == sorted(job_ids), "some jobs were never claimed"


async def test_every_job_ends_with_exactly_one_owner(sessions, queued_jobs):
    post_id, job_ids = await queued_jobs(6)

    workers = [await sessions() for _ in range(4)]
    results = await asyncio.gather(
        *(publishing.claim_due_jobs(s, limit=6, claimant=f"w{i}")
          for i, s in enumerate(workers))
    )

    claimed = [jid for batch in results for jid in batch]
    assert len(claimed) == len(set(claimed)) == len(job_ids)

    observer = await sessions()
    rows = (
        await observer.execute(
            select(PublishingJob).where(PublishingJob.post_id == post_id)
        )
    ).scalars().all()
    assert {r.status for r in rows} == {JobStatus.CLAIMED}
    assert all(r.claimed_by is not None for r in rows)


async def test_a_second_pass_finds_nothing(sessions, queued_jobs):
    """Claims are committed while the locks are held, so by the time they
    release the rows no longer match the queue filter."""
    post_id, job_ids = await queued_jobs(3)

    first = await publishing.claim_due_jobs(await sessions(), limit=10)
    second = await publishing.claim_due_jobs(await sessions(), limit=10)

    assert len(first) == 3
    assert second == []


async def test_jobs_scheduled_for_later_are_not_claimed(sessions, queued_jobs):
    post_id, job_ids = await queued_jobs(2)

    setup = await sessions()
    await setup.execute(
        text("UPDATE publishing_jobs SET run_at = :later WHERE post_id = :pid")
        .bindparams(
            later=datetime.now(timezone.utc) + timedelta(hours=1), pid=post_id
        )
    )
    await setup.commit()

    assert await publishing.claim_due_jobs(await sessions(), limit=10) == []
