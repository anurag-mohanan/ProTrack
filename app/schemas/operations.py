"""Schemas for the System Health & Operations Center."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

HealthLevel = Literal["healthy", "warning", "critical", "unknown"]
ServiceStatus = Literal["running", "degraded", "stopped", "unknown"]


class ServiceCard(BaseModel):
    name: str
    status: ServiceStatus = "unknown"
    status_label: str = "Unknown"
    last_checked: datetime
    uptime_seconds: int | None = None
    uptime_label: str | None = None
    version: str | None = None
    response_time_ms: int | None = None
    detail: str | None = None
    can_restart: bool = False


class DiskUsageItem(BaseModel):
    name: str
    path: str
    used_bytes: int = 0
    total_bytes: int = 0
    used_label: str = "0 B"
    total_label: str = "0 B"
    percent_used: float = 0.0
    warning: bool = False
    critical: bool = False


class DatabaseHealth(BaseModel):
    connected: bool = False
    database_name: str | None = None
    database_size_bytes: int = 0
    database_size_label: str = "0 B"
    sqlite_version: str | None = None
    table_count: int = 0
    total_projects: int = 0
    total_timesheets: int = 0
    total_users: int = 0
    total_customers: int = 0
    total_entries: int = 0
    open_connections: int = 1
    slow_queries: int = 0
    last_backup: datetime | None = None
    last_backup_label: str | None = None
    integrity_status: str | None = None
    integrity_checked_at: datetime | None = None


class IisHealth(BaseModel):
    website_running: bool | None = None
    app_pool_status: str | None = None
    site_name: str | None = None
    https_enabled: bool | None = None
    ssl_expiry: datetime | None = None
    requests_today: int = 0
    active_sessions: int = 0
    current_users: int = 0
    host_platform: str | None = None
    note: str | None = None


class BackgroundJobRow(BaseModel):
    job_id: str
    name: str
    status: str
    next_run: datetime | None = None
    last_run: datetime | None = None
    duration_seconds: float | None = None
    message: str | None = None
    can_retry: bool = False


class PerformanceMetrics(BaseModel):
    average_api_response_ms: int = 0
    slowest_endpoint: str | None = None
    requests_per_minute: float = 0.0
    memory_usage_mb: float | None = None
    cpu_usage_percent: float | None = None
    cache_hit_rate: float | None = None
    average_dashboard_load_ms: int | None = None


class ErrorLogRow(BaseModel):
    id: str
    occurred_at: datetime
    severity: Literal["critical", "warning", "info"]
    module: str
    endpoint: str | None = None
    user: str | None = None
    message: str
    resolved: bool = False
    stack_trace: str | None = None


class UserActivitySummary(BaseModel):
    users_logged_in: int = 0
    current_sessions: int = 0
    failed_logins_24h: int = 0
    average_session_minutes: int | None = None
    most_active_users: list[str] = Field(default_factory=list)
    inactive_users: int = 0


class EmailStatusSummary(BaseModel):
    smtp_connected: bool | None = None
    smtp_host: str | None = None
    last_email_sent: datetime | None = None
    failed_emails: int = 0
    queued_emails: int = 0
    retry_queue: int = 0


class AiStatusSummary(BaseModel):
    available: bool = False
    last_analysis: datetime | None = None
    average_response_ms: int | None = None
    recommendations_today: int = 0
    detail: str | None = None


class BackupSummary(BaseModel):
    last_backup: datetime | None = None
    last_backup_filename: str | None = None
    backup_size_bytes: int = 0
    backup_size_label: str = "0 B"
    backup_location: str
    retention_days: int = 30
    backup_count: int = 0


class ApplicationStatistics(BaseModel):
    projects: int = 0
    archived_projects: int = 0
    customers: int = 0
    users: int = 0
    teams: int = 0
    milestones: int = 0
    timesheet_entries: int = 0
    attachments: int = 0
    reports_generated: int = 0
    emails_sent: int = 0
    ai_recommendations: int = 0
    imports_completed: int = 0


class ApiMonitorRow(BaseModel):
    method: str
    endpoint: str
    average_response_ms: int = 0
    last_status: int = 200
    requests_today: int = 0
    errors_today: int = 0


class TimelineEvent(BaseModel):
    occurred_at: datetime
    event_type: str
    title: str
    detail: str | None = None
    severity: Literal["info", "warning", "error", "success"] = "info"


class HealthAlert(BaseModel):
    id: str
    severity: Literal["critical", "warning", "success", "info"]
    title: str
    detail: str | None = None


class HealthSnapshotPoint(BaseModel):
    recorded_at: datetime
    overall_status: HealthLevel
    response_time_ms: int = 0
    error_count: int = 0
    cpu_percent: float | None = None
    memory_mb: float | None = None
    disk_percent: float | None = None


class DiagnosticResult(BaseModel):
    name: str
    status: Literal["pass", "fail", "warning"]
    message: str
    duration_ms: int = 0


class DiagnosticsReport(BaseModel):
    generated_at: datetime
    overall_status: HealthLevel
    results: list[DiagnosticResult] = Field(default_factory=list)


class LogLine(BaseModel):
    timestamp: datetime | None = None
    level: str = "INFO"
    message: str
    source: str | None = None


class OperationsCenterSnapshot(BaseModel):
    generated_at: datetime
    overall_status: HealthLevel
    overall_label: str
    services: list[ServiceCard] = Field(default_factory=list)
    database: DatabaseHealth
    iis: IisHealth
    background_jobs: list[BackgroundJobRow] = Field(default_factory=list)
    disk_usage: list[DiskUsageItem] = Field(default_factory=list)
    performance: PerformanceMetrics
    errors: list[ErrorLogRow] = Field(default_factory=list)
    user_activity: UserActivitySummary
    email: EmailStatusSummary
    ai: AiStatusSummary
    backup: BackupSummary
    statistics: ApplicationStatistics
    api_monitor: list[ApiMonitorRow] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    alerts: list[HealthAlert] = Field(default_factory=list)
    application_version: str
    release_candidate: str


class TableDiagnosticsRow(BaseModel):
    table: str
    records: int = 0
    status: HealthLevel = "unknown"
    last_updated: datetime | None = None
    missing_fk: int = 0
    duplicate_keys: int = 0
    issues: int = 0


class RelationshipDiagnosticsRow(BaseModel):
    name: str
    status: Literal["pass", "fail", "warning"]
    broken_references: int = 0
    detail: str | None = None


class DefaultDataCheckRow(BaseModel):
    name: str
    status: Literal["pass", "warning", "fail"]
    detail: str | None = None
    restore_action: str | None = None


class CustomerTemplateValidationRow(BaseModel):
    customer: str
    template_name: str
    expected_milestones: int
    actual_milestones: int
    status: Literal["pass", "warning", "fail"]
    missing_milestones: list[str] = Field(default_factory=list)


class ApiDiagnosticsRow(BaseModel):
    method: str
    endpoint: str
    status: Literal["pass", "warning", "fail"]
    response_time_ms: int = 0
    payload_size_bytes: int = 0
    last_error: str | None = None


class CrudVerificationRow(BaseModel):
    resource: str
    read: bool = False
    create: bool = False
    update: bool = False
    delete: bool = False
    search: bool = False
    sort: bool = False
    pagination: bool = False
    filters: bool = False


class PaginationVerificationRow(BaseModel):
    resource: str
    status: Literal["pass", "warning", "fail"]
    page_1_rows: int = 0
    page_2_rows: int = 0
    page_3_rows: int = 0
    total_records: int = 0
    total_pages: int = 0
    detail: str | None = None


class RuntimeErrorSummaryRow(BaseModel):
    error_key: str
    category: str
    count: int = 0
    severity: Literal["info", "warning", "critical"] = "warning"
    last_seen_at: datetime | None = None
    sample_message: str | None = None


class VersionDiagnostics(BaseModel):
    application_version: str
    build_number: str | None = None
    git_commit: str | None = None
    release_date: str | None = None
    database_version: str | None = None
    python_version: str
    node_version: str | None = None
    react_version: str | None = None
    fastapi_version: str | None = None
    sqlite_version: str | None = None


class ReleaseValidationReport(BaseModel):
    generated_at: datetime
    pages_tested: int = 0
    api_tested: int = 0
    database_checks: int = 0
    passed: int = 0
    warnings: int = 0
    critical: int = 0
    status: Literal["ready", "warning", "blocked"] = "ready"
    status_label: str = "READY FOR INTERNAL RELEASE"
    duration_ms: int = 0
    modules: list[DiagnosticResult] = Field(default_factory=list)


class DeveloperDiagnosticsSummary(BaseModel):
    generated_at: datetime
    overall_status: HealthLevel
    overall_score: int = 0
    last_checked: datetime
    summary_cards: list[ServiceCard] = Field(default_factory=list)
    database_tables: list[TableDiagnosticsRow] = Field(default_factory=list)
    relationships: list[RelationshipDiagnosticsRow] = Field(default_factory=list)
    default_data: list[DefaultDataCheckRow] = Field(default_factory=list)
    customer_templates: list[CustomerTemplateValidationRow] = Field(default_factory=list)
    api_monitor: list[ApiDiagnosticsRow] = Field(default_factory=list)
    crud_checks: list[CrudVerificationRow] = Field(default_factory=list)
    pagination_checks: list[PaginationVerificationRow] = Field(default_factory=list)
    runtime_errors: list[RuntimeErrorSummaryRow] = Field(default_factory=list)
    release_validation: ReleaseValidationReport | None = None
    version: VersionDiagnostics
