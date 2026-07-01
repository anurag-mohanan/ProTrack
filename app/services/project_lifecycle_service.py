"""Project archive, restore, soft delete, and permanent delete."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import EntityType, ExecutionStatus, ProjectLifecycleFilter, ProjectStage
from app.models.models import Activity, Milestone, Project, TimesheetEntry, User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class ProjectDeleteDependencies:
    timesheet_entries: int = 0
    milestones: int = 0
    activities: int = 0

    @property
    def has_blockers(self) -> bool:
        return (
            self.timesheet_entries > 0
            or self.milestones > 0
            or self.activities > 0
        )

    def blocker_messages(self) -> list[str]:
        messages: list[str] = []
        if self.timesheet_entries:
            messages.append(
                f"{self.timesheet_entries} timesheet entr"
                f"{'y' if self.timesheet_entries == 1 else 'ies'}"
            )
        if self.milestones:
            messages.append(
                f"{self.milestones} milestone{'s' if self.milestones != 1 else ''}"
            )
        if self.activities:
            messages.append(
                f"{self.activities} activit{'y' if self.activities == 1 else 'ies'}"
            )
        return messages


def get_project_delete_dependencies(
    db: Session, project_id: UUID
) -> ProjectDeleteDependencies:
    timesheet_entries = int(
        db.scalar(
            select(func.count())
            .select_from(TimesheetEntry)
            .where(TimesheetEntry.project_id == project_id)
        )
        or 0
    )
    milestones = int(
        db.scalar(
            select(func.count())
            .select_from(Milestone)
            .where(Milestone.project_id == project_id)
        )
        or 0
    )
    activities = int(
        db.scalar(
            select(func.count())
            .select_from(Activity)
            .where(
                Activity.entity_type == EntityType.project,
                Activity.entity_id == project_id,
            )
        )
        or 0
    )
    return ProjectDeleteDependencies(
        timesheet_entries=timesheet_entries,
        milestones=milestones,
        activities=activities,
    )


def _require_project(db: Session, project_id: UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise ProTrackValidationError("Project not found")
    return project


def archive_project(db: Session, project_id: UUID, actor: User) -> Project:
    project = _require_project(db, project_id)
    if project.is_deleted:
        raise ProTrackValidationError("Deleted projects cannot be archived")
    if project.is_archived:
        raise ProTrackValidationError("Project is already archived")
    if (
        project.execution_status == ExecutionStatus.completed
        and project.completed_at is None
    ):
        project.completed_at = _utcnow()
    project.is_archived = True
    project.archived_at = _utcnow()
    project.archived_by_id = actor.id
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def restore_project_from_archive(db: Session, project_id: UUID) -> Project:
    project = _require_project(db, project_id)
    if project.is_deleted:
        raise ProTrackValidationError("Deleted projects must be restored from Deleted Projects")
    if not project.is_archived:
        raise ProTrackValidationError("Project is not archived")
    project.is_archived = False
    project.archived_at = None
    project.archived_by_id = None
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def soft_delete_project(db: Session, project_id: UUID, actor: User) -> Project:
    project = _require_project(db, project_id)
    if project.is_deleted:
        raise ProTrackValidationError("Project is already deleted")
    project.is_deleted = True
    project.deleted_at = _utcnow()
    project.deleted_by_id = actor.id
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def restore_project_from_deleted(db: Session, project_id: UUID) -> Project:
    project = _require_project(db, project_id)
    if not project.is_deleted:
        raise ProTrackValidationError("Project is not deleted")
    project.is_deleted = False
    project.deleted_at = None
    project.deleted_by_id = None
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def permanent_delete_project(db: Session, project_id: UUID) -> None:
    project = _require_project(db, project_id)
    if not project.is_deleted:
        raise ProTrackValidationError(
            "Only soft-deleted projects can be permanently deleted"
        )
    deps = get_project_delete_dependencies(db, project_id)
    if deps.has_blockers:
        detail = ", ".join(deps.blocker_messages())
        raise ProTrackValidationError(
            f"Cannot permanently delete project: {detail} still exist"
        )
    db.delete(project)
    db.commit()


def apply_lifecycle_filter(stmt, lifecycle: ProjectLifecycleFilter):
    if lifecycle == ProjectLifecycleFilter.deleted:
        return stmt.where(Project.is_deleted.is_(True))
    stmt = stmt.where(Project.is_deleted.is_(False))
    if lifecycle == ProjectLifecycleFilter.archived:
        return stmt.where(Project.is_archived.is_(True))
    stmt = stmt.where(Project.is_archived.is_(False))
    if lifecycle == ProjectLifecycleFilter.completed:
        return stmt.where(Project.execution_status == ExecutionStatus.completed)
    if lifecycle == ProjectLifecycleFilter.cancelled:
        return stmt.where(Project.execution_status == ExecutionStatus.cancelled)
    if lifecycle == ProjectLifecycleFilter.active:
        return stmt.where(
            Project.execution_status.in_(
                (
                    ExecutionStatus.currently_being_worked_on,
                    ExecutionStatus.on_hold,
                )
            )
        )
    return stmt


_EXECUTION_STATUS_SORT = case(
    (Project.execution_status == ExecutionStatus.currently_being_worked_on, 1),
    (Project.execution_status == ExecutionStatus.on_hold, 2),
    (Project.execution_status == ExecutionStatus.cancelled, 3),
    (Project.execution_status == ExecutionStatus.completed, 4),
    else_=5,
)

_PROJECT_STAGE_SORT = case(
    (Project.project_stage == ProjectStage.preliminary, 1),
    (Project.project_stage == ProjectStage.intermediate, 2),
    (Project.project_stage == ProjectStage.final, 3),
    else_=4,
)


def apply_lifecycle_sort(stmt, lifecycle: ProjectLifecycleFilter):
    if lifecycle == ProjectLifecycleFilter.archived:
        return stmt.order_by(Project.archived_at.desc(), Project.updated_at.desc())
    if lifecycle == ProjectLifecycleFilter.completed:
        return stmt.order_by(
            Project.completed_at.desc(),
            Project.updated_at.desc(),
        )
    if lifecycle == ProjectLifecycleFilter.cancelled:
        return stmt.order_by(Project.updated_at.desc(), Project.tool_number.asc())
    if lifecycle == ProjectLifecycleFilter.deleted:
        return stmt.order_by(Project.deleted_at.desc())
    return stmt.order_by(
        _EXECUTION_STATUS_SORT,
        _PROJECT_STAGE_SORT,
        Project.due_date.asc(),
        Project.updated_at.desc(),
    )


def exclude_hidden_projects(stmt):
    """Default visibility: active + completed, not archived or deleted."""
    return stmt.where(
        Project.is_deleted.is_(False),
        Project.is_archived.is_(False),
    )
