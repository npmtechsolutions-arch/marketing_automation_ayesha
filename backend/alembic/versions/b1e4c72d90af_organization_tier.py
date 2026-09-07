"""organization tier

Revision ID: b1e4c72d90af
Revises: aeed3c1c5c4e
Create Date: 2026-09-07 22:50:00.000000

Introduces ``Organization`` above ``Account`` and moves the subscription to it.

Before this, every ``Account`` carried its own tier and its own Stripe customer,
so a company running several client workspaces paid several times and nothing in
the model represented the company. Allowances are now spent across all of an
organization's workspaces.

What moves
----------
``subscription_tier``, ``subscription_status``, ``stripe_customer_id``,
``stripe_subscription_id``, ``trial_ends_at``, ``monthly_post_limit``,
``max_team_members`` and ``max_platforms`` leave ``accounts`` and live on
``organizations``. ``accounts`` gains a NOT NULL ``organization_id``.

Backfill
--------
One organization per existing account, owned by that account's owner, copying
the subscription verbatim, plus an OWNER/ACCEPTED ``organization_members`` row.
One-per-account rather than merging accounts that share an owner: merging would
silently collapse two separate Stripe subscriptions into one.

Soft-deleted accounts get an organization too. They have to -- otherwise the
``SET NOT NULL`` below fails on them.

Idempotent: an account that already has ``organization_id`` set is skipped, so a
re-run (or a resumed partial run) changes nothing.

Reversible: ``downgrade()`` restores the columns and copies the values back
before dropping anything.
"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b1e4c72d90af"
down_revision: Union[str, Sequence[str], None] = "aeed3c1c5c4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Enum types.
#
# The three below already exist -- the baseline created them. `create_type=False`
# is what stops op.create_table from issuing CREATE TYPE again, and it must be
# postgresql.ENUM: sa.Enum accepts `create_type` and silently ignores it.
#
# This matters more than it looks. Alembic memoises which types it has created
# per process, so a fresh `upgrade head` from zero would skip the duplicate
# CREATE (the baseline made them in the same process) and pass, while running
# only this migration against an existing database would raise
# DuplicateObjectError. It would go green in CI and fail in production.
#
# Labels are spelled out rather than derived from the model enums: a migration
# has to keep working after the models move on.
# ---------------------------------------------------------------------------
SUBSCRIPTION_TIER_ENUM = postgresql.ENUM(
    "FREE", "STARTER", "GROWTH", "PRO", "ENTERPRISE",
    name="subscription_tier_enum", create_type=False,
)
SUBSCRIPTION_STATUS_ENUM = postgresql.ENUM(
    "ACTIVE", "PAST_DUE", "CANCELLED", "TRIALING",
    name="subscription_status_enum", create_type=False,
)
INVITATION_STATUS_ENUM = postgresql.ENUM(
    "PENDING", "ACCEPTED", "EXPIRED",
    name="invitation_status_enum", create_type=False,
)
# New. Created and dropped explicitly by this migration -- the only one it owns.
ORG_ROLE_ENUM = postgresql.ENUM(
    "OWNER", "ADMIN", "MEMBER", name="org_role_enum", create_type=False,
)

# The columns that move off accounts, in the order they are dropped/restored.
MOVED_COLUMNS = (
    "subscription_tier",
    "subscription_status",
    "stripe_customer_id",
    "stripe_subscription_id",
    "trial_ends_at",
    "monthly_post_limit",
    "max_team_members",
    "max_platforms",
)

# UUIDs are bound through sa.Uuid so the same statements work on Postgres (which
# returns uuid.UUID) and SQLite (which stores bare hex).
_SELECT_ACCOUNTS = sa.text(
    "SELECT id, name, slug, owner_id, organization_id, "
    "subscription_tier, subscription_status, stripe_customer_id, "
    "stripe_subscription_id, trial_ends_at, monthly_post_limit, "
    "max_team_members, max_platforms FROM accounts"
).columns(id=sa.Uuid, owner_id=sa.Uuid, organization_id=sa.Uuid)

_INSERT_ORG = sa.text(
    "INSERT INTO organizations "
    "(id, name, slug, owner_id, subscription_tier, subscription_status, "
    " stripe_customer_id, stripe_subscription_id, trial_ends_at, "
    " monthly_post_limit, max_team_members, max_platforms, max_workspaces) "
    "VALUES (:id, :name, :slug, :owner_id, :subscription_tier, "
    " :subscription_status, :stripe_customer_id, :stripe_subscription_id, "
    " :trial_ends_at, :monthly_post_limit, :max_team_members, :max_platforms, "
    " :max_workspaces)"
).bindparams(
    sa.bindparam("id", type_=sa.Uuid),
    sa.bindparam("owner_id", type_=sa.Uuid),
    sa.bindparam("subscription_tier", type_=SUBSCRIPTION_TIER_ENUM),
    sa.bindparam("subscription_status", type_=SUBSCRIPTION_STATUS_ENUM),
)

_INSERT_ORG_MEMBER = sa.text(
    "INSERT INTO organization_members "
    "(id, user_id, organization_id, role, invitation_status, accepted_at) "
    "VALUES (:id, :user_id, :organization_id, :role, :invitation_status, "
    " :accepted_at)"
).bindparams(
    sa.bindparam("id", type_=sa.Uuid),
    sa.bindparam("user_id", type_=sa.Uuid),
    sa.bindparam("organization_id", type_=sa.Uuid),
    sa.bindparam("role", type_=ORG_ROLE_ENUM),
    sa.bindparam("invitation_status", type_=INVITATION_STATUS_ENUM),
)

_LINK_ACCOUNT = sa.text(
    "UPDATE accounts SET organization_id = :organization_id WHERE id = :id"
).bindparams(
    sa.bindparam("id", type_=sa.Uuid),
    sa.bindparam("organization_id", type_=sa.Uuid),
)

_SELECT_ORG_SLUGS = sa.text("SELECT id, slug FROM organizations").columns(id=sa.Uuid)

# Workspace allowance per tier, mirroring TIER_LIMITS at the time of writing.
# Inlined rather than imported for the same reason as the enum labels.
_MAX_WORKSPACES = {
    "FREE": 1, "STARTER": 3, "GROWTH": 10, "PRO": 25, "ENTERPRISE": -1,
}


def backfill_organizations(connection) -> int:
    """Give every account an organization carrying its subscription.

    Takes the connection explicitly rather than calling op.get_bind() so tests
    can drive it directly -- the same shape as rewrite_credentials in
    aeed3c1c5c4e.

    Returns the number of accounts linked.
    """
    rows = connection.execute(_SELECT_ACCOUNTS).mappings().all()
    # Recover from a partial run: an organization may exist with no link back.
    existing_by_slug = {
        r["slug"]: r["id"]
        for r in connection.execute(_SELECT_ORG_SLUGS).mappings()
    }

    changed = 0
    for row in rows:
        if row["organization_id"] is not None:
            continue  # already migrated

        org_id = existing_by_slug.get(row["slug"])
        if org_id is None:
            org_id = uuid.uuid4()
            tier = row["subscription_tier"]
            # The DB stores enum MEMBER NAMES ('FREE'), not the lowercase
            # values. These are copied straight across, so they stay correct
            # whatever the Python enum does later.
            connection.execute(
                _INSERT_ORG,
                {
                    "id": org_id,
                    "name": row["name"],
                    "slug": row["slug"],
                    "owner_id": row["owner_id"],
                    "subscription_tier": tier,
                    "subscription_status": row["subscription_status"],
                    "stripe_customer_id": row["stripe_customer_id"],
                    "stripe_subscription_id": row["stripe_subscription_id"],
                    "trial_ends_at": row["trial_ends_at"],
                    "monthly_post_limit": row["monthly_post_limit"],
                    "max_team_members": row["max_team_members"],
                    "max_platforms": row["max_platforms"],
                    "max_workspaces": _MAX_WORKSPACES.get(str(tier), 1),
                },
            )
            connection.execute(
                _INSERT_ORG_MEMBER,
                {
                    "id": uuid.uuid4(),
                    "user_id": row["owner_id"],
                    "organization_id": org_id,
                    "role": "OWNER",
                    "invitation_status": "ACCEPTED",
                    "accepted_at": datetime.now(timezone.utc),
                },
            )
            existing_by_slug[row["slug"]] = org_id

        connection.execute(_LINK_ACCOUNT, {"organization_id": org_id, "id": row["id"]})
        changed += 1

    print(f"  accounts: {changed} of {len(rows)} row(s) linked to an organization")
    return changed


def restore_account_subscriptions(connection) -> int:
    """Copy the subscription back onto accounts, for downgrade().

    A correlated subquery rather than UPDATE ... FROM, which SQLite only gained
    in 3.33. COALESCE supplies the model defaults so an account whose
    organization is missing cannot block the NOT NULL that follows.
    """
    result = connection.execute(
        sa.text(
            "UPDATE accounts SET "
            "subscription_tier = COALESCE("
            "  (SELECT o.subscription_tier FROM organizations o"
            "   WHERE o.id = accounts.organization_id), 'FREE'), "
            "subscription_status = COALESCE("
            "  (SELECT o.subscription_status FROM organizations o"
            "   WHERE o.id = accounts.organization_id), 'TRIALING'), "
            "stripe_customer_id = ("
            "  SELECT o.stripe_customer_id FROM organizations o"
            "  WHERE o.id = accounts.organization_id), "
            "stripe_subscription_id = ("
            "  SELECT o.stripe_subscription_id FROM organizations o"
            "  WHERE o.id = accounts.organization_id), "
            "trial_ends_at = ("
            "  SELECT o.trial_ends_at FROM organizations o"
            "  WHERE o.id = accounts.organization_id), "
            "monthly_post_limit = COALESCE("
            "  (SELECT o.monthly_post_limit FROM organizations o"
            "   WHERE o.id = accounts.organization_id), 10), "
            "max_team_members = COALESCE("
            "  (SELECT o.max_team_members FROM organizations o"
            "   WHERE o.id = accounts.organization_id), 1), "
            "max_platforms = COALESCE("
            "  (SELECT o.max_platforms FROM organizations o"
            "   WHERE o.id = accounts.organization_id), 2)"
        )
    )
    print(f"  accounts: {result.rowcount} row(s) restored from organizations")
    return result.rowcount


def upgrade() -> None:
    bind = op.get_bind()

    # 1. The one type this migration owns. No-op on SQLite.
    ORG_ROLE_ENUM.create(bind, checkfirst=True)

    # 2. Parent, then child.
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_tier", SUBSCRIPTION_TIER_ENUM, nullable=False),
        sa.Column("subscription_status", SUBSCRIPTION_STATUS_ENUM, nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("monthly_post_limit", sa.Integer(), nullable=False),
        sa.Column("max_team_members", sa.Integer(), nullable=False),
        sa.Column("max_platforms", sa.Integer(), nullable=False),
        sa.Column("max_workspaces", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)
    op.create_index(
        op.f("ix_organizations_stripe_customer_id"),
        "organizations", ["stripe_customer_id"], unique=False,
    )
    op.create_index(
        op.f("ix_organizations_stripe_subscription_id"),
        "organizations", ["stripe_subscription_id"], unique=False,
    )

    op.create_table(
        "organization_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("role", ORG_ROLE_ENUM, nullable=False),
        sa.Column("invitation_email", sa.String(length=255), nullable=True),
        sa.Column("invitation_token", sa.String(length=255), nullable=True),
        sa.Column("invitation_status", INVITATION_STATUS_ENUM, nullable=False),
        sa.Column("invited_by", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "organization_id",
                            name="uq_org_member_user_organization"),
    )
    op.create_index(
        op.f("ix_organization_members_organization_id"),
        "organization_members", ["organization_id"], unique=False,
    )

    # 3. Nullable first -- accounts already has rows. add_column does not render
    #    the FK inline, so the constraint is its own statement.
    op.add_column("accounts", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_accounts_organization_id_organizations",
        "accounts", "organizations", ["organization_id"], ["id"],
    )
    op.create_index(
        op.f("ix_accounts_organization_id"), "accounts", ["organization_id"], unique=False
    )

    # 4. Backfill while the source columns still exist.
    backfill_organizations(bind)

    # 5. Every row now has a value.
    op.alter_column("accounts", "organization_id", existing_type=sa.Uuid(), nullable=False)

    # 6. Drop the migrated-away columns last -- step 4 read them.
    for column in MOVED_COLUMNS:
        op.drop_column("accounts", column)


def downgrade() -> None:
    bind = op.get_bind()

    # 1. Restore nullable, so the copy-back has somewhere to land.
    op.add_column("accounts", sa.Column("subscription_tier", SUBSCRIPTION_TIER_ENUM, nullable=True))
    op.add_column("accounts", sa.Column("subscription_status", SUBSCRIPTION_STATUS_ENUM, nullable=True))
    op.add_column("accounts", sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))
    op.add_column("accounts", sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True))
    op.add_column("accounts", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("accounts", sa.Column("monthly_post_limit", sa.Integer(), nullable=True))
    op.add_column("accounts", sa.Column("max_team_members", sa.Integer(), nullable=True))
    op.add_column("accounts", sa.Column("max_platforms", sa.Integer(), nullable=True))

    # 2. Copy back before anything is dropped.
    restore_account_subscriptions(bind)

    # 3. Re-impose NOT NULL on the five that had it. max_workspaces is derived
    #    and simply disappears -- nothing on accounts ever held it.
    for column in ("subscription_tier", "subscription_status",
                   "monthly_post_limit", "max_team_members", "max_platforms"):
        op.alter_column("accounts", column, nullable=False)

    # 4. Unlink.
    op.drop_index(op.f("ix_accounts_organization_id"), table_name="accounts")
    op.drop_constraint("fk_accounts_organization_id_organizations", "accounts",
                       type_="foreignkey")
    op.drop_column("accounts", "organization_id")

    # 5. Child before parent.
    op.drop_index(op.f("ix_organization_members_organization_id"),
                  table_name="organization_members")
    op.drop_table("organization_members")
    for index in ("ix_organizations_stripe_subscription_id",
                  "ix_organizations_stripe_customer_id",
                  "ix_organizations_slug"):
        op.drop_index(op.f(index), table_name="organizations")
    op.drop_table("organizations")

    # 6. Only the type this migration created. The other three are left alone --
    #    create_type=False also suppresses their drop events.
    ORG_ROLE_ENUM.drop(bind, checkfirst=True)
