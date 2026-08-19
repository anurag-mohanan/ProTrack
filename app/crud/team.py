from datetime import date, datetime, timezone
from typing import override
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import TeamRelationshipType
from app.crud.base import CRUDBase
from app.models.models import Project, Team, TeamMember, User
from app.schemas.team import (
    TeamCreate,
    TeamMemberCreate,
    TeamMemberRead,
    TeamMemberUpdate,
    TeamRead,
    TeamUpdate,
)
from app.services.user_team_service import sync_user_team_membership


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
    billable_member_count = int(
        db.scalar(
            select(func.count())
            .select_from(TeamMember)
            .where(
                TeamMember.team_id == team.id,
                TeamMember.is_billable_headcount.is_(True),
            )
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
        allow_post_completion_timesheet=bool(
            getattr(team, "allow_post_completion_timesheet", True)
        ),
        organization_id=team.organization_id,
        created_at=team.created_at,
        updated_at=team.updated_at,
        member_count=member_count,
        billable_member_count=billable_member_count,
        team_lead_name=_user_display(team_lead) if team_lead else None,
    )


def build_team_member_read(db: Session, member: TeamMember) -> TeamMemberRead:
    user = db.get(User, member.user_id)
    return TeamMemberRead(
        id=member.id,
        team_id=member.team_id,
        user_id=member.user_id,
        role_within_team=member.role_within_team,
        relationship_type=member.relationship_type,
        is_primary=member.is_primary,
        is_billable_headcount=bool(getattr(member, "is_billable_headcount", True)),
        joined_at=member.joined_at,
        effective_from=getattr(member, "effective_from", None),
        created_at=member.created_at,
        updated_at=member.updated_at,
        user_name=_user_display(user),
        user_email=user.email if user else "—",
    )


class CRUDTeam(CRUDBase[Team, TeamCreate, TeamUpdate]):
    @override
    def create(self, db: Session, *, obj_in: TeamCreate) -> Team:
        name = obj_in.name.strip()
        if not name:
            raise ProTrackValidationError("Team name is required.")
        existing = db.scalar(select(Team.id).where(Team.name == name))
        if existing is not None:
            raise ProTrackValidationError("A team with this name already exists.")
        if obj_in.team_lead_id is not None:
            lead = db.get(User, obj_in.team_lead_id)
            if lead is None or not lead.is_active:
                raise ProTrackValidationError("team_lead_id must reference an active user")
        payload = obj_in.model_copy(update={"name": name})
        created = super().create(db, obj_in=payload)
        if created.team_lead_id is not None:
            sync_user_team_membership(db, created.team_lead_id, created.id)
            db.commit()
            db.refresh(created)
        return created

    @override
    def update(
        self,
        db: Session,
        *,
        db_obj: Team,
        obj_in: TeamUpdate | dict[str, object],
    ) -> Team:
        if isinstance(obj_in, dict):
            update_data = dict(obj_in)
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        if "name" in update_data and update_data["name"] is not None:
            name = str(update_data["name"]).strip()
            if not name:
                raise ProTrackValidationError("Team name is required.")
            duplicate = db.scalar(
                select(Team.id).where(Team.name == name, Team.id != db_obj.id)
            )
            if duplicate is not None:
                raise ProTrackValidationError("A team with this name already exists.")
            update_data["name"] = name
        if "team_lead_id" in update_data and update_data["team_lead_id"] is not None:
            lead = db.get(User, update_data["team_lead_id"])
            if lead is None or not lead.is_active:
                raise ProTrackValidationError("team_lead_id must reference an active user")
        updated = super().update(db, db_obj=db_obj, obj_in=update_data)
        if "team_lead_id" in update_data and updated.team_lead_id is not None:
            sync_user_team_membership(db, updated.team_lead_id, updated.id)
            db.commit()
            db.refresh(updated)
        return updated

    @override
    def delete(self, db: Session, *, record_id: UUID) -> Team | None:
        team_obj = self.get(db, record_id)
        if team_obj is None:
            return None
        db.execute(
            update(Project).where(Project.team_id == record_id).values(team_id=None)
        )
        db.execute(
            update(User).where(User.team_id == record_id).values(team_id=None)
        )
        db.execute(delete(TeamMember).where(TeamMember.team_id == record_id))
        db.delete(team_obj)
        db.commit()
        return team_obj

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
        from app.core.fixed_resource_eligibility import default_is_billable_headcount_for_user
        from app.db.phase28_team_member_billable_schema_sync import is_corporate_team

        billable = obj_in.is_billable_headcount
        if billable is None:
            if is_corporate_team(team):
                billable = False
            else:
                billable = default_is_billable_headcount_for_user(
                    db, team=team, user=user
                )
        member = TeamMember(
            team_id=team_id,
            user_id=obj_in.user_id,
            role_within_team=obj_in.role_within_team,
            relationship_type=obj_in.relationship_type,
            is_primary=False,
            is_billable_headcount=bool(billable),
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
        effective_from: date | None = None,
        update_reporting_manager: bool = True,
    ) -> TeamMemberRead:
        from app.services.team_transfer_service import transfer_primary_membership

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
        if not member.is_primary:
            raise ProTrackValidationError(
                "Only the primary team home can be transferred with an effective date. "
                "Set primary on Users or transfer the primary membership row."
            )
        user = db.get(User, member.user_id)
        if user is None or not user.is_active:
            raise ProTrackValidationError("User not found or inactive")
        transfer_date = effective_from or date.today()
        moved = transfer_primary_membership(
            db,
            user=user,
            source_team_id=team_id,
            target_team_id=target_team_id,
            effective_from=transfer_date,
            member=member,
            update_reporting_manager=update_reporting_manager,
        )
        db.commit()
        db.refresh(moved)
        return build_team_member_read(db, moved)

    def assign_primary_member(
        self,
        db: Session,
        *,
        team_id: UUID,
        user_id: UUID,
        effective_from: date | None = None,
        update_reporting_manager: bool = True,
    ) -> TeamMemberRead:
        from app.services.team_transfer_service import assign_primary_membership

        user = db.get(User, user_id)
        if user is None or not user.is_active:
            raise ProTrackValidationError("User not found or inactive")
        assign_date = effective_from or date.today()
        member = assign_primary_membership(
            db,
            user=user,
            target_team_id=team_id,
            effective_from=assign_date,
            update_reporting_manager=update_reporting_manager,
        )
        db.commit()
        db.refresh(member)
        return build_team_member_read(db, member)


team = CRUDTeam(Team)
