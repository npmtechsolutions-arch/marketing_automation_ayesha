"""Social listening: saved searches, their matches, and the plan limit.

Two tables and one feature key. The feature is seeded into every plan here
rather than left to a later data fix, because a plan with no row for a feature
resolves as *not granted*, and shipping the endpoints before the rows would
mean every workspace's first listening query was refused with a 402.

The limits reflect what the reads cost rather than what the tiers "feel" like.
At X's pay-per-use rate of $0.005 a post read, one query polling four times a
day at 25 posts a poll is roughly $15/month of API spend, so three queries on
Growth is around $45 -- real money against a $149 plan, and the reason Free
gets none at all.

Revision ID: a2f7c1d4e908
Revises: f4c82ae10d99
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2f7c1d4e908"
down_revision: Union[str, Sequence[str], None] = "f4c82ae10d99"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FEATURE_KEY = "listening_queries"
FEATURE_ROW = (
    FEATURE_KEY,
    "Listening queries",
    "Saved searches watched on X, within its rolling 7-day search window",
    "COUNT",
    False,  # not metered: a saved search is a thing that exists, not a spend
    35,     # beside social_accounts, which it is priced like
)

# plan key -> how many saved searches. None would mean unlimited; nothing here
# is unlimited except Enterprise, because every query costs money to poll.
PLAN_LIMITS = {
    "free": 0,
    "starter": 1,
    "growth": 3,
    "pro": 10,
    "enterprise": None,
}


def upgrade() -> None:
    op.create_table(
        "listening_queries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False, server_default="twitter"),
        sa.Column("query_text", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result_cursor", sa.String(length=64), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requests_made", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("posts_read", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "platform", "query_text", name="uq_listening_query"),
    )
    op.create_index(
        op.f("ix_listening_queries_account_id"), "listening_queries", ["account_id"]
    )

    op.create_table(
        "listening_mentions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("listening_query_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("author_handle", sa.String(length=120), nullable=True),
        sa.Column("author_name", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("matched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["listening_query_id"], ["listening_queries.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        # The whole of the idempotency. Without it a six-hourly poll would
        # duplicate its own stream four times a day.
        sa.UniqueConstraint(
            "listening_query_id", "external_id", name="uq_listening_mention"
        ),
    )
    op.create_index(
        op.f("ix_listening_mentions_listening_query_id"),
        "listening_mentions",
        ["listening_query_id"],
    )
    # Sorting a stream is by when the author posted, not when we noticed.
    op.create_index(
        "ix_listening_mentions_posted_at", "listening_mentions", ["posted_at"]
    )

    seed_listening_feature(op.get_bind())


def seed_listening_feature(connection) -> int:
    """Insert the feature and its per-plan limits. Idempotent.

    Called by the migration and, so the suite has the same rows, by the test
    harness -- the same arrangement ``seed_plans`` already has. An edited limit
    is left alone on a re-run.
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

    print(f"  listening: feature ensured, {added} plan limit(s) added")
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
    op.drop_index("ix_listening_mentions_posted_at", table_name="listening_mentions")
    op.drop_index(
        op.f("ix_listening_mentions_listening_query_id"),
        table_name="listening_mentions",
    )
    op.drop_table("listening_mentions")
    op.drop_index(op.f("ix_listening_queries_account_id"), table_name="listening_queries")
    op.drop_table("listening_queries")
