"""Competitor tracking: named accounts, their weekly snapshots, and the plan limit.

Two tables and one feature key, seeded here for the same reason the listening
migration seeds its own: a plan with no row for a feature resolves as **not
granted**, so shipping the endpoints without the rows would refuse every
workspace's first competitor with a 402.

The limits are set against what a competitor costs, which is one Instagram
Business Discovery lookup a week -- no money, but a share of a cap Meta applies
per account. They mirror the listening allowances rather than being generous:
tracking twenty accounts on a free plan would spend a workspace's whole
Discovery budget on data nobody paid for.

Revision ID: d3e6b9a71c25
Revises: a2f7c1d4e908
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3e6b9a71c25"
down_revision: Union[str, Sequence[str], None] = "a2f7c1d4e908"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FEATURE_KEY = "competitor_accounts"
FEATURE_ROW = (
    FEATURE_KEY,
    "Competitor accounts",
    "Instagram business accounts tracked for follower and post counts",
    "COUNT",
    False,  # not metered: a tracked account is a thing that exists, not a spend
    36,     # beside listening_queries, which it is shaped like
)

PLAN_LIMITS = {
    "free": 0,
    "starter": 2,
    "growth": 5,
    "pro": 15,
    "enterprise": None,
}


def upgrade() -> None:
    op.create_table(
        "competitor_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False, server_default="instagram"),
        sa.Column("handle", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("added_by", sa.Uuid(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "platform", "handle", name="uq_competitor_account"),
    )
    op.create_index(
        op.f("ix_competitor_accounts_account_id"), "competitor_accounts", ["account_id"]
    )

    op.create_table(
        "competitor_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("competitor_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        # Nullable, and that is the point: Discovery omits counts for a private
        # or personal account, and a 0 would be a measurement claiming none.
        sa.Column("followers", sa.BigInteger(), nullable=True),
        sa.Column("media_count", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(
            ["competitor_id"], ["competitor_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        # What makes a re-sync correct a day instead of adding a second point
        # to the same Tuesday.
        sa.UniqueConstraint("competitor_id", "date", name="uq_competitor_snapshot_day"),
    )
    op.create_index(
        op.f("ix_competitor_snapshots_competitor_id"),
        "competitor_snapshots",
        ["competitor_id"],
    )
    op.create_index(
        op.f("ix_competitor_snapshots_date"), "competitor_snapshots", ["date"]
    )

    seed_competitor_feature(op.get_bind())


def seed_competitor_feature(connection) -> int:
    """Insert the feature and its per-plan limits. Idempotent.

    Called by the migration and by the test harness, the same arrangement
    ``seed_plans`` and the listening migration already have.
    """
    from sqlalchemy.dialects import postgresql

    feature_unit = postgresql.ENUM(
        "COUNT", "BOOLEAN", "BYTES", name="feature_unit_enum", create_type=False,
    )

    existing = {
        r[0] for r in connection.execute(
            sa.text("SELECT key FROM features WHERE key = :key"),
            {"key": FEATURE_KEY},
        )
    }
    if not existing:
        key, name, description, unit, metered, sort = FEATURE_ROW
        connection.execute(
            sa.text(
                "INSERT INTO features (key, name, description, unit, is_metered, sort_order) "
                "VALUES (:key, :name, :description, :unit, :is_metered, :sort_order)"
            ).bindparams(sa.bindparam("unit", type_=feature_unit)),
            {
                "key": key, "name": name, "description": description,
                "unit": unit, "is_metered": metered, "sort_order": sort,
            },
        )

    added = 0
    plans = {
        r[0]: r[1]
        for r in connection.execute(sa.text("SELECT key, id FROM plans")).all()
    }
    for plan_key, limit_value in PLAN_LIMITS.items():
        plan_id = plans.get(plan_key)
        if plan_id is None:
            continue
        have = connection.execute(
            sa.text(
                "SELECT 1 FROM plan_features WHERE plan_id = :plan_id "
                "AND feature_key = :feature_key"
            ).bindparams(sa.bindparam("plan_id", type_=sa.Uuid)),
            {"plan_id": plan_id, "feature_key": FEATURE_KEY},
        ).first()
        if have:
            continue
        connection.execute(
            sa.text(
                "INSERT INTO plan_features (id, plan_id, feature_key, limit_value) "
                "VALUES (:id, :plan_id, :feature_key, :limit_value)"
            ).bindparams(
                sa.bindparam("id", type_=sa.Uuid),
                sa.bindparam("plan_id", type_=sa.Uuid),
                sa.bindparam("limit_value", type_=sa.BigInteger),
            ),
            {
                "id": uuid.uuid4(), "plan_id": plan_id,
                "feature_key": FEATURE_KEY, "limit_value": limit_value,
            },
        )
        added += 1

    print(f"  competitors: feature ensured, {added} plan limit(s) added")
    return added


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM plan_features WHERE feature_key = :key"),
        {"key": FEATURE_KEY},
    )
    bind.execute(
        sa.text("DELETE FROM features WHERE key = :key"), {"key": FEATURE_KEY}
    )
    op.drop_index(op.f("ix_competitor_snapshots_date"), table_name="competitor_snapshots")
    op.drop_index(
        op.f("ix_competitor_snapshots_competitor_id"), table_name="competitor_snapshots"
    )
    op.drop_table("competitor_snapshots")
    op.drop_index(
        op.f("ix_competitor_accounts_account_id"), table_name="competitor_accounts"
    )
    op.drop_table("competitor_accounts")
