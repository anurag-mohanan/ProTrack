import { useCallback, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
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
import UploadFileIcon from '@mui/icons-material/UploadFile';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DownloadIcon from '@mui/icons-material/Download';
import CancelIcon from '@mui/icons-material/Cancel';
import DeleteForeverIcon from '@mui/icons-material/DeleteForever';
import type {
  MasterImportJobProgress,
  MasterScanResponse,
} from '../types/TimesheetMasterImport';
import {
  cancelMasterImportJob,
  downloadMasterImportLog,
  fetchMasterImportJob,
  resetAllTimesheetData,
  runMasterTimesheetImport,
  uploadMasterTimesheetWorkbook,
} from '../api/timesheetImport';
import { getErrorMessage } from '../api/client';
import { PageHeader } from '../components/common/PageHeader';
import { formatNumber } from '../utils/format';

type WizardPhase = 'setup' | 'scanned' | 'importing' | 'completed';

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
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<WizardPhase>('setup');
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [filename, setFilename] = useState('');
  const [scanResult, setScanResult] = useState<MasterScanResponse | null>(null);
  const [selectedDesigners, setSelectedDesigners] = useState<Set<string>>(new Set());
  const [job, setJob] = useState<MasterImportJobProgress | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [importAll, setImportAll] = useState(true);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);
  const [resetConfirmText, setResetConfirmText] = useState('');
  const [resetBackupPath, setResetBackupPath] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollJob = useCallback(async (jobId: string) => {
    for (let attempt = 0; attempt < 600; attempt += 1) {
      const progress = await fetchMasterImportJob(jobId);
      setJob(progress);
      if (['completed', 'failed', 'cancelled'].includes(progress.status)) {
        setPhase('completed');
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    setError('Import is taking longer than expected. Check back shortly.');
  }, []);

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const result = await uploadMasterTimesheetWorkbook(file);
      setUploadId(result.upload_id);
      setFilename(result.filename);
      setScanResult(result.scan);
      setSelectedDesigners(new Set(result.scan.designers.map((row) => row.designer)));
      setPhase('scanned');
    } catch (err) {
      setError(getErrorMessage(err));
      setPhase('setup');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const toggleDesigner = (designer: string) => {
    setSelectedDesigners((current) => {
      const next = new Set(current);
      if (next.has(designer)) next.delete(designer);
      else next.add(designer);
      return next;
    });
    setImportAll(false);
  };

  const handleImport = async () => {
    if (!uploadId) return;
    setConfirmOpen(false);
    setError(null);
    setLoading(true);
    try {
      const designers = importAll ? undefined : Array.from(selectedDesigners);
      const run = await runMasterTimesheetImport({ upload_id: uploadId, designers });
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
    if (!job?.job_id) return;
    try {
      await cancelMasterImportJob(job.job_id);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  const handleDownloadLog = async () => {
    if (!job?.job_id) return;
    try {
      await downloadMasterImportLog(job.job_id, job.log_download_name ?? undefined);
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
      setResetBackupPath(result.backup_path);
      setResetConfirmOpen(false);
      setResetConfirmText('');
      resetWizard();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setResetting(false);
    }
  };

  const resetWizard = () => {
    setPhase('setup');
    setUploadId(null);
    setFilename('');
    setScanResult(null);
    setSelectedDesigners(new Set());
    setJob(null);
    setImportAll(true);
    setError(null);
  };

  const unmatchedDesigners = useMemo(
    () => scanResult?.designers.filter((row) => !row.user_matched) ?? [],
    [scanResult],
  );

  return (
    <Box>
      <PageHeader
        title="Master Historical Timesheet Import"
        subtitle="One-time migration utility for importing a consolidated historical workbook."
      />

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      ) : null}

      {resetBackupPath ? (
        <Alert severity="success" sx={{ mb: 2 }}>
          Database reset complete. Backup: {resetBackupPath}
        </Alert>
      ) : null}

      <Card sx={{ mb: 3, borderColor: 'error.light', borderWidth: 1, borderStyle: 'solid' }}>
        <CardContent>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1, color: 'error.main' }}>
            Delete All Timesheet Entries
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Clear all timesheet data before a full historical re-import. Users, projects, and
            settings are not affected.
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
            Select Excel File
          </Typography>
          <Button
            variant="outlined"
            startIcon={<UploadFileIcon />}
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading || phase === 'importing'}
          >
            Choose File
          </Button>
          {filename ? (
            <Typography variant="body2" sx={{ mt: 1 }}>
              Selected: <strong>{filename}</strong>
            </Typography>
          ) : null}
          <input
            ref={fileInputRef}
            type="file"
            hidden
            accept=".xlsx,.xlsm"
            onChange={handleFileSelect}
          />
          {uploading ? <LinearProgress sx={{ mt: 2 }} /> : null}
        </CardContent>
      </Card>

      {scanResult ? (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>
              Workbook Information
            </Typography>
            <Stack direction="row" spacing={3} sx={{ mb: 3, flexWrap: 'wrap', gap: 2 }}>
              <SummaryMetric label="Rows Found" value={formatNumber(scanResult.row_count, 0)} />
              <SummaryMetric
                label="Designers Found"
                value={formatNumber(scanResult.designer_count, 0)}
              />
              <SummaryMetric
                label="Date Range"
                value={scanResult.date_range_label ?? '—'}
              />
            </Stack>

            {unmatchedDesigners.length ? (
              <Alert severity="warning" sx={{ mb: 2 }}>
                {unmatchedDesigners.length} designer(s) in the workbook do not match a ProTrack
                user. Their rows will be skipped during import.
              </Alert>
            ) : null}

            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
              Designers
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell padding="checkbox" />
                    <TableCell>Designer</TableCell>
                    <TableCell align="right">Rows</TableCell>
                    <TableCell>Date Range</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {scanResult.designers.map((row) => (
                    <TableRow key={row.designer} hover>
                      <TableCell padding="checkbox">
                        <Checkbox
                          checked={selectedDesigners.has(row.designer)}
                          onChange={() => toggleDesigner(row.designer)}
                          disabled={phase === 'importing'}
                        />
                      </TableCell>
                      <TableCell>{row.designer}</TableCell>
                      <TableCell align="right">{formatNumber(row.rows, 0)}</TableCell>
                      <TableCell>{row.date_range_label}</TableCell>
                      <TableCell>
                        {row.user_matched ? 'Matched' : 'Unknown user'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            <Divider sx={{ my: 3 }} />

            <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap' }}>
              <Button
                variant="contained"
                color="success"
                startIcon={<PlayArrowIcon />}
                disabled={loading || phase === 'importing'}
                onClick={() => {
                  setImportAll(true);
                  setConfirmOpen(true);
                }}
              >
                Import All
              </Button>
              <Button
                variant="contained"
                startIcon={<PlayArrowIcon />}
                disabled={
                  loading || phase === 'importing' || selectedDesigners.size === 0
                }
                onClick={() => {
                  setImportAll(false);
                  setConfirmOpen(true);
                }}
              >
                Import Selected Designers
              </Button>
              {phase !== 'setup' ? (
                <Button variant="text" onClick={resetWizard} disabled={phase === 'importing'}>
                  Reset
                </Button>
              ) : null}
            </Stack>
          </CardContent>
        </Card>
      ) : null}

      {phase === 'importing' && job ? (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
              Progress
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {job.message ?? 'Importing…'}
            </Typography>
            <LinearProgress variant="determinate" value={job.percent_complete} sx={{ mb: 1 }} />
            <Typography variant="body2">
              {formatNumber(job.rows_processed, 0)} / {formatNumber(job.rows_total, 0)} rows
            </Typography>
            {job.current_designer ? (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                Current designer: {job.current_designer}
              </Typography>
            ) : null}
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

      {phase === 'completed' && job?.status === 'failed' && !job.summary ? (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Alert severity="error" sx={{ mb: 2 }}>
              Import failed.
            </Alert>
            <Typography variant="body2" sx={{ mb: 2 }}>
              Reason: {job.message ?? 'Unknown error'}
            </Typography>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              onClick={handleDownloadLog}
            >
              View Log
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
              <SummaryMetric label="Skipped" value={job.summary.rows_skipped} />
              <SummaryMetric label="Errors" value={job.summary.errors} />
              <SummaryMetric
                label="Duplicate Check"
                value={job.summary.duplicate_check_disabled ? 'Disabled' : 'Enabled'}
              />
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
        <DialogTitle>Historical Import Mode</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            This utility is intended for one-time historical migration.
          </Alert>
          <Typography variant="body2" sx={{ mb: 1 }}>
            Duplicate checking is <strong>disabled</strong>.
          </Typography>
          <Typography variant="body2" sx={{ mb: 2 }}>
            All valid rows will be imported exactly as they appear in the Excel file. If duplicate
            records exist, they can be removed later using the Timesheet page.
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {importAll
              ? `Importing all ${formatNumber(scanResult?.row_count ?? 0, 0)} rows.`
              : `Importing ${selectedDesigners.size} selected designer(s).`}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmOpen(false)}>Cancel</Button>
          <Button variant="contained" color="success" onClick={handleImport}>
            Continue
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
          <Typography variant="body2" sx={{ mb: 2 }}>
            This will permanently delete <strong>ALL</strong> timesheet records. A database backup
            will be created automatically before deletion.
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
