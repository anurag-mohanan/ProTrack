"""Validate and normalize timesheet entry payloads."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.core.permissions import FULL_ACCESS_ROLES, get_role_name, is_admin
from app.models.enums import ExecutionStatus, WorkCategory
from app.models.models import (
    Customer,
    Milestone,
    NonProductiveCode,
    Project,
    TaskType,
    TimesheetEntry,
    User,
)
from app.schemas.timesheet import TimesheetEntryCreate, TimesheetEntryUpdate

ACTIVE_PROJECT_STATUSES = (
    ExecutionStatus.currently_being_worked_on,
    ExecutionStatus.on_hold,
)


def can_override_billable(db: Session, user: User) -> bool:
    role_name = get_role_name(db, user)
    return is_admin(db, user) or role_name in FULL_ACCESS_ROLES


def _validate_hours(hours: Decimal) -> None:
    if hours <= 0 or hours > 24:
        raise ProTrackValidationError("Hours must be between 0 and 24")
    if (hours * 2) % 1 != 0:
        raise ProTrackValidationError("Hours must be in 0.5 increments")


def _get_active_project(db: Session, project_id: UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise ProTrackValidationError("Project not found")
    if project.is_deleted or project.is_archived:
        raise ProTrackValidationError("Project is not available for timesheet entry")
    if project.execution_status not in ACTIVE_PROJECT_STATUSES:
        raise ProTrackValidationError(
            "Only active projects (Not Started, In Progress, On Hold) can be used"
        )
    return project


def normalize_entry_payload(
    db: Session,
    payload: TimesheetEntryCreate | TimesheetEntryUpdate,
    *,
    actor: User | None = None,
    existing: TimesheetEntry | None = None,
) -> dict:
    if isinstance(payload, TimesheetEntryUpdate):
        base = {
            "timesheet_id": existing.timesheet_id if existing else None,
            "work_category": existing.work_category if existing else WorkCategory.productive,
            "project_id": existing.project_id if existing else None,
            "customer_id": existing.customer_id if existing else None,
            "task_type_id": existing.task_type_id if existing else None,
            "milestone_id": existing.milestone_id if existing else None,
            "non_productive_code_id": existing.non_productive_code_id if existing else None,
            "entry_date": existing.entry_date if existing else None,
            "hours": existing.hours if existing else None,
            "description": existing.description if existing else None,
            "is_billable": existing.is_billable if existing else True,
        }
        updates = payload.model_dump(exclude_unset=True)
        data = {**base, **updates}
    else:
        data = payload.model_dump()

    work_category = data.get("work_category") or WorkCategory.productive
    hours = data.get("hours")
    if hours is not None:
        _validate_hours(Decimal(str(hours)))

    if work_category == WorkCategory.productive:
        project_id = data.get("project_id")
        if project_id is None:
            raise ProTrackValidationError("Project is required for productive work")
        if data.get("non_productive_code_id"):
            raise ProTrackValidationError(
                "Non-productive code cannot be set for productive work"
            )
        project = _get_active_project(db, project_id)
        data["customer_id"] = project.customer_id
        data["non_productive_code_id"] = None

        task_type_id = data.get("task_type_id")
        if task_type_id is None:
            raise ProTrackValidationError("Task is required for productive work")
        task_type = db.get(TaskType, task_type_id)
        if task_type is None or not task_type.is_active:
            raise ProTrackValidationError("Task type not found or inactive")
        if task_type.stream_id != project.stream_id:
            raise ProTrackValidationError("Task type must belong to the project stream")

        milestone_id = data.get("milestone_id")
        if milestone_id is not None:
            milestone = db.get(Milestone, milestone_id)
            if milestone is None or milestone.project_id != project.id:
                raise ProTrackValidationError("Milestone must belong to the selected project")

        if data.get("is_billable") is None:
            data["is_billable"] = True
        elif actor is not None and not can_override_billable(db, actor):
            data["is_billable"] = True
    else:
        if data.get("project_id") is not None:
            raise ProTrackValidationError("Project must remain blank for non-productive work")
        if data.get("milestone_id") is not None:
            raise ProTrackValidationError("Milestone cannot be set for non-productive work")
        if data.get("task_type_id") is not None:
            raise ProTrackValidationError("Task cannot be set for non-productive work")

        np_code_id = data.get("non_productive_code_id")
        if np_code_id is None:
            raise ProTrackValidationError("NP code is required for non-productive work")
        np_code = db.get(NonProductiveCode, np_code_id)
        if np_code is None or not np_code.is_active:
            raise ProTrackValidationError("Non-productive code not found or inactive")

        customer_id = data.get("customer_id")
        if customer_id is not None:
            customer = db.get(Customer, customer_id)
            if customer is None or not customer.is_active:
                raise ProTrackValidationError("Customer not found or inactive")

        data["project_id"] = None
        data["milestone_id"] = None
        data["task_type_id"] = None
        unset = payload.model_dump(exclude_unset=True)
        if (
            actor is not None
            and can_override_billable(db, actor)
            and "is_billable" in unset
        ):
            data["is_billable"] = bool(unset["is_billable"])
        else:
            data["is_billable"] = False

    data["work_category"] = work_category
    return data
