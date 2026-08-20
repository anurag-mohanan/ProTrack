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
PLANNING_BOARD = "Planning Board"
LEGACY_PROJECT_MANAGER = "Project Manager"
HR = "HR"
OFFICE_ADMINISTRATOR = "Office Administrator"

# Executive / leadership tier (phase 52). Seeded by the role hierarchy
# (phase 49) but previously unwired into access control, so an MD / Director
# login fell back to Designer-level access. These roles form a company-wide
# oversight tier: full visibility + top-level approvals, WITHOUT the destructive
# / system-administration powers reserved for Admin (IT).
MANAGING_DIRECTOR = "Managing Director"
DIRECTOR_OF_ENGINEERING = "Director of Engineering"
DIRECTOR_OF_SALES = "Director of Sales"
DIRECTOR_OF_HR = "Director of HR"
DIRECTOR_OF_ACCOUNTS = "Director of Accounts"
DIRECTOR_OF_IT = "Director of IT"
DIRECTOR_GENERIC = "Director"

DIRECTOR_ROLES: frozenset[str] = frozenset(
    {
        DIRECTOR_OF_ENGINEERING,
        DIRECTOR_OF_SALES,
        DIRECTOR_OF_HR,
        DIRECTOR_OF_ACCOUNTS,
        DIRECTOR_OF_IT,
        DIRECTOR_GENERIC,
    }
)
# The full executive tier (MD + all Directors) shares one access profile.
EXECUTIVE_ROLES: frozenset[str] = frozenset({MANAGING_DIRECTOR}) | DIRECTOR_ROLES

# Standardized Engineering roles (phase 49) map to their existing
# permission-bearing equivalents so access control, timesheet/salary/fixed-
# resource eligibility, and module defaults all behave correctly without
# touching every call site. Display still uses the real (aliased) name.
ROLE_ALIASES: dict[str, str] = {
    LEGACY_PROJECT_MANAGER: ENGINEERING_MANAGER,
    "Design Engineer": DESIGNER,
    "Senior Design Engineer": SENIOR_DESIGNER,
    "Junior Design Engineer": JUNIOR_DESIGNER,
    "Trainee Design Engineer": JUNIOR_DESIGNER,
    "Team Leader": SENIOR_DESIGNER,
}


def normalize_role_name(role_name: str) -> str:
    return ROLE_ALIASES.get(role_name, role_name)


MODULE_DASHBOARD = "dashboard"
MODULE_PROJECTS = "projects"
MODULE_ARCHIVED_PROJECTS = "archived_projects"
MODULE_TIMESHEETS = "timesheets"
MODULE_WORKLOAD = "workload"
MODULE_RESOURCE_PLANNING = "resource_planning"
MODULE_REPORTS = "reports"
MODULE_SYSTEM_ADMINISTRATION = "system_administration"
MODULE_FINANCIAL_PLANNING = "financial_planning"
MODULE_HUMAN_RESOURCES = "human_resources"
MODULE_REPORTS_ANALYTICS = "reports_analytics"
MODULE_PLANNING_BOARD = "planning_board"
MODULE_CALENDAR = "calendar"
MODULE_PERFORMANCE = "performance"
MODULE_TICKETS = "tickets"
MODULE_IT_OPERATIONS = "it_operations"

ALL_MODULES: tuple[str, ...] = (
    MODULE_DASHBOARD,
    MODULE_PROJECTS,
    MODULE_ARCHIVED_PROJECTS,
    MODULE_TIMESHEETS,
    MODULE_WORKLOAD,
    MODULE_RESOURCE_PLANNING,
    MODULE_REPORTS,
    MODULE_SYSTEM_ADMINISTRATION,
    MODULE_FINANCIAL_PLANNING,
    MODULE_HUMAN_RESOURCES,
    MODULE_REPORTS_ANALYTICS,
    MODULE_PLANNING_BOARD,
    MODULE_CALENDAR,
    MODULE_PERFORMANCE,
    MODULE_TICKETS,
    MODULE_IT_OPERATIONS,
)

# EBMP top-level nav groups (ops modules remain granular under Engineering Operations).
EBMP_NAV_MODULES: tuple[str, ...] = (
    MODULE_FINANCIAL_PLANNING,
    MODULE_HUMAN_RESOURCES,
    MODULE_REPORTS_ANALYTICS,
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
SPECIAL_MANAGE_PROJECT_SETTINGS = "manage_project_settings"
SPECIAL_VIEW_REPORTS = "view_reports"
SPECIAL_VIEW_RESOURCE_PLANNING = "view_resource_planning"
# --- Field-level security & governance specials (security foundation) ---
SPECIAL_VIEW_SALARY = "view_salary"
SPECIAL_VIEW_FINANCIAL_COST = "view_financial_cost"
SPECIAL_VIEW_BUDGET = "view_budget"
SPECIAL_VIEW_PROFITABILITY = "view_profitability"
SPECIAL_FINANCIAL_APPROVAL = "financial_approval"
SPECIAL_BUDGET_APPROVAL = "budget_approval"
SPECIAL_MANAGE_PERMISSIONS = "manage_permissions"
# --- IT Operations specials ---
SPECIAL_VIEW_IT_OPERATIONS = "view_it_operations"
SPECIAL_MANAGE_IT_ASSETS = "manage_it_assets"
SPECIAL_ASSIGN_IT_ASSETS = "assign_it_assets"
SPECIAL_MANAGE_IT_NETWORKS = "manage_it_networks"
SPECIAL_ALLOCATE_IT_IPS = "allocate_it_ips"
SPECIAL_MANAGE_IT_ACCOUNTS = "manage_it_accounts"
SPECIAL_GENERATE_IT_CREDENTIALS = "generate_it_credentials"
SPECIAL_MANAGE_IT_REQUESTS = "manage_it_requests"
SPECIAL_VIEW_IT_REPORTS = "view_it_reports"
SPECIAL_MANAGE_IT_SETTINGS = "manage_it_settings"

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
    SPECIAL_MANAGE_PROJECT_SETTINGS,
    SPECIAL_VIEW_REPORTS,
    SPECIAL_VIEW_RESOURCE_PLANNING,
    SPECIAL_VIEW_SALARY,
    SPECIAL_VIEW_FINANCIAL_COST,
    SPECIAL_VIEW_BUDGET,
    SPECIAL_VIEW_PROFITABILITY,
    SPECIAL_FINANCIAL_APPROVAL,
    SPECIAL_BUDGET_APPROVAL,
    SPECIAL_MANAGE_PERMISSIONS,
    SPECIAL_VIEW_IT_OPERATIONS,
    SPECIAL_MANAGE_IT_ASSETS,
    SPECIAL_ASSIGN_IT_ASSETS,
    SPECIAL_MANAGE_IT_NETWORKS,
    SPECIAL_ALLOCATE_IT_IPS,
    SPECIAL_MANAGE_IT_ACCOUNTS,
    SPECIAL_GENERATE_IT_CREDENTIALS,
    SPECIAL_MANAGE_IT_REQUESTS,
    SPECIAL_VIEW_IT_REPORTS,
    SPECIAL_MANAGE_IT_SETTINGS,
)

# Executive tier: every business module EXCEPT System Administration (which
# stays an Admin/IT responsibility). Gives the MD / Directors a company-wide
# cockpit: finance, HR, analytics, performance, planning, projects, timesheets.
EXECUTIVE_MODULES: frozenset[str] = frozenset(ALL_MODULES) - {MODULE_SYSTEM_ADMINISTRATION}

# Executive tier specials: top-level approvals + full financial-field visibility.
# Deliberately excludes create/edit/archive/delete project ops and the
# manage_users / company_settings / permissions system powers (Admin-only), so
# the MD is an oversight-and-approval authority, not an operational editor.
EXECUTIVE_SPECIALS: frozenset[str] = frozenset(
    {
        SPECIAL_APPROVE_PROJECTS,
        SPECIAL_VIEW_REPORTS,
        SPECIAL_EXPORT_REPORTS,
        SPECIAL_VIEW_RESOURCE_PLANNING,
        SPECIAL_VIEW_SALARY,
        SPECIAL_VIEW_FINANCIAL_COST,
        SPECIAL_VIEW_BUDGET,
        SPECIAL_VIEW_PROFITABILITY,
        SPECIAL_FINANCIAL_APPROVAL,
        SPECIAL_BUDGET_APPROVAL,
    }
)

EXECUTIVE_IT_VIEW_SPECIALS: frozenset[str] = frozenset({
    SPECIAL_VIEW_IT_OPERATIONS,
    SPECIAL_VIEW_IT_REPORTS,
})

DEFAULT_MODULES_BY_ROLE: dict[str, frozenset[str]] = {
    ADMIN: frozenset(ALL_MODULES),
    MANAGING_DIRECTOR: EXECUTIVE_MODULES,
    DIRECTOR_OF_ENGINEERING: EXECUTIVE_MODULES,
    DIRECTOR_OF_SALES: EXECUTIVE_MODULES,
    DIRECTOR_OF_HR: EXECUTIVE_MODULES,
    DIRECTOR_OF_ACCOUNTS: EXECUTIVE_MODULES,
    DIRECTOR_OF_IT: EXECUTIVE_MODULES,
    DIRECTOR_GENERIC: EXECUTIVE_MODULES,
    ENGINEERING_MANAGER: frozenset(
        {
            MODULE_DASHBOARD,
            MODULE_PROJECTS,
            MODULE_ARCHIVED_PROJECTS,
            MODULE_TIMESHEETS,
            MODULE_WORKLOAD,
            MODULE_RESOURCE_PLANNING,
            MODULE_REPORTS,
            MODULE_FINANCIAL_PLANNING,
            MODULE_REPORTS_ANALYTICS,
            MODULE_CALENDAR,
            MODULE_PERFORMANCE,
        }
    ),
    DESIGN_LEADER: frozenset(
        {
            MODULE_DASHBOARD,
            MODULE_PROJECTS,
            MODULE_ARCHIVED_PROJECTS,
            MODULE_TIMESHEETS,
            MODULE_WORKLOAD,
            MODULE_REPORTS_ANALYTICS,
            MODULE_CALENDAR,
            MODULE_PERFORMANCE,
        }
    ),
    DESIGNER: frozenset({MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS, MODULE_PERFORMANCE}),
    SENIOR_DESIGNER: frozenset(
        {MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS, MODULE_PERFORMANCE}
    ),
    JUNIOR_DESIGNER: frozenset(
        {MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS, MODULE_PERFORMANCE}
    ),
    SURFACER: frozenset({MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS, MODULE_PERFORMANCE}),
    READ_ONLY: frozenset(
        {MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_REPORTS_ANALYTICS, MODULE_PERFORMANCE}
    ),
    PLANNING_BOARD: frozenset({MODULE_PLANNING_BOARD}),
    HR: frozenset(
        {
            MODULE_DASHBOARD,
            MODULE_HUMAN_RESOURCES,
            MODULE_TIMESHEETS,
            MODULE_REPORTS_ANALYTICS,
            MODULE_PERFORMANCE,
        }
    ),
    OFFICE_ADMINISTRATOR: frozenset(
        {
            MODULE_DASHBOARD,
            MODULE_HUMAN_RESOURCES,
            MODULE_TIMESHEETS,
            MODULE_REPORTS_ANALYTICS,
            MODULE_PERFORMANCE,
        }
    ),
}

DEFAULT_SPECIAL_BY_ROLE: dict[str, frozenset[str]] = {
    ADMIN: frozenset(ALL_SPECIAL_PERMISSIONS),
    MANAGING_DIRECTOR: EXECUTIVE_SPECIALS | EXECUTIVE_IT_VIEW_SPECIALS,
    DIRECTOR_OF_ENGINEERING: EXECUTIVE_SPECIALS | EXECUTIVE_IT_VIEW_SPECIALS,
    DIRECTOR_OF_SALES: EXECUTIVE_SPECIALS | EXECUTIVE_IT_VIEW_SPECIALS,
    DIRECTOR_OF_HR: EXECUTIVE_SPECIALS | EXECUTIVE_IT_VIEW_SPECIALS,
    DIRECTOR_OF_ACCOUNTS: EXECUTIVE_SPECIALS | EXECUTIVE_IT_VIEW_SPECIALS,
    DIRECTOR_OF_IT: EXECUTIVE_SPECIALS | frozenset({
        SPECIAL_VIEW_IT_OPERATIONS,
        SPECIAL_MANAGE_IT_ASSETS,
        SPECIAL_ASSIGN_IT_ASSETS,
        SPECIAL_MANAGE_IT_NETWORKS,
        SPECIAL_ALLOCATE_IT_IPS,
        SPECIAL_MANAGE_IT_ACCOUNTS,
        SPECIAL_MANAGE_IT_REQUESTS,
        SPECIAL_VIEW_IT_REPORTS,
        SPECIAL_MANAGE_IT_SETTINGS,
    }),
    DIRECTOR_GENERIC: EXECUTIVE_SPECIALS | EXECUTIVE_IT_VIEW_SPECIALS,
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
            SPECIAL_EXPORT_REPORTS,
        }
    ),
    DESIGNER: frozenset(),
    SENIOR_DESIGNER: frozenset({SPECIAL_CREATE_PROJECTS, SPECIAL_EDIT_PROJECTS}),
    JUNIOR_DESIGNER: frozenset(),
    SURFACER: frozenset(),
    READ_ONLY: frozenset(),
    PLANNING_BOARD: frozenset(),
    HR: frozenset({SPECIAL_VIEW_REPORTS, SPECIAL_EXPORT_REPORTS}),
    OFFICE_ADMINISTRATOR: frozenset({SPECIAL_VIEW_REPORTS, SPECIAL_EXPORT_REPORTS}),
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
    "/finance": MODULE_FINANCIAL_PLANNING,
    "/hr": MODULE_HUMAN_RESOURCES,
    "/analytics": MODULE_REPORTS_ANALYTICS,
    "/planning-board": MODULE_PLANNING_BOARD,
    "/calendar": MODULE_CALENDAR,
    "/performance": MODULE_PERFORMANCE,
    "/help-desk": MODULE_TICKETS,
    "/it": MODULE_IT_OPERATIONS,
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
    modules = set(
        DEFAULT_MODULES_BY_ROLE.get(normalized, DEFAULT_MODULES_BY_ROLE[DESIGNER])
    )
    # Help Desk is a company-wide capability — every user can raise a ticket.
    modules.add(MODULE_TICKETS)
    return sorted(modules)


def default_special_permissions_for_role(role_name: str) -> list[str]:
    normalized = normalize_role_name(role_name)
    return sorted(DEFAULT_SPECIAL_BY_ROLE.get(normalized, frozenset()))


def resolve_user_modules(user: User, role_name: str) -> list[str]:
    normalized = normalize_role_name(role_name)
    # Admins always receive the full module catalog so new modules (e.g. Performance)
    # appear without requiring a manual Users-page re-save.
    if normalized == ADMIN:
        return sorted(ALL_MODULES)
    stored = _parse_json_list(user.module_access)
    if stored is not None:
        modules = {module for module in stored if module in ALL_MODULES}
        # Performance previously sat under the Dashboard nav gate — keep parity for
        # accounts whose saved module_access pre-dates MODULE_PERFORMANCE.
        if MODULE_DASHBOARD in modules:
            modules.add(MODULE_PERFORMANCE)
        # Help Desk is company-wide — surface it for every account, including
        # those whose saved module_access pre-dates MODULE_TICKETS.
        modules.add(MODULE_TICKETS)
        return sorted(modules)
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
