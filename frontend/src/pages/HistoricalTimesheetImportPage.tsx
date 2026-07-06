import { useCallback, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  FormControlLabel,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import SearchIcon from '@mui/icons-material/Search';
import DownloadIcon from '@mui/icons-material/Download';
import CancelIcon from '@mui/icons-material/Cancel';
import DeleteForeverIcon from '@mui/icons-material/DeleteForever';
import type { FolderImportJobProgress, FolderScanResponse } from '../types/TimesheetFolderImport';
import {
  cancelFolderImportJob,
  downloadFolderImportLog,
  fetchFolderImportJob,
  resetAllTimesheetData,
  runHistoricalTimesheetFolderImport,
  scanHistoricalTimesheetFolder,
  uploadHistoricalTimesheetFolder,
} from '../api/timesheetImport';
import { getErrorMessage } from '../api/client';
import { PageHeader } from '../components/common/PageHeader';
import { formatNumber } from '../utils/format';

type WizardPhase = 'setup' | 'scanned' | 'importing' | 'completed';

function isValidExcelFile(file: File): boolean {
  const name = file.name;
  return name.toLowerCase().endsWith('.xlsx') && !name.startsWith('~$');
}

function designerFromPath(relativePath: string): string {
  const parts = relativePath.replace(/\\/g, '/').split('/');
  return parts.length >= 2 ? parts[parts.length - 2] : 'Unknown';
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function SummaryMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <Box sx={{ textAlign: 'center', minWidth: 120 }}>
      <Typography variant="h5" color="primary" sx={{ fontWeight: 700 }}>
        {value}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
    </Box>
  );
}

export function HistoricalTimesheetImportPage() {
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<WizardPhase>('setup');
  const [sourceLabel, setSourceLabel] = useState('');
  const [serverPath, setServerPath] = useState('');
  const [batchId, setBatchId] = useState<string | null>(null);
  const [localPaths, setLocalPaths] = useState<string[]>([]);
  const [scanResult, setScanResult] = useState<FolderScanResponse | null>(null);
  const [job, setJob] = useState<FolderImportJobProgress | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);
  const [resetConfirmText, setResetConfirmText] = useState('');
  const [databaseResetPerformed, setDatabaseResetPerformed] = useState(false);
  const [resetBackupPath, setResetBackupPath] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [ignoreDuplicateCheck, setIgnoreDuplicateCheck] = useState(true);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const quickEstimate = useMemo(() => {
    if (!localPaths.length) {
      return null;
    }
    const designers = new Set(localPaths.map(designerFromPath));
    return {
      designers: designers.size,
      files: localPaths.length,
    };
  }, [localPaths]);

  const pollJob = useCallback(async (jobId: string) => {
    for (let attempt = 0; attempt < 600; attempt += 1) {
      const progress = await fetchFolderImportJob(jobId);
      setJob(progress);
      if (['completed', 'failed', 'cancelled'].includes(progress.status)) {
        setPhase('completed');
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    setError('Import is taking longer than expected. Check back shortly.');
  }, []);

  const handleFolderSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = event.target.files;
    if (!fileList?.length) {
      return;
    }
    setError(null);
    const files: File[] = [];
    const paths: string[] = [];
    for (const file of Array.from(fileList)) {
      if (!isValidExcelFile(file)) {
        continue;
      }
      const rel = file.webkitRelativePath || file.name;
      files.push(file);
      paths.push(rel);
    }
    if (!files.length) {
      setError('No valid Excel (.xlsx) files were found in the selected folder.');
      return;
    }

    setLocalPaths(paths);
    setServerPath('');
    const root = paths[0]?.split('/')[0] ?? 'Selected folder';
    setSourceLabel(root);
    setBatchId(null);
    setScanResult(null);
    setPhase('setup');

    setUploading(true);
    try {
      const upload = await uploadHistoricalTimesheetFolder(files, paths);
      setBatchId(upload.batch_id);
      setSourceLabel(upload.source_label);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setUploading(false);
      if (folderInputRef.current) {
        folderInputRef.current.value = '';
      }
    }
  };

  const handleScan = async () => {
    setError(null);
    setLoading(true);
    try {
      const payload = batchId
        ? { batch_id: batchId }
        : serverPath.trim()
          ? { source_path: serverPath.trim() }
          : null;
      if (!payload) {
        setError('Select a folder or enter a server path before scanning.');
        return;
      }
      const result = await scanHistoricalTimesheetFolder(payload);
      setScanResult(result);
      setSourceLabel(result.source_label);
      setPhase('scanned');
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async () => {
    setConfirmOpen(false);
    setError(null);
    setLoading(true);
    try {
      const payload = batchId
        ? {
            batch_id: batchId,
            after_database_reset: databaseResetPerformed,
            ignore_duplicate_check: ignoreDuplicateCheck,
          }
        : {
            source_path: serverPath.trim(),
            after_database_reset: databaseResetPerformed,
            ignore_duplicate_check: ignoreDuplicateCheck,
          };
      const run = await runHistoricalTimesheetFolderImport(payload);
      setPhase('importing');
      await pollJob(run.job_id);
    } catch (err) {
      setError(getErrorMessage(err));
      setPhase('scanned');
    } finally {
      setLoading(false);
    }
  };

  const handleCancelImport = async () => {
    if (!job?.job_id) {
      return;
    }
    try {
      await cancelFolderImportJob(job.job_id);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  const handleDownloadLog = async () => {
    if (!job?.job_id) {
      return;
    }
    try {
      await downloadFolderImportLog(job.job_id, job.log_download_name ?? undefined);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  const handleResetAll = async () => {
    if (resetConfirmText.trim() !== 'DELETE') {
      setError('Type DELETE to confirm.');
      return;
    }
    setResetting(true);
    setError(null);
    try {
      const result = await resetAllTimesheetData(resetConfirmText.trim());
      setDatabaseResetPerformed(true);
      setResetBackupPath(result.backup_path);
      setResetConfirmOpen(false);
      setResetConfirmText('');
      setPhase('setup');
      setScanResult(null);
      setJob(null);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setResetting(false);
    }
  };

  const resetWizard = () => {
    setPhase('setup');
    setScanResult(null);
    setJob(null);
    setBatchId(null);
    setLocalPaths([]);
    setSourceLabel('');
    setError(null);
  };

  const displayDesigners = scanResult?.designer_count ?? quickEstimate?.designers ?? 0;
  const displayFiles = scanResult?.file_count ?? quickEstimate?.files ?? localPaths.length;
  const displayEntries = scanResult?.estimated_entries ?? 0;

  return (
    <Box>
      <PageHeader
        title="Historical Timesheet Import"
        subtitle="Import all historical monthly timesheets from a folder in one operation."
      />

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      ) : null}

      {databaseResetPerformed ? (
        <Alert severity="success" sx={{ mb: 2 }}>
          Database reset complete. Duplicate checking is disabled for the next import.
          {resetBackupPath ? ` Backup: ${resetBackupPath}` : null}
        </Alert>
      ) : null}

      <Card sx={{ mb: 3, borderColor: 'error.light', borderWidth: 1, borderStyle: 'solid' }}>
        <CardContent>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1, color: 'error.main' }}>
            Delete All Timesheet Entries
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Permanently remove all timesheet records before a full historical re-import.
            Users, customers, projects, and settings are not affected.
          </Typography>
          <Button
            variant="outlined"
            color="error"
            startIcon={<DeleteForeverIcon />}
            disabled={resetting || phase === 'importing'}
            onClick={() => setResetConfirmOpen(true)}
          >
            Delete All Timesheet Entries
          </Button>
        </CardContent>
      </Card>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 2 }}>
            Source Folder
          </Typography>

          <Stack
            direction={{ xs: 'column', md: 'row' }}
            spacing={2}
            sx={{ alignItems: 'stretch' }}
          >
            <Button
              variant="outlined"
              startIcon={<FolderOpenIcon />}
              onClick={() => folderInputRef.current?.click()}
              disabled={uploading || phase === 'importing'}
              sx={{ whiteSpace: 'nowrap' }}
            >
              Browse Folder
            </Button>
            <TextField
              fullWidth
              label="Folder path"
              placeholder="D:\Historical Timesheets (server path) or use Browse Folder"
              value={sourceLabel || serverPath}
              onChange={(event) => {
                setServerPath(event.target.value);
                setSourceLabel('');
                setBatchId(null);
                setLocalPaths([]);
                setScanResult(null);
                setPhase('setup');
              }}
              disabled={Boolean(batchId) || phase === 'importing'}
            />
          </Stack>

          <input
            ref={folderInputRef}
            type="file"
            hidden
            multiple
            // @ts-expect-error webkitdirectory is supported by Chromium browsers
            webkitdirectory=""
            onChange={handleFolderSelect}
          />

          {uploading ? <LinearProgress sx={{ mt: 2 }} /> : null}

          <Divider sx={{ my: 3 }} />

          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={3}
            sx={{ mb: 2, flexWrap: 'wrap' }}
          >
            <SummaryMetric label="Designers" value={displayDesigners} />
            <SummaryMetric label="Excel Files" value={displayFiles} />
            <SummaryMetric
              label="Estimated Entries"
              value={displayEntries ? formatNumber(displayEntries, 0) : '—'}
            />
          </Stack>

          <FormControlLabel
            sx={{ mb: 2, display: 'block' }}
            control={
              <Checkbox
                checked={ignoreDuplicateCheck}
                onChange={(event) => setIgnoreDuplicateCheck(event.target.checked)}
                disabled={phase === 'importing'}
              />
            }
            label="Ignore duplicate checking (Recommended for first migration)"
          />

          <Stack direction="row" spacing={2}>
            <Button
              variant="contained"
              startIcon={<SearchIcon />}
              onClick={handleScan}
              disabled={loading || phase === 'importing' || (!batchId && !serverPath.trim())}
            >
              Scan Folder
            </Button>
            <Button
              variant="contained"
              color="success"
              startIcon={<PlayArrowIcon />}
              onClick={() => setConfirmOpen(true)}
              disabled={
                loading ||
                phase === 'importing' ||
                !scanResult ||
                scanResult.file_count === 0
              }
            >
              Import All
            </Button>
            {phase !== 'setup' ? (
              <Button variant="text" onClick={resetWizard} disabled={phase === 'importing'}>
                Reset
              </Button>
            ) : null}
          </Stack>
        </CardContent>
      </Card>

      {scanResult && phase !== 'setup' ? (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>
              Scan Results
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Designer</TableCell>
                    <TableCell align="right">Files</TableCell>
                    <TableCell align="right">Entries</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {scanResult.designers.map((row) => (
                    <TableRow key={row.designer}>
                      <TableCell>{row.designer}</TableCell>
                      <TableCell align="right">{row.files}</TableCell>
                      <TableCell align="right">{formatNumber(row.entries, 0)}</TableCell>
                    </TableRow>
                  ))}
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700 }}>Total</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700 }}>
                      {scanResult.file_count}
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700 }}>
                      {formatNumber(scanResult.estimated_entries, 0)}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      ) : null}

      {phase === 'importing' && job ? (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>
              Importing Historical Timesheets
            </Typography>
            <LinearProgress
              variant="determinate"
              value={job.percent_complete}
              sx={{ mb: 2, height: 10, borderRadius: 1 }}
            />
            <Typography variant="body2" sx={{ mb: 2 }}>
              {job.percent_complete}% complete
            </Typography>
            <Stack spacing={1}>
              <Typography variant="body2">
                <strong>Current Designer:</strong> {job.current_designer ?? '—'}
              </Typography>
              <Typography variant="body2">
                <strong>Current File:</strong> {job.current_file ?? '—'}
              </Typography>
              <Typography variant="body2">
                <strong>Rows Imported:</strong>{' '}
                {formatNumber(job.rows_imported, 0)} / {formatNumber(job.rows_total, 0)}
              </Typography>
            </Stack>
            <Button
              sx={{ mt: 2 }}
              variant="outlined"
              color="warning"
              startIcon={<CancelIcon />}
              onClick={handleCancelImport}
              disabled={job.status !== 'running'}
            >
              Cancel Import
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {phase === 'completed' && job?.summary ? (
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>
              Historical Import Completed
            </Typography>
            {job.status === 'cancelled' ? (
              <Alert severity="warning" sx={{ mb: 2 }}>
                Import was cancelled. Partial data may have been saved before cancellation.
              </Alert>
            ) : null}
            {job.status === 'failed' ? (
              <Alert severity="error" sx={{ mb: 2 }}>
                {job.message ?? 'Import failed.'}
              </Alert>
            ) : null}
            <Stack direction="row" spacing={3} sx={{ mb: 3, flexWrap: 'wrap', gap: 2 }}>
              <SummaryMetric label="Rows Read" value={job.summary.rows_read} />
              <SummaryMetric label="Imported" value={job.summary.rows_imported} />
              <SummaryMetric label="Validation Errors" value={job.summary.errors} />
              <SummaryMetric
                label="Duplicate Check"
                value={job.summary.duplicate_check_disabled ? 'Disabled' : 'Enabled'}
              />
              {job.summary.database_reset_performed ? (
                <SummaryMetric label="Database Reset" value="Yes" />
              ) : null}
              <SummaryMetric
                label="Duration"
                value={formatDuration(job.summary.duration_seconds)}
              />
            </Stack>
            {job.summary.backup_path ? (
              <Alert severity="info" sx={{ mb: 2 }}>
                Database backup created at: {job.summary.backup_path}
              </Alert>
            ) : null}
            <Button
              variant="contained"
              startIcon={<DownloadIcon />}
              onClick={handleDownloadLog}
            >
              Download Import Log
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {ignoreDuplicateCheck ? 'Historical Import Mode' : 'Confirm Historical Import'}
        </DialogTitle>
        <DialogContent>
          {ignoreDuplicateCheck ? (
            <>
              <Alert severity="warning" sx={{ mb: 2 }}>
                Duplicate checking has been <strong>DISABLED</strong>.
              </Alert>
              <Typography variant="body2" sx={{ mb: 1 }}>
                All valid rows will be imported exactly as they appear in the Excel files.
              </Typography>
              <Typography variant="body2" sx={{ mb: 2 }}>
                If duplicate records exist, they can be removed later using the Timesheet page.
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Importing {scanResult?.file_count ?? 0} files (
                {formatNumber(scanResult?.estimated_entries ?? 0, 0)} estimated entries).
              </Typography>
              <Alert severity="info">
                A timestamped database backup will be created automatically before import begins.
              </Alert>
            </>
          ) : (
            <>
              <DialogContentText sx={{ mb: 2 }}>
                You are about to import:
              </DialogContentText>
              <Typography variant="body1" sx={{ mb: 1 }}>
                • {scanResult?.file_count ?? 0} Excel files
              </Typography>
              <Typography variant="body1" sx={{ mb: 2 }}>
                • {formatNumber(scanResult?.estimated_entries ?? 0, 0)} entries
              </Typography>
              <Alert severity="warning">
                Normal duplicate detection is enabled. Rows that match existing database
                records may be skipped.
              </Alert>
              <Alert severity="info" sx={{ mt: 2 }}>
                A timestamped database backup will be created automatically before import begins.
              </Alert>
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmOpen(false)}>Cancel</Button>
          <Button variant="contained" color="success" onClick={handleImport}>
            Import
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={resetConfirmOpen}
        onClose={() => !resetting && setResetConfirmOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ color: 'error.main' }}>WARNING</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            This will permanently delete <strong>ALL</strong> timesheet records.
          </DialogContentText>
          <Typography variant="body2" sx={{ mb: 1 }}>
            Users, Customers, Projects and Settings will <strong>NOT</strong> be affected.
          </Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>
            Historical reports will be cleared.
          </Typography>
          <Typography variant="body2" sx={{ mb: 2 }}>
            A database backup will be created automatically before deletion.
          </Typography>
          <Alert severity="error" sx={{ mb: 2 }}>
            Type <strong>DELETE</strong> to continue.
          </Alert>
          <TextField
            fullWidth
            label='Type "DELETE" to confirm'
            value={resetConfirmText}
            onChange={(event) => setResetConfirmText(event.target.value)}
            disabled={resetting}
            autoFocus
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResetConfirmOpen(false)} disabled={resetting}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            disabled={resetting || resetConfirmText.trim() !== 'DELETE'}
            onClick={() => void handleResetAll()}
          >
            Delete All Timesheet Entries
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
