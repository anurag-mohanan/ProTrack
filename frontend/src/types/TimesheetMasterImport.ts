export interface MasterDesignerScanRow {
  designer: string;
  rows: number;
  date_from: string | null;
  date_to: string | null;
  date_range_label: string;
  user_matched: boolean;
}

export interface MasterScanResponse {
  upload_id: string;
  filename: string;
  row_count: number;
  designer_count: number;
  date_from: string | null;
  date_to: string | null;
  date_range_label: string | null;
  designers: MasterDesignerScanRow[];
}

export interface MasterUploadResponse {
  upload_id: string;
  filename: string;
  scan: MasterScanResponse;
}

export interface MasterImportRunResponse {
  job_id: string;
  backup_path: string | null;
}

export interface MasterImportSummary {
  rows_read: number;
  rows_imported: number;
  rows_skipped: number;
  errors: number;
  duration_seconds: number;
  backup_path: string | null;
  duplicate_check_disabled: boolean;
}

export type MasterImportJobStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface MasterImportJobProgress {
  job_id: string;
  status: MasterImportJobStatus;
  percent_complete: number;
  rows_processed: number;
  rows_total: number;
  rows_imported: number;
  current_designer: string | null;
  message: string | null;
  summary: MasterImportSummary | null;
  log_download_name: string | null;
}
