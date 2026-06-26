export type DuplicateAction = 'skip' | 'update' | 'create';

export type ImportRowStatus =
  | 'ready'
  | 'error'
  | 'skipped'
  | 'duplicate'
  | 'imported'
  | 'updated';

export type ImportJobStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface ImportRowPreview {
  row_number: number;
  tool_number: string | null;
  customer: string | null;
  designer: string | null;
  surfacer: string | null;
  quoted_hours: string | null;
  actual_hours: string | null;
  design_phase: string | null;
  progress: string | null;
  status: string | null;
  status_label: ImportRowStatus;
  messages: string[];
  existing_project_id: string | null;
}

export interface ImportUploadResponse {
  upload_id: string;
  file_name: string;
  total_rows: number;
  ready_rows: number;
  error_rows: number;
  duplicate_rows: number;
  missing_customer_rows: number;
  missing_designer_rows: number;
  preview: ImportRowPreview[];
}

export interface ImportSummary {
  projects_imported: number;
  projects_updated: number;
  projects_skipped: number;
  customers_created: number;
  users_created: number;
  milestones_created: number;
  errors: number;
}

export interface ImportJobProgress {
  job_id: string;
  status: ImportJobStatus;
  total_rows: number;
  processed_rows: number;
  percent_complete: number;
  summary: ImportSummary | null;
  error_log: ImportRowPreview[];
  started_at: string | null;
  completed_at: string | null;
  message: string | null;
}

export interface ImportRunRequest {
  upload_id: string;
  dry_run: boolean;
  duplicate_action: DuplicateAction;
  import_as_archived?: boolean;
}

export interface ImportRunResponse {
  job_id: string;
}
