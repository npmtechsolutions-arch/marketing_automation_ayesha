"""delete fabricated X and LinkedIn post metrics

Revision ID: b8d3aa61c94f
Revises: a4c17f6b2e08
Create Date: 2026-09-09

Fixing the code stops new fabrications; it does not remove the ones already
stored, which keep appearing on post cards, in analytics and in reports a
client may be sent again.

``TwitterConnector.get_post_metrics`` and ``LinkedInConnector.get_post_metrics``
returned ``mock_metrics_fallback(...)`` -- random integers -- unconditionally,
from the day the connector abstraction landed until now. Neither ever had a
real implementation. So **every** ``post_performances`` row for those two
platforms is invented, with no measured row to tell it apart from, and deleting
them is unambiguous rather than a judgement call.

Deleting is right rather than zeroing: a zeroed row still says "measured, and
the answer was nothing", which is the confident-zero this project keeps
removing. An absent row says "not measured", which is the truth.

The other three platforms are deliberately left alone. Facebook, Instagram and
YouTube each had a real fetch with a fabricated *fallback*, so their rows are a
mix of measurement and invention with nothing in the row to separate them.
Deleting real measurements to be rid of the invented ones would be its own
data loss; the fallback is gone, so the mix stops growing and the rows age out
as posts are re-synced.

Irreversible by nature: the downgrade cannot restore the deleted rows, and
would not want to -- restoring fabricated numbers is not a recovery.
"""

import sqlalchemy as sa
from alembic import op

revision = "b8d3aa61c94f"
down_revision = "a4c17f6b2e08"
branch_labels = None
depends_on = None

# Whatever the platform catalogue happens to call them. platform_type is a
# free string column populated from the platform slug, so this matches the
# spellings actually seen rather than assuming one.
FABRICATED_PLATFORMS = ("twitter", "x", "x-twitter", "x_twitter", "linkedin")


def upgrade() -> None:
    bind = op.get_bind()

    # Rows that were seeded all-zero at publish time and never updated. Until
    # this revision, publishing inserted a fully zeroed PostPerformance row per
    # platform -- a measurement claiming nobody saw the post. Where every metric
    # is still zero, nothing was ever measured, and an absent row says that
    # honestly. A genuine all-zero measurement is indistinguishable and
    # vanishingly rare; it will be recreated by the next sync.
    zeroed = bind.execute(
        sa.text(
            "DELETE FROM post_performances WHERE impressions = 0 AND reach = 0 "
            "AND likes = 0 AND comments = 0 AND shares = 0 AND saves = 0 "
            "AND clicks = 0 AND video_views = 0"
        )
    )
    print(f"  removed {zeroed.rowcount} never-measured all-zero row(s)")

    result = bind.execute(
        sa.text(
            "DELETE FROM post_performances WHERE lower(platform_type) IN :slugs"
        ).bindparams(sa.bindparam("slugs", expanding=True)),
        {"slugs": list(FABRICATED_PLATFORMS)},
    )
    print(
        f"  removed {result.rowcount} fabricated X/LinkedIn performance row(s)"
    )


def downgrade() -> None:
    """Nothing to restore.

    The deleted rows held randomly generated numbers. Recreating them would be
    reintroducing the defect, not undoing a migration.
    """
