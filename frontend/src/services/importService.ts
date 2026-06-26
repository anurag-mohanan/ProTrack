import {
  fetchImportJob,
  getImportErrorLogUrl,
  runHistoricalImport,
  uploadHistoricalProjects,
} from '../api/import';
import type {
  DuplicateAction,
  ImportJobProgress,
  ImportRunRequest,
  ImportUploadResponse,
} from '../types/Import';
import { getAccessToken } from '../api/client';

export async function uploadImportFile(file: File): Promise<ImportUploadResponse> {
  return uploadHistoricalProjects(file);
}

export async function startImportJob(
  uploadId: string,
  dryRun: boolean,
  duplicateAction: DuplicateAction,
  importAsArchived = false,
) {
  const payload: ImportRunRequest = {
    upload_id: uploadId,
    dry_run: dryRun,
    duplicate_action: duplicateAction,
    import_as_archived: importAsArchived,
  };
  return runHistoricalImport(payload);
}

export async function pollImportJob(
  jobId: string,
  onProgress?: (job: ImportJobProgress) => void,
): Promise<ImportJobProgress> {
  const poll = async (): Promise<ImportJobProgress> => {
    const job = await fetchImportJob(jobId);
    onProgress?.(job);
    if (job.status === 'completed' || job.status === 'failed') {
      return job;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 500));
    return poll();
  };
  return poll();
}

export function downloadImportErrorLog(jobId: string): void {
  const token = getAccessToken();
  const url = getImportErrorLogUrl(jobId);
  const link = document.createElement('a');
  link.href = token ? `${url}?token=${token}` : url;
  link.setAttribute('download', `import-errors-${jobId}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export async function downloadImportErrorLogAuthenticated(jobId: string): Promise<void> {
  const response = await fetch(getImportErrorLogUrl(jobId), {
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
  link.download = `import-errors-${jobId}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}
