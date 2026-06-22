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
