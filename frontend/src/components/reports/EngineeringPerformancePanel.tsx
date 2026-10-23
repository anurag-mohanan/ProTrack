import { useMemo, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
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
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { fetchCustomers, fetchTeams, fetchUsers } from '../../api/lookups';
import { fetchProjectTypes } from '../../api/projectTemplates';
import { fetchPublicSettings } from '../../api/settings';
import {
  downloadEngineeringPerformanceExcel,
  engineeringPerformanceQueryKeys,
  fetchEngineeringPerformance,
  fetchTemplateLookups,
} from '../../api/engineeringPerformance';
import type {
  Breakdown,
  BreakdownRow,
  EngineeringPerformanceParams,
  EngineeringPerformanceReport,
  PerformancePeriodType,
  KpiDefinition,
  PerformanceDataWarning,
  PerformancePlanBasis,
  ProjectPerformanceRow,
  StagePerformanceRow,
  TemplateLookup,
} from '../../types/EngineeringPerformance';
import type { Customer, User } from '../../types';
import type { Team } from '../../types/Team';
import type { ProjectType } from '../../types/ProjectTemplate';
import { ensureArray } from '../../types/pagination';
import { formatDate, formatNumber, userDisplayName } from '../../utils/format';
import { defaultAnchorForPeriod, toIsoDate } from '../../utils/reportPeriodSelection';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { AnalyticsBarChart } from '../analytics/AnalyticsCharts';
import { ReportPeriodSelectors, syncAnchorForPeriodChange } from './ReportPeriodSelectors';

const PERIOD_OPTIONS: { value: PerformancePeriodType; label: string }[] = [
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly (financial)' },
  { value: 'yearly', label: 'Financial year' },
  { value: 'custom', label: 'Custom range' },
];

const MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function fyStartYearFor(date: Date, fyStartMonth: number): number {
  return date.getMonth() + 1 >= fyStartMonth ? date.getFullYear() : date.getFullYear() - 1;
}

function fyLabel(startYear: number, fyStartMonth: number): string {
  if (fyStartMonth === 1) return `FY ${startYear}`;
  return `FY ${startYear}-${String((startYear + 1) % 100).padStart(2, '0')}`;
}

/** First day of financial quarter `quarter` (1–4) of the FY starting in `startYear`. */
function fyQuarterStart(startYear: number, quarter: number, fyStartMonth: number): Date {
  const offset = fyStartMonth - 1 + (quarter - 1) * 3;
  return new Date(startYear + Math.floor(offset / 12), offset % 12, 1);
}

function fyQuarterLabel(quarter: number, fyStartMonth: number): string {
  const first = (fyStartMonth - 1 + (quarter - 1) * 3) % 12;
  const last = (first + 2) % 12;
  return `Q${quarter} (${MONTH_SHORT[first]}–${MONTH_SHORT[last]})`;
}

function fyQuarterFor(date: Date, fyStartMonth: number): number {
  const monthsIn = (date.getMonth() + 1 - fyStartMonth + 12) % 12;
  return Math.floor(monthsIn / 3) + 1;
}

function hours(value: number | null | undefined): string {
  return value == null ? '—' : formatNumber(value, 1);
}

function percent(value: number | null | undefined): string {
  return value == null ? '—' : `${formatNumber(value, 1)}%`;
}

function signedHours(value: number | null | undefined): string {
  if (value == null) return '—';
  return `${value > 0 ? '+' : ''}${formatNumber(value, 1)}`;
}

function varianceColor(value: number | null | undefined): string | undefined {
  if (value == null || value === 0) return undefined;
  return value > 0 ? 'error.main' : 'success.main';
}

function KpiCard({ label, value, caption }: { label: string; value: string; caption?: string }) {
  return (
    <Paper variant="outlined" sx={{ p: 1.75, minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {label}
      </Typography>
      <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.3 }}>
        {value}
      </Typography>
      {caption ? (
        <Typography variant="caption" color="text.secondary">
          {caption}
        </Typography>
      ) : null}
    </Paper>
  );
}

function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <Box sx={{ mb: 1.5 }}>
      <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
        {title}
      </Typography>
      {subtitle ? (
        <Typography variant="body2" color="text.secondary">
          {subtitle}
        </Typography>
      ) : null}
    </Box>
  );
}

function BreakdownTable({ breakdown }: { breakdown: Breakdown }) {
  const rows = ensureArray<BreakdownRow>(breakdown.rows);
  const top = rows.slice(0, 10);
  return (
    <Stack spacing={1.5}>
      {top.length ? (
        <AnalyticsBarChart
          categories={top.map((row) => row.label)}
          series={[
            { label: 'Planned hours', data: top.map((row) => row.planned_hours) },
            { label: 'Actual hours', data: top.map((row) => row.actual_hours) },
          ]}
          height={260}
        />
      ) : null}
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{breakdown.label}</TableCell>
              <TableCell align="right">Projects</TableCell>
              <TableCell align="right">Planned h</TableCell>
              <TableCell align="right">Actual h</TableCell>
              <TableCell align="right">Variance h</TableCell>
              <TableCell align="right">Variance %</TableCell>
              <TableCell align="right">On time</TableCell>
              <TableCell align="right">On-time rate</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.key} hover>
                <TableCell>{row.label}</TableCell>
                <TableCell align="right">{row.projects}</TableCell>
                <TableCell align="right">{hours(row.planned_hours)}</TableCell>
                <TableCell align="right">{hours(row.actual_hours)}</TableCell>
                <TableCell align="right" sx={{ color: varianceColor(row.variance_hours) }}>
                  {signedHours(row.variance_hours)}
                </TableCell>
                <TableCell align="right">{percent(row.variance_percent)}</TableCell>
                <TableCell align="right">{row.on_time_projects}</TableCell>
                <TableCell align="right">{percent(row.on_time_rate)}</TableCell>
              </TableRow>
            ))}
            {!rows.length ? (
              <TableRow>
                <TableCell colSpan={8}>
                  <Typography variant="body2" color="text.secondary">
                    No rows for this breakdown.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
}

function ReportBody({ report }: { report: EngineeringPerformanceReport }) {
  const { summary, stage_performance: stage } = report;
  const breakdowns = ensureArray<Breakdown>(report.breakdowns);
  const [dimension, setDimension] = useState<string>('customer');
  const activeBreakdown =
    breakdowns.find((item) => item.dimension === dimension) ?? breakdowns[0] ?? null;
  const stageRows = ensureArray<StagePerformanceRow>(stage.rows);
  const basisLabel = summary.plan_basis === 'original' ? 'original estimate' : 'current estimate';

  return (
    <Stack spacing={2.5}>
      <Paper sx={{ p: 2 }}>
        <SectionTitle
          title={`Summary — ${report.period.label}`}
          subtitle={`${formatDate(report.period.start_date)} to ${formatDate(report.period.end_date)} · completed projects only · planned hours use the ${basisLabel}`}
        />
        <Box
          sx={{
            display: 'grid',
            gap: 1.5,
            gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, minmax(0, 1fr))' },
          }}
        >
          <KpiCard label="Projects completed" value={String(summary.projects_completed)} />
          <KpiCard
            label="Planned hours"
            value={hours(summary.planned_hours)}
            caption={
              summary.projects_without_plan
                ? `${summary.projects_without_plan} project(s) without a plan excluded`
                : undefined
            }
          />
          <KpiCard label="Actual hours" value={hours(summary.actual_hours)} caption={`EAC ${hours(summary.eac_hours)}`} />
          <KpiCard
            label="Hours variance"
            value={signedHours(summary.variance_hours)}
            caption={summary.variance_percent == null ? 'No planned hours' : `${percent(summary.variance_percent)} vs plan`}
          />
          <KpiCard
            label="On-time delivery"
            value={percent(summary.on_time_rate)}
            caption={`${summary.on_time_projects} on time · ${summary.late_projects} late${
              summary.projects_without_reference_date
                ? ` · ${summary.projects_without_reference_date} without a target date`
                : ''
            }`}
          />
          <KpiCard
            label="Average days late"
            value={summary.average_days_late == null ? '—' : formatNumber(summary.average_days_late, 1)}
            caption="Late projects only"
          />
          <KpiCard
            label="Milestone on-time rate"
            value={percent(summary.milestone_on_time_rate)}
            caption={`${summary.milestones_on_time} of ${summary.milestones_completed} completed milestones`}
          />
          <KpiCard
            label="Projects with stage plan"
            value={`${stage.projects_with_stage_plan} / ${summary.projects_completed}`}
          />
        </Box>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <SectionTitle
          title="Stage Performance"
          subtitle={`Blockout, Intermediate Design and Final Design for ${stage.projects_with_stage_plan} project(s) with stage estimates${
            stage.projects_without_stage_plan
              ? `; ${stage.projects_without_stage_plan} project(s) without stage estimates are not included`
              : ''
          }.`}
        />
        {stageRows.length ? (
          <AnalyticsBarChart
            categories={stageRows.map((row) => row.label)}
            series={[
              { label: 'Original estimate', data: stageRows.map((row) => row.original_hours) },
              { label: 'Current estimate', data: stageRows.map((row) => row.current_hours) },
              { label: 'Actual', data: stageRows.map((row) => row.actual_hours) },
            ]}
            height={260}
          />
        ) : null}
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Stage</TableCell>
                <TableCell align="right">Projects</TableCell>
                <TableCell align="right">Original h</TableCell>
                <TableCell align="right">Current h</TableCell>
                <TableCell align="right">Actual h</TableCell>
                <TableCell align="right">Variance h</TableCell>
                <TableCell align="right">Variance %</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {stageRows.map((row) => (
                <TableRow key={row.stage} hover>
                  <TableCell>{row.label}</TableCell>
                  <TableCell align="right">{row.projects}</TableCell>
                  <TableCell align="right">{hours(row.original_hours)}</TableCell>
                  <TableCell align="right">{hours(row.current_hours)}</TableCell>
                  <TableCell align="right">{hours(row.actual_hours)}</TableCell>
                  <TableCell align="right" sx={{ color: varianceColor(row.variance_hours) }}>
                    {signedHours(row.variance_hours)}
                  </TableCell>
                  <TableCell align="right">{percent(row.variance_percent)}</TableCell>
                </TableRow>
              ))}
              {!stageRows.length ? (
                <TableRow>
                  <TableCell colSpan={7}>
                    <Typography variant="body2" color="text.secondary">
                      None of the completed projects in this period have stage estimates.
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </TableContainer>
        {stage.unstaged_actual_hours ? (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            {hours(stage.unstaged_actual_hours)} actual hours on staged projects were booked without a
            stage milestone and are not in the stage rows.
          </Typography>
        ) : null}
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1.5}
          sx={{ justifyContent: 'space-between', alignItems: { sm: 'flex-start' }, mb: 1 }}
        >
          <SectionTitle title="Customer / Team Breakdown" subtitle="Completed projects grouped by the selected dimension." />
          <TextField
            select
            size="small"
            label="Group by"
            value={activeBreakdown?.dimension ?? ''}
            onChange={(event) => setDimension(event.target.value)}
            sx={{ minWidth: 200 }}
          >
            {breakdowns.map((item) => (
              <MenuItem key={item.dimension} value={item.dimension}>
                {item.label}
              </MenuItem>
            ))}
          </TextField>
        </Stack>
        {activeBreakdown ? <BreakdownTable breakdown={activeBreakdown} /> : null}
      </Paper>

      <Paper sx={{ p: 2 }}>
        <SectionTitle title="Project Details" subtitle={`${report.projects.length} completed project(s)`} />
        <TableContainer sx={{ maxHeight: 560 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>Project</TableCell>
                <TableCell>Customer</TableCell>
                <TableCell>End customer</TableCell>
                <TableCell>Team</TableCell>
                <TableCell>Designer</TableCell>
                <TableCell>Completed</TableCell>
                <TableCell>Target</TableCell>
                <TableCell align="right">Days late</TableCell>
                <TableCell align="right">Planned h</TableCell>
                <TableCell align="right">Actual h</TableCell>
                <TableCell align="right">Variance h</TableCell>
                <TableCell align="right">Milestones on time</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {ensureArray<ProjectPerformanceRow>(report.projects).map((row) => (
                <TableRow key={row.project_id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {row.code ?? row.tool_number ?? '—'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {row.part_description ?? ''}
                      {row.template_name ? ` · ${row.template_name}` : ''}
                    </Typography>
                  </TableCell>
                  <TableCell>{row.customer_name ?? '—'}</TableCell>
                  <TableCell>{row.end_customer_name ?? '—'}</TableCell>
                  <TableCell>{row.team_name ?? '—'}</TableCell>
                  <TableCell>{row.designer_name ?? '—'}</TableCell>
                  <TableCell>{formatDate(row.actual_completion_date)}</TableCell>
                  <TableCell>
                    {row.reference_completion_date ? formatDate(row.reference_completion_date) : '—'}
                    {row.reference_source === 'legacy_due_date' ? (
                      <Chip size="small" label="legacy due date" sx={{ ml: 0.5 }} />
                    ) : null}
                  </TableCell>
                  <TableCell align="right">
                    {row.on_time == null ? '—' : row.on_time ? 'On time' : row.days_late}
                  </TableCell>
                  <TableCell align="right">
                    {hours(row.planned_hours)}
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      {row.plan_source}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">{hours(row.actual_hours)}</TableCell>
                  <TableCell align="right" sx={{ color: varianceColor(row.variance_hours) }}>
                    {signedHours(row.variance_hours)}
                  </TableCell>
                  <TableCell align="right">
                    {row.milestones_on_time} / {row.milestones_completed}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Stack>
  );
}

interface EngineeringPerformancePanelProps {
  canExport: boolean;
  includeArchived: boolean;
}

export function EngineeringPerformancePanel({ canExport, includeArchived }: EngineeringPerformancePanelProps) {
  const settingsQuery = useQuery({
    queryKey: ['settings', 'public'],
    queryFn: fetchPublicSettings,
    staleTime: 5 * 60 * 1000,
  });
  const fyStartMonth = settingsQuery.data?.company.financial_year_start_month ?? 4;
  const today = useMemo(() => new Date(), []);

  const [periodType, setPeriodType] = useState<PerformancePeriodType>('quarterly');
  const [anchor, setAnchor] = useState(defaultAnchorForPeriod('monthly'));
  const [fyYear, setFyYear] = useState<number | null>(null);
  const [fyQuarter, setFyQuarter] = useState<number | null>(null);
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [planBasis, setPlanBasis] = useState<PerformancePlanBasis>('current');
  const [customerId, setCustomerId] = useState('');
  const [endCustomerId, setEndCustomerId] = useState('');
  const [teamId, setTeamId] = useState('');
  const [designLeaderId, setDesignLeaderId] = useState('');
  const [designerId, setDesignerId] = useState('');
  const [surfacerId, setSurfacerId] = useState('');
  const [projectTypeId, setProjectTypeId] = useState('');
  const [templateId, setTemplateId] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const selectedFyYear = fyYear ?? fyStartYearFor(today, fyStartMonth);
  const selectedFyQuarter = fyQuarter ?? fyQuarterFor(today, fyStartMonth);
  const currentFy = fyStartYearFor(today, fyStartMonth);
  const fyYears = Array.from({ length: 7 }, (_, index) => currentFy + 1 - index);

  const customerQuery = useQuery({ queryKey: ['lookups', 'customers'], queryFn: fetchCustomers, staleTime: 300_000 });
  const teamsQuery = useQuery({
    queryKey: ['lookups', 'teams', 'reports'],
    queryFn: () => fetchTeams({ forReports: true }),
    staleTime: 300_000,
  });
  const usersQuery = useQuery({
    queryKey: ['lookups', 'users', 'reports'],
    queryFn: () => fetchUsers({ forReports: true }),
    staleTime: 300_000,
  });
  const typesQuery = useQuery({ queryKey: ['lookups', 'project-types'], queryFn: fetchProjectTypes, staleTime: 300_000 });
  const templatesQuery = useQuery({
    queryKey: engineeringPerformanceQueryKeys.templates,
    queryFn: fetchTemplateLookups,
    staleTime: 300_000,
  });
  const lookupError =
    customerQuery.error ?? teamsQuery.error ?? usersQuery.error ?? typesQuery.error ?? templatesQuery.error;

  const customRangeError =
    periodType === 'custom'
      ? !customStart || !customEnd
        ? 'Choose a start and end date.'
        : customEnd < customStart
          ? 'End date must be on or after the start date.'
          : null
      : null;

  const params = useMemo<EngineeringPerformanceParams>(() => {
    let periodParams: Partial<EngineeringPerformanceParams>;
    if (periodType === 'custom') {
      periodParams = { start_date: customStart, end_date: customEnd };
    } else if (periodType === 'quarterly') {
      periodParams = { anchor: toIsoDate(fyQuarterStart(selectedFyYear, selectedFyQuarter, fyStartMonth)) };
    } else if (periodType === 'yearly') {
      periodParams = { anchor: toIsoDate(new Date(selectedFyYear, fyStartMonth - 1, 1)) };
    } else {
      periodParams = { anchor };
    }
    return {
      period_type: periodType,
      ...periodParams,
      plan_basis: planBasis,
      customer_id: customerId || undefined,
      end_customer_id: endCustomerId || undefined,
      team_id: teamId || undefined,
      design_leader_id: designLeaderId || undefined,
      designer_id: designerId || undefined,
      surfacer_id: surfacerId || undefined,
      project_type_id: projectTypeId || undefined,
      template_id: templateId || undefined,
      include_archived: includeArchived,
    };
  }, [
    periodType, customStart, customEnd, selectedFyYear, selectedFyQuarter, fyStartMonth, anchor, planBasis,
    customerId, endCustomerId, teamId, designLeaderId, designerId, surfacerId, projectTypeId, templateId,
    includeArchived,
  ]);

  const reportQuery = useQuery({
    queryKey: engineeringPerformanceQueryKeys.report(params),
    queryFn: () => fetchEngineeringPerformance(params),
    enabled: !customRangeError && settingsQuery.isFetched,
    placeholderData: keepPreviousData,
  });

  const handlePeriodChange = (next: PerformancePeriodType) => {
    setPeriodType(next);
    if (next === 'weekly' || next === 'monthly') {
      setAnchor((current) => syncAnchorForPeriodChange(next, current));
    }
  };

  const handleDownload = async () => {
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadEngineeringPerformanceExcel(params);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : 'Export failed.');
    } finally {
      setDownloading(false);
    }
  };

  const customers = ensureArray<Customer>(customerQuery.data);
  const users = ensureArray<User>(usersQuery.data);
  const report = reportQuery.data;
  const isStale = reportQuery.isPlaceholderData;

  const select = (
    label: string,
    value: string,
    onChange: (value: string) => void,
    options: { id: string; label: string }[],
    allLabel: string,
  ) => (
    <TextField
      select
      size="small"
      label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      fullWidth
      slotProps={{ inputLabel: { shrink: true } }}
    >
      <MenuItem value="">{allLabel}</MenuItem>
      {options.map((option) => (
        <MenuItem key={option.id} value={option.id}>
          {option.label}
        </MenuItem>
      ))}
    </TextField>
  );

  const customerOptions = customers.map((item) => ({ id: item.id, label: item.name }));
  const userOptions = users.map((item) => ({ id: item.id, label: userDisplayName(item) || item.email }));

  return (
    <Stack spacing={2.5}>
      <Paper sx={{ p: 2 }}>
        <Stack spacing={1.5}>
          <Box>
            <Typography variant="h6">Engineering Performance</Typography>
            <Typography variant="body2" color="text.secondary">
              Delivery and hours performance for projects completed in the selected period. Quarters and
              years follow the financial year ({MONTH_SHORT[fyStartMonth - 1]} start). Active work is on
              the Operational Overview tab.
            </Typography>
          </Box>
          <Box
            sx={{
              display: 'grid',
              gap: 1.5,
              gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, minmax(0, 1fr))', md: 'repeat(4, minmax(0, 1fr))' },
              '& > *': { minWidth: 0 },
            }}
          >
            <TextField
              select
              size="small"
              label="Period"
              value={periodType}
              onChange={(event) => handlePeriodChange(event.target.value as PerformancePeriodType)}
              fullWidth
            >
              {PERIOD_OPTIONS.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </TextField>
            {periodType === 'weekly' || periodType === 'monthly' ? (
              <ReportPeriodSelectors periodType={periodType} anchor={anchor} onAnchorChange={setAnchor} fluid />
            ) : null}
            {periodType === 'quarterly' || periodType === 'yearly' ? (
              <TextField
                select
                size="small"
                label="Financial year"
                value={selectedFyYear}
                onChange={(event) => setFyYear(Number(event.target.value))}
                fullWidth
              >
                {fyYears.map((year) => (
                  <MenuItem key={year} value={year}>
                    {fyLabel(year, fyStartMonth)}
                  </MenuItem>
                ))}
              </TextField>
            ) : null}
            {periodType === 'quarterly' ? (
              <TextField
                select
                size="small"
                label="Quarter"
                value={selectedFyQuarter}
                onChange={(event) => setFyQuarter(Number(event.target.value))}
                fullWidth
              >
                {[1, 2, 3, 4].map((quarter) => (
                  <MenuItem key={quarter} value={quarter}>
                    {fyQuarterLabel(quarter, fyStartMonth)}
                  </MenuItem>
                ))}
              </TextField>
            ) : null}
            {periodType === 'custom' ? (
              <>
                <TextField
                  size="small"
                  type="date"
                  label="From"
                  value={customStart}
                  onChange={(event) => setCustomStart(event.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                  fullWidth
                />
                <TextField
                  size="small"
                  type="date"
                  label="To"
                  value={customEnd}
                  onChange={(event) => setCustomEnd(event.target.value)}
                  error={Boolean(customStart && customEnd && customEnd < customStart)}
                  helperText={customRangeError ?? ' '}
                  slotProps={{ inputLabel: { shrink: true } }}
                  fullWidth
                />
              </>
            ) : null}
            <TextField
              select
              size="small"
              label="Plan basis"
              value={planBasis}
              onChange={(event) => setPlanBasis(event.target.value as PerformancePlanBasis)}
              fullWidth
            >
              <MenuItem value="current">Current approved estimate</MenuItem>
              <MenuItem value="original">Original estimate</MenuItem>
            </TextField>
          </Box>
          <Box
            sx={{
              display: 'grid',
              gap: 1.5,
              gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, minmax(0, 1fr))', md: 'repeat(4, minmax(0, 1fr))' },
              '& > *': { minWidth: 0 },
            }}
          >
            {select('Customer', customerId, setCustomerId, customerOptions, 'All customers')}
            {select('End customer', endCustomerId, setEndCustomerId, customerOptions, 'All end customers')}
            {select(
              'Team',
              teamId,
              setTeamId,
              ensureArray<Team>(teamsQuery.data).map((item) => ({ id: item.id, label: item.name })),
              'All accessible teams',
            )}
            {select(
              'Project type',
              projectTypeId,
              setProjectTypeId,
              ensureArray<ProjectType>(typesQuery.data).map((item) => ({ id: item.id, label: item.name })),
              'All project types',
            )}
            {select('Design leader', designLeaderId, setDesignLeaderId, userOptions, 'Anyone')}
            {select('Designer', designerId, setDesignerId, userOptions, 'Anyone')}
            {select('Surfacer', surfacerId, setSurfacerId, userOptions, 'Anyone')}
            {select(
              'Template',
              templateId,
              setTemplateId,
              ensureArray<TemplateLookup>(templatesQuery.data).map((item) => ({
                id: item.id,
                label: item.is_active ? item.name : `${item.name} (inactive)`,
              })),
              'All templates',
            )}
          </Box>
          {lookupError ? (
            <ErrorState
              error={lookupError}
              title="Some filter lists could not be loaded"
              onRetry={() => {
                void customerQuery.refetch();
                void teamsQuery.refetch();
                void usersQuery.refetch();
                void typesQuery.refetch();
                void templatesQuery.refetch();
              }}
            />
          ) : null}
          <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap', alignItems: 'center' }}>
            {canExport ? (
              <Button
                variant="outlined"
                startIcon={<DownloadRoundedIcon />}
                disabled={!report || isStale || reportQuery.isFetching || downloading}
                onClick={() => void handleDownload()}
              >
                {downloading ? 'Downloading…' : 'Download Excel'}
              </Button>
            ) : (
              <Typography variant="caption" color="text.secondary">
                Excel export requires the export reports permission.
              </Typography>
            )}
            {reportQuery.isFetching && report ? (
              <Typography variant="caption" color="text.secondary">
                Updating…
              </Typography>
            ) : null}
          </Stack>
          {downloadError ? <Alert severity="error">{downloadError}</Alert> : null}
        </Stack>
      </Paper>

      {customRangeError ? (
        <Alert severity="info">{customRangeError}</Alert>
      ) : reportQuery.isError ? (
        <ErrorState
          error={reportQuery.error}
          title="Unable to load the Engineering Performance report"
          onRetry={() => void reportQuery.refetch()}
        />
      ) : !report ? (
        <LoadingState message="Loading engineering performance…" />
      ) : (
        <Box sx={{ opacity: isStale ? 0.6 : 1, transition: 'opacity 120ms' }}>
          <Stack spacing={2.5}>
            {ensureArray<PerformanceDataWarning>(report.warnings).map((warning) => (
              <Alert key={warning.code} severity="warning">
                {warning.message}
                {warning.project_codes.length ? ` (${warning.project_codes.slice(0, 12).join(', ')}${
                  warning.project_codes.length > 12 ? `, +${warning.project_codes.length - 12} more` : ''
                })` : ''}
              </Alert>
            ))}
            {report.summary.projects_completed === 0 ? (
              <Alert severity="info">
                {report.empty_message ?? 'No projects were completed during the selected period.'}
                {' '}({report.period.label}: {formatDate(report.period.start_date)} to{' '}
                {formatDate(report.period.end_date)})
              </Alert>
            ) : (
              <ReportBody report={report} />
            )}
            <Accordion disableGutters variant="outlined">
              <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
                <Typography variant="subtitle2">KPI definitions</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Stack spacing={1}>
                  {ensureArray<KpiDefinition>(report.definitions).map((item) => (
                    <Box key={item.key}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {item.label}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {item.definition}
                      </Typography>
                    </Box>
                  ))}
                </Stack>
              </AccordionDetails>
            </Accordion>
          </Stack>
        </Box>
      )}
    </Stack>
  );
}
