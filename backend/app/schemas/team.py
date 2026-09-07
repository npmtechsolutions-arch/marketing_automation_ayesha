from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.user import UserResponse


# Every role that may be assigned by invitation. OWNER is absent deliberately:
# ownership transfers are not an invitation, and letting one be issued here
# would be a privilege-escalation path for any admin.
ASSIGNABLE_ROLES = Literal[
    "admin", "manager", "editor", "viewer", "contributor", "analyst", "client",
]


class TeamInvite(BaseModel):
    email: EmailStr
    role: ASSIGNABLE_ROLES


class TeamMemberUpdate(BaseModel):
    role: ASSIGNABLE_ROLES


class RoleOption(BaseModel):
    """A role the UI can offer, with text explaining what it grants."""

    value: str
    label: str
    description: str
    permissions: list[str]


class TeamMemberResponse(BaseModel):
    id: UUID
    user_id: UUID | None = None
    account_id: UUID
    role: str
    invitation_email: str | None = None
    invitation_status: str
    invitation_token: str | None = None
    user: UserResponse | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InviteInfoResponse(BaseModel):
    account_id: UUID
    workspace_name: str
    invitation_email: str | None = None
    role: str
    invitation_status: str
    inviter_name: str | None = None
