from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.enums import TimesheetStatus
from app.models.models import Project, Role, Timesheet, TimesheetEntry, User

ADMIN = "Admin"
ENGINEERING_MANAGER = "Engineering Manager"
DESIGN_LEADER = "Design Leader"
SENIOR_DESIGNER = "Senior Designer"
DESIGNER = "Designer"
JUNIOR_DESIGNER = "Junior Designer"
SURFACER = "Surfacer"
READ_ONLY = "Read Only"
LEGACY_PROJECT_MANAGER = "Project Manager"

DESIGNER_ASSIGNMENT_ROLES = frozenset({SENIOR_DESIGNER, DESIGNER, JUNIOR_DESIGNER})
PROJECT_STAFF_ROLES = DESIGNER_ASSIGNMENT_ROLES | {SURFACER}
ASSIGNED_PROJECT_ROLES = PROJECT_STAFF_ROLES

FULL_ACCESS_ROLES = {ADMIN, ENGINEERING_MANAGER}
READ_ALL_PROJECT_ROLES = FULL_ACCESS_ROLES | {DESIGN_LEADER, READ_ONLY}
REPORT_VIEWER_ROLES = FULL_ACCESS_ROLES | {DESIGN_LEADER, READ_ONLY}
RESOURCE_PLANNING_ROLES = REPORT_VIEWER_ROLES
TIMESHEET_APPROVER_ROLES = FULL_ACCESS_ROLES | {DESIGN_LEADER}
TIMESHEET_ENTRY_WRITE_ROLES = FULL_ACCESS_ROLES | {
    DESIGN_LEADER,
    SENIOR_DESIGNER,
    DESIGNER,
    JUNIOR_DESIGNER,
    SURFACER,
}
PROJECT_EDIT_ROLES = FULL_ACCESS_ROLES | {DESIGN_LEADER, SENIOR_DESIGNER}
MILESTONE_WRITE_ROLES = FULL_ACCESS_ROLES | {
    DESIGN_LEADER,
    SENIOR_DESIGNER,
    DESIGNER,
    JUNIOR_DESIGNER,
    SURFACER,
}


def get_role_name(db: Session, user: User) -> str:
    role = db.get(Role, user.role_id)
    return role.name if role is not None else ""


def normalize_role_name(role_name: str) -> str:
    if role_name == LEGACY_PROJECT_MANAGER:
        return ENGINEERING_MANAGER
    return role_name


def has_role(db: Session, user: User, *roles: str) -> bool:
    role_name = normalize_role_name(get_role_name(db, user))
    normalized_roles = {normalize_role_name(role) for role in roles}
    return role_name in normalized_roles


def can_view_reports(db: Session, user: User) -> bool:
    return has_role(db, user, *REPORT_VIEWER_ROLES)


def can_view_resource_planning(db: Session, user: User) -> bool:
    return can_view_reports(db, user)


def is_admin(db: Session, user: User) -> bool:
    return has_role(db, user, ADMIN)


ADMINISTRATION_ROLES = FULL_ACCESS_ROLES


def can_access_administration(db: Session, user: User) -> bool:
    return has_role(db, user, *ADMINISTRATION_ROLES)


def can_manage_users(db: Session, user: User) -> bool:
    return can_access_administration(db, user)


def can_delete_records(db: Session, user: User) -> bool:
    return is_admin(db, user)


def can_write_master_data(db: Session, user: User) -> bool:
    return has_role(db, user, ADMIN, ENGINEERING_MANAGER)


def can_create_project(db: Session, user: User) -> bool:
    return has_role(db, user, ADMIN, ENGINEERING_MANAGER)


def can_delete_project(db: Session, user: User) -> bool:
    return is_admin(db, user)


def can_view_deleted_projects(db: Session, user: User) -> bool:
    return is_admin(db, user)


def can_archive_project(db: Session, user: User, project: Project) -> bool:
    return can_update_project(db, user, project)


def can_soft_delete_project(db: Session, user: User) -> bool:
    return is_admin(db, user)


def can_update_project_status(db: Session, user: User) -> bool:
    return has_role(db, user, ADMIN, ENGINEERING_MANAGER)


def is_assigned_to_project(project: Project, user_id: UUID) -> bool:
    assigned_ids = {project.design_leader_id}
    if project.designer_id is not None:
        assigned_ids.add(project.designer_id)
    if project.surfacer_id is not None:
        assigned_ids.add(project.surfacer_id)
    return user_id in assigned_ids


def can_read_project(db: Session, user: User, project: Project) -> bool:
    if project.is_deleted and not is_admin(db, user):
        return False
    role_name = get_role_name(db, user)
    if role_name in READ_ALL_PROJECT_ROLES:
        return True
    if role_name in ASSIGNED_PROJECT_ROLES:
        return is_assigned_to_project(project, user.id)
    return False


def can_update_project(db: Session, user: User, project: Project) -> bool:
    role_name = get_role_name(db, user)
    if role_name in FULL_ACCESS_ROLES:
        return True
    if role_name == DESIGN_LEADER:
        return project.design_leader_id == user.id
    if role_name == SENIOR_DESIGNER:
        return user.id in {project.designer_id, project.surfacer_id}
    return False


def can_write_milestones(db: Session, user: User, project: Project) -> bool:
    role_name = get_role_name(db, user)
    if role_name in FULL_ACCESS_ROLES | {DESIGN_LEADER}:
        return can_read_project(db, user, project)
    if role_name in ASSIGNED_PROJECT_ROLES:
        return is_assigned_to_project(project, user.id)
    return False


def can_complete_milestone(db: Session, user: User, project: Project) -> bool:
    return can_write_milestones(db, user, project)


def can_write_timesheet_entry(db: Session, user: User) -> bool:
    return has_role(db, user, *TIMESHEET_ENTRY_WRITE_ROLES)


def _timesheet_project_ids(db: Session, timesheet: Timesheet) -> set[UUID]:
    rows = db.scalars(
        select(TimesheetEntry.project_id).where(
            TimesheetEntry.timesheet_id == timesheet.id
        )
    ).all()
    return set(rows)


def _design_leader_can_approve(db: Session, user: User, timesheet: Timesheet) -> bool:
    project_ids = _timesheet_project_ids(db, timesheet)
    if not project_ids:
        return False
    projects = db.scalars(
        select(Project).where(
            Project.id.in_(project_ids),
            Project.design_leader_id == user.id,
        )
    ).all()
    for project in projects:
        if timesheet.user_id in {project.designer_id, project.surfacer_id}:
            return True
    return False


def can_read_timesheet(db: Session, user: User, timesheet: Timesheet) -> bool:
    role_name = normalize_role_name(get_role_name(db, user))
    if role_name in FULL_ACCESS_ROLES | {READ_ONLY}:
        return True
    if role_name == DESIGN_LEADER and _design_leader_can_approve(db, user, timesheet):
        return True
    return timesheet.user_id == user.id


def can_edit_timesheet(db: Session, user: User, timesheet: Timesheet) -> bool:
    if timesheet.status != TimesheetStatus.draft:
        return False
    if not can_read_timesheet(db, user, timesheet):
        return False
    role_name = get_role_name(db, user)
    if role_name in FULL_ACCESS_ROLES:
        return True
    return timesheet.user_id == user.id


def can_delete_timesheet(db: Session, user: User, timesheet: Timesheet) -> bool:
    return can_edit_timesheet(db, user, timesheet)


def can_submit_timesheet(db: Session, user: User, timesheet: Timesheet) -> bool:
    if timesheet.status != TimesheetStatus.draft:
        return False
    role_name = get_role_name(db, user)
    if role_name in FULL_ACCESS_ROLES:
        return True
    return timesheet.user_id == user.id


def can_approve_timesheet(db: Session, user: User, timesheet: Timesheet) -> bool:
    if timesheet.status != TimesheetStatus.submitted:
        return False
    role_name = get_role_name(db, user)
    if role_name in FULL_ACCESS_ROLES:
        return True
    if role_name == DESIGN_LEADER:
        return _design_leader_can_approve(db, user, timesheet)
    return False


def can_reject_timesheet(db: Session, user: User, timesheet: Timesheet) -> bool:
    return can_approve_timesheet(db, user, timesheet)


def can_return_timesheet_to_draft(db: Session, user: User, timesheet: Timesheet) -> bool:
    if timesheet.status not in {TimesheetStatus.submitted, TimesheetStatus.rejected}:
        return False
    role_name = get_role_name(db, user)
    if role_name in FULL_ACCESS_ROLES:
        return True
    if role_name == DESIGN_LEADER:
        return _design_leader_can_approve(db, user, timesheet)
    return timesheet.user_id == user.id and timesheet.status == TimesheetStatus.rejected


def can_edit_timesheet_entry(db: Session, user: User, timesheet: Timesheet) -> bool:
    return can_edit_timesheet(db, user, timesheet)


def project_assignment_filter(user: User, role_name: str):
    if role_name == DESIGN_LEADER:
        return Project.design_leader_id == user.id
    if role_name in PROJECT_STAFF_ROLES:
        return or_(
            Project.designer_id == user.id,
            Project.surfacer_id == user.id,
        )
    return None
