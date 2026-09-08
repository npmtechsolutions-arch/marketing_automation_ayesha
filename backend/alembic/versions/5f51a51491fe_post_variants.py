"""post variants

One post, customised per platform. The base post keeps the master content and a
variant overrides it for one platform.

Every override column is nullable, and NULL means "inherit" -- not "empty". A
variant created to set a first comment keeps following the master content as it
is edited, which it could not do if absence and emptiness were the same value.

No enum here, so none of the create_type care the other migrations need.

Revision ID: 5f51a51491fe
Revises: ff4fbbf5e16f
Create Date: 2026-09-08 10:32:05.898417

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5f51a51491fe'
down_revision: Union[str, Sequence[str], None] = 'ff4fbbf5e16f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('post_variants',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('post_id', sa.UUID(), nullable=False),
    sa.Column('platform_slug', sa.String(length=64), nullable=False),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('media', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
    sa.Column('link_url', sa.String(length=2048), nullable=True),
    sa.Column('alt_texts', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
    sa.Column('thumbnail_media_id', sa.UUID(), nullable=True),
    sa.Column('first_comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['thumbnail_media_id'], ['media.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('post_id', 'platform_slug', name='uq_post_variant_platform')
    )
    op.create_index(op.f('ix_post_variants_post_id'), 'post_variants', ['post_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_post_variants_post_id'), table_name='post_variants')
    op.drop_table('post_variants')
