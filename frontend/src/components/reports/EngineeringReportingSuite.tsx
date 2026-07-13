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
import {
  downloadEngineeringReportExcel,
  engineeringReportQueryKeys,
  fetchEngineeringReportCatalog,
  fetchEngineeringReportPreview,
  fetchEngineeringReportSchedules,
  saveEngineeringReportSchedule,
} from '../../api/engineeringReporting';
import type { EngineeringReportOptions, ReportCatalogEntry } from '../../types/EngineeringReporting';
import { formatNumber } from '../../utils/format';

const CATEGORY_LABELS: Record<string, string> = {
  executive: 'Executive Reports',
  productivity: 'Productivity Reports',
  projects: 'Project Reports',
  timesheets: 'Timesheet Reports',
  customers: 'Customer Reports',
};

interface EngineeringReportingSuiteProps {
  canExport: boolean;
  includeArchived: boolean;
  includeDeleted: boolean;
}

function currentMonthAnchor(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  return `${now.getFullYear()}-${month}-01`;
}

export function EngineeringReportingSuite({
  canExport,
  includeArchived,
  includeDeleted,
}: EngineeringReportingSuiteProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedReportId, setSelectedReportId] = useState('monthly-engineering');
  const [periodType, setPeriodType] = useState('monthly');
  const [anchor, setAnchor] = useState(currentMonthAnchor());
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

  const selectedReport = useMemo(
    () => catalogQuery.data?.reports.find((report) => report.id === selectedReportId),
    [catalogQuery.data, selectedReportId],
  );

  const isCustomerTimesheetPack = selectedReportId === 'customer-timesheet-pack';

  const reportOptions: EngineeringReportOptions = useMemo(
    () => ({
      period_type: periodType,
      anchor,
      include_archived: includeArchived,
      include_deleted: includeDeleted,
    }),
    [periodType, anchor, includeArchived, includeDeleted],
  );

  const previewQuery = useQuery({
    queryKey: engineeringReportQueryKeys.preview(selectedReportId, reportOptions),
    queryFn: () => fetchEngineeringReportPreview(selectedReportId, reportOptions),
    enabled: Boolean(selectedReportId) && !isCustomerTimesheetPack,
    staleTime: 2 * 60 * 1000,
  });

  const scheduleMutation = useMutation({
    mutationFn: saveEngineeringReportSchedule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: engineeringReportQueryKeys.schedules });
    },
  });

  const groupedReports = useMemo(() => {
    const groups = new Map<string, ReportCatalogEntry[]>();
    for (const report of catalogQuery.data?.reports ?? []) {
      const list = groups.get(report.category) ?? [];
      list.push(report);
      groups.set(report.category, list);
    }
    return groups;
  }, [catalogQuery.data]);

  const scheduled = schedulesQuery.data?.find((entry) => entry.report_id === selectedReportId);

  const handleDownload = async () => {
    if (!canExport || isCustomerTimesheetPack) return;
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

  const payload = previewQuery.data;
  const customerChart = payload?.charts.find((chart) => chart.title.toLowerCase().includes('customer'));

  return (
    <Stack spacing={3}>
      <Paper sx={{ p: 2.5 }}>
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', md: 'row' },
            gap: 2,
            alignItems: { md: 'center' },
            justifyContent: 'space-between',
          }}
        >
          <Box>
            <Typography variant="h6">Engineering Management Reporting Suite</Typography>
            <Typography variant="body2" color="text.secondary">
              Executive dashboards, productivity analytics, and management-ready Excel exports.
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {!isCustomerTimesheetPack ? (
              <>
                <TextField
                  select
                  size="small"
                  label="Period"
                  value={periodType}
                  onChange={(event) => setPeriodType(event.target.value)}
                  sx={{ minWidth: 140 }}
                >
                  {(selectedReport?.supported_periods ?? ['monthly']).map((period) => (
                    <MenuItem key={period} value={period}>
                      {period.charAt(0).toUpperCase() + period.slice(1)}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField
                  size="small"
                  label="Anchor date"
                  type="date"
                  value={anchor}
                  onChange={(event) => setAnchor(event.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                  sx={{ minWidth: 160 }}
                />
                {canExport ? (
                  <Button
                    variant="contained"
                    startIcon={<DownloadRoundedIcon />}
                    onClick={handleDownload}
                    disabled={downloading}
                  >
                    {downloading ? 'Generating…' : 'Download Excel'}
                  </Button>
                ) : null}
              </>
            ) : (
              <Chip
                size="small"
                color="primary"
                label="Use Customer / Team / Week-Month filters below"
              />
            )}
          </Box>
        </Box>
        {downloadError ? <Alert severity="error" sx={{ mt: 2 }}>{downloadError}</Alert> : null}
      </Paper>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: 'minmax(240px, 1fr) 2fr' },
          gap: 2,
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
                        if (!report.supported_periods.includes(periodType)) {
                          setPeriodType(report.supported_periods[0] ?? 'monthly');
                        }
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
                {!isCustomerTimesheetPack && payload ? (
                  <Chip size="small" label={payload.period.label} sx={{ mt: 1 }} />
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
          {previewQuery.isLoading ? <LoadingState message="Building report preview…" /> : null}
          {previewQuery.error ? <ErrorState error={previewQuery.error} /> : null}

          {payload ? (
            <>
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
                {payload.executive.kpis.map((kpi) => (
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
                      {payload.designer_productivity.slice(0, 12).map((row) => (
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
                  Tool Hours
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Tool</TableCell>
                        <TableCell>Customer</TableCell>
                        <TableCell align="right">Quoted</TableCell>
                        <TableCell align="right">Actual</TableCell>
                        <TableCell align="right">Variance</TableCell>
                        <TableCell align="right">Completion</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {payload.tool_hours.slice(0, 12).map((row) => (
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
                        <TableCell align="right">Productive</TableCell>
                        <TableCell align="right">NP</TableCell>
                        <TableCell align="right">Total</TableCell>
                        <TableCell align="right">Avg / Project</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {payload.customer_summary.slice(0, 10).map((row) => (
                        <TableRow key={row.customer_name} hover>
                          <TableCell>
                            <RouterLink to="/admin/customers" style={{ textDecoration: 'none', color: 'inherit' }}>
                              {row.customer_name}
                            </RouterLink>
                          </TableCell>
                          <TableCell align="right">{row.project_count}</TableCell>
                          <TableCell align="right">{formatNumber(row.productive_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.np_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.total_hours)}</TableCell>
                          <TableCell align="right">{formatNumber(row.avg_hours_per_project)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>

              {payload.ai_insights.length > 0 ? (
                <Card variant="outlined">
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <InsightsRoundedIcon color="primary" />
                      <Typography variant="subtitle1">AI Engineering Insights</Typography>
                    </Box>
                    <List dense>
                      {payload.ai_insights.map((insight) => (
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
