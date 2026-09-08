"""account health

Adds connection health to social_accounts so a dying token is visible before a
scheduled post fails on it.

The enum is created explicitly with checkfirst rather than left to add_column:
op.add_column fires the type's before_create with checkfirst=False, and whether
that re-issues CREATE TYPE depends on a per-process memo -- so a from-scratch
run passes while a re-apply after a partial failure raises DuplicateObjectError.

Existing rows default to UNKNOWN rather than CONNECTED: nothing has checked
them, and a clean bill of health nobody verified is worse than an honest "not
checked yet". The first sweep resolves them within the hour.

Revision ID: 88ca81d60b93
Revises: 473557f3ff15
Create Date: 2026-09-08 11:25:09.133751

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '88ca81d60b93'
down_revision: Union[str, Sequence[str], None] = '473557f3ff15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACCOUNT_HEALTH_ENUM = postgresql.ENUM(
    "CONNECTED", "EXPIRING", "FAILED", "UNKNOWN",
    name="account_health_enum", create_type=False,
)


def upgrade() -> None:
    ACCOUNT_HEALTH_ENUM.create(op.get_bind(), checkfirst=True)

    op.add_column('social_accounts', sa.Column('health', ACCOUNT_HEALTH_ENUM, server_default='UNKNOWN', nullable=False))
    op.add_column('social_accounts', sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('social_accounts', sa.Column('health_changed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('social_accounts', sa.Column('health_detail', sa.Text(), nullable=True))
    op.create_index(op.f('ix_social_accounts_health'), 'social_accounts', ['health'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_social_accounts_health'), table_name='social_accounts')
    op.drop_column('social_accounts', 'health_detail')
    op.drop_column('social_accounts', 'health_changed_at')
    op.drop_column('social_accounts', 'last_checked_at')
    op.drop_column('social_accounts', 'health')

    ACCOUNT_HEALTH_ENUM.drop(op.get_bind(), checkfirst=True)
