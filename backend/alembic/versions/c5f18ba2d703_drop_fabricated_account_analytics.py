"""delete fabricated account-level analytics

Revision ID: c5f18ba2d703
Revises: b8d3aa61c94f
Create Date: 2026-09-10

The companion to ``b8d3aa61c94f``, and the half of it that was missed.

That migration deleted fabricated **post** metrics. It left ``analytics_daily``
alone, which is where ``mock_account_metrics()`` had been writing invented
follower counts, reach and impressions for any account whose token
``is_mock_token()`` matched -- a predicate that catches an empty token, and any
token merely *containing* "test" or "mock".

Found by a Walk B pre-flight: a report generated to check that unmeasured
metrics render as em-dashes rendered "62,233 followers" instead, from 112 rows
none of which described anything real.

**What is deleted.** Rows belonging to a social account whose stored token is
still a development placeholder. For those accounts the connector now returns
nothing at all, so no row it holds can have come from a live API -- the same
unambiguous argument as X and LinkedIn post metrics in the previous revision.
Accounts with a real token are untouched, including their history.

The token is encrypted at rest, so this cannot be a WHERE clause; it decrypts
each account in Python using the application's own predicate rather than
re-implementing the check in SQL and getting it subtly different.

Irreversible, deliberately: the downgrade will not put invented numbers back.
"""

import sqlalchemy as sa
from alembic import op

revision = "c5f18ba2d703"
down_revision = "b8d3aa61c94f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.connectors.base import is_mock_token
    from app.models.platform import SocialAccount

    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)
    try:
        placeholder_ids = [
            account.id
            for account in session.query(SocialAccount).all()
            if is_mock_token(account.access_token)
        ]
        if not placeholder_ids:
            print("  no placeholder-token accounts; nothing to remove")
            return

        result = bind.execute(
            sa.text(
                "DELETE FROM analytics_daily WHERE social_account_id IN :ids"
            ).bindparams(sa.bindparam("ids", expanding=True)),
            {"ids": placeholder_ids},
        )
        print(
            f"  removed {result.rowcount} fabricated daily row(s) across "
            f"{len(placeholder_ids)} placeholder-token account(s)"
        )
    finally:
        session.close()


def downgrade() -> None:
    """Nothing to restore. The deleted rows were randomly generated."""
