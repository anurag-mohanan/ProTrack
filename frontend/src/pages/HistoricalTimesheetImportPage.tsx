import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  Alert,
  Button,
  Card,
  CardContent,
  FormControl,
  FormControlLabel,
  Grid,
  LinearProgress,
  Paper,
  Radio,
  RadioGroup,
  Stack,
  Step,
  StepLabel,
  Stepper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DownloadIcon from '@mui/icons-material/Download';
import HistoryIcon from '@mui/icons-material/History';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import RefreshIcon from '@mui/icons-material/Refresh';
import type {
  DuplicateWeekAction,
  TimesheetImportHistoryRead,
  TimesheetImportJobProgress,
  TimesheetImportRowPreview,
  TimesheetImportUploadResponse,
  TimesheetImportValidateResponse,
} from '../types/TimesheetImport';
import {
  downloadTimesheetImportErrorLog,
  pollTimesheetImportJob,
  saveTimesheetImportResolutions,
  startTimesheetImportJob,
  uploadTimesheetImportFile,
  validateTimesheetImportFile,
} from '../services/timesheetImportService';
import {
  fetchTimesheetImportHistory,
  reimportTimesheetHistory,
} from '../api/timesheetImport';
import { getErrorMessage } from '../api/client';
import { PageHeader } from '../components/common/PageHeader';
import { formatCellValue } from '../utils/format';

const STEPS = ['Upload', 'Preview', 'Validate', 'Resolve', 'Import', 'Summary'];

function statusColor(status: TimesheetImportRowPreview['status_label']): string {
  if (status === 'ready' || status === 'imported') return 'success.main';
  if (status === 'warning' || status === 'skipped') return 'warning.main';
  if (status === 'error') return 'error.main';
  return 'text.primary';
}

function SummaryCard({ label, value }: { label: string; value: number | string }) {
  return (
    <Paper sx={{ p: 2, textAlign: 'center' }}>
      <Typography variant="h4" color="primary">
        {value}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
    </Paper>
  );
}

export function HistoricalTimesheetImportPage() {
  const location = useLocation();
  const [activeStep, setActiveStep] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<TimesheetImportUploadResponse | null>(null);
  const [validation, setValidation] = useState<TimesheetImportValidateResponse | null>(null);
  const [duplicateWeekAction, setDuplicateWeekAction] = useState<DuplicateWeekAction>('skip');
  const [createDesigner, setCreateDesigner] = useState(false);
  const [loading, setLoading] = useState(false);
  const [job, setJob] = useState<TimesheetImportJobProgress | null>(null);
  const [history, setHistory] = useState<TimesheetImportHistoryRead[]>([]);
  const [error, setError] = useState<string | null>(null);

  const previewRows = uploadResult?.preview ?? [];
  const errorRows = useMemo(
    () => previewRows.filter((row) => row.status_label === 'error'),
    [previewRows],
  );
  const missingProjectRows = useMemo(
    () =>
      previewRows.filter(
        (row) => !row.is_np_row && !row.matched_project_id && row.status_label !== 'error',
      ),
    [previewRows],
  );

  useEffect(() => {
    fetchTimesheetImportHistory()
      .then(setHistory)
      .catch(() => undefined);
  }, [job]);

  useEffect(() => {
    if (location.hash !== '#history') return;
    const timer = window.setTimeout(() => {
      document.getElementById('import-history')?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    }, 100);
    return () => window.clearTimeout(timer);
  }, [location.hash, history.length]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFile(event.target.files?.[0] ?? null);
    setUploadResult(null);
    setValidation(null);
    setJob(null);
    setError(null);
    setActiveStep(0);
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const result = await uploadTimesheetImportFile(file);
      setUploadResult(result);
      setCreateDesigner(result.designer.requires_resolution);
      setActiveStep(1);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleValidate = async () => {
    if (!uploadResult) return;
    setLoading(true);
    setError(null);
    try {
      const result = await validateTimesheetImportFile(uploadResult.upload_id);
      setValidation(result);
      setActiveStep(2);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async () => {
    if (!uploadResult) return;
    setLoading(true);
    setError(null);
    try {
      await saveTimesheetImportResolutions({
        upload_id: uploadResult.upload_id,
        duplicate_week_action: duplicateWeekAction,
        designer: uploadResult.designer.requires_resolution
          ? createDesigner
            ? { action: 'create_new' }
            : uploadResult.designer.matched_user_id
              ? { action: 'match_existing', user_id: uploadResult.designer.matched_user_id }
              : { action: 'create_new' }
          : uploadResult.designer.matched_user_id
            ? { action: 'match_existing', user_id: uploadResult.designer.matched_user_id }
            : { action: 'create_new' },
        project_resolutions: missingProjectRows.map((row) => ({
          row_number: row.row_number,
          action: 'create',
        })),
      });
      setActiveStep(4);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async (dryRun: boolean) => {
    if (!uploadResult) return;
    setLoading(true);
    setError(null);
    setJob(null);
    try {
      const designerResolution = uploadResult.designer.requires_resolution
        ? createDesigner
          ? { action: 'create_new' as const }
          : uploadResult.designer.matched_user_id
            ? { action: 'match_existing' as const, user_id: uploadResult.designer.matched_user_id }
            : { action: 'create_new' as const }
        : uploadResult.designer.matched_user_id
          ? { action: 'match_existing' as const, user_id: uploadResult.designer.matched_user_id }
          : { action: 'create_new' as const };

      const { job_id } = await startTimesheetImportJob(
        uploadResult.upload_id,
        dryRun,
        duplicateWeekAction,
        designerResolution,
      );
      const completedJob = await pollTimesheetImportJob(job_id, setJob);
      setJob(completedJob);
      setActiveStep(5);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleReimport = async (historyId: string) => {
    setLoading(true);
    setError(null);
    try {
      const { job_id } = await reimportTimesheetHistory(historyId);
      const completedJob = await pollTimesheetImportJob(job_id, setJob);
      setJob(completedJob);
      setActiveStep(5);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Stack spacing={3}>
      <PageHeader
        title="Import Historical Timesheets"
        subtitle="Upload a designer timesheet (.xlsx, .xlsm, or .csv) to import historical hours"
      />

      {error && <Alert severity="error">{error}</Alert>}

      <Stepper activeStep={activeStep} alternativeLabel>
        {STEPS.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {activeStep === 0 && (
        <Card>
          <CardContent>
            <Stack spacing={2}>
              <Typography variant="h6">1. Upload file</Typography>
              <Typography variant="body2" color="text.secondary">
                Import one designer timesheet at a time. You can upload multiple files in sequence.
              </Typography>
              <Button variant="outlined" component="label" startIcon={<CloudUploadIcon />}>
                Choose file
                <input
                  hidden
                  type="file"
                  accept=".xlsx,.xlsm,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
                  onChange={handleFileChange}
                />
              </Button>
              {file && <Typography variant="body2">Selected: {file.name}</Typography>}
              <Button variant="contained" onClick={handleUpload} disabled={!file || loading}>
                Upload and analyze
              </Button>
            </Stack>
          </CardContent>
        </Card>
      )}

      {uploadResult && activeStep >= 1 && (
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              2. Preview
            </Typography>
            <Grid container spacing={2} sx={{ mb: 2 }}>
              <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                <SummaryCard label="Total rows" value={uploadResult.total_rows} />
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                <SummaryCard label="Ready" value={uploadResult.ready_rows} />
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                <SummaryCard label="Errors" value={uploadResult.error_rows} />
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                <SummaryCard label="Warnings" value={uploadResult.warning_rows} />
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                <SummaryCard
                  label="Designer"
                  value={uploadResult.designer.detected_name}
                />
              </Grid>
            </Grid>

            {uploadResult.duplicate_weeks.length > 0 && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                Duplicate import detected for{' '}
                {uploadResult.duplicate_weeks.map((w) => w.week_label).join(', ')}.
              </Alert>
            )}

            <TableContainer component={Paper} sx={{ maxHeight: 360 }}>
              <Table stickyHeader size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Row</TableCell>
                    <TableCell>Date</TableCell>
                    <TableCell>Project</TableCell>
                    <TableCell>Task / NP</TableCell>
                    <TableCell>Hours</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {previewRows.slice(0, 100).map((row) => (
                    <TableRow key={row.row_number}>
                      <TableCell>{row.row_number}</TableCell>
                      <TableCell>{formatCellValue(row.entry_date)}</TableCell>
                      <TableCell>{formatCellValue(row.tool_number) || formatCellValue(row.project_code)}</TableCell>
                      <TableCell>{formatCellValue(row.task_type) || formatCellValue(row.np_code)}</TableCell>
                      <TableCell>{formatCellValue(row.hours)}</TableCell>
                      <TableCell sx={{ color: statusColor(row.status_label) }}>
                        {row.status_label}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            {activeStep === 1 && (
              <Button sx={{ mt: 2 }} variant="contained" onClick={handleValidate} disabled={loading}>
                Continue to validation
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {validation && activeStep >= 2 && (
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              3. Validate
            </Typography>
            <Alert severity={validation.is_valid ? 'success' : 'error'} sx={{ mb: 2 }}>
              {validation.is_valid
                ? 'All rows passed validation.'
                : `${validation.error_rows} validation error(s) found.`}
            </Alert>
            {validation.issues.length > 0 && (
              <TableContainer component={Paper} sx={{ maxHeight: 240, mb: 2 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Row</TableCell>
                      <TableCell>Severity</TableCell>
                      <TableCell>Message</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {validation.issues.map((issue, idx) => (
                      <TableRow key={`${issue.code}-${idx}`}>
                        <TableCell>{formatCellValue(issue.row_number)}</TableCell>
                        <TableCell>{issue.severity}</TableCell>
                        <TableCell>{issue.message}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
            {activeStep === 2 && (
              <Button variant="contained" onClick={() => setActiveStep(3)} disabled={loading}>
                Continue to resolve
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {uploadResult && activeStep >= 3 && (
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              4. Resolve missing data
            </Typography>

            {uploadResult.designer.requires_resolution && (
              <FormControlLabel
                control={
                  <Radio
                    checked={createDesigner}
                    onChange={() => setCreateDesigner(true)}
                  />
                }
                label={`Create new user for "${uploadResult.designer.detected_name}"`}
              />
            )}

            {uploadResult.duplicate_weeks.length > 0 && (
              <FormControl sx={{ mt: 2, display: 'block' }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Duplicate week action
                </Typography>
                <RadioGroup
                  value={duplicateWeekAction}
                  onChange={(e) => setDuplicateWeekAction(e.target.value as DuplicateWeekAction)}
                >
                  <FormControlLabel value="skip" control={<Radio />} label="Skip" />
                  <FormControlLabel value="replace" control={<Radio />} label="Replace" />
                  <FormControlLabel value="merge" control={<Radio />} label="Merge" />
                </RadioGroup>
              </FormControl>
            )}

            {missingProjectRows.length > 0 && (
              <Alert severity="info" sx={{ mt: 2 }}>
                {missingProjectRows.length} row(s) with missing projects will create new projects on
                import.
              </Alert>
            )}

            {activeStep === 3 && (
              <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
                <Button variant="contained" onClick={handleResolve} disabled={loading}>
                  Save resolutions
                </Button>
                <Button variant="outlined" onClick={() => setActiveStep(4)}>
                  Continue to import
                </Button>
              </Stack>
            )}
          </CardContent>
        </Card>
      )}

      {uploadResult && activeStep >= 4 && !job && (
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              5. Import
            </Typography>
            <Stack direction="row" spacing={2}>
              <Button
                variant="outlined"
                startIcon={<PlayArrowIcon />}
                onClick={() => handleImport(true)}
                disabled={loading || errorRows.length > 0}
              >
                Dry run
              </Button>
              <Button
                variant="contained"
                startIcon={<PlayArrowIcon />}
                onClick={() => handleImport(false)}
                disabled={loading || errorRows.length > 0}
              >
                Import
              </Button>
            </Stack>
            {loading && <LinearProgress sx={{ mt: 2 }} />}
          </CardContent>
        </Card>
      )}

      {job && activeStep >= 5 && (
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              6. Summary
            </Typography>
            {job.status === 'failed' && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {job.message ?? 'Import failed. All changes were rolled back.'}
              </Alert>
            )}
            {job.summary && (
              <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                  <SummaryCard label="Rows read" value={job.summary.rows_read} />
                </Grid>
                <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                  <SummaryCard label="Imported" value={job.summary.rows_imported} />
                </Grid>
                <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                  <SummaryCard label="Skipped" value={job.summary.rows_skipped} />
                </Grid>
                <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                  <SummaryCard label="Failed" value={job.summary.rows_failed} />
                </Grid>
                <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                  <SummaryCard label="NP entries" value={job.summary.np_entries} />
                </Grid>
                <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                  <SummaryCard label="Projects created" value={job.summary.projects_created} />
                </Grid>
              </Grid>
            )}
            <Stack direction="row" spacing={2}>
              <Button
                variant="outlined"
                startIcon={<DownloadIcon />}
                onClick={() => downloadTimesheetImportErrorLog(job.job_id)}
              >
                Download log
              </Button>
              <Button
                variant="outlined"
                startIcon={<RefreshIcon />}
                onClick={() => {
                  setFile(null);
                  setUploadResult(null);
                  setValidation(null);
                  setJob(null);
                  setActiveStep(0);
                }}
              >
                Import another file
              </Button>
            </Stack>
          </CardContent>
        </Card>
      )}

      <Card id="import-history">
        <CardContent>
          <Stack direction="row" spacing={1} sx={{ mb: 2, alignItems: 'center' }}>
            <HistoryIcon color="primary" />
            <Typography variant="h6">Import history</Typography>
          </Stack>
          {history.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No imports yet.
            </Typography>
          ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>File</TableCell>
                    <TableCell>Designer</TableCell>
                    <TableCell>Period</TableCell>
                    <TableCell>Imported</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {history.map((record) => (
                    <TableRow key={record.id}>
                      <TableCell>{record.filename}</TableCell>
                      <TableCell>{record.designer_name}</TableCell>
                      <TableCell>{formatCellValue(record.date_range_label)}</TableCell>
                      <TableCell>{record.rows_imported}</TableCell>
                      <TableCell>{record.status}</TableCell>
                      <TableCell align="right">
                        <Button
                          size="small"
                          disabled={loading}
                          onClick={() => handleReimport(record.id)}
                        >
                          Re-import
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>
    </Stack>
  );
}
