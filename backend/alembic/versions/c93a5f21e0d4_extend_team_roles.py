"""extend team roles

Revision ID: c93a5f21e0d4
Revises: b1e4c72d90af
Create Date: 2026-09-07 23:30:00.000000

Adds CONTRIBUTOR, ANALYST and CLIENT to ``team_role_enum``.

Postgres can only ADD VALUE to an enum -- there is no DROP VALUE -- so the
downgrade rebuilds the type without them, after moving any member holding one
of the new roles to VIEWER. That reassignment is lossy and deliberate: leaving
a row referencing a value the type no longer has would make the column
unreadable, and VIEWER is the least-privileged role that every version of the
enum shares.

ADD VALUE cannot run inside a transaction block on PostgreSQL below 12. The
project targets 15, where it is allowed, so this runs in the normal
per-migration transaction.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c93a5f21e0d4"
down_revision: Union[str, Sequence[str], None] = "b1e4c72d90af"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_ROLES = ("CONTRIBUTOR", "ANALYST", "CLIENT")
# The five that existed before, in their original order.
ORIGINAL_ROLES = ("OWNER", "ADMIN", "MANAGER", "EDITOR", "VIEWER")
# Every table whose column is typed team_role_enum.
USING_TABLES = ("team_members", "role_permissions")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite stores the enum as VARCHAR; there is no type to alter.
        return
    for role in NEW_ROLES:
        # IF NOT EXISTS makes a re-run harmless.
        op.execute(f"ALTER TYPE team_role_enum ADD VALUE IF NOT EXISTS '{role}'")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Two tables share this type -- team_members.role and role_permissions.role.
    # Both must be converted, or DROP TYPE fails on the remaining dependency.
    for table in USING_TABLES:
        op.execute(
            sa.text(
                f"UPDATE {table} SET role = 'VIEWER' "
                "WHERE role::text = ANY(:new_roles)"
            ).bindparams(sa.bindparam("new_roles", list(NEW_ROLES)))
        )

    labels = ", ".join(f"'{role}'" for role in ORIGINAL_ROLES)
    op.execute("ALTER TYPE team_role_enum RENAME TO team_role_enum_old")
    op.execute(f"CREATE TYPE team_role_enum AS ENUM ({labels})")
    for table in USING_TABLES:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN role TYPE team_role_enum "
            "USING role::text::team_role_enum"
        )
    op.execute("DROP TYPE team_role_enum_old")
