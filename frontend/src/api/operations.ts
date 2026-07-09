import { apiClient } from './client';

export type HealthLevel = 'healthy' | 'warning' | 'critical' | 'unknown';
export type ServiceStatus = 'running' | 'degraded' | 'stopped' | 'unknown';

export interface ServiceCard {
  name: string;
  status: ServiceStatus;
  status_label: string;
  last_checked: string;
  uptime_seconds?: number | null;
  uptime_label?: string | null;
  version?: string | null;
  response_time_ms?: number | null;
  detail?: string | null;
  can_restart: boolean;
}

export interface DiskUsageItem {
  name: string;
  path: string;
  used_bytes: number;
  total_bytes: number;
  used_label: string;
  total_label: string;
  percent_used: number;
  warning: boolean;
  critical: boolean;
}

export interface DatabaseHealth {
  connected: boolean;
  database_name: string | null;
  database_size_bytes: number;
  database_size_label: string;
  sqlite_version: string | null;
  table_count: number;
  total_projects: number;
  total_timesheets: number;
  total_users: number;
  total_customers: number;
  total_entries: number;
  open_connections: number;
  slow_queries: number;
  last_backup: string | null;
  last_backup_label: string | null;
  integrity_status: string | null;
  integrity_checked_at: string | null;
}

export interface BackgroundJobRow {
  job_id: string;
  name: string;
  status: string;
  next_run?: string | null;
  last_run?: string | null;
  duration_seconds?: number | null;
  message?: string | null;
  can_retry: boolean;
}

export interface ErrorLogRow {
  id: string;
  occurred_at: string;
  severity: 'critical' | 'warning' | 'info';
  module: string;
  endpoint?: string | null;
  user?: string | null;
  message: string;
  resolved: boolean;
  stack_trace?: string | null;
}

export interface HealthAlert {
  id: string;
  severity: 'critical' | 'warning' | 'success' | 'info';
  title: string;
  detail?: string | null;
}

export interface OperationsCenterSnapshot {
  generated_at: string;
  overall_status: HealthLevel;
  overall_label: string;
  services: ServiceCard[];
  database: DatabaseHealth;
  iis: {
    website_running: boolean | null;
    app_pool_status: string | null;
    site_name: string | null;
    https_enabled: boolean | null;
    current_users: number;
    host_platform: string | null;
    note: string | null;
  };
  background_jobs: BackgroundJobRow[];
  disk_usage: DiskUsageItem[];
  performance: {
    average_api_response_ms: number;
    slowest_endpoint: string | null;
    requests_per_minute: number;
    memory_usage_mb: number | null;
    cpu_usage_percent: number | null;
    cache_hit_rate: number | null;
    average_dashboard_load_ms: number | null;
  };
  errors: ErrorLogRow[];
  user_activity: {
    users_logged_in: number;
    current_sessions: number;
    failed_logins_24h: number;
    inactive_users: number;
  };
  email: {
    smtp_connected: boolean | null;
    smtp_host: string | null;
    last_email_sent: string | null;
    failed_emails: number;
    queued_emails: number;
    retry_queue: number;
  };
  ai: {
    available: boolean;
    recommendations_today: number;
    detail: string | null;
  };
  backup: {
    last_backup: string | null;
    last_backup_filename: string | null;
    backup_size_bytes: number;
    backup_size_label: string;
    backup_location: string;
    retention_days: number;
    backup_count: number;
  };
  statistics: {
    projects: number;
    archived_projects: number;
    customers: number;
    users: number;
    teams: number;
    milestones: number;
    timesheet_entries: number;
    emails_sent: number;
    imports_completed: number;
  };
  api_monitor: Array<{
    method: string;
    endpoint: string;
    average_response_ms: number;
    last_status: number;
    requests_today: number;
    errors_today: number;
  }>;
  timeline: Array<{
    occurred_at: string;
    event_type: string;
    title: string;
    detail?: string | null;
    severity: string;
  }>;
  alerts: HealthAlert[];
  application_version: string;
  release_candidate: string;
}

export interface HealthSnapshotPoint {
  recorded_at: string;
  overall_status: HealthLevel;
  response_time_ms: number;
  error_count: number;
  cpu_percent?: number | null;
  memory_mb?: number | null;
  disk_percent?: number | null;
}

export interface DiagnosticResult {
  name: string;
  status: 'pass' | 'fail' | 'warning';
  message: string;
  duration_ms: number;
}

export interface DiagnosticsReport {
  generated_at: string;
  overall_status: HealthLevel;
  results: DiagnosticResult[];
}

export interface TableDiagnosticsRow {
  table: string;
  records: number;
  status: HealthLevel;
  last_updated: string | null;
  missing_fk: number;
  duplicate_keys: number;
  issues: number;
}

export interface RelationshipDiagnosticsRow {
  name: string;
  status: 'pass' | 'warning' | 'fail';
  broken_references: number;
  detail?: string | null;
}

export interface DefaultDataCheckRow {
  name: string;
  status: 'pass' | 'warning' | 'fail';
  detail?: string | null;
  restore_action?: string | null;
}

export interface CustomerTemplateValidationRow {
  customer: string;
  template_name: string;
  expected_milestones: number;
  actual_milestones: number;
  status: 'pass' | 'warning' | 'fail';
  missing_milestones: string[];
}

export interface CrudVerificationRow {
  resource: string;
  read: boolean;
  create: boolean;
  update: boolean;
  delete: boolean;
  search: boolean;
  sort: boolean;
  pagination: boolean;
  filters: boolean;
}

export interface PaginationVerificationRow {
  resource: string;
  status: 'pass' | 'warning' | 'fail';
  page_1_rows: number;
  page_2_rows: number;
  page_3_rows: number;
  total_records: number;
  total_pages: number;
  detail?: string | null;
}

export interface RuntimeErrorSummaryRow {
  error_key: string;
  category: string;
  count: number;
  severity: 'info' | 'warning' | 'critical';
  last_seen_at: string | null;
  sample_message?: string | null;
}

export interface VersionDiagnostics {
  application_version: string;
  build_number?: string | null;
  git_commit?: string | null;
  release_date?: string | null;
  database_version?: string | null;
  python_version: string;
  node_version?: string | null;
  react_version?: string | null;
  fastapi_version?: string | null;
  sqlite_version?: string | null;
}

export interface ReleaseValidationReport {
  generated_at: string;
  pages_tested: number;
  api_tested: number;
  database_checks: number;
  passed: number;
  warnings: number;
  critical: number;
  status: 'ready' | 'warning' | 'blocked';
  status_label: string;
  duration_ms: number;
  modules: DiagnosticResult[];
}

export interface DeveloperDiagnosticsSummary {
  generated_at: string;
  overall_status: HealthLevel;
  overall_score: number;
  last_checked: string;
  summary_cards: ServiceCard[];
  database_tables: TableDiagnosticsRow[];
  relationships: RelationshipDiagnosticsRow[];
  default_data: DefaultDataCheckRow[];
  customer_templates: CustomerTemplateValidationRow[];
  api_monitor: Array<{
    method: string;
    endpoint: string;
    status: 'pass' | 'warning' | 'fail';
    response_time_ms: number;
    payload_size_bytes: number;
    last_error?: string | null;
  }>;
  crud_checks: CrudVerificationRow[];
  pagination_checks: PaginationVerificationRow[];
  runtime_errors: RuntimeErrorSummaryRow[];
  release_validation?: ReleaseValidationReport | null;
  version: VersionDiagnostics;
}

export interface LogLine {
  timestamp?: string | null;
  level: string;
  message: string;
  source?: string | null;
}

export async function fetchOperationsCenter(): Promise<OperationsCenterSnapshot> {
  const { data } = await apiClient.get<OperationsCenterSnapshot>('/system/operations');
  return data;
}

export async function fetchOperationsHistory(period = '24h'): Promise<HealthSnapshotPoint[]> {
  const { data } = await apiClient.get<HealthSnapshotPoint[]>('/system/operations/history', {
    params: { period },
  });
  return data;
}

export async function runOperationsDiagnostics(): Promise<DiagnosticsReport> {
  const { data } = await apiClient.post<DiagnosticsReport>('/system/operations/diagnostics');
  return data;
}

export async function runIntegrityCheck(): Promise<{ status: string; result: string }> {
  const { data } = await apiClient.post('/system/operations/integrity-check');
  return data;
}

export async function optimizeDatabase(): Promise<{ status: string; message: string }> {
  const { data } = await apiClient.post('/system/operations/optimize');
  return data;
}

export async function runMaintenanceAction(action: string): Promise<{ status: string; message: string }> {
  const { data } = await apiClient.post('/system/operations/maintenance', { action });
  return data;
}

export async function fetchOperationsLogs(category: string, limit = 100): Promise<LogLine[]> {
  const { data } = await apiClient.get<LogLine[]>('/system/operations/logs', {
    params: { category, limit },
  });
  return data;
}

export async function fetchDeveloperDiagnosticsSummary(): Promise<DeveloperDiagnosticsSummary> {
  const { data } = await apiClient.get<DeveloperDiagnosticsSummary>('/system/diagnostics/summary');
  return data;
}

export async function runReleaseValidation(): Promise<ReleaseValidationReport> {
  const { data } = await apiClient.post<ReleaseValidationReport>('/system/diagnostics/release-validation');
  return data;
}

export const operationsQueryKeys = {
  all: ['operations'] as const,
  snapshot: ['operations', 'snapshot'] as const,
  history: (period: string) => ['operations', 'history', period] as const,
  logs: (category: string) => ['operations', 'logs', category] as const,
  diagnosticsSummary: ['operations', 'diagnostics-summary'] as const,
  releaseValidation: ['operations', 'release-validation'] as const,
};
