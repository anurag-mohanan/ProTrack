import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  FormControl,
  FormControlLabel,
  Grid,
  LinearProgress,
  Paper,
  Radio,
  RadioGroup,
  Stack,
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
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import type {
  DuplicateAction,
  ImportJobProgress,
  ImportRowPreview,
  ImportUploadResponse,
} from '../types/Import';
import {
  downloadImportErrorLogAuthenticated,
  pollImportJob,
  startImportJob,
  uploadImportFile,
} from '../services/importService';
import { getErrorMessage } from '../api/client';

function statusColor(status: ImportRowPreview['status_label']): string {
  if (status === 'ready' || status === 'imported' || status === 'updated') return 'success.main';
  if (status === 'duplicate' || status === 'skipped') return 'warning.main';
  if (status === 'error') return 'error.main';
  return 'text.primary';
}

function SummaryCard({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
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

export function HistoricalImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<ImportUploadResponse | null>(null);
  const [duplicateAction, setDuplicateAction] = useState<DuplicateAction>('skip');
  const [dryRun, setDryRun] = useState(true);
  const [loading, setLoading] = useState(false);
  const [job, setJob] = useState<ImportJobProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  const previewRows = uploadResult?.preview ?? [];
  const errorRows = useMemo(
    () => previewRows.filter((row) => row.status_label === 'error'),
    [previewRows],
  );
  const readyRows = useMemo(
    () => previewRows.filter((row) => row.status_label === 'ready'),
    [previewRows],
  );
  const duplicateRows = useMemo(
    () => previewRows.filter((row) => row.status_label === 'duplicate'),
    [previewRows],
  );

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    setUploadResult(null);
    setJob(null);
    setError(null);
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const result = await uploadImportFile(file);
      setUploadResult(result);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async () => {
    if (!uploadResult) return;
    setLoading(true);
    setError(null);
    setJob(null);
    try {
      const { job_id } = await startImportJob(
        uploadResult.upload_id,
        dryRun,
        duplicateAction,
      );
      const completedJob = await pollImportJob(job_id, setJob);
      setJob(completedJob);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Import Historical Projects
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Upload a Prosohm Tool Tracking workbook (.xlsx / .xlsm) to import historical project data.
        </Typography>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      <Card>
        <CardContent>
          <Stack spacing={2}>
            <Typography variant="h6">1. Upload workbook</Typography>
            <Button variant="outlined" component="label" startIcon={<CloudUploadIcon />}>
              Choose file
              <input
                hidden
                type="file"
                accept=".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel.sheet.macroEnabled.12"
                onChange={handleFileChange}
              />
            </Button>
            {file && (
              <Typography variant="body2">
                Selected: {file.name}
              </Typography>
            )}
            <Button
              variant="contained"
              onClick={handleUpload}
              disabled={!file || loading}
            >
              Analyze file
            </Button>
          </Stack>
        </CardContent>
      </Card>

      {uploadResult && (
        <>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                2. Review analysis
              </Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                  <SummaryCard label="Total rows" value={uploadResult.total_rows} />
                </Grid>
                <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                  <SummaryCard label="Ready" value={uploadResult.ready_rows} />
                </Grid>
                <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                  <SummaryCard label="Duplicates" value={uploadResult.duplicate_rows} />
                </Grid>
                <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                  <SummaryCard label="Errors" value={uploadResult.error_rows} />
                </Grid>
                <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                  <SummaryCard label="Missing customer" value={uploadResult.missing_customer_rows} />
                </Grid>
                <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                  <SummaryCard label="Missing designer" value={uploadResult.missing_designer_rows} />
                </Grid>
              </Grid>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                3. Import options
              </Typography>
              <Stack spacing={2}>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={dryRun}
                      onChange={(event) => setDryRun(event.target.checked)}
                    />
                  }
                  label="Dry run mode (validate without writing to the database)"
                />

                <FormControl>
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    Duplicate tool numbers
                  </Typography>
                  <RadioGroup
                    value={duplicateAction}
                    onChange={(event) =>
                      setDuplicateAction(event.target.value as DuplicateAction)
                    }
                  >
                    <FormControlLabel value="skip" control={<Radio />} label="Skip existing projects" />
                    <FormControlLabel value="update" control={<Radio />} label="Update existing projects" />
                    <FormControlLabel value="create" control={<Radio />} label="Create duplicate projects" />
                  </RadioGroup>
                </FormControl>

                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<PlayArrowIcon />}
                  onClick={handleImport}
                  disabled={loading}
                >
                  {dryRun ? 'Run dry import' : 'Import projects'}
                </Button>
              </Stack>
            </CardContent>
          </Card>

          {(loading || job) && (
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 1 }}>
                  Import progress
                </Typography>
                <LinearProgress
                  variant={job ? 'determinate' : 'indeterminate'}
                  value={job?.percent_complete ?? 0}
                  sx={{ mb: 1 }}
                />
                <Typography variant="body2" color="text.secondary">
                  {job
                    ? `${job.processed_rows} / ${job.total_rows} rows (${job.percent_complete}%)`
                    : 'Starting import...'}
                </Typography>
              </CardContent>
            </Card>
          )}

          {job?.summary && (
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Typography variant="h6">
                    {dryRun ? 'Dry run summary' : 'Import summary'}
                  </Typography>
                  {job.error_log.length > 0 && (
                    <Button
                      startIcon={<DownloadIcon />}
                      onClick={() => downloadImportErrorLogAuthenticated(job.job_id)}
                    >
                      Download error log
                    </Button>
                  )}
                </Box>
                <Grid container spacing={2}>
                  <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                    <SummaryCard label="Projects imported" value={job.summary.projects_imported} />
                  </Grid>
                  <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                    <SummaryCard label="Projects updated" value={job.summary.projects_updated} />
                  </Grid>
                  <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                    <SummaryCard label="Projects skipped" value={job.summary.projects_skipped} />
                  </Grid>
                  <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                    <SummaryCard label="Errors" value={job.summary.errors} />
                  </Grid>
                  <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                    <SummaryCard label="Customers created" value={job.summary.customers_created} />
                  </Grid>
                  <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                    <SummaryCard label="Users created" value={job.summary.users_created} />
                  </Grid>
                  <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                    <SummaryCard label="Milestones created" value={job.summary.milestones_created} />
                  </Grid>
                </Grid>
                {job.message && (
                  <Alert severity="success" sx={{ mt: 2 }}>
                    {job.message}
                  </Alert>
                )}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Preview rows
              </Typography>
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Row</TableCell>
                      <TableCell>Tool No.</TableCell>
                      <TableCell>Customer</TableCell>
                      <TableCell>Designer</TableCell>
                      <TableCell>Phase</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Result</TableCell>
                      <TableCell>Messages</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {previewRows.map((row) => (
                      <TableRow key={row.row_number}>
                        <TableCell>{row.row_number}</TableCell>
                        <TableCell>{row.tool_number ?? '—'}</TableCell>
                        <TableCell>{row.customer ?? '—'}</TableCell>
                        <TableCell>{row.designer ?? '—'}</TableCell>
                        <TableCell>{row.design_phase ?? '—'}</TableCell>
                        <TableCell>{row.status ?? '—'}</TableCell>
                        <TableCell>
                          <Typography variant="body2" color={statusColor(row.status_label)}>
                            {row.status_label}
                          </Typography>
                        </TableCell>
                        <TableCell>{row.messages.join('; ') || '—'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
              {errorRows.length > 0 && (
                <Alert severity="warning" sx={{ mt: 2 }}>
                  {errorRows.length} row(s) have validation errors.
                </Alert>
              )}
              {duplicateRows.length > 0 && (
                <Alert severity="info" sx={{ mt: 2 }}>
                  {duplicateRows.length} duplicate tool number(s) detected. Choose how to handle them before importing.
                </Alert>
              )}
              {readyRows.length > 0 && (
                <Alert severity="success" sx={{ mt: 2 }}>
                  {readyRows.length} row(s) are ready to import.
                </Alert>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </Stack>
  );
}
