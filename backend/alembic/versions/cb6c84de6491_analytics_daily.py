"""analytics daily

One row per connected account per day, so follower growth can be shown at all --
nothing previously recorded a count at a point in time, which is why the
dashboard's growth figure has been returning null.

Every metric column is nullable on purpose. Null means "this platform does not
report it", not zero: X exposes no reach on our tier, LinkedIn no saves,
profile visits exist on Instagram and nowhere else. Storing 0 for those would
draw a real flat line and drag every cross-platform average down.

No enum here, so none of the create_type handling the other migrations need.

Revision ID: cb6c84de6491
Revises: 88ca81d60b93
Create Date: 2026-09-08 12:20:39.858492

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb6c84de6491'
down_revision: Union[str, Sequence[str], None] = '88ca81d60b93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('analytics_daily',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('social_account_id', sa.UUID(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('followers', sa.BigInteger(), nullable=True),
    sa.Column('following', sa.BigInteger(), nullable=True),
    sa.Column('posts_count', sa.BigInteger(), nullable=True),
    sa.Column('likes', sa.BigInteger(), nullable=True),
    sa.Column('comments', sa.BigInteger(), nullable=True),
    sa.Column('shares', sa.BigInteger(), nullable=True),
    sa.Column('saves', sa.BigInteger(), nullable=True),
    sa.Column('reach', sa.BigInteger(), nullable=True),
    sa.Column('impressions', sa.BigInteger(), nullable=True),
    sa.Column('video_views', sa.BigInteger(), nullable=True),
    sa.Column('profile_visits', sa.BigInteger(), nullable=True),
    sa.Column('clicks', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['social_account_id'], ['social_accounts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('social_account_id', 'date', name='uq_analytics_daily_day')
    )
    op.create_index('ix_analytics_daily_account_date', 'analytics_daily', ['social_account_id', 'date'], unique=False)
    op.create_index('ix_analytics_daily_date', 'analytics_daily', ['date'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_analytics_daily_date', table_name='analytics_daily')
    op.drop_index('ix_analytics_daily_account_date', table_name='analytics_daily')
    op.drop_table('analytics_daily')
