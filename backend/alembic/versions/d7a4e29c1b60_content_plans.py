"""content plans

Revision ID: d7a4e29c1b60
Revises: c5f18ba2d703
Create Date: 2026-09-10

The AI manager's monthly proposals (§14/§26). A plan is a row rather than a
response body because a proposal you cannot come back to is one nobody reviews
properly.

Three enums, created with ``postgresql.ENUM(create_type=False)`` and an
explicit ``.create(bind, checkfirst=True)``. ``op.create_table`` fires an
enum's ``before_create`` with ``checkfirst=False``, memoised per Alembic
process, so a downgrade-then-upgrade in one process raises DuplicateObject --
the trap recorded in CLAUDE.md.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "d7a4e29c1b60"
down_revision = "c5f18ba2d703"
branch_labels = None
depends_on = None

goal_enum = postgresql.ENUM(
    "AWARENESS", "ENGAGEMENT", "TRAFFIC", "LEADS",
    name="plan_goal_enum", create_type=False,
)
plan_status_enum = postgresql.ENUM(
    "PROPOSED", "PARTIALLY_ACCEPTED", "ACCEPTED", "DISCARDED",
    name="plan_status_enum", create_type=False,
)
item_status_enum = postgresql.ENUM(
    "PROPOSED", "ACCEPTED", "DISCARDED",
    name="plan_item_status_enum", create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (goal_enum, plan_status_enum, item_status_enum):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "content_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id", UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "created_by", UUID(as_uuid=True),
            sa.ForeignKey("users.id"), nullable=True,
        ),
        # SET NULL: a plan already reviewed should not vanish with its campaign.
        sa.Column(
            "campaign_id", UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="SET NULL"),
            nullable=True, index=True,
        ),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("goal", goal_enum, nullable=False),
        sa.Column(
            "status", plan_status_enum, nullable=False, server_default="PROPOSED"
        ),
        sa.Column("grounding", JSONB(), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )

    op.create_table(
        "content_plan_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "plan_id", UUID(as_uuid=True),
            sa.ForeignKey("content_plans.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        # Both readings kept: the local one is what a reviewer sees and what a
        # rationale quotes; the instant is what a post would be scheduled at.
        sa.Column("scheduled_local", sa.DateTime(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_account_ids", JSONB(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("hashtags", JSONB(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        # "observed" or "default" -- the same vocabulary best_times uses.
        sa.Column("slot_source", sa.String(16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status", item_status_enum, nullable=False, server_default="PROPOSED"
        ),
        sa.Column(
            "post_id", UUID(as_uuid=True),
            sa.ForeignKey("posts.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("content_plan_items")
    op.drop_table("content_plans")
    bind = op.get_bind()
    for name in ("plan_item_status_enum", "plan_status_enum", "plan_goal_enum"):
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
