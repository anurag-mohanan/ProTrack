from datetime import datetime

from pydantic import BaseModel, Field


class OperationalRoleTypeRead(BaseModel):
    id: str
    code: str
    name: str
    description: str | None = None
    dashboard_profile: str
    default_kpi_engineering_productivity: bool = True
    default_kpi_capacity_planning: bool = True
    default_kpi_utilization: bool = True
    default_kpi_workload_planning: bool = True
    default_kpi_dashboard_productivity: bool = True


class UserKpiConfiguration(BaseModel):
    operational_role_type_id: str | None = None
    operational_role_name: str | None = None
    dashboard_profile: str = "engineering"
    kpi_engineering_productivity: bool = True
    kpi_capacity_planning: bool = True
    kpi_utilization: bool = True
    kpi_workload_planning: bool = True
    kpi_dashboard_productivity: bool = True


class ManagementKpis(BaseModel):
    projects_managed: int = 0
    projects_delivered: int = 0
    overdue_projects: int = 0
    pending_reviews: int = 0
    pending_milestone_approvals: int = 0
    upcoming_deliveries: int = 0
    timesheet_compliance_pending: int = 0
    team_utilization_percent: float | None = None
    high_risk_projects: int = 0


class AdministrationKpis(BaseModel):
    active_users: int = 0
    import_queue: int = 0
    failed_jobs: int = 0
    failed_emails: int = 0
    backups_count: int = 0
    last_backup: datetime | None = None
    audit_actions_7d: int = 0
    emails_sent: int = 0
    backend_status: str = "ok"
    database_status: str = "ok"


class RoleKpiSnapshot(BaseModel):
    dashboard_profile: str
    management: ManagementKpis | None = None
    administration: AdministrationKpis | None = None
    engineering_productivity_user_count: int = 0
    capacity_planning_user_count: int = 0
