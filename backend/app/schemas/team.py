from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.user import UserResponse


class TeamInvite(BaseModel):
    email: EmailStr
    role: Literal["admin", "manager", "editor", "viewer"]


class TeamMemberUpdate(BaseModel):
    role: str


class TeamMemberResponse(BaseModel):
    id: UUID
    user_id: UUID | None = None
    account_id: UUID
    role: str
    invitation_email: str | None = None
    invitation_status: str
    user: UserResponse | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
