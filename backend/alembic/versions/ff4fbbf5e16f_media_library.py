"""media library

Revision ID: ff4fbbf5e16f
Revises: a71e93c5d240
Create Date: 2026-09-08

Uploads were previously untracked files in a directory, referenced by URL
strings in ``Post.media_urls``. Nothing recorded who uploaded what, whether a
file was still used, or how much storage a workspace had spent -- the
``storage_bytes`` entitlement always read as zero because nothing counted.

``media_kind_enum`` is created explicitly with ``checkfirst=True`` and declared
``create_type=False`` on the column, rather than being left to
``op.create_table``. create_table fires the type's before_create with
``checkfirst=False``, and whether that re-issues CREATE TYPE depends on a memo
held per Alembic process -- so a from-scratch run passes while a re-apply after
a partial failure raises DuplicateObjectError. Note ``sa.Enum(create_type=False)``
silently ignores the flag; only ``postgresql.ENUM`` honours it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ff4fbbf5e16f'
down_revision: Union[str, Sequence[str], None] = 'a71e93c5d240'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal labels, never sa.Enum(MediaKind): a migration must stay frozen against
# later edits to the model's enum.
MEDIA_KIND_ENUM = postgresql.ENUM(
    "IMAGE", "VIDEO", "DOCUMENT", name="media_kind_enum", create_type=False
)


def upgrade() -> None:
    MEDIA_KIND_ENUM.create(op.get_bind(), checkfirst=True)

    op.create_table('media_folders',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('account_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('parent_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['parent_id'], ['media_folders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('account_id', 'parent_id', 'name', name='uq_media_folder_sibling_name')
    )
    op.create_index('ix_media_folders_account_parent', 'media_folders', ['account_id', 'parent_id'], unique=False)
    op.create_table('media',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('account_id', sa.UUID(), nullable=False),
    sa.Column('folder_id', sa.UUID(), nullable=True),
    sa.Column('uploaded_by', sa.UUID(), nullable=True),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('s3_key', sa.String(length=1024), nullable=False),
    sa.Column('mime_type', sa.String(length=128), nullable=False),
    sa.Column('kind', MEDIA_KIND_ENUM, nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('width', sa.Integer(), nullable=True),
    sa.Column('height', sa.Integer(), nullable=True),
    sa.Column('duration_seconds', sa.Float(), nullable=True),
    sa.Column('alt_text', sa.Text(), nullable=True),
    sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['folder_id'], ['media_folders.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('s3_key', name='uq_media_s3_key')
    )
    op.create_index('ix_media_account_created', 'media', ['account_id', 'created_at'], unique=False)
    op.create_index('ix_media_account_folder', 'media', ['account_id', 'folder_id'], unique=False)
    op.create_index(op.f('ix_media_deleted_at'), 'media', ['deleted_at'], unique=False)
    op.create_table('post_media',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('post_id', sa.UUID(), nullable=False),
    sa.Column('media_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['media_id'], ['media.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('post_id', 'media_id', name='uq_post_media')
    )
    op.create_index('ix_post_media_media', 'post_media', ['media_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_post_media_media', table_name='post_media')
    op.drop_table('post_media')
    op.drop_index(op.f('ix_media_deleted_at'), table_name='media')
    op.drop_index('ix_media_account_folder', table_name='media')
    op.drop_index('ix_media_account_created', table_name='media')
    op.drop_table('media')
    op.drop_index('ix_media_folders_account_parent', table_name='media_folders')
    op.drop_table('media_folders')

    # Introduced here and used by nothing else, and create_type=False suppressed
    # the automatic drop, so this is the only place it happens.
    MEDIA_KIND_ENUM.drop(op.get_bind(), checkfirst=True)
