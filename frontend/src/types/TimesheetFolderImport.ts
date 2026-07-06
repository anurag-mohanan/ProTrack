export interface FolderDesignerScanRow {
  designer: string;
  files: number;
  entries: number;
}

export interface FolderScanResponse {
  batch_id: string | null;
  source_label: string;
  designer_count: number;
  file_count: number;
  estimated_entries: number;
  designers: FolderDesignerScanRow[];
}

export interface FolderBatchUploadResponse {
  batch_id: string;
  file_count: number;
  source_label: string;
}

export interface FolderImportRunResponse {
  job_id: string;
  backup_path: string | null;
}

export interface FolderImportSummary {
  designers_imported: number;
  files_imported: number;
  rows_read: number;
  rows_imported: number;
  duplicates_skipped: number;
  errors: number;
  duration_seconds: number;
  backup_path: string | null;
}

export type FolderImportJobStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface FolderImportJobProgress {
  job_id: string;
  status: FolderImportJobStatus;
  percent_complete: number;
  current_designer: string | null;
  current_file: string | null;
  rows_imported: number;
  rows_total: number;
  files_processed: number;
  files_total: number;
  summary: FolderImportSummary | null;
  message: string | null;
  log_download_name: string | null;
}
