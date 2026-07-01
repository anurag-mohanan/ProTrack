from datetime import datetime, timezone
from typing import override
from uuid import UUID

from sqlalchemy import func, select

from app.core.exceptions import ProTrackValidationError
from app.crud.base import CRUDBase, Session
from app.models.models import Team, TeamMember, User
from app.schemas.team import (
    TeamCreate,
    TeamMemberCreate,
    TeamMemberRead,
    TeamMemberUpdate,
    TeamRead,
    TeamUpdate,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _user_display(user: User | None) -> str:
    if user is None:
        return "—"
    return f"{user.first_name} {user.last_name}".strip()


def build_team_read(db: Session, team: Team) -> TeamRead:
    member_count = int(
        db.scalar(
            select(func.count())
            .select_from(TeamMember)
            .where(TeamMember.team_id == team.id)
        )
        or 0
    )
    team_lead = db.get(User, team.team_lead_id) if team.team_lead_id else None
    return TeamRead(
        id=team.id,
        name=team.name,
        description=team.description,
        team_lead_id=team.team_lead_id,
        colour=team.colour,
        is_active=team.is_active,
        organization_id=team.organization_id,
        created_at=team.created_at,
        updated_at=team.updated_at,
        member_count=member_count,
        team_lead_name=_user_display(team_lead) if team_lead else None,
    )


def build_team_member_read(db: Session, member: TeamMember) -> TeamMemberRead:
    user = db.get(User, member.user_id)
    return TeamMemberRead(
        id=member.id,
        team_id=member.team_id,
        user_id=member.user_id,
        role_within_team=member.role_within_team,
        joined_at=member.joined_at,
        created_at=member.created_at,
        updated_at=member.updated_at,
        user_name=_user_display(user),
        user_email=user.email if user else "—",
    )


class CRUDTeam(CRUDBase[Team, TeamCreate, TeamUpdate]):
    @override
    def create(self, db: Session, *, obj_in: TeamCreate) -> Team:
        if obj_in.team_lead_id is not None:
            lead = db.get(User, obj_in.team_lead_id)
            if lead is None or not lead.is_active:
                raise ProTrackValidationError("team_lead_id must reference an active user")
        return super().create(db, obj_in=obj_in)

    @override
    def update(
        self,
        db: Session,
        *,
        db_obj: Team,
        obj_in: TeamUpdate | dict[str, object],
    ) -> Team:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        if "team_lead_id" in update_data and update_data["team_lead_id"] is not None:
            lead = db.get(User, update_data["team_lead_id"])
            if lead is None or not lead.is_active:
                raise ProTrackValidationError("team_lead_id must reference an active user")
        return super().update(db, db_obj=db_obj, obj_in=update_data)

    def get_read(self, db: Session, record_id: UUID) -> TeamRead | None:
        team = self.get(db, record_id)
        if team is None:
            return None
        return build_team_read(db, team)

    def list_read(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
    ) -> list[TeamRead]:
        filters: dict[str, object] = {}
        if is_active is not None:
            filters["is_active"] = is_active
        teams = self.get_multi(db, skip=skip, limit=limit, filters=filters or None)
        return [build_team_read(db, team) for team in teams]

    def add_member(
        self, db: Session, *, team_id: UUID, obj_in: TeamMemberCreate
    ) -> TeamMemberRead:
        team = self.get(db, team_id)
        if team is None:
            raise ProTrackValidationError("Team not found")
        user = db.get(User, obj_in.user_id)
        if user is None or not user.is_active:
            raise ProTrackValidationError("user_id must reference an active user")
        existing = db.scalar(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == obj_in.user_id,
            )
        )
        if existing is not None:
            raise ProTrackValidationError("User is already a member of this team")
        member = TeamMember(
            team_id=team_id,
            user_id=obj_in.user_id,
            role_within_team=obj_in.role_within_team,
            joined_at=_utcnow(),
        )
        db.add(member)
        db.commit()
        db.refresh(member)
        return build_team_member_read(db, member)

    def list_members(self, db: Session, team_id: UUID) -> list[TeamMemberRead]:
        members = db.scalars(
            select(TeamMember)
            .where(TeamMember.team_id == team_id)
            .order_by(TeamMember.joined_at)
        ).all()
        return [build_team_member_read(db, member) for member in members]

    def update_member(
        self,
        db: Session,
        *,
        team_id: UUID,
        member_id: UUID,
        obj_in: TeamMemberUpdate,
    ) -> TeamMemberRead:
        member = db.scalar(
            select(TeamMember).where(
                TeamMember.id == member_id,
                TeamMember.team_id == team_id,
            )
        )
        if member is None:
            raise ProTrackValidationError("Team member not found")
        update_data = obj_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(member, key, value)
        db.add(member)
        db.commit()
        db.refresh(member)
        return build_team_member_read(db, member)

    def remove_member(self, db: Session, *, team_id: UUID, member_id: UUID) -> None:
        member = db.scalar(
            select(TeamMember).where(
                TeamMember.id == member_id,
                TeamMember.team_id == team_id,
            )
        )
        if member is None:
            raise ProTrackValidationError("Team member not found")
        db.delete(member)
        db.commit()

    def transfer_member(
        self,
        db: Session,
        *,
        team_id: UUID,
        member_id: UUID,
        target_team_id: UUID,
    ) -> TeamMemberRead:
        if team_id == target_team_id:
            raise ProTrackValidationError("Target team must differ from source team")
        member = db.scalar(
            select(TeamMember).where(
                TeamMember.id == member_id,
                TeamMember.team_id == team_id,
            )
        )
        if member is None:
            raise ProTrackValidationError("Team member not found")
        target = self.get(db, target_team_id)
        if target is None:
            raise ProTrackValidationError("Target team not found")
        duplicate = db.scalar(
            select(TeamMember).where(
                TeamMember.team_id == target_team_id,
                TeamMember.user_id == member.user_id,
            )
        )
        if duplicate is not None:
            raise ProTrackValidationError("User is already a member of the target team")
        member.team_id = target_team_id
        db.add(member)
        db.commit()
        db.refresh(member)
        return build_team_member_read(db, member)


team = CRUDTeam(Team)
