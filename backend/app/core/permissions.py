"""What each workspace role may do.

Authorization used to compare roles by their index in a list, which only works
while roles form a straight ladder. CONTRIBUTOR, ANALYST and CLIENT break that:
an analyst is not a weaker manager, they see a different slice entirely. A
ranked comparison cannot express "may read analytics but not content".

So a role maps to a *set* of permissions and endpoints declare the permission
they need. Adding a role becomes a matter of listing what it may do, rather than
finding somewhere to slot it into an order that no longer exists.
"""

from app.models.team_member import TeamRole

# ---------------------------------------------------------------------------
# The permission vocabulary. Endpoints reference these constants rather than
# bare strings so a typo is an ImportError instead of a silent allow.
# ---------------------------------------------------------------------------

CONTENT_VIEW = "content.view"
CONTENT_CREATE = "content.create"
CONTENT_PUBLISH = "content.publish"
CONTENT_APPROVE = "content.approve"
CONTENT_DELETE = "content.delete"

ACCOUNTS_CONNECT = "accounts.connect"
ACCOUNTS_MANAGE = "accounts.manage"

ANALYTICS_VIEW = "analytics.view"
REPORTS_VIEW = "reports.view"
REPORTS_MANAGE = "reports.manage"

TEAM_VIEW = "team.view"
TEAM_MANAGE = "team.manage"

BILLING_VIEW = "billing.view"
BILLING_MANAGE = "billing.manage"

SETTINGS_MANAGE = "settings.manage"

PERMISSIONS: dict[str, str] = {
    CONTENT_VIEW: "View posts, campaigns and strategies",
    CONTENT_CREATE: "Create and edit drafts",
    CONTENT_PUBLISH: "Publish and schedule content",
    CONTENT_APPROVE: "Approve or reject content awaiting review",
    CONTENT_DELETE: "Delete content",
    ACCOUNTS_CONNECT: "Connect a social account",
    ACCOUNTS_MANAGE: "Disconnect or reconfigure social accounts",
    ANALYTICS_VIEW: "View analytics",
    REPORTS_VIEW: "View reports",
    REPORTS_MANAGE: "Create and edit reports",
    TEAM_VIEW: "See who is on the team",
    TEAM_MANAGE: "Invite, remove and change roles",
    BILLING_VIEW: "View the plan, usage and invoices",
    BILLING_MANAGE: "Change the plan and payment details",
    SETTINGS_MANAGE: "Change workspace settings",
}

_ALL_PERMISSIONS = frozenset(PERMISSIONS)

# ---------------------------------------------------------------------------
# Role → permissions.
#
# These preserve what each of the original five roles could already do; the
# three new roles are additions, not a re-cut of the existing ones.
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: dict[TeamRole, frozenset[str]] = {
    TeamRole.OWNER: _ALL_PERMISSIONS,
    # ADMIN matches OWNER across this vocabulary. The one thing only an owner
    # may do -- delete the workspace -- is not a permission here; it stays an
    # explicit owner check in accounts.py.
    TeamRole.ADMIN: _ALL_PERMISSIONS,
    TeamRole.MANAGER: frozenset({
        CONTENT_VIEW, CONTENT_CREATE, CONTENT_PUBLISH, CONTENT_APPROVE,
        CONTENT_DELETE, ACCOUNTS_CONNECT, ANALYTICS_VIEW, REPORTS_VIEW,
        REPORTS_MANAGE, TEAM_VIEW, BILLING_VIEW,
    }),
    TeamRole.EDITOR: frozenset({
        CONTENT_VIEW, CONTENT_CREATE, CONTENT_PUBLISH, CONTENT_DELETE,
        ACCOUNTS_CONNECT, ANALYTICS_VIEW, REPORTS_VIEW, TEAM_VIEW,
    }),
    TeamRole.VIEWER: frozenset({
        CONTENT_VIEW, ANALYTICS_VIEW, REPORTS_VIEW, TEAM_VIEW,
    }),
    # Drafts only. The absence of CONTENT_PUBLISH is the whole point of the
    # role, and scheduling counts as publishing -- it is publishing later.
    TeamRole.CONTRIBUTOR: frozenset({
        CONTENT_VIEW, CONTENT_CREATE, TEAM_VIEW,
    }),
    # Numbers, not content. No CONTENT_VIEW: an analyst reading every draft
    # would defeat the point of a read-only reporting role.
    TeamRole.ANALYST: frozenset({
        ANALYTICS_VIEW, REPORTS_VIEW, TEAM_VIEW,
    }),
    # External. Exactly two permissions, and CONTENT_VIEW is additionally
    # narrowed at the query level to items awaiting approval -- see
    # `restricts_content_to_approvals`. A permission bit alone would let a
    # client read every draft in the workspace.
    TeamRole.CLIENT: frozenset({
        CONTENT_VIEW, CONTENT_APPROVE,
    }),
}


def permissions_for(role: TeamRole | str) -> frozenset[str]:
    """The permission set for a role, empty for anything unrecognised.

    Fails closed: an unknown role grants nothing rather than raising, so a role
    added to the enum without a mapping locks itself out instead of inheriting
    someone else's access.
    """
    if isinstance(role, str) and not isinstance(role, TeamRole):
        try:
            role = TeamRole(role)
        except ValueError:
            return frozenset()
    return ROLE_PERMISSIONS.get(role, frozenset())


def role_has_permission(role: TeamRole | str, permission: str) -> bool:
    return permission in permissions_for(role)


def restricts_content_to_approvals(role: TeamRole | str) -> bool:
    """Whether this role may only see content awaiting approval.

    CLIENT is an external reviewer. Holding CONTENT_VIEW lets them open the
    approval queue; it must not also expose drafts, internal notes or anything
    else in the workspace, so content queries narrow themselves for this role.
    """
    if isinstance(role, str) and not isinstance(role, TeamRole):
        try:
            role = TeamRole(role)
        except ValueError:
            return True  # unknown role: show nothing
    return role is TeamRole.CLIENT


# Human-readable, for the invite UI and the team page.
ROLE_DESCRIPTIONS: dict[TeamRole, str] = {
    TeamRole.OWNER: "Full access, including billing and deleting the workspace.",
    TeamRole.ADMIN: "Full access to content, team, billing and settings.",
    TeamRole.MANAGER: "Manages content and approvals, and sees billing. Cannot change the team or settings.",
    TeamRole.EDITOR: "Creates, edits and publishes content.",
    TeamRole.VIEWER: "Read-only access to content and analytics.",
    TeamRole.CONTRIBUTOR: "Writes drafts. Cannot publish or schedule.",
    TeamRole.ANALYST: "Reads analytics and reports only. No access to content.",
    TeamRole.CLIENT: "External reviewer. Sees only content awaiting their approval, and can approve or reject it.",
}
