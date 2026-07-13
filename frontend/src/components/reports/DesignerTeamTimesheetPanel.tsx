import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  MenuItem,
  Paper,
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
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded';
import { useQuery } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import { fetchCustomers, fetchTeams } from '../../api/lookups';
import {
  downloadEngineeringReportExcel,
  engineeringReportQueryKeys,
  fetchEngineeringReportPreview,
  isDesignerTeamTimesheetReport,
} from '../../api/engineeringReporting';
import type { DesignerTeamTimesheetPayload, DesignerProductivityRow, ToolHoursRow } from '../../types/EngineeringReporting';
import type { Customer } from '../../types';
import type { Team } from '../../types/Team';
import { ensureArray } from '../../types/pagination';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { KpiMetricCard } from '../ui/design-system';
import AssessmentRoundedIcon from '@mui/icons-material/AssessmentRounded';
import { formatNumber } from '../../utils/format';
import { defaultAnchorForPeriod } from '../../utils/reportPeriodSelection';
import {
  ReportPeriodSelectors,
  syncAnchorForPeriodChange,
} from './ReportPeriodSelectors';

const PERIOD_REPORTS = [
  { id: 'weekly-timesheet', label: 'Weekly', period: 'weekly' },
  { id: 'monthly-timesheet', label: 'Monthly', period: 'monthly' },
  { id: 'quarterly-timesheet', label: 'Quarterly', period: 'quarterly' },
  { id: 'yearly-timesheet', label: 'Yearly', period: 'yearly' },
] as const;

interface DesignerTeamTimesheetPanelProps {
  canExport: boolean;
  includeArchived?: boolean;
  includeDeleted?: boolean;
}

export function DesignerTeamTimesheetPanel({
  canExport,
  includeArchived = true,
  includeDeleted = false,
}: DesignerTeamTimesheetPanelProps) {
  const [reportId, setReportId] = useState<(typeof PERIOD_REPORTS)[number]['id']>('monthly-timesheet');
  const [anchor, setAnchor] = useState(defaultAnchorForPeriod('monthly'));
  const [customerId, setCustomerId] = useState('');
  const [teamId, setTeamId] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const selected = PERIOD_REPORTS.find((row) => row.id === reportId) ?? PERIOD_REPORTS[1];

  const customersQuery = useQuery({
    queryKey: ['lookups', 'customers'],
    queryFn: fetchCustomers,
    staleTime: 5 * 60 * 1000,
  });
  const teamsQuery = useQuery({
    queryKey: ['lookups', 'teams'],
    queryFn: fetchTeams,
    staleTime: 5 * 60 * 1000,
  });

  const customers = ensureArray<Customer>(customersQuery.data);
  const teams = ensureArray<Team>(teamsQuery.data);

  const options = useMemo(
    () => ({
      period_type: selected.period,
      anchor,
      customer_id: customerId || undefined,
      team_id: teamId || undefined,
      include_archived: includeArchived,
      include_deleted: includeDeleted,
    }),
    [selected.period, anchor, customerId, teamId, includeArchived, includeDeleted],
  );

  const previewQuery = useQuery({
    queryKey: engineeringReportQueryKeys.preview(reportId, options),
    queryFn: () => fetchEngineeringReportPreview(reportId, options),
    enabled: isDesignerTeamTimesheetReport(reportId),
    staleTime: 60 * 1000,
  });

  const payload =
    previewQuery.data && 'designers' in previewQuery.data
      ? (previewQuery.data as DesignerTeamTimesheetPayload)
      : null;
  const designers = ensureArray<DesignerProductivityRow>(payload?.designers);
  const projects = ensureArray<ToolHoursRow>(payload?.projects);

  const handlePeriodChange = (nextId: (typeof PERIOD_REPORTS)[number]['id']) => {
    setReportId(nextId);
    const next = PERIOD_REPORTS.find((row) => row.id === nextId);
    if (next) {
      setAnchor((current) => syncAnchorForPeriodChange(next.period, current));
    }
  };

  const handleDownload = async () => {
    if (!canExport) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadEngineeringReportExcel(reportId, options);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : 'Download failed');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Stack spacing={2}>
      <Paper sx={{ p: 2.5 }}>
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', md: 'row' },
            gap: 2,
            justifyContent: 'space-between',
            alignItems: { md: 'flex-start' },
          }}
        >
          <Box>
            <Typography variant="h6">Timesheet Reports</Typography>
            <Typography variant="body2" color="text.secondary">
              Weekly / Monthly / Quarterly / Yearly — designer hours by team for the period, plus
              total project hours up to report generation.
            </Typography>
          </Box>
          <Box
            sx={{
              display: 'grid',
              gap: 1.5,
              gridTemplateColumns: {
                xs: '1fr',
                sm: 'repeat(2, minmax(140px, 1fr))',
                lg: 'repeat(4, minmax(140px, 1fr)) auto',
              },
              alignItems: 'start',
              minWidth: { md: 480 },
              maxWidth: 960,
              flex: 1,
            }}
          >
            <TextField
              select
              size="small"
              label="Period"
              value={reportId}
              onChange={(event) =>
                handlePeriodChange(event.target.value as (typeof PERIOD_REPORTS)[number]['id'])
              }
            >
              {PERIOD_REPORTS.map((row) => (
                <MenuItem key={row.id} value={row.id}>
                  {row.label}
                </MenuItem>
              ))}
            </TextField>
            <ReportPeriodSelectors
              periodType={selected.period}
              anchor={anchor}
              onAnchorChange={setAnchor}
            />
            <TextField
              select
              size="small"
              label="Customer"
              value={customerId}
              onChange={(event) => setCustomerId(event.target.value)}
              helperText="Optional"
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
              helperText="Your accessible teams only"
            >
              <MenuItem value="">All accessible teams</MenuItem>
              {teams.map((team) => (
                <MenuItem key={team.id} value={team.id}>
                  {team.name}
                </MenuItem>
              ))}
            </TextField>
            {canExport ? (
              <Button
                variant="contained"
                startIcon={<DownloadRoundedIcon />}
                onClick={handleDownload}
                disabled={downloading || previewQuery.isFetching}
                sx={{ alignSelf: { lg: 'center' } }}
              >
                {downloading ? 'Generating…' : 'Download Excel'}
              </Button>
            ) : null}
          </Box>
        </Box>
        {downloadError ? <Alert severity="error" sx={{ mt: 2 }}>{downloadError}</Alert> : null}
      </Paper>

      {previewQuery.isLoading ? <LoadingState message="Building timesheet report…" /> : null}
      {previewQuery.error ? <ErrorState error={previewQuery.error} /> : null}

      {payload ? (
        <>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' },
              gap: 2,
            }}
          >
            <KpiMetricCard
              title="Period designer hours"
              value={formatNumber(payload.total_designer_hours)}
              icon={AssessmentRoundedIcon}
              accent="primary"
              compact
            />
            <KpiMetricCard
              title="Designers"
              value={String(payload.designer_count)}
              icon={AssessmentRoundedIcon}
              accent="primary"
              compact
            />
            <KpiMetricCard
              title="Teams"
              value={String(payload.team_count)}
              icon={AssessmentRoundedIcon}
              accent="primary"
              compact
            />
            <KpiMetricCard
              title="Project hours to date"
              value={formatNumber(payload.total_project_actual_hours)}
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
              {payload.period.label}
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
                  {designers.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7}>
                        <Typography variant="body2" color="text.secondary">
                          No designer hours for this period and filter.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ) : (
                    designers.map((row) => (
                      <TableRow key={row.user_id} hover>
                        <TableCell>{row.team_name ?? '—'}</TableCell>
                        <TableCell>
                          <RouterLink
                            to={`/dashboard?user=${row.user_id}`}
                            style={{ textDecoration: 'none', color: 'inherit' }}
                          >
                            {row.designer_name}
                          </RouterLink>
                        </TableCell>
                        <TableCell align="right">{formatNumber(row.productive_hours)}</TableCell>
                        <TableCell align="right">{formatNumber(row.non_productive_hours)}</TableCell>
                        <TableCell align="right">{formatNumber(row.leave_days)}</TableCell>
                        <TableCell align="right">{formatNumber(row.total_hours)}</TableCell>
                        <TableCell align="right">{formatNumber(row.utilization_percent)}%</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>

          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ mb: 0.5 }}>
              Total project hours to date
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Cumulative as of {new Date(payload.generated_at).toLocaleString()}
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
                  {projects.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6}>
                        <Typography variant="body2" color="text.secondary">
                          No projects in scope.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ) : (
                    projects.slice(0, 50).map((row) => (
                      <TableRow key={`${row.project_id ?? row.tool_number}-${row.customer_name}`} hover>
                        <TableCell>
                          {row.project_id ? (
                            <RouterLink
                              to={`/projects/${row.project_id}`}
                              style={{ textDecoration: 'none', color: 'inherit' }}
                            >
                              {row.tool_number}
                            </RouterLink>
                          ) : (
                            row.tool_number
                          )}
                        </TableCell>
                        <TableCell>{row.customer_name}</TableCell>
                        <TableCell align="right">{formatNumber(row.quoted_hours)}</TableCell>
                        <TableCell align="right">{formatNumber(row.actual_hours)}</TableCell>
                        <TableCell align="right">{formatNumber(row.variance_hours)}</TableCell>
                        <TableCell align="right">{formatNumber(row.completion_percent)}%</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </>
      ) : null}
    </Stack>
  );
}
