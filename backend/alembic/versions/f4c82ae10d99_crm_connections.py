"""crm connections

Revision ID: f4c82ae10d99
Revises: e3b91d5a77c4
Create Date: 2026-09-10

One CRM connection per organization per provider.

**Organization-scoped, not workspace-scoped.** A CRM belongs to the company
rather than to one of its brands: an agency running four workspaces has one
HubSpot portal, and a per-workspace credential would mean four copies of the
same secret and four chances for three of them to go stale.

The unique constraint is what makes reconnecting an update rather than an
accumulation -- two rows for the same provider would be two portals silently
competing for the same "Send to CRM" press.

Tokens are plain TEXT at the database level; encryption is the application
type's job, exactly as with ``social_accounts.access_token`` and
``accounts.slack_webhook_url``.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "f4c82ae10d99"
down_revision = "e3b91d5a77c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id", UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_account_id", sa.String(100), nullable=True),
        sa.Column("external_account_name", sa.String(255), nullable=True),
        # SET NULL: removing a person must not remove the company's CRM link.
        sa.Column(
            "connected_by", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=True,
        ),
        sa.UniqueConstraint(
            "organization_id", "provider", name="uq_crm_connection"
        ),
    )


def downgrade() -> None:
    op.drop_table("crm_connections")
