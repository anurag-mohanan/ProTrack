"""Management and administration KPI calculations."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import ExecutionStatus, MilestoneStatus, TimesheetStatus
from app.models.models import Activity, Milestone, Project, Timesheet, User
from app.schemas.kpi import AdministrationKpis, ManagementKpis


def get_management_kpis(db: Session, user: User) -> ManagementKpis:
    today = date.today()
    week_ago = today - timedelta(days=7)

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
    )


def get_administration_kpis(db: Session) -> AdministrationKpis:
    from app.services.backup_service import list_database_backups
    from app.services.system_health_service import get_system_health

    health = get_system_health(db)
    backups = list_database_backups()

    audit_actions = int(
        db.scalar(select(func.count()).select_from(Activity).where(Activity.created_at >= datetime.now(UTC) - timedelta(days=7)))
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
