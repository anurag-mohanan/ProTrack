import enum


class ProjectStatus(enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    waiting_for_customer = "waiting_for_customer"
    completed = "completed"


class ProjectHealth(enum.Enum):
    green = "green"
    yellow = "yellow"
    red = "red"


class MilestoneStatus(enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"
    not_applicable = "not_applicable"


class TimesheetStatus(enum.Enum):
    draft = "draft"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"


class ProjectLifecycleFilter(enum.Enum):
    active = "active"
    completed = "completed"
    archived = "archived"
    deleted = "deleted"


class ActivityAction(enum.Enum):
    project_created = "project_created"
    project_updated = "project_updated"
    project_archived = "project_archived"
    project_restored = "project_restored"
    project_deleted = "project_deleted"
    project_restored_from_deleted = "project_restored_from_deleted"
    milestone_completed = "milestone_completed"
    milestone_reopened = "milestone_reopened"
    timesheet_submitted = "timesheet_submitted"
    timesheet_approved = "timesheet_approved"
    timesheet_rejected = "timesheet_rejected"
    user_logged_in = "user_logged_in"
    user_archived = "user_archived"
    user_restored = "user_restored"
    user_deleted = "user_deleted"
    user_restored_from_deleted = "user_restored_from_deleted"


class NotificationType(enum.Enum):
    project_assigned = "project_assigned"
    milestone_due_tomorrow = "milestone_due_tomorrow"
    timesheet_approved = "timesheet_approved"
    timesheet_rejected = "timesheet_rejected"
    project_overdue = "project_overdue"
    timesheet_submitted = "timesheet_submitted"


class EntityType(enum.Enum):
    project = "project"
    milestone = "milestone"
    timesheet = "timesheet"
    user = "user"
