from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import Project, Role, User

ADMIN = "Admin"
PROJECT_MANAGER = "Project Manager"
DESIGN_LEADER = "Design Leader"
DESIGNER = "Designer"
SURFACER = "Surfacer"

FULL_ACCESS_ROLES = {ADMIN, PROJECT_MANAGER}
READ_ALL_PROJECT_ROLES = FULL_ACCESS_ROLES | {DESIGN_LEADER}
TIMESHEET_ENTRY_WRITE_ROLES = FULL_ACCESS_ROLES | {
    DESIGN_LEADER,
    DESIGNER,
    SURFACER,
}


def get_role_name(db: Session, user: User) -> str:
    role = db.get(Role, user.role_id)
    return role.name if role is not None else ""


def has_role(db: Session, user: User, *roles: str) -> bool:
    return get_role_name(db, user) in roles


def is_admin(db: Session, user: User) -> bool:
    return has_role(db, user, ADMIN)


def can_manage_users(db: Session, user: User) -> bool:
    return is_admin(db, user)


def can_write_master_data(db: Session, user: User) -> bool:
    return has_role(db, user, ADMIN, PROJECT_MANAGER)


def can_create_project(db: Session, user: User) -> bool:
    return has_role(db, user, ADMIN, PROJECT_MANAGER)


def can_delete_project(db: Session, user: User) -> bool:
    return has_role(db, user, ADMIN, PROJECT_MANAGER)


def is_assigned_to_project(project: Project, user_id: UUID) -> bool:
    assigned_ids = {project.design_leader_id}
    if project.designer_id is not None:
        assigned_ids.add(project.designer_id)
    if project.surfacer_id is not None:
        assigned_ids.add(project.surfacer_id)
    return user_id in assigned_ids


def can_read_project(db: Session, user: User, project: Project) -> bool:
    role_name = get_role_name(db, user)
    if role_name in READ_ALL_PROJECT_ROLES:
        return True
    if role_name in {DESIGNER, SURFACER}:
        return is_assigned_to_project(project, user.id)
    return False


def can_update_project(db: Session, user: User, project: Project) -> bool:
    role_name = get_role_name(db, user)
    if role_name in FULL_ACCESS_ROLES:
        return True
    if role_name == DESIGN_LEADER:
        return project.design_leader_id == user.id
    return False


def can_write_milestones(db: Session, user: User, project: Project) -> bool:
    return can_update_project(db, user, project)


def can_write_timesheet_entry(db: Session, user: User) -> bool:
    return has_role(db, user, *TIMESHEET_ENTRY_WRITE_ROLES)


def can_write_timesheet(db: Session, user: User, timesheet_user_id: UUID) -> bool:
    role_name = get_role_name(db, user)
    if role_name in FULL_ACCESS_ROLES:
        return True
    return user.id == timesheet_user_id


def project_assignment_filter(user: User, role_name: str):
    if role_name == DESIGN_LEADER:
        return Project.design_leader_id == user.id
    if role_name == DESIGNER:
        return Project.designer_id == user.id
    if role_name == SURFACER:
        return Project.surfacer_id == user.id
    return None
