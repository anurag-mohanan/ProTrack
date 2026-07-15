from datetime import datetime
from uuid import UUID

from app.models.enums import TeamRelationshipType
from pydantic import BaseModel, Field

from app.schemas.common import BlankOptionalFieldsMixin, TimestampSchema


class TeamBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    team_lead_id: UUID | None = None
    colour: str = Field(default="#1976d2", max_length=20)
    is_active: bool = True
    organization_id: UUID | None = None


class TeamCreate(BlankOptionalFieldsMixin, TeamBase):
    pass


class TeamUpdate(BlankOptionalFieldsMixin, BaseModel):
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
    relationship_type: TeamRelationshipType = TeamRelationshipType.member
    is_primary: bool = False
    is_billable_headcount: bool | None = None


class TeamMemberCreate(BlankOptionalFieldsMixin, TeamMemberBase):
    pass


class TeamMemberUpdate(BlankOptionalFieldsMixin, BaseModel):
    role_within_team: str | None = Field(default=None, max_length=100)
    relationship_type: TeamRelationshipType | None = None
    is_primary: bool | None = None
    is_billable_headcount: bool | None = None


class TeamMemberRead(TeamMemberBase, TimestampSchema):
    team_id: UUID
    user_name: str
    user_email: str
    joined_at: datetime
    is_billable_headcount: bool = True


class TeamMemberTransfer(BaseModel):
    target_team_id: UUID
