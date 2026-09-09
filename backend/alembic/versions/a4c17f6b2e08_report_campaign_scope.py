"""scope a report to a campaign

Revision ID: a4c17f6b2e08
Revises: 3e7835da8a96
Create Date: 2026-09-09

Adds ``reports.campaign_id``. Null means what it has always meant: the report
covers the whole workspace. A value scopes it to one campaign, which is what
``POST /campaigns/{id}/report`` sets.

``ondelete="SET NULL"`` rather than CASCADE, deliberately. Deleting a campaign
should not delete a report a client has already been sent -- the row keeps its
frozen ``summary`` payload and its rendered files and simply stops being
linked. The generator refuses to widen an orphaned campaign report back to the
whole workspace, so an unlinked row is a dead record rather than a silently
different report.

The index exists for "reports for this campaign", which is the only way the
column is queried.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "a4c17f6b2e08"
down_revision = "3e7835da8a96"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reports",
        sa.Column("campaign_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_reports_campaign_id_campaigns",
        "reports",
        "campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_reports_campaign_id", "reports", ["campaign_id"])


def downgrade() -> None:
    op.drop_index("ix_reports_campaign_id", table_name="reports")
    op.drop_constraint(
        "fk_reports_campaign_id_campaigns", "reports", type_="foreignkey"
    )
    op.drop_column("reports", "campaign_id")
