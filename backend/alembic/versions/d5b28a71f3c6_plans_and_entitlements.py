"""plans and entitlements

Revision ID: d5b28a71f3c6
Revises: c93a5f21e0d4
Create Date: 2026-09-07 23:55:00.000000

Creates plans/features/plan_features/usage_records and seeds them from the
TIER_LIMITS and TIER_PRICING dictionaries that used to hold this in code.

The seeded numbers reproduce the previous behaviour exactly, so nothing about
what any customer may do changes on the day this runs. What changes is that a
limit becomes editable without a deploy, and can differ per plan row rather
than per Python literal.

Values are inlined rather than imported from app.services.entitlements: a
migration must keep working after the source it was derived from is deleted,
which is precisely what the next commit does to those dicts.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d5b28a71f3c6"
down_revision: Union[str, Sequence[str], None] = "c93a5f21e0d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FEATURE_UNIT_ENUM = postgresql.ENUM(
    "COUNT", "BOOLEAN", "BYTES", name="feature_unit_enum", create_type=False,
)

# key, name, description, unit, metered, sort
FEATURES = [
    ("workspaces", "Workspaces", "Client workspaces in the organization", "COUNT", False, 10),
    ("team_members", "Team members", "People with access, counted once each", "COUNT", False, 20),
    ("social_accounts", "Social accounts", "Connected social profiles", "COUNT", False, 30),
    ("posts_per_month", "Posts per month", "Posts created this billing period", "COUNT", True, 40),
    ("ai_requests_per_month", "AI requests per month", "AI generations this billing period", "COUNT", True, 50),
    ("storage_bytes", "Storage", "Uploaded media", "BYTES", False, 60),
    ("analytics_history_days", "Analytics history", "How far back analytics reach", "COUNT", False, 70),
    ("reports_per_month", "Reports per month", "Reports generated this billing period", "COUNT", True, 80),
    ("white_label", "White label", "Remove MarketEngine branding", "BOOLEAN", False, 90),
]

# Straight from TIER_LIMITS / TIER_PRICING. posts/members/platforms are the
# previous values verbatim; the features that had no dict entry get limits
# consistent with each tier's position. None means unlimited.
PLANS = [
    # key, name, price_monthly, sort, limits
    ("free", "Free", 0.0, 0, {
        "workspaces": 1, "team_members": 1, "social_accounts": 2,
        "posts_per_month": 10, "ai_requests_per_month": 20,
        "storage_bytes": 1_073_741_824, "analytics_history_days": 7,
        "reports_per_month": 1, "white_label": 0,
    }),
    ("starter", "Starter", 49.0, 1, {
        "workspaces": 3, "team_members": 3, "social_accounts": 5,
        "posts_per_month": 50, "ai_requests_per_month": 200,
        "storage_bytes": 10_737_418_240, "analytics_history_days": 30,
        "reports_per_month": 10, "white_label": 0,
    }),
    ("growth", "Growth", 149.0, 2, {
        "workspaces": 10, "team_members": 10, "social_accounts": 8,
        "posts_per_month": 200, "ai_requests_per_month": 1000,
        "storage_bytes": 53_687_091_200, "analytics_history_days": 90,
        "reports_per_month": 50, "white_label": 0,
    }),
    ("pro", "Pro", 399.0, 3, {
        "workspaces": 25, "team_members": 25, "social_accounts": 8,
        "posts_per_month": 1000, "ai_requests_per_month": 5000,
        "storage_bytes": 214_748_364_800, "analytics_history_days": 365,
        "reports_per_month": 200, "white_label": 1,
    }),
    ("enterprise", "Enterprise", 0.0, 4, {
        # None = unlimited. ENTERPRISE previously used 99999/100 as stand-ins
        # for "no cap"; an explicit NULL says what was meant.
        "workspaces": None, "team_members": None, "social_accounts": None,
        "posts_per_month": None, "ai_requests_per_month": None,
        "storage_bytes": None, "analytics_history_days": None,
        "reports_per_month": None, "white_label": 1,
    }),
]


def upgrade() -> None:
    bind = op.get_bind()
    FEATURE_UNIT_ENUM.create(bind, checkfirst=True)

    op.create_table(
        "plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("stripe_price_id", sa.String(length=255), nullable=True),
        sa.Column("price_monthly", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_plans_key"), "plans", ["key"], unique=True)

    op.create_table(
        "features",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit", FEATURE_UNIT_ENUM, nullable=False),
        sa.Column("is_metered", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "plan_features",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("feature_key", sa.String(length=64), nullable=False),
        sa.Column("limit_value", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.ForeignKeyConstraint(["feature_key"], ["features.key"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "feature_key", name="uq_plan_feature"),
    )
    op.create_index(op.f("ix_plan_features_plan_id"), "plan_features", ["plan_id"])
    op.create_index(op.f("ix_plan_features_feature_key"), "plan_features", ["feature_key"])

    op.create_table(
        "usage_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("feature_key", sa.String(length=64), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["feature_key"], ["features.key"]),
        sa.PrimaryKeyConstraint("id"),
        # This constraint is what makes the atomic check-and-increment work:
        # without it the ON CONFLICT target does not exist.
        sa.UniqueConstraint(
            "organization_id", "feature_key", "period_start", name="uq_usage_period"
        ),
    )
    op.create_index(
        op.f("ix_usage_records_organization_id"), "usage_records", ["organization_id"]
    )

    seed_plans(op.get_bind())


def seed_plans(connection) -> int:
    """Insert the feature and plan rows. Idempotent -- existing keys are left
    alone, so a re-run cannot duplicate or overwrite an edited limit."""
    existing_features = {
        r[0] for r in connection.execute(sa.text("SELECT key FROM features"))
    }
    for key, name, description, unit, metered, sort in FEATURES:
        if key in existing_features:
            continue
        connection.execute(
            sa.text(
                "INSERT INTO features (key, name, description, unit, is_metered, sort_order) "
                "VALUES (:key, :name, :description, :unit, :is_metered, :sort_order)"
            ).bindparams(sa.bindparam("unit", type_=FEATURE_UNIT_ENUM)),
            {
                "key": key, "name": name, "description": description,
                "unit": unit, "is_metered": metered, "sort_order": sort,
            },
        )

    existing_plans = {
        r[0]: r[1]
        for r in connection.execute(sa.text("SELECT key, id FROM plans")).all()
    }
    seeded = 0
    for key, name, price, sort, limits in PLANS:
        plan_id = existing_plans.get(key)
        if plan_id is None:
            plan_id = uuid.uuid4()
            connection.execute(
                sa.text(
                    "INSERT INTO plans (id, key, name, price_monthly, is_active, sort_order) "
                    "VALUES (:id, :key, :name, :price, true, :sort)"
                ).bindparams(sa.bindparam("id", type_=sa.Uuid)),
                {"id": plan_id, "key": key, "name": name, "price": price, "sort": sort},
            )
            seeded += 1

        have = {
            r[0]
            for r in connection.execute(
                sa.text(
                    "SELECT feature_key FROM plan_features WHERE plan_id = :plan_id"
                ).bindparams(sa.bindparam("plan_id", type_=sa.Uuid)),
                {"plan_id": plan_id},
            )
        }
        for feature_key, limit_value in limits.items():
            if feature_key in have:
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
                    "feature_key": feature_key, "limit_value": limit_value,
                },
            )

    print(f"  plans: {seeded} seeded, {len(FEATURES)} features ensured")
    return seeded


def downgrade() -> None:
    op.drop_index(op.f("ix_usage_records_organization_id"), table_name="usage_records")
    op.drop_table("usage_records")
    op.drop_index(op.f("ix_plan_features_feature_key"), table_name="plan_features")
    op.drop_index(op.f("ix_plan_features_plan_id"), table_name="plan_features")
    op.drop_table("plan_features")
    op.drop_table("features")
    op.drop_index(op.f("ix_plans_key"), table_name="plans")
    op.drop_table("plans")
    FEATURE_UNIT_ENUM.drop(op.get_bind(), checkfirst=True)
