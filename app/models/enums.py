import enum


class ProjectStage(enum.Enum):
    preliminary = "preliminary"
    intermediate = "intermediate"
    final = "final"


class ExecutionStatus(enum.Enum):
    planning = "planning"
    currently_being_worked_on = "currently_being_worked_on"
    on_hold = "on_hold"
    cancelled = "cancelled"
    completed = "completed"


class ProjectHealth(enum.Enum):
    green = "green"
    yellow = "yellow"
    red = "red"


class MilestoneStatus(enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    waiting = "waiting"
    on_hold = "on_hold"
    completed = "completed"
    cancelled = "cancelled"
    not_applicable = "not_applicable"


class TimesheetStatus(enum.Enum):
    draft = "draft"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"


class WorkCategory(enum.Enum):
    productive = "productive"
    non_productive = "non_productive"


class NonProductiveCodeCategory(enum.Enum):
    non_productive = "non_productive"
    leave = "leave"


class ProjectLifecycleFilter(enum.Enum):
    all = "all"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"
    archived = "archived"
    deleted = "deleted"


class ProjectPriority(enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class EmploymentType(enum.Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    intern = "intern"


class SkillLevel(enum.Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"
    expert = "expert"


class UserAvailabilityStatus(enum.Enum):
    available = "available"
    allocated = "allocated"
    on_leave = "on_leave"
    unavailable = "unavailable"


class DueDateCalculationMode(enum.Enum):
    from_start = "from_start"
    from_previous_milestone = "from_previous_milestone"
    business_days = "business_days"


class ActivityAction(enum.Enum):
    project_created = "project_created"
    project_updated = "project_updated"
    project_archived = "project_archived"
    project_restored = "project_restored"
    project_deleted = "project_deleted"
    project_restored_from_deleted = "project_restored_from_deleted"
    milestone_completed = "milestone_completed"
    milestone_reopened = "milestone_reopened"
    milestone_created = "milestone_created"
    milestone_updated = "milestone_updated"
    milestone_deleted = "milestone_deleted"
    milestone_reordered = "milestone_reordered"
    timesheet_submitted = "timesheet_submitted"
    timesheet_approved = "timesheet_approved"
    timesheet_rejected = "timesheet_rejected"
    user_logged_in = "user_logged_in"
    user_logged_out = "user_logged_out"
    login_failed = "login_failed"
    password_changed = "password_changed"
    password_reset = "password_reset"
    admin_impersonation_started = "admin_impersonation_started"
    admin_impersonation_stopped = "admin_impersonation_stopped"
    user_archived = "user_archived"
    user_restored = "user_restored"
    user_deleted = "user_deleted"
    user_restored_from_deleted = "user_restored_from_deleted"
    record_deleted = "record_deleted"
    record_restored = "record_restored"
    record_archived = "record_archived"
    customer_created = "customer_created"
    customer_updated = "customer_updated"
    settings_updated = "settings_updated"
    import_completed = "import_completed"
    data_exported = "data_exported"


class NotificationType(enum.Enum):
    project_assigned = "project_assigned"
    milestone_due_tomorrow = "milestone_due_tomorrow"
    timesheet_approved = "timesheet_approved"
    timesheet_rejected = "timesheet_rejected"
    project_overdue = "project_overdue"
    timesheet_submitted = "timesheet_submitted"
    project_due_soon = "project_due_soon"
    import_completed = "import_completed"
    pending_approval = "pending_approval"


class EntityType(enum.Enum):
    project = "project"
    milestone = "milestone"
    timesheet = "timesheet"
    user = "user"
    customer = "customer"
    contact = "contact"
    team = "team"
    role = "role"
    stream = "stream"
    task_type = "task_type"
    project_template = "project_template"
    project_type = "project_type"
    np_code = "np_code"
    settings = "settings"
    import_batch = "import_batch"


class DesignerAvailabilityStatus(enum.Enum):
    available = "available"
    working = "working"
    on_hold = "on_hold"
    leave = "leave"


class DashboardActivityCategory(enum.Enum):
    project = "project"
    milestone = "milestone"
    timesheet = "timesheet"
    user = "user"
    import_event = "import"


class DecisionCategory(enum.Enum):
    design = "design"
    customer = "customer"
    manufacturing = "manufacturing"
    tooling = "tooling"
    schedule = "schedule"
    quality = "quality"
    general = "general"


class EngineeringChangeStatus(enum.Enum):
    open = "open"
    closed = "closed"


class TimelineStepStatus(enum.Enum):
    completed = "completed"
    current = "current"
    upcoming = "upcoming"
    delayed = "delayed"


class ProjectRiskType(enum.Enum):
    milestone_delay = "milestone_delay"
    hours_over_quote = "hours_over_quote"
    overdue = "overdue"
    missing_approvals = "missing_approvals"
    designer_overloaded = "designer_overloaded"
