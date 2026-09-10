"""slack webhook on the workspace

Revision ID: e3b91d5a77c4
Revises: d7a4e29c1b60
Create Date: 2026-09-10

A Slack incoming webhook, per workspace. A column rather than a key in the
`settings` JSON blob for two reasons, and both matter:

* it is a **credential** -- anyone holding it can post into the workspace's
  channel as this app -- so it is stored through ``EncryptedText`` like the
  social account tokens, and the settings blob is plain JSON;
* ``GET /settings/`` returns the whole blob, so a key there would put the
  credential in every settings response and in whatever logs carry one.

The column is plain TEXT at the database level; the encryption is the
application type's job, exactly as with ``social_accounts.access_token``.

Per-event routing toggles are *not* here. They are preferences rather than
secrets, they belong beside the timezone and the approval flags, and they live
in the settings blob under ``slack_events``.
"""

import sqlalchemy as sa
from alembic import op

revision = "e3b91d5a77c4"
down_revision = "d7a4e29c1b60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("slack_webhook_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "slack_webhook_url")
