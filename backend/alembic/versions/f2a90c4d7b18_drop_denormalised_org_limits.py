"""drop denormalised organization limits

Revision ID: f2a90c4d7b18
Revises: d5b28a71f3c6
Create Date: 2026-09-08

``organizations`` carried four limit columns -- ``monthly_post_limit``,
``max_team_members``, ``max_platforms`` and ``max_workspaces`` -- denormalised
from ``TIER_LIMITS`` by ``apply_tier``. Since d5b28a71f3c6 nothing reads them
for enforcement: limits live in ``plan_features`` and are resolved through
``EntitlementService``.

They were still serialized by ``OrganizationResponse`` and three other
endpoints, though, which is the drift the previous migration existed to end.
A superadmin raising a cap in the admin panel changes ``plan_features`` and
invalidates the cache; these columns would keep the old number and the UI
would show a limit that disagreed with both the usage endpoint and what
enforcement actually does.

The downgrade cannot round-trip faithfully and does not pretend to. The old
columns are NOT NULL integers with no way to express "unlimited", so an
enterprise plan's NULL is restored as ``UNLIMITED_SENTINEL`` -- the same kind
of stand-in that made the original scheme ambiguous. Anything relying on the
restored values is reading a lossy copy.
"""

import sqlalchemy as sa
from alembic import op

revision = "f2a90c4d7b18"
down_revision = "d5b28a71f3c6"
branch_labels = None
depends_on = None

# Column -> the feature key it was denormalised from, in drop order.
COLUMNS = (
    ("monthly_post_limit", "posts_per_month", 10),
    ("max_team_members", "team_members", 1),
    ("max_platforms", "social_accounts", 2),
    ("max_workspaces", "workspaces", 1),
)

# "Unlimited" has no representation in a NOT NULL integer column. The original
# code used 99999 for this; the downgrade reuses a large number rather than
# inventing a new convention.
UNLIMITED_SENTINEL = 999999


def upgrade() -> None:
    for column, _feature, _default in COLUMNS:
        op.drop_column("organizations", column)


def downgrade() -> None:
    # 1. Re-add nullable so existing rows are accepted.
    for column, _feature, _default in COLUMNS:
        op.add_column("organizations", sa.Column(column, sa.Integer(), nullable=True))

    # 2. Backfill from the plan the organization is on. A limit of NULL
    #    (unlimited) becomes the sentinel; a plan or feature row that is
    #    missing falls back to the column's original default.
    connection = op.get_bind()
    for column, feature_key, default in COLUMNS:
        connection.execute(
            sa.text(
                f"UPDATE organizations SET {column} = COALESCE("  # noqa: S608
                "  (SELECT COALESCE(pf.limit_value, :sentinel)"
                "     FROM plan_features pf"
                "     JOIN plans p ON p.id = pf.plan_id"
                "    WHERE p.key = LOWER(organizations.subscription_tier::text)"
                "      AND pf.feature_key = :feature_key),"
                "  :default)"
            ).bindparams(
                sentinel=UNLIMITED_SENTINEL, feature_key=feature_key, default=default
            )
        )

    # 3. Restore NOT NULL and the server-side defaults the models declared.
    for column, _feature, default in COLUMNS:
        op.alter_column(
            "organizations",
            column,
            existing_type=sa.Integer(),
            nullable=False,
            server_default=str(default),
        )
