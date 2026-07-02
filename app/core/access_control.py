"""Role defaults and per-user module / special permission resolution."""

from __future__ import annotations

import json

from app.models.models import User

ADMIN = "Admin"
ENGINEERING_MANAGER = "Engineering Manager"
DESIGN_LEADER = "Design Leader"
SENIOR_DESIGNER = "Senior Designer"
DESIGNER = "Designer"
JUNIOR_DESIGNER = "Junior Designer"
SURFACER = "Surfacer"
READ_ONLY = "Read Only"
LEGACY_PROJECT_MANAGER = "Project Manager"


def normalize_role_name(role_name: str) -> str:
    if role_name == LEGACY_PROJECT_MANAGER:
        return ENGINEERING_MANAGER
    return role_name
MODULE_DASHBOARD = "dashboard"
MODULE_PROJECTS = "projects"
MODULE_ARCHIVED_PROJECTS = "archived_projects"
MODULE_TIMESHEETS = "timesheets"
MODULE_WORKLOAD = "workload"
MODULE_RESOURCE_PLANNING = "resource_planning"
MODULE_REPORTS = "reports"
MODULE_SYSTEM_ADMINISTRATION = "system_administration"

ALL_MODULES: tuple[str, ...] = (
    MODULE_DASHBOARD,
    MODULE_PROJECTS,
    MODULE_ARCHIVED_PROJECTS,
    MODULE_TIMESHEETS,
    MODULE_WORKLOAD,
    MODULE_RESOURCE_PLANNING,
    MODULE_REPORTS,
    MODULE_SYSTEM_ADMINISTRATION,
)

SPECIAL_CREATE_PROJECTS = "create_projects"
SPECIAL_EDIT_PROJECTS = "edit_projects"
SPECIAL_ARCHIVE_PROJECTS = "archive_projects"
SPECIAL_DELETE_PROJECTS = "delete_projects"
SPECIAL_APPROVE_PROJECTS = "approve_projects"
SPECIAL_APPROVE_TIMESHEETS = "approve_timesheets"
SPECIAL_IMPORT_TIMESHEETS = "import_timesheets"
SPECIAL_EXPORT_REPORTS = "export_reports"
SPECIAL_MANAGE_CUSTOMERS = "manage_customers"
SPECIAL_MANAGE_CONTACTS = "manage_contacts"
SPECIAL_MANAGE_TEAMS = "manage_teams"
SPECIAL_MANAGE_USERS = "manage_users"
SPECIAL_MANAGE_COMPANY_SETTINGS = "manage_company_settings"
SPECIAL_VIEW_REPORTS = "view_reports"
SPECIAL_VIEW_RESOURCE_PLANNING = "view_resource_planning"

ALL_SPECIAL_PERMISSIONS: tuple[str, ...] = (
    SPECIAL_CREATE_PROJECTS,
    SPECIAL_EDIT_PROJECTS,
    SPECIAL_ARCHIVE_PROJECTS,
    SPECIAL_DELETE_PROJECTS,
    SPECIAL_APPROVE_PROJECTS,
    SPECIAL_APPROVE_TIMESHEETS,
    SPECIAL_IMPORT_TIMESHEETS,
    SPECIAL_EXPORT_REPORTS,
    SPECIAL_MANAGE_CUSTOMERS,
    SPECIAL_MANAGE_CONTACTS,
    SPECIAL_MANAGE_TEAMS,
    SPECIAL_MANAGE_USERS,
    SPECIAL_MANAGE_COMPANY_SETTINGS,
    SPECIAL_VIEW_REPORTS,
    SPECIAL_VIEW_RESOURCE_PLANNING,
)

DEFAULT_MODULES_BY_ROLE: dict[str, frozenset[str]] = {
    ADMIN: frozenset(ALL_MODULES),
    ENGINEERING_MANAGER: frozenset(
        {
            MODULE_DASHBOARD,
            MODULE_PROJECTS,
            MODULE_ARCHIVED_PROJECTS,
            MODULE_TIMESHEETS,
            MODULE_WORKLOAD,
            MODULE_RESOURCE_PLANNING,
            MODULE_REPORTS,
        }
    ),
    DESIGN_LEADER: frozenset(
        {
            MODULE_DASHBOARD,
            MODULE_PROJECTS,
            MODULE_ARCHIVED_PROJECTS,
            MODULE_TIMESHEETS,
            MODULE_WORKLOAD,
        }
    ),
    DESIGNER: frozenset({MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS}),
    SENIOR_DESIGNER: frozenset({MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS}),
    JUNIOR_DESIGNER: frozenset({MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS}),
    SURFACER: frozenset({MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS}),
    READ_ONLY: frozenset({MODULE_DASHBOARD, MODULE_PROJECTS}),
}

DEFAULT_SPECIAL_BY_ROLE: dict[str, frozenset[str]] = {
    ADMIN: frozenset(ALL_SPECIAL_PERMISSIONS),
    ENGINEERING_MANAGER: frozenset(
        {
            SPECIAL_CREATE_PROJECTS,
            SPECIAL_EDIT_PROJECTS,
            SPECIAL_ARCHIVE_PROJECTS,
            SPECIAL_APPROVE_PROJECTS,
            SPECIAL_APPROVE_TIMESHEETS,
            SPECIAL_EXPORT_REPORTS,
            SPECIAL_VIEW_REPORTS,
            SPECIAL_VIEW_RESOURCE_PLANNING,
        }
    ),
    DESIGN_LEADER: frozenset(
        {
            SPECIAL_CREATE_PROJECTS,
            SPECIAL_EDIT_PROJECTS,
            SPECIAL_ARCHIVE_PROJECTS,
            SPECIAL_APPROVE_TIMESHEETS,
            SPECIAL_VIEW_REPORTS,
        }
    ),
    DESIGNER: frozenset({SPECIAL_EDIT_PROJECTS}),
    SENIOR_DESIGNER: frozenset({SPECIAL_CREATE_PROJECTS, SPECIAL_EDIT_PROJECTS}),
    JUNIOR_DESIGNER: frozenset(),
    SURFACER: frozenset(),
    READ_ONLY: frozenset(),
}

PATH_MODULE_MAP: dict[str, str] = {
    "/dashboard": MODULE_DASHBOARD,
    "/projects": MODULE_PROJECTS,
    "/projects/archived": MODULE_ARCHIVED_PROJECTS,
    "/timesheets": MODULE_TIMESHEETS,
    "/timesheets/month": MODULE_TIMESHEETS,
    "/workload": MODULE_WORKLOAD,
    "/resource-planning": MODULE_RESOURCE_PLANNING,
    "/reports": MODULE_REPORTS,
}


def _parse_json_list(raw: str | None) -> list[str] | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    return [str(item) for item in parsed if isinstance(item, str)]


def parse_access_list(raw: str | None) -> list[str] | None:
    return _parse_json_list(raw)


def serialize_module_access(values: list[str] | None) -> str | None:
    if values is None:
        return None
    cleaned = [value for value in values if value in ALL_MODULES]
    return json.dumps(sorted(set(cleaned)))


def serialize_special_permissions(values: list[str] | None) -> str | None:
    if values is None:
        return None
    cleaned = [value for value in values if value in ALL_SPECIAL_PERMISSIONS]
    return json.dumps(sorted(set(cleaned)))


def default_modules_for_role(role_name: str) -> list[str]:
    normalized = normalize_role_name(role_name)
    return sorted(DEFAULT_MODULES_BY_ROLE.get(normalized, DEFAULT_MODULES_BY_ROLE[DESIGNER]))


def default_special_permissions_for_role(role_name: str) -> list[str]:
    normalized = normalize_role_name(role_name)
    return sorted(DEFAULT_SPECIAL_BY_ROLE.get(normalized, frozenset()))


def resolve_user_modules(user: User, role_name: str) -> list[str]:
    stored = _parse_json_list(user.module_access)
    if stored is not None:
        return sorted({module for module in stored if module in ALL_MODULES})
    return default_modules_for_role(role_name)


def resolve_user_special_permissions(user: User, role_name: str) -> list[str]:
    stored = _parse_json_list(user.special_permissions)
    if stored is not None:
        return sorted({perm for perm in stored if perm in ALL_SPECIAL_PERMISSIONS})
    return default_special_permissions_for_role(role_name)


def user_has_module(user: User, role_name: str, module: str) -> bool:
    return module in resolve_user_modules(user, role_name)


def user_has_special(user: User, role_name: str, permission: str) -> bool:
    return permission in resolve_user_special_permissions(user, role_name)


def module_for_path(pathname: str) -> str | None:
    if pathname.startswith("/admin"):
        return MODULE_SYSTEM_ADMINISTRATION
    for prefix, module in sorted(PATH_MODULE_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if pathname == prefix or pathname.startswith(f"{prefix}/"):
            return module
    return None
