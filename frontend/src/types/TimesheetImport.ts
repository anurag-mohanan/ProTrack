export type DuplicateWeekAction = 'skip' | 'replace' | 'merge';

export type DesignerResolutionAction = 'match_existing' | 'create_new';

export type ProjectResolutionAction = 'create' | 'skip' | 'map_existing';

export type TimesheetImportRowStatus =
  | 'ready'
  | 'error'
  | 'skipped'
  | 'warning'
  | 'imported';

export type TimesheetImportJobStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface TimesheetImportRowPreview {
  row_number: number;
  designer: string | null;
  tool_number: string | null;
  project_code: string | null;
  customer: string | null;
  task_type: string | null;
  np_code: string | null;
  hours: string | null;
  entry_date: string | null;
  description: string | null;
  is_np_row: boolean;
  status_label: TimesheetImportRowStatus;
  messages: string[];
  matched_project_id: string | null;
  matched_user_id: string | null;
  matched_task_type_id: string | null;
}

export interface DesignerMatchInfo {
  detected_name: string;
  matched_user_id: string | null;
  matched_user_name: string | null;
  requires_resolution: boolean;
}

export interface DuplicateWeekInfo {
  week_start: string;
  week_label: string;
  designer_name: string;
  existing_entry_count: number;
  previously_imported: boolean;
  import_history_id: string | null;
}

export interface TimesheetImportUploadResponse {
  upload_id: string;
  file_name: string;
  total_rows: number;
  ready_rows: number;
  error_rows: number;
  warning_rows: number;
  skipped_rows: number;
  designer: DesignerMatchInfo;
  duplicate_weeks: DuplicateWeekInfo[];
  preview: TimesheetImportRowPreview[];
}

export interface TimesheetValidationIssue {
  row_number: number | null;
  severity: string;
  code: string;
  message: string;
}

export interface TimesheetImportValidateResponse {
  upload_id: string;
  is_valid: boolean;
  issues: TimesheetValidationIssue[];
  ready_rows: number;
  error_rows: number;
}

export interface DesignerResolution {
  action: DesignerResolutionAction;
  user_id?: string | null;
}

export interface ProjectRowResolution {
  row_number: number;
  action: ProjectResolutionAction;
  project_id?: string | null;
}

export interface CustomerRowResolution {
  row_number: number;
  customer_id?: string | null;
  create_name?: string | null;
}

export interface TaskTypeRowResolution {
  row_number: number;
  task_type_id: string;
}

export interface TimesheetImportResolveRequest {
  upload_id: string;
  designer: DesignerResolution;
  duplicate_week_action: DuplicateWeekAction;
  project_resolutions?: ProjectRowResolution[];
  customer_resolutions?: CustomerRowResolution[];
  task_type_resolutions?: TaskTypeRowResolution[];
}

export interface TimesheetImportSummary {
  designer: string | null;
  rows_read: number;
  rows_imported: number;
  rows_skipped: number;
  rows_failed: number;
  projects_matched: number;
  projects_created: number;
  customers_created: number;
  users_created: number;
  np_entries: number;
  warnings: number;
  errors: number;
}

export interface TimesheetImportJobProgress {
  job_id: string;
  status: TimesheetImportJobStatus;
  total_rows: number;
  processed_rows: number;
  percent_complete: number;
  summary: TimesheetImportSummary | null;
  error_log: TimesheetImportRowPreview[];
  started_at: string | null;
  completed_at: string | null;
  message: string | null;
  history_id: string | null;
}

export interface TimesheetImportRunRequest {
  upload_id: string;
  dry_run: boolean;
  duplicate_week_action: DuplicateWeekAction;
  designer?: DesignerResolution | null;
  project_resolutions?: ProjectRowResolution[];
  customer_resolutions?: CustomerRowResolution[];
  task_type_resolutions?: TaskTypeRowResolution[];
}

export interface TimesheetImportRunResponse {
  job_id: string;
}

export interface TimesheetImportHistoryRead {
  id: string;
  filename: string;
  imported_by_name: string;
  designer_name: string;
  date_range_label: string | null;
  rows_imported: number;
  rows_failed: number;
  duration_ms: number;
  status: string;
  created_at: string;
}

export interface TimesheetImportHistoryDetail extends TimesheetImportHistoryRead {
  log_json: string | null;
  upload_id: string | null;
}
