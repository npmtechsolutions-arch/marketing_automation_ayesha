"""The Organization backfill migration.

Only the *data* half is tested here. The DDL cannot run under this suite:
SQLite rejects `ALTER COLUMN ... SET NOT NULL`, raises NotImplementedError for
`create_foreign_key`/`drop_constraint`, and the schema comes from
`Base.metadata.create_all` rather than from Alembic anyway. The DDL is verified
against a real Postgres out of band (see the plan's verification section).

What that leaves worth testing is the part that can silently corrupt data: which
rows get an organization, whether the subscription is copied faithfully, and
whether a re-run duplicates anything.
"""

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.models.account import Account
from app.models.organization import Organization, OrganizationMember

pytestmark = pytest.mark.asyncio


def _load_migration():
    """Import the migration by path -- alembic/versions is not a package."""
    path = (
        Path(__file__).resolve().parent.parent
        / "alembic" / "versions" / "b1e4c72d90af_organization_tier.py"
    )
    spec = importlib.util.spec_from_file_location("organization_tier_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sql(query: str, **params):
    """text() with UUID-typed binds, so raw SQL matches what the ORM stored."""
    binds = [
        sa.bindparam(k, v, type_=sa.Uuid) if isinstance(v, uuid.UUID)
        else sa.bindparam(k, v)
        for k, v in params.items()
    ]
    return sa.text(query).bindparams(*binds)


async def _legacy_account(db_session, owner, **overrides):
    """Insert a pre-migration account: no organization_id, subscription inline.

    Written with raw SQL because the current model no longer has those columns
    -- which is exactly the state the migration has to cope with.
    """
    account_id = uuid.uuid4()
    values = {
        "id": account_id,
        "name": overrides.get("name", "Legacy Workspace"),
        "slug": overrides.get("slug", f"legacy-{uuid.uuid4().hex[:10]}"),
        "owner_id": owner.id,
        "organization_id": None,
        "deleted_at": overrides.get("deleted_at"),
    }
    await db_session.execute(
        _sql(
            "INSERT INTO accounts (id, name, slug, owner_id, organization_id, deleted_at)"
            " VALUES (:id, :name, :slug, :owner_id, :organization_id, :deleted_at)",
            **values,
        )
    )
    return account_id


# The migration's input is the PRE-migration shape of `accounts`: the eight
# subscription columns present, and organization_id absent. The models have
# already moved on, so `create_all` builds the post-migration table -- the
# fixture rebuilds it as it was.
_LEGACY_ACCOUNTS_DDL = """
CREATE TABLE accounts (
    id CHAR(32) NOT NULL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    owner_id CHAR(32) NOT NULL,
    organization_id CHAR(32),
    subscription_tier VARCHAR(20),
    subscription_status VARCHAR(20),
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    trial_ends_at TIMESTAMP,
    monthly_post_limit INTEGER,
    max_team_members INTEGER,
    max_platforms INTEGER,
    settings JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP
)
"""


# `organizations` as this migration creates it. The four limit columns were
# dropped again in f2a90c4d7b18, so `create_all` no longer builds them -- but
# this migration's backfill writes them, and a migration is frozen at the shape
# of the schema it ran against. Rebuilding here keeps the test about the
# backfill's logic rather than about today's models.
_LEGACY_ORGANIZATIONS_DDL = """
CREATE TABLE organizations (
    id CHAR(32) NOT NULL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    owner_id CHAR(32) NOT NULL,
    subscription_tier VARCHAR(20),
    subscription_status VARCHAR(20),
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    trial_ends_at TIMESTAMP,
    monthly_post_limit INTEGER,
    max_team_members INTEGER,
    max_platforms INTEGER,
    max_workspaces INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP
)
"""


@pytest.fixture
async def legacy_schema(db_session):
    """Replace `accounts` and `organizations` with their definitions as of this
    migration.

    A rebuild rather than ALTER: SQLite cannot drop a NOT NULL constraint, and
    the current schema makes organization_id NOT NULL -- which is precisely what
    the migration is responsible for establishing.
    """
    await db_session.execute(sa.text("DROP TABLE accounts"))
    await db_session.execute(sa.text(_LEGACY_ACCOUNTS_DDL))
    await db_session.execute(sa.text("DROP TABLE organizations"))
    await db_session.execute(sa.text(_LEGACY_ORGANIZATIONS_DDL))
    await db_session.flush()
    yield


async def _set_subscription(db_session, account_id, **values):
    assignments = ", ".join(f"{k} = :{k}" for k in values)
    await db_session.execute(
        _sql(f"UPDATE accounts SET {assignments} WHERE id = :id", id=account_id, **values)
    )


async def test_backfill_creates_one_organization_per_account(
    db_session, legacy_schema, user_factory
):
    migration = _load_migration()
    owner = await user_factory()
    account_id = await _legacy_account(db_session, owner, name="Acme Client")
    await _set_subscription(
        db_session, account_id,
        subscription_tier="GROWTH", subscription_status="ACTIVE",
        stripe_customer_id="cus_123", stripe_subscription_id="sub_456",
        monthly_post_limit=200, max_team_members=10, max_platforms=8,
    )

    changed = await db_session.run_sync(
        lambda conn: migration.backfill_organizations(conn)
    )
    assert changed == 1

    organization = (
        await db_session.execute(select_org_for(account_id))
    ).scalar_one()
    # The subscription is copied verbatim, uppercase member names included.
    assert organization.subscription_tier.name == "GROWTH"
    assert organization.subscription_status.name == "ACTIVE"
    assert organization.stripe_customer_id == "cus_123"
    assert organization.stripe_subscription_id == "sub_456"
    assert organization.owner_id == owner.id

    # The limit columns are read with raw SQL: f2a90c4d7b18 dropped them from
    # the model, but this migration still writes them and is judged against the
    # schema it ran against, not against today's.
    limits = (
        await db_session.execute(
            sa.text(
                "SELECT monthly_post_limit, max_team_members, max_platforms,"
                " max_workspaces FROM organizations WHERE id = :id"
            ).bindparams(id=organization.id)
        )
    ).one()
    assert limits.monthly_post_limit == 200
    assert limits.max_team_members == 10
    assert limits.max_platforms == 8
    # Derived from the tier, since accounts never had this column.
    assert limits.max_workspaces == 10


def select_org_for(account_id):
    return (
        sa.select(Organization)
        .join(Account, Account.organization_id == Organization.id)
        .where(Account.id == account_id)
    )


async def test_backfill_creates_an_owner_membership(
    db_session, legacy_schema, user_factory
):
    migration = _load_migration()
    owner = await user_factory()
    account_id = await _legacy_account(db_session, owner)
    await _set_subscription(
        db_session, account_id,
        subscription_tier="FREE", subscription_status="TRIALING",
        monthly_post_limit=10, max_team_members=1, max_platforms=2,
    )

    await db_session.run_sync(lambda c: migration.backfill_organizations(c))

    organization = (await db_session.execute(select_org_for(account_id))).scalar_one()
    member = (
        await db_session.execute(
            sa.select(OrganizationMember).where(
                OrganizationMember.organization_id == organization.id
            )
        )
    ).scalar_one()
    assert member.user_id == owner.id
    assert member.role.name == "OWNER"
    assert member.invitation_status.name == "ACCEPTED"


async def test_soft_deleted_accounts_are_backfilled_too(
    db_session, legacy_schema, user_factory
):
    """They must be: the migration makes organization_id NOT NULL, and a
    soft-deleted row with a NULL would block it."""
    migration = _load_migration()
    owner = await user_factory()
    account_id = await _legacy_account(
        db_session, owner, name="Deleted", deleted_at=datetime.now(timezone.utc)
    )
    await _set_subscription(
        db_session, account_id,
        subscription_tier="FREE", subscription_status="CANCELLED",
        monthly_post_limit=10, max_team_members=1, max_platforms=2,
    )

    changed = await db_session.run_sync(lambda c: migration.backfill_organizations(c))
    assert changed == 1

    linked = (
        await db_session.execute(
            _sql("SELECT organization_id FROM accounts WHERE id = :id", id=account_id)
        )
    ).scalar_one()
    assert linked is not None


async def test_backfill_is_idempotent(db_session, legacy_schema, user_factory):
    """A re-run -- or a resumed partial run -- must change nothing."""
    migration = _load_migration()
    owner = await user_factory()
    account_id = await _legacy_account(db_session, owner)
    await _set_subscription(
        db_session, account_id,
        subscription_tier="STARTER", subscription_status="ACTIVE",
        monthly_post_limit=50, max_team_members=3, max_platforms=5,
    )

    first = await db_session.run_sync(lambda c: migration.backfill_organizations(c))
    assert first == 1
    organization_id = (
        await db_session.execute(select_org_for(account_id))
    ).scalar_one().id

    second = await db_session.run_sync(lambda c: migration.backfill_organizations(c))
    assert second == 0, "a second run rewrote rows"

    orgs = (await db_session.execute(sa.select(Organization))).scalars().all()
    assert len(orgs) == 1, "the re-run duplicated the organization"
    assert orgs[0].id == organization_id

    members = (
        await db_session.execute(sa.select(OrganizationMember))
    ).scalars().all()
    assert len(members) == 1, "the re-run duplicated the owner membership"


async def test_each_account_gets_its_own_organization(
    db_session, legacy_schema, user_factory
):
    """Two accounts owned by the same user do NOT get merged.

    Merging would silently collapse two separate Stripe subscriptions into one.
    """
    migration = _load_migration()
    owner = await user_factory()
    first = await _legacy_account(db_session, owner, name="Client A")
    second = await _legacy_account(db_session, owner, name="Client B")
    for account_id, customer in ((first, "cus_A"), (second, "cus_B")):
        await _set_subscription(
            db_session, account_id,
            subscription_tier="FREE", subscription_status="TRIALING",
            stripe_customer_id=customer,
            monthly_post_limit=10, max_team_members=1, max_platforms=2,
        )

    changed = await db_session.run_sync(lambda c: migration.backfill_organizations(c))
    assert changed == 2

    orgs = (await db_session.execute(sa.select(Organization))).scalars().all()
    assert len(orgs) == 2
    assert {o.stripe_customer_id for o in orgs} == {"cus_A", "cus_B"}
