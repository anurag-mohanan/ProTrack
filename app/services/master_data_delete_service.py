"""Dependency checks and safe permanent deletion for master data records."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.core.system_roles import SYSTEM_ROLE_NAMES
from app.models.enums import ActivityAction, EntityType
from app.models.models import (
    Contact,
    Customer,
    NonProductiveCode,
    Project,
    ProjectTemplate,
    ProjectType,
    Role,
    Stream,
    TaskType,
    Team,
    TimesheetEntry,
    User,
)
from app.schemas.delete_check import DeleteCheckResponse
from app.services.activity_service import log_activity

DELETE_ENTITY_TYPES: dict[str, EntityType] = {
    "customer": EntityType.customer,
    "contact": EntityType.contact,
    "team": EntityType.team,
    "role": EntityType.role,
    "stream": EntityType.stream,
    "task_type": EntityType.task_type,
    "project_template": EntityType.project_template,
    "project_type": EntityType.project_type,
    "np_code": EntityType.np_code,
}


@dataclass(frozen=True)
class _CheckResult:
    record_name: str
    record_type: str
    blockers: list[str]

    @property
    def related_records(self) -> list[str]:
        return list(self.blockers)

    def to_response(self) -> DeleteCheckResponse:
        return DeleteCheckResponse(
            can_delete=not self.blockers,
            blockers=self.blockers,
            record_name=self.record_name,
            record_type=self.record_type,
            related_records=self.related_records,
        )


def _count(query) -> int:
    return int(query or 0)


def check_customer_delete(db: Session, customer_id: UUID) -> DeleteCheckResponse:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise ProTrackValidationError("Customer not found")
    blockers: list[str] = []
    projects = _count(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.customer_id == customer_id, Project.is_deleted.is_(False))
        )
    )
    if projects:
        blockers.append(f"{projects} active project{'s' if projects != 1 else ''}")
    contacts = _count(
        db.scalar(select(func.count()).select_from(Contact).where(Contact.customer_id == customer_id))
    )
    if contacts:
        blockers.append(f"{contacts} contact{'s' if contacts != 1 else ''}")
    templates = _count(
        db.scalar(
            select(func.count())
            .select_from(ProjectTemplate)
            .where(ProjectTemplate.customer_id == customer_id)
        )
    )
    if templates:
        blockers.append(f"{templates} project template{'s' if templates != 1 else ''}")
    entries = _count(
        db.scalar(
            select(func.count())
            .select_from(TimesheetEntry)
            .where(TimesheetEntry.customer_id == customer_id)
        )
    )
    if entries:
        blockers.append(f"{entries} timesheet entr{'y' if entries == 1 else 'ies'}")
    return _CheckResult(customer.name, "Customer", blockers).to_response()


def check_contact_delete(db: Session, contact_id: UUID) -> DeleteCheckResponse:
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise ProTrackValidationError("Contact not found")
    blockers: list[str] = []
    projects = _count(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.customer_contact_id == contact_id, Project.is_deleted.is_(False))
        )
    )
    if projects:
        blockers.append(f"{projects} project{'s' if projects != 1 else ''}")
    name = f"{contact.first_name} {contact.last_name}".strip()
    return _CheckResult(name, "Contact", blockers).to_response()


def check_team_delete(db: Session, team_id: UUID) -> DeleteCheckResponse:
    team = db.get(Team, team_id)
    if team is None:
        raise ProTrackValidationError("Team not found")
    blockers: list[str] = []
    users = _count(
        db.scalar(select(func.count()).select_from(User).where(User.team_id == team_id, User.is_deleted.is_(False)))
    )
    if users:
        blockers.append(f"{users} assigned user{'s' if users != 1 else ''}")
    projects = _count(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.team_id == team_id, Project.is_deleted.is_(False))
        )
    )
    if projects:
        blockers.append(f"{projects} project{'s' if projects != 1 else ''}")
    default_customers = _count(
        db.scalar(
            select(func.count())
            .select_from(Customer)
            .where(Customer.default_team_id == team_id)
        )
    )
    if default_customers:
        blockers.append(f"{default_customers} customer default team reference{'s' if default_customers != 1 else ''}")
    default_templates = _count(
        db.scalar(
            select(func.count())
            .select_from(ProjectTemplate)
            .where(ProjectTemplate.default_team_id == team_id)
        )
    )
    if default_templates:
        blockers.append(f"{default_templates} template default team reference{'s' if default_templates != 1 else ''}")
    return _CheckResult(team.name, "Team", blockers).to_response()


def check_role_delete(db: Session, role_id: UUID) -> DeleteCheckResponse:
    role = db.get(Role, role_id)
    if role is None:
        raise ProTrackValidationError("Role not found")
    blockers: list[str] = []
    if role.name in SYSTEM_ROLE_NAMES:
        blockers.append("system role cannot be deleted")
    users = _count(
        db.scalar(select(func.count()).select_from(User).where(User.role_id == role_id, User.is_deleted.is_(False)))
    )
    if users:
        blockers.append(f"{users} assigned user{'s' if users != 1 else ''}")
    return _CheckResult(role.name, "Role", blockers).to_response()


def check_stream_delete(db: Session, stream_id: UUID) -> DeleteCheckResponse:
    stream = db.get(Stream, stream_id)
    if stream is None:
        raise ProTrackValidationError("Stream not found")
    blockers: list[str] = []
    task_types = _count(
        db.scalar(select(func.count()).select_from(TaskType).where(TaskType.stream_id == stream_id))
    )
    if task_types:
        blockers.append(f"{task_types} task type{'s' if task_types != 1 else ''}")
    projects = _count(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.stream_id == stream_id, Project.is_deleted.is_(False))
        )
    )
    if projects:
        blockers.append(f"{projects} project{'s' if projects != 1 else ''}")
    return _CheckResult(stream.name, "Stream", blockers).to_response()


def check_task_type_delete(db: Session, task_type_id: UUID) -> DeleteCheckResponse:
    task_type = db.get(TaskType, task_type_id)
    if task_type is None:
        raise ProTrackValidationError("Task type not found")
    blockers: list[str] = []
    entries = _count(
        db.scalar(
            select(func.count())
            .select_from(TimesheetEntry)
            .where(TimesheetEntry.task_type_id == task_type_id)
        )
    )
    if entries:
        blockers.append(f"{entries} timesheet entr{'y' if entries == 1 else 'ies'}")
    return _CheckResult(task_type.name, "Task Type", blockers).to_response()


def check_project_template_delete(db: Session, template_id: UUID) -> DeleteCheckResponse:
    template = db.get(ProjectTemplate, template_id)
    if template is None:
        raise ProTrackValidationError("Project template not found")
    blockers: list[str] = []
    projects = _count(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.project_template_id == template_id, Project.is_deleted.is_(False))
        )
    )
    if projects:
        blockers.append(f"{projects} project{'s' if projects != 1 else ''}")
    default_customers = _count(
        db.scalar(
            select(func.count())
            .select_from(Customer)
            .where(Customer.default_project_template_id == template_id)
        )
    )
    if default_customers:
        blockers.append(
            f"{default_customers} customer default template reference{'s' if default_customers != 1 else ''}"
        )
    return _CheckResult(template.name, "Project Template", blockers).to_response()


def check_project_type_delete(db: Session, project_type_id: UUID) -> DeleteCheckResponse:
    project_type = db.get(ProjectType, project_type_id)
    if project_type is None:
        raise ProTrackValidationError("Project type not found")
    blockers: list[str] = []
    projects = _count(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.project_type_id == project_type_id, Project.is_deleted.is_(False))
        )
    )
    if projects:
        blockers.append(f"{projects} project{'s' if projects != 1 else ''}")
    templates = _count(
        db.scalar(
            select(func.count())
            .select_from(ProjectTemplate)
            .where(ProjectTemplate.project_type_id == project_type_id)
        )
    )
    if templates:
        blockers.append(f"{templates} template{'s' if templates != 1 else ''}")
    default_customers = _count(
        db.scalar(
            select(func.count())
            .select_from(Customer)
            .where(Customer.default_project_type_id == project_type_id)
        )
    )
    if default_customers:
        blockers.append(
            f"{default_customers} customer default type reference{'s' if default_customers != 1 else ''}"
        )
    return _CheckResult(project_type.name, "Project Type", blockers).to_response()


def check_np_code_delete(db: Session, code_id: UUID) -> DeleteCheckResponse:
    code = db.get(NonProductiveCode, code_id)
    if code is None:
        raise ProTrackValidationError("NP code not found")
    blockers: list[str] = []
    entries = _count(
        db.scalar(
            select(func.count())
            .select_from(TimesheetEntry)
            .where(TimesheetEntry.non_productive_code_id == code_id)
        )
    )
    if entries:
        blockers.append(f"{entries} timesheet entr{'y' if entries == 1 else 'ies'}")
    return _CheckResult(code.name, "Non Productive Code", blockers).to_response()


DELETE_CHECKERS = {
    "customer": check_customer_delete,
    "contact": check_contact_delete,
    "team": check_team_delete,
    "role": check_role_delete,
    "stream": check_stream_delete,
    "task_type": check_task_type_delete,
    "project_template": check_project_template_delete,
    "project_type": check_project_type_delete,
    "np_code": check_np_code_delete,
}


def run_delete_check(db: Session, entity_key: str, record_id: UUID) -> DeleteCheckResponse:
    checker = DELETE_CHECKERS.get(entity_key)
    if checker is None:
        raise ProTrackValidationError(f"No delete check configured for {entity_key}")
    return checker(db, record_id)


def ensure_can_delete(db: Session, entity_key: str, record_id: UUID) -> DeleteCheckResponse:
    result = run_delete_check(db, entity_key, record_id)
    if not result.can_delete:
        detail = ", ".join(result.blockers) or "Record is currently in use"
        raise ProTrackValidationError(f"This record is currently in use: {detail}")
    return result


def log_record_deleted(
    db: Session,
    *,
    user: User,
    entity_key: str,
    record_id: UUID,
    record_name: str,
) -> None:
    entity_type = DELETE_ENTITY_TYPES.get(entity_key)
    if entity_type is None:
        return
    log_activity(
        db,
        user=user,
        entity_type=entity_type,
        entity_id=record_id,
        action=ActivityAction.record_deleted,
        new_value=record_name,
    )
