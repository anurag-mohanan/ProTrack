from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.access_control import (
    MODULE_REPORTS,
    MODULE_RESOURCE_PLANNING,
    MODULE_SYSTEM_ADMINISTRATION,
    MODULE_TIMESHEETS,
    MODULE_WORKLOAD,
    SPECIAL_APPROVE_TIMESHEETS,
    SPECIAL_CREATE_PROJECTS,
    SPECIAL_EDIT_PROJECTS,
    SPECIAL_VIEW_REPORTS,
    SPECIAL_VIEW_RESOURCE_PLANNING,
    resolve_user_modules,
    resolve_user_special_permissions,
    user_has_special,
)
from app.core.timesheet_locking import is_timesheet_month_calendar_locked
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
PLANNING_BOARD = "Planning Board"
LEGACY_PROJECT_MANAGER = "Project Manager"

DESIGNER_ASSIGNMENT_ROLES = frozenset({SENIOR_DESIGNER, DESIGNER, JUNIOR_DESIGNER})
PROJECT_STAFF_ROLES = DESIGNER_ASSIGNMENT_ROLES | {SURFACER}
ASSIGNED_PROJECT_ROLES = PROJECT_STAFF_ROLES

FULL_ACCESS_ROLES = {ADMIN, ENGINEERING_MANAGER}
READ_ALL_PROJECT_ROLES = FULL_ACCESS_ROLES | {DESIGN_LEADER, READ_ONLY, PLANNING_BOARD}
REPORT_VIEWER_ROLES = FULL_ACCESS_ROLES | {DESIGN_LEADER, READ_ONLY, PLANNING_BOARD}
RESOURCE_PLANNING_ROLES = FULL_ACCESS_ROLES | {PLANNING_BOARD}
WORKLOAD_VIEWER_ROLES = FULL_ACCESS_ROLES | {DESIGN_LEADER, PLANNING_BOARD}
TIMESHEET_APPROVER_ROLES = FULL_ACCESS_ROLES | {DESIGN_LEADER}
PROJECT_CREATE_ROLES = FULL_ACCESS_ROLES | {DESIGN_LEADER}
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
    return has_role(db, user, *RESOURCE_PLANNING_ROLES)


def can_view_workload(db: Session, user: User) -> bool:
    return has_role(db, user, *WORKLOAD_VIEWER_ROLES)


def is_admin(db: Session, user: User) -> bool:
    return has_role(db, user, ADMIN)


ADMINISTRATION_ROLES = {ADMIN}


def can_access_administration(db: Session, user: User) -> bool:
    return has_role(db, user, ADMIN)


def can_manage_users(db: Session, user: User) -> bool:
    return is_admin(db, user)


def can_write_master_data(db: Session, user: User) -> bool:
    return is_admin(db, user)


def can_delete_records(db: Session, user: User) -> bool:
    return is_admin(db, user)


def can_create_project(db: Session, user: User) -> bool:
    return has_role(db, user, *PROJECT_CREATE_ROLES)


def can_delete_project(db: Session, user: User) -> bool:
    return is_admin(db, user)


def can_view_deleted_projects(db: Session, user: User) -> bool:
    return is_admin(db, user)


def can_archive_project(db: Session, user: User, project: Project) -> bool:
    role_name = get_role_name(db, user)
    if role_name in FULL_ACCESS_ROLES:
        return True
    if role_name == DESIGN_LEADER:
        return project.design_leader_id == user.id
    return False


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
    # Org-wide only for Admin / unscoped EM. Leaders and staff see team
    # portfolio plus personally assigned cross-utilization work.
    from app.core.team_access import user_can_read_scoped_project

    return user_can_read_scoped_project(db, user, project)


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
    if role_name in FULL_ACCESS_ROLES | {DESIGN_LEADER, LEGACY_PROJECT_MANAGER}:
        return can_read_project(db, user, project)
    if role_name in ASSIGNED_PROJECT_ROLES:
        return is_assigned_to_project(project, user.id)
    return False


def _is_team_leader_for_project(db: Session, user: User, project: Project) -> bool:
    if project.team_id is None:
        return False
    from app.models.models import Team

    team = db.get(Team, project.team_id)
    return team is not None and team.team_lead_id == user.id


def can_edit_milestone(
    db: Session,
    user: User,
    project: Project,
    milestone_row: "Milestone | None" = None,
) -> bool:
    if can_write_milestones(db, user, project):
        return True
    if milestone_row is None:
        return _is_team_leader_for_project(db, user, project)
    if _is_team_leader_for_project(db, user, project):
        if milestone_row.assigned_user_id == user.id:
            return True
        return milestone_row.assigned_user_id is not None
    return False


def can_update_milestone_progress(
    db: Session,
    user: User,
    project: Project,
    milestone_row: "Milestone",
) -> bool:
    if can_edit_milestone(db, user, project, milestone_row):
        return True
    if milestone_row.assigned_user_id == user.id:
        return can_read_project(db, user, project)
    if is_assigned_to_project(project, user.id):
        return can_read_project(db, user, project)
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
    # Editability is governed by the calendar rule (current + previous two
    # months), NOT by workflow status. Approved/submitted timesheets remain
    # editable so users can correct entries.
    if is_timesheet_month_calendar_locked(
        timesheet.week_start,
        admin_override=is_admin(db, user),
    ):
        return False
    if not can_read_timesheet(db, user, timesheet):
        return False
    if timesheet.user_id == user.id:
        return True
    if is_admin(db, user):
        return True
    role_name = normalize_role_name(get_role_name(db, user))
    if user_has_special(user, role_name, SPECIAL_APPROVE_TIMESHEETS):
        return True
    if role_name in FULL_ACCESS_ROLES:
        return True
    return False


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


def get_user_permission_keys(db: Session, user: User) -> list[str]:
    role_name = normalize_role_name(get_role_name(db, user))
    modules = set(resolve_user_modules(user, role_name))
    special = set(resolve_user_special_permissions(user, role_name))
    permissions: list[str] = []
    if MODULE_SYSTEM_ADMINISTRATION in modules:
        permissions.append("administration")
    if SPECIAL_CREATE_PROJECTS in special:
        permissions.append("create_project")
    if MODULE_REPORTS in modules or SPECIAL_VIEW_REPORTS in special:
        permissions.append("view_reports")
    if MODULE_RESOURCE_PLANNING in modules or SPECIAL_VIEW_RESOURCE_PLANNING in special:
        permissions.append("resource_planning")
    if MODULE_WORKLOAD in modules:
        permissions.append("view_workload")
    if MODULE_TIMESHEETS in modules:
        permissions.append("write_timesheet")
    if SPECIAL_APPROVE_TIMESHEETS in special:
        permissions.append("approve_timesheet")
    if SPECIAL_EDIT_PROJECTS in special:
        permissions.append("edit_project")
    return permissions
