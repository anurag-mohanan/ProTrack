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


class ContributionReason(enum.Enum):
    assisting_designer = "assisting_designer"
    peer_review = "peer_review"
    design_support = "design_support"
    surfacing_support = "surfacing_support"
    engineering_change = "engineering_change"
    customer_request = "customer_request"
    training_mentoring = "training_mentoring"
    # Designer/resource rework from quality issues — always non-billable for efficiency tracking.
    rework_quality = "rework_quality"
    other = "other"


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


class ProjectComplexity(enum.Enum):
    """Ops scale for matching tools to designer skillset."""

    low = "low"
    medium = "medium"
    high = "high"
    expert = "expert"


class SkillProficiency(enum.Enum):
    """Industry-style skill matrix levels (learning → expert)."""

    learning = "learning"
    developing = "developing"
    proficient = "proficient"
    expert = "expert"


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


class TeamRelationshipType(enum.Enum):
    member = "member"
    team_leader = "team_leader"
    engineering_manager = "engineering_manager"
    reviewer = "reviewer"


class DashboardProfile(enum.Enum):
    engineering = "engineering"
    management = "management"
    administration = "administration"


class TaskTypeFunctionCategory(enum.Enum):
    engineering = "engineering"
    management = "management"
    administration = "administration"
    non_productive = "non_productive"


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
    user_department_changed = "user_department_changed"
    employee_offboard_scheduled = "employee_offboard_scheduled"
    employee_offboard_applied = "employee_offboard_applied"
    record_deleted = "record_deleted"
    record_restored = "record_restored"
    record_archived = "record_archived"
    customer_created = "customer_created"
    customer_updated = "customer_updated"
    settings_updated = "settings_updated"
    import_completed = "import_completed"
    data_exported = "data_exported"
    email_sent = "email_sent"
    quote_imported = "quote_imported"
    quote_revised = "quote_revised"
    budget_created = "budget_created"
    budget_approved = "budget_approved"
    budget_rejected = "budget_rejected"
    finance_planning_scenario_created = "finance_planning_scenario_created"
    finance_planning_scenario_updated = "finance_planning_scenario_updated"
    finance_planning_scenario_deleted = "finance_planning_scenario_deleted"
    fx_rate_updated = "fx_rate_updated"
    cost_updated = "cost_updated"
    ticket_created = "ticket_created"
    ticket_updated = "ticket_updated"
    ticket_assigned = "ticket_assigned"
    ticket_status_changed = "ticket_status_changed"
    ticket_commented = "ticket_commented"
    ticket_resolved = "ticket_resolved"
    ticket_closed = "ticket_closed"
    ticket_reopened = "ticket_reopened"


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
    expense_renewal = "expense_renewal"
    quote_not_invoiced = "quote_not_invoiced"
    quote_payment_follow_up = "quote_payment_follow_up"
    new_hire_onboarding = "new_hire_onboarding"
    training_assigned = "training_assigned"


class WorkingModelCode(enum.Enum):
    project_based = "project_based"
    time_materials = "time_materials"
    retainer = "retainer"
    overheads = "overheads"


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
    working_model = "working_model"
    np_code = "np_code"
    settings = "settings"
    import_batch = "import_batch"
    quote = "quote"
    budget = "budget"
    finance_planning_scenario = "finance_planning_scenario"
    cost_centre = "cost_centre"
    expense = "expense"
    fx_rate = "fx_rate"
    employee_cost = "employee_cost"
    ticket = "ticket"
    training_course = "training_course"
    training_assignment = "training_assignment"


class CostNature(enum.Enum):
    capex = "capex"
    opex = "opex"


class ExpensePaidBy(enum.Enum):
    prosohm = "prosohm"
    customer = "customer"


class CostFrequency(enum.Enum):
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"
    one_time = "one_time"
    recurring = "recurring"


class TeamBillingMode(enum.Enum):
    fixed_price = "fixed_price"
    subscription = "subscription"
    time_materials = "time_materials"
    project_based = "project_based"


class TeamBillingPeriod(enum.Enum):
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"
    one_time = "one_time"


class BudgetScopeType(enum.Enum):
    department = "department"
    customer = "customer"
    project = "project"
    team = "team"
    business_unit = "business_unit"


class BudgetApprovalStatus(enum.Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"
    closed = "closed"


class FinancePlanSection(enum.Enum):
    sales = "sales"
    expenses = "expenses"
    resources = "resources"
    capex = "capex"


class FinancePlanStatus(enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class FinancePlanningScenarioType(enum.Enum):
    expansion = "expansion"
    downsize = "downsize"
    what_if = "what_if"


class FinancePlanningScenarioStatus(enum.Enum):
    draft = "draft"
    approved = "approved"
    archived = "archived"


class AiForecastKind(enum.Enum):
    revenue_forecast = "revenue_forecast"
    capacity_forecast = "capacity_forecast"
    profit_forecast = "profit_forecast"
    underquoted_projects = "underquoted_projects"
    overquoted_projects = "overquoted_projects"
    customer_profitability = "customer_profitability"
    employee_productivity = "employee_productivity"
    software_renewal_prediction = "software_renewal_prediction"
    budget_risk = "budget_risk"
    cash_flow_trend = "cash_flow_trend"


class EmailMessageStatus(enum.Enum):
    queued = "queued"
    sending = "sending"
    sent = "sent"
    failed = "failed"


class EmailProviderType(enum.Enum):
    smtp = "smtp"
    zoho = "zoho"


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
