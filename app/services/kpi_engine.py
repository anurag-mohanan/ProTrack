"""Management and administration KPI calculations."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.permissions import (
    DESIGN_LEADER,
    ENGINEERING_MANAGER,
    get_role_name,
    normalize_role_name,
)
from app.core.team_access import team_member_user_ids
from app.models.enums import ExecutionStatus, MilestoneStatus, TeamRelationshipType, TimesheetStatus
from app.models.models import Activity, Milestone, Project, Team, TeamMember, Timesheet, User
from app.schemas.kpi import AdministrationKpis, LeadershipScopeKpis, ManagementKpis
from app.services.user_team_service import get_user_team_ids


def _active_user_filters():
    return (
        User.is_active.is_(True),
        User.is_archived.is_(False),
        User.is_deleted.is_(False),
    )


def _led_team_ids(db: Session, user: User) -> set[UUID]:
    """Teams where the user is the designated team lead or has a leadership membership."""
    lead_ids = set(
        db.scalars(
            select(Team.id).where(
                Team.team_lead_id == user.id,
                Team.is_active.is_(True),
            )
        ).all()
    )
    membership_ids = set(
        db.scalars(
            select(TeamMember.team_id)
            .join(Team, Team.id == TeamMember.team_id)
            .where(
                TeamMember.user_id == user.id,
                Team.is_active.is_(True),
                TeamMember.relationship_type.in_(
                    (
                        TeamRelationshipType.team_leader,
                        TeamRelationshipType.engineering_manager,
                    )
                ),
            )
        ).all()
    )
    return lead_ids | membership_ids


def get_leadership_scope(db: Session, user: User) -> LeadershipScopeKpis:
    """Resolve managed teams and people under the current leader."""
    role_name = normalize_role_name(get_role_name(db, user))
    show_teams = role_name in {ENGINEERING_MANAGER, DESIGN_LEADER}
    led_teams = _led_team_ids(db, user)
    assigned = get_user_team_ids(db, user.id)

    managed_team_ids: set[UUID] = set()
    if show_teams:
        # Engineering managers / design leaders manage their assigned teams.
        candidate_ids = assigned | led_teams
        if candidate_ids:
            managed_team_ids = set(
                db.scalars(
                    select(Team.id).where(
                        Team.id.in_(candidate_ids),
                        Team.is_active.is_(True),
                    )
                ).all()
            )
    else:
        managed_team_ids = led_teams

    member_ids = team_member_user_ids(db, list(managed_team_ids))
    member_ids.discard(user.id)
    team_members_under = 0
    if member_ids:
        team_members_under = int(
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.id.in_(member_ids), *_active_user_filters())
            )
            or 0
        )

    return LeadershipScopeKpis(
        teams_managed=len(managed_team_ids),
        team_members_under=team_members_under,
        show_teams_managed=show_teams,
        is_team_leader=bool(led_teams) and not show_teams,
    )


def get_management_kpis(db: Session, user: User) -> ManagementKpis:
    today = date.today()
    leadership = get_leadership_scope(db, user)

    managed_filter = or_(
        Project.design_leader_id == user.id,
        Project.team_id.in_(
            select(User.team_id).where(User.id == user.id, User.team_id.is_not(None))
        )
        if user.team_id
        else False,
    )

    active_statuses = (
        ExecutionStatus.currently_being_worked_on,
        ExecutionStatus.on_hold,
        ExecutionStatus.planning,
    )

    projects_managed = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                managed_filter,
            )
        )
        or 0
    )

    projects_delivered = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.is_deleted.is_(False),
                Project.execution_status == ExecutionStatus.completed,
                Project.completed_at >= datetime.now(UTC) - timedelta(days=30),
                managed_filter,
            )
        )
        or 0
    )

    overdue_projects = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                Project.due_date.is_not(None),
                Project.due_date < today,
                Project.execution_status.in_(active_statuses),
                managed_filter,
            )
        )
        or 0
    )

    pending_reviews = int(
        db.scalar(
            select(func.count())
            .select_from(Timesheet)
            .where(Timesheet.status == TimesheetStatus.submitted)
        )
        or 0
    )

    pending_milestones = int(
        db.scalar(
            select(func.count())
            .select_from(Milestone)
            .join(Project, Milestone.project_id == Project.id)
            .where(
                Milestone.status != MilestoneStatus.completed,
                Milestone.due_date.is_not(None),
                Milestone.due_date <= today + timedelta(days=7),
                Project.is_deleted.is_(False),
            )
        )
        or 0
    )

    upcoming_deliveries = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                Project.due_date.is_not(None),
                Project.due_date >= today,
                Project.due_date <= today + timedelta(days=14),
                managed_filter,
            )
        )
        or 0
    )

    return ManagementKpis(
        projects_managed=projects_managed,
        projects_delivered=projects_delivered,
        overdue_projects=overdue_projects,
        pending_reviews=pending_reviews,
        pending_milestone_approvals=pending_milestones,
        upcoming_deliveries=upcoming_deliveries,
        timesheet_compliance_pending=pending_reviews,
        teams_managed=leadership.teams_managed,
        team_members_under=leadership.team_members_under,
    )


def get_administration_kpis(db: Session) -> AdministrationKpis:
    from app.services.backup_service import list_database_backups
    from app.services.system_health_service import get_system_health

    health = get_system_health(db)
    backups = list_database_backups()

    audit_actions = int(
        db.scalar(
            select(func.count())
            .select_from(Activity)
            .where(Activity.created_at >= datetime.now(UTC) - timedelta(days=7))
        )
        or 0
    )

    emails_sent = 0
    try:
        from app.models.foundation import EmailMessage

        emails_sent = int(
            db.scalar(
                select(func.count()).select_from(EmailMessage).where(EmailMessage.status == "sent")
            )
            or 0
        )
    except Exception:
        pass

    return AdministrationKpis(
        active_users=health.active_users,
        import_queue=health.import_queue,
        failed_jobs=health.failed_jobs,
        failed_emails=health.failed_emails,
        backups_count=len(backups),
        last_backup=health.last_backup,
        audit_actions_7d=audit_actions,
        emails_sent=emails_sent,
        backend_status=health.backend_status,
        database_status=health.database_status,
    )
