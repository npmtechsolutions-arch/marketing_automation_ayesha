from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AccountBase(BaseModel):
    name: str


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: str | None = None
    settings: dict | None = None


class AccountResponse(AccountBase):
    id: UUID
    slug: str
    owner_id: UUID
    # The workspace's billing entity. Subscription tier, limits and Stripe ids
    # are the organization's -- read them from /organizations or /billing, not
    # from a workspace.
    organization_id: UUID
    created_at: datetime

    # The caller's role *in this workspace*. Per-workspace rather than on the
    # user, because one person is an owner here and a viewer there -- a single
    # user.role could only ever be right for one of them.
    #
    # Owners are reported as "owner" although they have no TeamMember row: they
    # are the owner_id. The UI used to read a `role` field that UserResponse
    # never sent and fall back to "Member", so the person who created the
    # workspace was told they were a member of it.
    role: str | None = None

    # The owning organization's display name, so the workspace switcher can
    # group by company without a second call -- and, more to the point, without
    # depending on GET /organizations/.
    #
    # That endpoint lists organizations the caller is an accepted *organization*
    # member of, which is correct and deliberately strict. But accepting a
    # *workspace* invitation creates a TeamMember row and no OrganizationMember
    # row, so an invited collaborator reaches the workspace and not its
    # organization. The switcher grouped workspaces under organizations and
    # dropped any whose organization was missing, which meant the one workspace
    # such a person was invited to was the one they could never select.
    #
    # A name is not access: nothing here grants organization permissions, and
    # /organizations/{id} still refuses them.
    organization_name: str | None = None

    model_config = ConfigDict(from_attributes=True)
