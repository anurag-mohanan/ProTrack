import {
  fetchTimesheetImportJob,
  getTimesheetImportErrorLogUrl,
  resolveTimesheetUpload,
  runHistoricalTimesheetImport,
  uploadHistoricalTimesheet,
  validateTimesheetUpload,
} from '../api/timesheetImport';
import { getAccessToken } from '../api/client';
import type {
  DuplicateWeekAction,
  DesignerResolution,
  TimesheetImportJobProgress,
  TimesheetImportResolveRequest,
  TimesheetImportRunRequest,
  TimesheetImportUploadResponse,
  TimesheetImportValidateResponse,
} from '../types/TimesheetImport';

export async function uploadTimesheetImportFile(
  file: File,
): Promise<TimesheetImportUploadResponse> {
  return uploadHistoricalTimesheet(file);
}

export async function validateTimesheetImportFile(
  uploadId: string,
): Promise<TimesheetImportValidateResponse> {
  return validateTimesheetUpload(uploadId);
}

export async function saveTimesheetImportResolutions(
  payload: TimesheetImportResolveRequest,
): Promise<void> {
  return resolveTimesheetUpload(payload);
}

export async function startTimesheetImportJob(
  uploadId: string,
  dryRun: boolean,
  duplicateWeekAction: DuplicateWeekAction,
  designer?: DesignerResolution,
) {
  const payload: TimesheetImportRunRequest = {
    upload_id: uploadId,
    dry_run: dryRun,
    duplicate_week_action: duplicateWeekAction,
    designer,
  };
  return runHistoricalTimesheetImport(payload);
}

export async function pollTimesheetImportJob(
  jobId: string,
  onProgress?: (job: TimesheetImportJobProgress) => void,
): Promise<TimesheetImportJobProgress> {
  const poll = async (): Promise<TimesheetImportJobProgress> => {
    const job = await fetchTimesheetImportJob(jobId);
    onProgress?.(job);
    if (job.status === 'completed' || job.status === 'failed') {
      return job;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 500));
    return poll();
  };
  return poll();
}

export async function downloadTimesheetImportErrorLog(jobId: string): Promise<void> {
  const response = await fetch(getTimesheetImportErrorLogUrl(jobId), {
    headers: {
      Authorization: `Bearer ${getAccessToken() ?? ''}`,
    },
  });
  if (!response.ok) {
    throw new Error('Failed to download error log.');
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `timesheet-import-${jobId}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}
