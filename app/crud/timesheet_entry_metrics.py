from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import (
    Customer,
    Milestone,
    NonProductiveCode,
    Project,
    TaskType,
    Timesheet,
    TimesheetEntry,
    User,
)
from app.schemas.timesheet import TimesheetEntryRead


def _entry_timestamp(entry: TimesheetEntry, field: str) -> datetime:
    value = getattr(entry, field)
    if value is not None:
        return value
    return datetime.combine(entry.entry_date, datetime.min.time(), tzinfo=timezone.utc)


def _entry_owner(db: Session, entry: TimesheetEntry) -> tuple[UUID | None, str | None]:
    timesheet = db.get(Timesheet, entry.timesheet_id)
    if timesheet is None:
        return None, None
    user = db.get(User, timesheet.user_id)
    if user is None:
        return timesheet.user_id, None
    return user.id, f"{user.first_name} {user.last_name}".strip() or None


def build_timesheet_entry_read(db: Session, entry: TimesheetEntry) -> TimesheetEntryRead:
    project_tool_number = None
    project_code = None
    customer_name = None
    task_type_name = None
    milestone_name = None
    np_code = None
    np_description = None
    owner_id, owner_name = _entry_owner(db, entry)

    if entry.project_id is not None:
        project = db.get(Project, entry.project_id)
        if project is not None:
            project_tool_number = project.tool_number
            project_code = project.code
    if entry.customer_id is not None:
        customer = db.get(Customer, entry.customer_id)
        if customer is not None:
            customer_name = customer.name
    if entry.task_type_id is not None:
        task_type = db.get(TaskType, entry.task_type_id)
        if task_type is not None:
            task_type_name = task_type.name
    if entry.milestone_id is not None:
        milestone = db.get(Milestone, entry.milestone_id)
        if milestone is not None:
            milestone_name = milestone.name
    if entry.non_productive_code_id is not None:
        np = db.get(NonProductiveCode, entry.non_productive_code_id)
        if np is not None:
            np_code = np.code
            np_description = np.description

    return TimesheetEntryRead(
        id=entry.id,
        created_at=_entry_timestamp(entry, "created_at"),
        updated_at=_entry_timestamp(entry, "updated_at"),
        timesheet_id=entry.timesheet_id,
        work_category=entry.work_category,
        project_id=entry.project_id,
        customer_id=entry.customer_id,
        task_type_id=entry.task_type_id,
        milestone_id=entry.milestone_id,
        non_productive_code_id=entry.non_productive_code_id,
        entry_date=entry.entry_date,
        hours=entry.hours,
        is_billable=entry.is_billable,
        description=entry.description,
        project_tool_number=project_tool_number,
        project_code=project_code,
        customer_name=customer_name,
        task_type_name=task_type_name,
        milestone_name=milestone_name,
        non_productive_code=np_code,
        non_productive_description=np_description,
        user_id=owner_id,
        user_name=owner_name,
    )


def build_timesheet_entry_reads(
    db: Session, entries: list[TimesheetEntry]
) -> list[TimesheetEntryRead]:
    return [build_timesheet_entry_read(db, entry) for entry in entries]
