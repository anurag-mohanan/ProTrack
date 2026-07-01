from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampSchema


class TeamBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    team_lead_id: UUID | None = None
    colour: str = Field(default="#1976d2", max_length=20)
    is_active: bool = True
    organization_id: UUID | None = None


class TeamCreate(TeamBase):
    pass


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    team_lead_id: UUID | None = None
    colour: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None
    organization_id: UUID | None = None


class TeamRead(TeamBase, TimestampSchema):
    member_count: int = 0
    team_lead_name: str | None = None


class TeamMemberBase(BaseModel):
    user_id: UUID
    role_within_team: str | None = Field(default=None, max_length=100)


class TeamMemberCreate(TeamMemberBase):
    pass


class TeamMemberUpdate(BaseModel):
    role_within_team: str | None = Field(default=None, max_length=100)


class TeamMemberRead(TeamMemberBase, TimestampSchema):
    team_id: UUID
    user_name: str
    user_email: str
    joined_at: datetime


class TeamMemberTransfer(BaseModel):
    target_team_id: UUID
