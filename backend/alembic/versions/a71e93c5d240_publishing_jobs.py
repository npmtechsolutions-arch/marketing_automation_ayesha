"""publishing jobs and logs

Revision ID: a71e93c5d240
Revises: f2a90c4d7b18
Create Date: 2026-09-08

Publishing becomes durable and observable. One job per (post, social account)
replaces the inline loop whose only record was a JSON blob on the post, and
every attempt writes a log row carrying the platform's own response.

The two enums are created explicitly with ``postgresql.ENUM`` rather than left
to ``op.create_table``. ``create_table`` fires the type's ``before_create`` with
``checkfirst=False``, and whether that re-issues ``CREATE TYPE`` depends on a
memo held per Alembic process: a from-scratch ``upgrade head`` skips it and
passes, while an existing database running only this migration raises
``DuplicateObjectError``. Creating them up front with ``checkfirst=True`` and
declaring them ``create_type=False`` in the table makes both paths identical.
``sa.Enum(create_type=False)`` silently ignores the flag; only
``postgresql.ENUM`` honours it.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a71e93c5d240"
down_revision = "f2a90c4d7b18"
branch_labels = None
depends_on = None

# Literal labels, never sa.Enum(JobStatus) -- a migration has to stay frozen
# against later edits to the model's enum.
JOB_STATUS_ENUM = postgresql.ENUM(
    "QUEUED", "CLAIMED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED",
    name="publishing_job_status_enum",
    create_type=False,
)
LOG_LEVEL_ENUM = postgresql.ENUM(
    "INFO", "WARNING", "ERROR",
    name="publishing_log_level_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    JOB_STATUS_ENUM.create(bind, checkfirst=True)
    LOG_LEVEL_ENUM.create(bind, checkfirst=True)

    op.create_table(
        "publishing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("social_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", JOB_STATUS_ENUM, nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("claimed_by", sa.String(length=128), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "manual_required", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("external_post_id", sa.String(length=255), nullable=True),
        sa.Column("post_url", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        # Deleting a post takes its jobs with it; disconnecting a social
        # account does not, so the record of what was published through it
        # survives.
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["social_account_id"], ["social_accounts.id"]),
    )
    op.create_index("ix_publishing_jobs_claim", "publishing_jobs", ["status", "run_at"])
    op.create_index("ix_publishing_jobs_post", "publishing_jobs", ["post_id"])
    op.create_index("ix_publishing_jobs_run_at", "publishing_jobs", ["run_at"])

    op.create_table(
        "publishing_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("level", LOG_LEVEL_ENUM, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("platform_response", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["job_id"], ["publishing_jobs.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_publishing_logs_job_created", "publishing_logs", ["job_id", "created_at"]
    )
    op.create_index("ix_publishing_logs_created_at", "publishing_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_publishing_logs_created_at", table_name="publishing_logs")
    op.drop_index("ix_publishing_logs_job_created", table_name="publishing_logs")
    op.drop_table("publishing_logs")

    op.drop_index("ix_publishing_jobs_run_at", table_name="publishing_jobs")
    op.drop_index("ix_publishing_jobs_post", table_name="publishing_jobs")
    op.drop_index("ix_publishing_jobs_claim", table_name="publishing_jobs")
    op.drop_table("publishing_jobs")

    # Safe to drop unconditionally: both types were introduced here and nothing
    # else uses them. create_type=False suppressed the automatic drop, so this
    # is the only place it happens.
    bind = op.get_bind()
    LOG_LEVEL_ENUM.drop(bind, checkfirst=True)
    JOB_STATUS_ENUM.drop(bind, checkfirst=True)
