import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  FormControlLabel,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Paper,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded';
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded';
import InsightsRoundedIcon from '@mui/icons-material/InsightsRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import AssessmentRoundedIcon from '@mui/icons-material/AssessmentRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { AnalyticsBarChart } from '../analytics/AnalyticsCharts';
import { KpiMetricCard } from '../ui/design-system';
import { CustomerTimesheetPackPanel } from './CustomerTimesheetPackPanel';
import { useGeneratedReportQuery } from '../../hooks/useGeneratedReportQuery';
import {
  ReportPeriodSelectors,
  syncAnchorForPeriodChange,
} from './ReportPeriodSelectors';
import { fetchCustomers, fetchTeams } from '../../api/lookups';
import {
  downloadEngineeringReportExcel,
  engineeringReportQueryKeys,
  fetchEngineeringReportCatalog,
  fetchEngineeringReportPreview,
  fetchEngineeringReportSchedules,
  isDesignerTeamTimesheetReport,
  saveEngineeringReportSchedule,
} from '../../api/engineeringReporting';
import type {
  CustomerHoursRow,
  DesignerProductivityRow,
  DesignerTeamTimesheetPayload,
  DesignerToolBreakdownRow,
  DetailedTimesheetRow,
  EngineeringReportOptions,
  EngineeringReportPayload,
  ExecutiveKpiCard,
  FunctionHoursRow,
  LeaveAnalysisRow,
  NpAnalysisRow,
  ProjectPerformanceRow,
  QuotedVsActualRow,
  ReportCatalogEntry,
  ReportScheduleEntry,
  TeamSummaryRow,
  ToolHoursRow,
} from '../../types/EngineeringReporting';
import type { Customer } from '../../types';
import type { Team } from '../../types/Team';
import { formatNumber } from '../../utils/format';
import { ensureArray } from '../../types/pagination';
import { defaultAnchorForPeriod } from '../../utils/reportPeriodSelection';

const CATEGORY_LABELS: Record<string, string> = {
  executive: 'Engineering Overview',
  timesheets: 'Timesheet Reports',
  customers: 'Customer Reports',
};

const EXCEL_SHEETS = [
  'Executive Summary',
  'Designer Productivity',
  'Designer Tool Breakdown',
  'Tool Hours',
  'Customer Summary',
  'Team Summary',
  'Function Hours',
  'Non-Productive Analysis',
  'Leave Analysis',
  'Quoted vs Actual',
  'Project Performance',
  'Detailed Entries',
  'Charts',
  'AI Insights',
] as const;

interface EngineeringReportingSuiteProps {
  canExport: boolean;
  includeArchived: boolean;
  includeDeleted: boolean;
  /** Prefer this catalog report when the suite mounts (e.g. Timesheet Reports tab). */
  initialReportId?: string;
}

function currentMonthAnchor(): string {
  return defaultAnchorForPeriod('monthly');
}

export function EngineeringReportingSuite({
  canExport,
  includeArchived,
  includeDeleted,
  initialReportId = 'monthly-engineering',
}: EngineeringReportingSuiteProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedReportId, setSelectedReportId] = useState(initialReportId);
  const [periodType, setPeriodType] = useState(
    isDesignerTeamTimesheetReport(initialReportId)
      ? initialReportId.replace('-timesheet', '')
      : 'monthly',
  );
  const [anchor, setAnchor] = useState(currentMonthAnchor());
  const [customerId, setCustomerId] = useState('');
  const [teamId, setTeamId] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const catalogQuery = useQuery({
    queryKey: engineeringReportQueryKeys.catalog,
    queryFn: fetchEngineeringReportCatalog,
    staleTime: 10 * 60 * 1000,
  });

  const schedulesQuery = useQuery({
    queryKey: engineeringReportQueryKeys.schedules,
    queryFn: fetchEngineeringReportSchedules,
    staleTime: 60 * 1000,
  });

  const customersQuery = useQuery({
    queryKey: ['lookups', 'customers'],
    queryFn: fetchCustomers,
    staleTime: 5 * 60 * 1000,
  });
  const teamsQuery = useQuery({
    queryKey: ['lookups', 'teams', 'reports'],
    queryFn: () => fetchTeams({ forReports: true }),
    staleTime: 5 * 60 * 1000,
  });

  const teams = ensureArray<Team>(teamsQuery.data);
  const customers = ensureArray<Customer>(customersQuery.data);
  const multiTeam = teams.length > 1;

  const catalogReports = ensureArray<ReportCatalogEntry>(catalogQuery.data?.reports);

  const selectedReport = useMemo(
    () => catalogReports.find((report) => report.id === selectedReportId),
    [catalogReports, selectedReportId],
  );

  const isCustomerTimesheetPack = selectedReportId === 'customer-timesheet-pack';
  const isDesignerTeamTimesheet = isDesignerTeamTimesheetReport(selectedReportId);

  const reportOptions: EngineeringReportOptions = useMemo(
    () => ({
      period_type: periodType,
      anchor,
      customer_id: customerId || undefined,
      team_id: teamId || undefined,
      include_archived: includeArchived,
      include_deleted: includeDeleted,
    }),
    [periodType, anchor, customerId, teamId, includeArchived, includeDeleted],
  );

  const previewQuery = useGeneratedReportQuery({
    queryKey: engineeringReportQueryKeys.preview(selectedReportId, reportOptions),
    queryFn: () => fetchEngineeringReportPreview(selectedReportId, reportOptions),
    ready: Boolean(selectedReportId) && !isCustomerTimesheetPack,
  });

  const scheduleMutation = useMutation({
    mutationFn: saveEngineeringReportSchedule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: engineeringReportQueryKeys.schedules });
    },
  });

  const groupedReports = useMemo(() => {
    const groups = new Map<string, ReportCatalogEntry[]>();
    for (const report of catalogReports) {
      const list = groups.get(report.category) ?? [];
      list.push(report);
      groups.set(report.category, list);
    }
    return groups;
  }, [catalogReports]);

  const scheduled = ensureArray<ReportScheduleEntry>(schedulesQuery.data).find(
    (entry) => entry.report_id === selectedReportId,
  );

  const handleDownload = async () => {
    if (!canExport || isCustomerTimesheetPack || !previewQuery.canDownload) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadEngineeringReportExcel(selectedReportId, reportOptions);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : 'Download failed');
    } finally {
      setDownloading(false);
    }
  };

  const handleScheduleToggle = (enabled: boolean) => {
    scheduleMutation.mutate({
      report_id: selectedReportId,
      period_type: periodType,
      frequency: periodType === 'weekly' ? 'weekly' : periodType === 'quarterly' ? 'quarterly' : 'monthly',
      enabled,
    });
  };

  if (catalogQuery.isLoading) {
    return <LoadingState message="Loading engineering report catalog…" />;
  }
  if (catalogQuery.error) {
    return <ErrorState error={catalogQuery.error} />;
  }

  const payload = previewQuery.hasGenerated ? previewQuery.data : undefined;
  const engineeringPayload =
    payload && 'executive' in payload ? (payload as EngineeringReportPayload) : null;
  const timesheetPayload =
    payload && 'designers' in payload ? (payload as DesignerTeamTimesheetPayload) : null;
  const customerChart = ensureArray<{ title: string; labels: string[]; values: number[] }>(
    engineeringPayload?.charts,
  ).find((chart) => chart.title.toLowerCase().includes('customer'));

  return (
    <Stack spacing={3}>
      <Paper sx={{ p: 2.5, overflow: 'hidden' }}>
        <Stack spacing={2}>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h6">Engineering Management Reporting Suite</Typography>
            <Typography variant="body2" color="text.secondary">
              Filter Customer → Team → Week/Month. Team leaders can only download their own teams.
            </Typography>
          </Box>
          {!isCustomerTimesheetPack ? (
            <Stack spacing={1.5}>
              <Box
                sx={{
                  display: 'grid',
                  gap: 1.5,
                  width: '100%',
                  minWidth: 0,
                  gridTemplateColumns: {
                    xs: '1fr',
                    sm: 'repeat(2, minmax(0, 1fr))',
                    md: 'repeat(3, minmax(0, 1fr))',
                    lg: 'repeat(4, minmax(0, 1fr))',
                  },
                  '& > *': { minWidth: 0, width: '100%' },
                }}
              >
                <TextField
                  select
                  size="small"
                  label="Customer"
                  value={customerId}
                  onChange={(event) => setCustomerId(event.target.value)}
                  fullWidth
                  helperText="Optional"
                  slotProps={{ inputLabel: { shrink: true } }}
                >
                  <MenuItem value="">All customers</MenuItem>
                  {customers.map((customer) => (
                    <MenuItem key={customer.id} value={customer.id}>
                      {customer.name}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField
                  select
                  size="small"
                  label="Team"
                  value={teamId}
                  onChange={(event) => setTeamId(event.target.value)}
                  fullWidth
                  helperText={
                    multiTeam
                      ? 'Leaders: pick one or all accessible'
                      : 'Your accessible teams only'
                  }
                  slotProps={{ inputLabel: { shrink: true } }}
                >
                  <MenuItem value="">All accessible teams</MenuItem>
                  {teams.map((team) => (
                    <MenuItem key={team.id} value={team.id}>
                      {team.name}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField
                  select
                  size="small"
                  label="Period"
                  value={periodType}
                  onChange={(event) => {
                    const next = event.target.value;
                    setPeriodType(next);
                    setAnchor((current) => syncAnchorForPeriodChange(next, current));
                  }}
                  fullWidth
                >
                  {(selectedReport?.supported_periods ?? ['monthly']).map((period) => (
                    <MenuItem key={period} value={period}>
                      {period.charAt(0).toUpperCase() + period.slice(1)}
                    </MenuItem>
                  ))}
                </TextField>
                <ReportPeriodSelectors
                  periodType={periodType}
                  anchor={anchor}
                  onAnchorChange={setAnchor}
                  fluid
                />
              </Box>
              <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                <Button
                  variant="contained"
                  startIcon={<PlayArrowRoundedIcon />}
                  onClick={() => previewQuery.generate()}
                  disabled={!selectedReportId || previewQuery.isFetching}
                >
                  {previewQuery.isFetching ? 'Generating…' : 'Generate'}
                </Button>
                {canExport ? (
                  <Button
                    variant="outlined"
                    startIcon={<DownloadRoundedIcon />}
                    onClick={() => void handleDownload()}
                    disabled={!previewQuery.canDownload || downloading}
                  >
                    {downloading ? 'Downloading…' : 'Download Excel'}
                  </Button>
                ) : null}
              </Stack>
            </Stack>
          ) : (
            <Chip
              size="small"
              color="primary"
              label="Use Customer / Team / Week-Month filters below"
              sx={{ alignSelf: 'flex-start' }}
            />
          )}
        </Stack>
        {downloadError ? <Alert severity="error" sx={{ mt: 2 }}>{downloadError}</Alert> : null}
      </Paper>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 280px) minmax(0, 1fr)' },
          gap: 2,
          width: '100%',
          minWidth: 0,
        }}
      >
        <Paper sx={{ p: 2, height: '100%' }}>
          <Typography variant="subtitle1" sx={{ mb: 1.5 }}>
            Report Catalog
          </Typography>
          <Stack spacing={2}>
            {[...groupedReports.entries()].map(([category, reports]) => (
              <Box key={category}>
                <Typography variant="overline" color="text.secondary">
                  {CATEGORY_LABELS[category] ?? category}
                </Typography>
                <Stack spacing={0.5} sx={{ mt: 0.5 }}>
                  {reports.map((report) => (
                    <Button
                      key={report.id}
                      variant={report.id === selectedReportId ? 'contained' : 'text'}
                      onClick={() => {
                        setSelectedReportId(report.id);
                        const nextPeriod = report.supported_periods.includes(periodType)
                          ? periodType
                          : (report.supported_periods[0] ?? 'monthly');
                        setPeriodType(nextPeriod);
                        setAnchor((current) => syncAnchorForPeriodChange(nextPeriod, current));
                      }}
                      sx={{ justifyContent: 'flex-start', textAlign: 'left' }}
                    >
                      {report.title}
                    </Button>
                  ))}
                </Stack>
              </Box>
            ))}
          </Stack>
        </Paper>

        <Stack spacing={2}>
          <Paper sx={{ p: 2 }}>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                gap: 2,
                flexWrap: 'wrap',
              }}
            >
              <Box>
                <Typography variant="h6">{selectedReport?.title ?? 'Report Preview'}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {selectedReport?.description}
                </Typography>
                {!isCustomerTimesheetPack && (engineeringPayload || timesheetPayload) ? (
                  <Chip
                    size="small"
                    label={
                      (engineeringPayload ?? timesheetPayload)?.period.label ?? ''
                    }
                    sx={{ mt: 1 }}
                  />
                ) : null}
              </Box>
              {!isCustomerTimesheetPack ? (
                <FormControlLabel
                  control={
                    <Switch
                      checked={Boolean(scheduled?.enabled)}
                      onChange={(_, checked) => handleScheduleToggle(checked)}
                    />
                  }
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <ScheduleRoundedIcon fontSize="small" />
                      <span>Schedule</span>
                    </Box>
                  }
                />
              ) : null}
            </Box>
            {!isCustomerTimesheetPack && scheduled?.enabled ? (
              <Alert severity="info" sx={{ mt: 1.5 }}>
                {scheduled.note}
              </Alert>
            ) : null}
          </Paper>

          {isCustomerTimesheetPack ? (
            <CustomerTimesheetPackPanel canExport={canExport} embedded />
          ) : (
            <>
          {isCustomerTimesheetPack ? null : !previewQuery.generationRequested ? (
            <Alert severity="info" sx={{ mb: 2 }}>
              Choose a report and filters, then click Generate to preview results. Download Excel
              unlocks after generate.
            </Alert>
          ) : null}
          {previewQuery.generationRequested && previewQuery.isLoading ? (
            <LoadingState message="Building report preview…" />
          ) : null}
          {previewQuery.error ? <ErrorState error={previewQuery.error} /> : null}

          {isDesignerTeamTimesheet && timesheetPayload ? (
            <>
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: {
                    xs: '1fr',
                    sm: 'repeat(2, 1fr)',
                    md: 'repeat(4, 1fr)',
                  },
                  gap: 2,
                }}
              >
                <KpiMetricCard
                  title="Period designer hours"
                  value={formatNumber(timesheetPayload.total_designer_hours)}
                  icon={AssessmentRoundedIcon}
                  accent="primary"
                  compact
                />
                <KpiMetricCard
                  title="Designers"
                  value={String(timesheetPayload.designer_count)}
                  icon={AssessmentRoundedIcon}
                  accent="primary"
                  compact
                />
                <KpiMetricCard
                  title="Teams"
                  value={String(timesheetPayload.team_count)}
                  icon={AssessmentRoundedIcon}
                  accent="primary"
                  compact
                />
                <KpiMetricCard
                  title="Project hours to date"
                  value={formatNumber(timesheetPayload.total_project_actual_hours)}
                  icon={AssessmentRoundedIcon}
                  accent="primary"
                  compact
                />
              </Box>

              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" sx={{ mb: 0.5 }}>
                  Individual designer hours by team
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  Hours booked in {timesheetPayload.period.label}
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Team</TableCell>
                        <TableCell>Designer</TableCell>
                        <TableCell align="right">Productive</TableCell>
                        <TableCell align="right">NP</TableCell>
                        <TableCell align="right">Leave days</TableCell>
                        <TableCell align="right">Total</TableCell>
                        <TableCell align="right">Utilization</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {ensureArray<DesignerProductivityRow>(timesheetPayload.designers).map((row) => (
                        <TableRow
                          key={row.user_id}
                          hover
                          sx={{ cursor: 'pointer' }}
                          onClick={() => navigate(`/dashboard?user=${row.user_id}`)}
                        >
                          <TableCell>{row.team_name ?? '—'}</TableCell>
                          <TableCell>{row.designer_name}</TableCell>
                          <TableCell align="right">{formatNumber(row.productive_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.non_productive_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.leave_days)}</TableCell>
                          <TableCell align="right">{formatNumber(row.total_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.utilization_percent)}%</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>

              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" sx={{ mb: 0.5 }}>
                  Total project hours to date
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  Cumulative as of {new Date(timesheetPayload.generated_at).toLocaleString()}
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Tool</TableCell>
                        <TableCell>Customer</TableCell>
                        <TableCell align="right">Quoted</TableCell>
                        <TableCell align="right">Actual to date</TableCell>
                        <TableCell align="right">Variance</TableCell>
                        <TableCell align="right">Completion</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {ensureArray<ToolHoursRow>(timesheetPayload.projects).slice(0, 40).map((row) => (
                        <TableRow
                          key={`${row.tool_number}-${row.customer_name}`}
                          hover
                          sx={{ cursor: row.project_id ? 'pointer' : 'default' }}
                          onClick={() => {
                            if (row.project_id) navigate(`/projects/${row.project_id}`);
                          }}
                        >
                          <TableCell>{row.tool_number}</TableCell>
                          <TableCell>{row.customer_name}</TableCell>
                          <TableCell align="right">{formatNumber(row.quoted_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.actual_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.variance_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.completion_percent)}%</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>
            </>
          ) : null}

          {!isDesignerTeamTimesheet && engineeringPayload ? (
            <>
              <Alert severity="info" variant="outlined">
                Excel download includes all {EXCEL_SHEETS.length} workbook sheets used in prior production
                reports ({EXCEL_SHEETS.join(' · ')}). Preview below shows key sections; open the Excel file for
                full row-level detail.
              </Alert>

              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: {
                    xs: '1fr',
                    sm: 'repeat(2, 1fr)',
                    md: 'repeat(3, 1fr)',
                    lg: 'repeat(4, 1fr)',
                  },
                  gap: 2,
                }}
              >
                {ensureArray<ExecutiveKpiCard>(engineeringPayload.executive?.kpis).map((kpi) => (
                  <KpiMetricCard
                    key={kpi.label}
                    title={kpi.label}
                    value={kpi.value}
                    icon={AssessmentRoundedIcon}
                    accent="primary"
                    compact
                  />
                ))}
              </Box>

              {customerChart ? (
                <Paper sx={{ p: 2 }}>
                  <Typography variant="subtitle1" sx={{ mb: 1 }}>
                    {customerChart.title}
                  </Typography>
                  <AnalyticsBarChart
                    categories={customerChart.labels}
                    series={[{ label: 'Hours', data: customerChart.values }]}
                    height={260}
                  />
                </Paper>
              ) : null}

              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                  Designer Productivity
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Designer</TableCell>
                        <TableCell>Team</TableCell>
                        <TableCell align="right">Productive</TableCell>
                        <TableCell align="right">NP</TableCell>
                        <TableCell align="right">Total</TableCell>
                        <TableCell align="right">Billable %</TableCell>
                        <TableCell align="right">Utilization</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {ensureArray<DesignerProductivityRow>(engineeringPayload.designer_productivity).slice(0, 12).map((row) => (
                        <TableRow
                          key={row.user_id}
                          hover
                          sx={{ cursor: 'pointer' }}
                          onClick={() => navigate(`/dashboard?user=${row.user_id}`)}
                        >
                          <TableCell>{row.designer_name}</TableCell>
                          <TableCell>{row.team_name ?? '—'}</TableCell>
                          <TableCell align="right">{formatNumber(row.productive_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.non_productive_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.total_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.billable_percent)}%</TableCell>
                          <TableCell align="right">{formatNumber(row.utilization_percent)}%</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>

              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                  Designer Tool Breakdown (preview)
                </Typography>
                <TableContainer sx={{ maxHeight: 320 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell>Designer</TableCell>
                        <TableCell>Tool</TableCell>
                        <TableCell>Customer</TableCell>
                        <TableCell align="right">Design</TableCell>
                        <TableCell align="right">Surfacing</TableCell>
                        <TableCell align="right">NP</TableCell>
                        <TableCell align="right">Total</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {ensureArray<DesignerToolBreakdownRow>(engineeringPayload.designer_tool_breakdown)
                        .slice(0, 25)
                        .map((row) => (
                          <TableRow key={`${row.designer_name}-${row.tool_number}-${row.customer_name}`} hover>
                            <TableCell>{row.designer_name}</TableCell>
                            <TableCell>{row.tool_number}</TableCell>
                            <TableCell>{row.customer_name}</TableCell>
                            <TableCell align="right">{formatNumber(row.design_hours)}</TableCell>
                            <TableCell align="right">{formatNumber(row.surfacing_hours)}</TableCell>
                            <TableCell align="right">{formatNumber(row.np_hours)}</TableCell>
                            <TableCell align="right">{formatNumber(row.total_hours)}</TableCell>
                          </TableRow>
                        ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>

              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                  Tool Hours
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Tool</TableCell>
                        <TableCell>Customer</TableCell>
                        <TableCell align="right">Quoted</TableCell>
                        <TableCell align="right">Original</TableCell>
                        <TableCell align="right">Additional</TableCell>
                        <TableCell align="right">Rework</TableCell>
                        <TableCell align="right">Total</TableCell>
                        <TableCell align="right">Variance</TableCell>
                        <TableCell align="right">Completion</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {ensureArray<ToolHoursRow>(engineeringPayload.tool_hours).slice(0, 12).map((row) => (
                        <TableRow
                          key={`${row.tool_number}-${row.customer_name}`}
                          hover
                          sx={{ cursor: row.project_id ? 'pointer' : 'default' }}
                          onClick={() => {
                            if (row.project_id) navigate(`/projects/${row.project_id}`);
                          }}
                        >
                          <TableCell>{row.tool_number}</TableCell>
                          <TableCell>{row.customer_name}</TableCell>
                          <TableCell align="right">{formatNumber(row.quoted_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.original_hours ?? row.actual_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.additional_work_hours ?? 0)}</TableCell>
                          <TableCell align="right">{formatNumber(row.rework_hours ?? 0)}</TableCell>
                          <TableCell align="right">{formatNumber(row.actual_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.variance_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.completion_percent)}%</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>

              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                  Customer Summary
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Customer</TableCell>
                        <TableCell align="right">Projects</TableCell>
                        <TableCell align="right">Original</TableCell>
                        <TableCell align="right">Additional</TableCell>
                        <TableCell align="right">Rework</TableCell>
                        <TableCell align="right">Customer Chg</TableCell>
                        <TableCell align="right">Internal</TableCell>
                        <TableCell align="right">Productive</TableCell>
                        <TableCell align="right">NP</TableCell>
                        <TableCell align="right">Total</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {ensureArray<CustomerHoursRow>(engineeringPayload.customer_summary).slice(0, 10).map((row) => (
                        <TableRow key={row.customer_name} hover>
                          <TableCell>
                            <RouterLink to="/admin/customers" style={{ textDecoration: 'none', color: 'inherit' }}>
                              {row.customer_name}
                            </RouterLink>
                          </TableCell>
                          <TableCell align="right">{row.project_count}</TableCell>
                          <TableCell align="right">{formatNumber(row.original_hours ?? 0)}</TableCell>
                          <TableCell align="right">{formatNumber(row.additional_work_hours ?? 0)}</TableCell>
                          <TableCell align="right">{formatNumber(row.rework_hours ?? 0)}</TableCell>
                          <TableCell align="right">{formatNumber(row.customer_change_hours ?? 0)}</TableCell>
                          <TableCell align="right">{formatNumber(row.internal_correction_hours ?? 0)}</TableCell>
                          <TableCell align="right">{formatNumber(row.productive_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.np_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.total_hours)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>

              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
                  gap: 2,
                }}
              >
                <Paper sx={{ p: 2 }}>
                  <Typography variant="subtitle1" sx={{ mb: 1 }}>
                    Team Summary
                  </Typography>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Team</TableCell>
                          <TableCell align="right">Designers</TableCell>
                          <TableCell align="right">Total</TableCell>
                          <TableCell align="right">Util %</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {ensureArray<TeamSummaryRow>(engineeringPayload.team_summary).map((row) => (
                          <TableRow key={row.team_name} hover>
                            <TableCell>{row.team_name}</TableCell>
                            <TableCell align="right">{row.designer_count}</TableCell>
                            <TableCell align="right">{formatNumber(row.total_hours)}</TableCell>
                            <TableCell align="right">{formatNumber(row.utilization_percent)}%</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Paper>

                <Paper sx={{ p: 2 }}>
                  <Typography variant="subtitle1" sx={{ mb: 1 }}>
                    Function Hours
                  </Typography>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Function</TableCell>
                          <TableCell align="right">Hours</TableCell>
                          <TableCell align="right">%</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {ensureArray<FunctionHoursRow>(engineeringPayload.function_hours).map((row) => (
                          <TableRow key={row.function_group} hover>
                            <TableCell>{row.function_group}</TableCell>
                            <TableCell align="right">{formatNumber(row.hours)}</TableCell>
                            <TableCell align="right">{formatNumber(row.percent)}%</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Paper>

                <Paper sx={{ p: 2 }}>
                  <Typography variant="subtitle1" sx={{ mb: 1 }}>
                    Non-Productive Analysis
                  </Typography>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Code</TableCell>
                          <TableCell>Description</TableCell>
                          <TableCell align="right">Hours</TableCell>
                          <TableCell align="right">%</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {ensureArray<NpAnalysisRow>(engineeringPayload.np_analysis).map((row) => (
                          <TableRow key={row.code} hover>
                            <TableCell>{row.code}</TableCell>
                            <TableCell>{row.description}</TableCell>
                            <TableCell align="right">{formatNumber(row.hours)}</TableCell>
                            <TableCell align="right">{formatNumber(row.percent)}%</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Paper>

                <Paper sx={{ p: 2 }}>
                  <Typography variant="subtitle1" sx={{ mb: 1 }}>
                    Leave Analysis
                  </Typography>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Designer</TableCell>
                          <TableCell align="right">Leave Days</TableCell>
                          <TableCell align="right">Leave Hours</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {ensureArray<LeaveAnalysisRow>(engineeringPayload.leave_analysis).map((row) => (
                          <TableRow key={row.designer_name} hover>
                            <TableCell>{row.designer_name}</TableCell>
                            <TableCell align="right">{formatNumber(row.leave_days)}</TableCell>
                            <TableCell align="right">{formatNumber(row.leave_hours)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Paper>
              </Box>

              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                  Quoted vs Actual
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Tool</TableCell>
                        <TableCell>Customer</TableCell>
                        <TableCell align="right">Quoted</TableCell>
                        <TableCell align="right">Original</TableCell>
                        <TableCell align="right">Additional</TableCell>
                        <TableCell align="right">Rework</TableCell>
                        <TableCell align="right">Total Actual</TableCell>
                        <TableCell align="right">Variance %</TableCell>
                        <TableCell>Health</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {ensureArray<QuotedVsActualRow>(engineeringPayload.quoted_vs_actual).slice(0, 15).map((row) => (
                        <TableRow key={`${row.tool_number}-${row.customer_name}`} hover>
                          <TableCell>{row.tool_number}</TableCell>
                          <TableCell>{row.customer_name}</TableCell>
                          <TableCell align="right">{formatNumber(row.quoted_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.original_hours ?? row.actual_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.additional_work_hours ?? 0)}</TableCell>
                          <TableCell align="right">{formatNumber(row.rework_hours ?? 0)}</TableCell>
                          <TableCell align="right">
                            {formatNumber(
                              (row.original_hours ?? row.actual_hours) + (row.post_completion_hours ?? 0),
                            )}
                          </TableCell>
                          <TableCell align="right">{formatNumber(row.variance_percent)}%</TableCell>
                          <TableCell>{row.health ?? '—'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>

              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                  Project Performance
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Tool</TableCell>
                        <TableCell>Customer</TableCell>
                        <TableCell>Designer</TableCell>
                        <TableCell>Stage</TableCell>
                        <TableCell align="right">Milestone %</TableCell>
                        <TableCell>Health</TableCell>
                        <TableCell>Predicted Finish</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {ensureArray<ProjectPerformanceRow>(engineeringPayload.project_performance).slice(0, 15).map((row) => (
                        <TableRow key={`${row.tool_number}-${row.customer_name}`} hover>
                          <TableCell>{row.tool_number}</TableCell>
                          <TableCell>{row.customer_name}</TableCell>
                          <TableCell>{row.designer_name ?? '—'}</TableCell>
                          <TableCell>{row.project_stage ?? '—'}</TableCell>
                          <TableCell align="right">{formatNumber(row.milestone_completion_percent)}%</TableCell>
                          <TableCell>{row.health ?? '—'}</TableCell>
                          <TableCell>{row.predicted_finish ?? '—'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>

              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                  Detailed Entries (preview of first 40 — full list in Excel)
                </Typography>
                <TableContainer sx={{ maxHeight: 360 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell>Date</TableCell>
                        <TableCell>Designer</TableCell>
                        <TableCell>Customer</TableCell>
                        <TableCell>Tool</TableCell>
                        <TableCell>Task</TableCell>
                        <TableCell align="right">Hours</TableCell>
                        <TableCell>Category</TableCell>
                        <TableCell>Work Type</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {ensureArray<DetailedTimesheetRow>(engineeringPayload.detailed_entries).slice(0, 40).map((row, idx) => (
                        <TableRow key={`${row.entry_date}-${row.designer_name}-${idx}`} hover>
                          <TableCell>{row.entry_date}</TableCell>
                          <TableCell>{row.designer_name}</TableCell>
                          <TableCell>{row.customer_name ?? '—'}</TableCell>
                          <TableCell>{row.tool_number ?? '—'}</TableCell>
                          <TableCell>{row.task_name ?? '—'}</TableCell>
                          <TableCell align="right">{formatNumber(row.hours)}</TableCell>
                          <TableCell>{row.category}</TableCell>
                          <TableCell>{row.post_completion_type ?? 'Original'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>

              {engineeringPayload.ai_insights.length > 0 ? (
                <Card variant="outlined">
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <InsightsRoundedIcon color="primary" />
                      <Typography variant="subtitle1">AI Engineering Insights</Typography>
                    </Box>
                    <List dense>
                      {ensureArray<string>(engineeringPayload.ai_insights).map((insight) => (
                        <ListItem key={insight} disablePadding>
                          <ListItemText primary={insight} />
                        </ListItem>
                      ))}
                    </List>
                  </CardContent>
                </Card>
              ) : null}
            </>
          ) : null}
            </>
          )}
        </Stack>
      </Box>
    </Stack>
  );
}
