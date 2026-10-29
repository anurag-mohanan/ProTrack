import { useMemo, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  Link,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TableSortLabel,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import { Link as RouterLink } from 'react-router-dom';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { fetchCustomers, fetchTeams, fetchUsers } from '../../api/lookups';
import { fetchProjectTypes } from '../../api/projectTemplates';
import { fetchPublicSettings } from '../../api/settings';
import {
  downloadQuoteToDeliveryExcel,
  fetchQuoteToDelivery,
  quoteToDeliveryQueryKeys,
} from '../../api/quoteToDelivery';
import type { KpiDefinition, PerformanceDataWarning } from '../../types/EngineeringPerformance';
import type {
  QtdDataQuality,
  QtdPopulationKey,
  QtdProjectRow,
  QtdSegment,
  QtdStageRow,
  QuoteToDeliveryParams,
  QuoteToDeliveryReport,
} from '../../types/QuoteToDelivery';
import type { Customer, User } from '../../types';
import type { Team } from '../../types/Team';
import type { ProjectType } from '../../types/ProjectTemplate';
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS, ensureArray } from '../../types/pagination';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { formatDate, formatNumber, userDisplayName } from '../../utils/format';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { PerformancePeriodFields } from './PerformancePeriodFields';
import { KpiCard, SectionTitle } from './ReportKpi';
import { hours, percent, signedDays, signedHours, varianceColor } from './reportFormat';
import { usePerformancePeriod } from './usePerformancePeriod';

const OPEN_STATUS_OPTIONS = [
  { value: 'planning', label: 'Planning' },
  { value: 'currently_being_worked_on', label: 'In progress' },
  { value: 'on_hold', label: 'On hold' },
];

const CLASSIFICATION_OPTIONS = [
  { value: 'full_design', label: 'Full design' },
  { value: 'small_task', label: 'Small task' },
  { value: 'unclassified', label: 'Unclassified' },
];

const SEGMENT_LABELS: Record<QtdSegment, string> = {
  over_estimate: 'Over estimate',
  under_estimate: 'Under estimate',
  on_estimate: 'On estimate',
  not_comparable: 'Not in hour totals',
  metrics_incomplete: 'Missing or incomplete metrics',
  stage_eligible: 'Eligible for stage',
  stage_over: 'Over stage estimate',
  stage_missing_attribution: 'Stage hours not attributable',
  stage_no_estimate: 'No stage estimate',
  delivered_on_or_before: 'Delivered on or before original baseline',
  delivered_after: 'Delivered after original baseline',
  delivery_not_evaluable: 'No original baseline to compare',
  overdue_milestones: 'Overdue milestones',
  past_target: 'Past current target',
  no_target: 'No current target date',
};

const HISTORICAL_SEGMENTS: QtdSegment[] = ['delivered_on_or_before', 'delivered_after', 'delivery_not_evaluable'];
const OPERATIONAL_SEGMENTS: QtdSegment[] = ['overdue_milestones', 'past_target', 'no_target'];

const DATA_QUALITY: Record<QtdDataQuality, { label: string; color: 'success' | 'warning' | 'default' }> = {
  available: { label: 'Complete', color: 'success' },
  available_with_limitations: { label: 'Limited', color: 'warning' },
  unavailable: { label: 'Unavailable', color: 'default' },
};

const DELIVERY_STATUS_LABELS: Record<string, string> = {
  early: 'Early',
  on_time: 'On time',
  late: 'Late',
  overdue: 'Overdue',
  not_due: 'Not due',
  no_target: 'No target date',
  completion_date_missing: 'Completion date missing',
  not_applicable: 'Not applicable',
};

const STATUS_LABELS: Record<string, string> = {
  planning: 'Planning',
  currently_being_worked_on: 'In progress',
  on_hold: 'On hold',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

interface Drilldown {
  segment: QtdSegment;
  stage?: string;
  label: string;
}

type DrillHandler = (drill: Drilldown | null, population?: QtdPopulationKey) => void;

function definitionFor(report: QuoteToDeliveryReport, key: string): string | undefined {
  return ensureArray<KpiDefinition>(report.definitions).find((item) => item.key === key)?.definition;
}

function CountLink({ count, onClick, label }: { count: number; onClick: () => void; label: string }) {
  if (!count) return <>0</>;
  return (
    <Link component="button" type="button" underline="hover" onClick={onClick} aria-label={`Show ${label}`}>
      {count}
    </Link>
  );
}

function SummarySection({
  report,
  onDrill,
  active,
}: {
  report: QuoteToDeliveryReport;
  onDrill: DrillHandler;
  active: QtdSegment | null;
}) {
  const s = report.summary;
  const drill = (segment: QtdSegment) => () =>
    onDrill(active === segment ? null : { segment, label: SEGMENT_LABELS[segment] });
  const sources = Object.entries(s.estimate_source_counts)
    .map(([key, count]) => `${count} ${key.replace(/_/g, ' ')}`)
    .join(' · ');
  return (
    <Paper sx={{ p: 2 }}>
      <SectionTitle
        title={`Summary — ${report.population.label}`}
        subtitle={
          report.population.key === 'completed'
            ? `Completed ${formatDate(report.period.start_date)} to ${formatDate(report.period.end_date)} (by actual completion date)`
            : `Open as of ${formatDate(report.population.as_of)} · hours consumed to date, not a forecast`
        }
      />
      <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, minmax(0, 1fr))' } }}>
        <KpiCard
          label="Eligible projects"
          value={String(s.eligible_projects)}
          definition={definitionFor(report, 'eligible_projects')}
        />
        <KpiCard
          label="Original quoted hours"
          value={hours(s.quoted_hours_total)}
          caption={`${s.projects_with_quoted_hours} project(s) with quoted hours`}
          definition={definitionFor(report, 'quoted_hours_total')}
        />
        <KpiCard
          label="Current approved estimate"
          value={hours(s.current_estimate_total)}
          caption={`${s.projects_with_current_estimate} project(s)${sources ? ` · source: ${sources}` : ''}`}
          definition={definitionFor(report, 'current_estimate_total')}
        />
        <KpiCard
          label="Actual hours"
          value={hours(s.actual_hours_total)}
          caption={`${s.projects_with_actual_hours} project(s)${
            s.projects_actual_missing ? ` · ${s.projects_actual_missing} missing (not zero)` : ''
          }`}
          definition={definitionFor(report, 'actual_hours_total')}
        />
        <KpiCard
          label="Aggregate variance (h)"
          value={signedHours(s.variance_hours)}
          caption={
            s.comparable_projects
              ? `${hours(s.comparable_actual_hours)} actual vs ${hours(s.comparable_estimate_hours)} estimate · ${s.comparable_projects} comparable project(s)`
              : 'No comparable projects'
          }
          definition={definitionFor(report, 'variance_hours')}
        />
        <KpiCard
          label="Utilization"
          value={percent(s.utilization_percent)}
          caption="Σ actual ÷ Σ approved estimate"
          definition={definitionFor(report, 'utilization_percent')}
        />
        <KpiCard
          label="Over estimate"
          value={String(s.projects_over_estimate)}
          caption={`${s.projects_under_estimate} under · ${s.projects_on_estimate} on estimate`}
          definition={definitionFor(report, 'over_under')}
          onClick={drill('over_estimate')}
          selected={active === 'over_estimate'}
        />
        <KpiCard
          label="Under estimate"
          value={String(s.projects_under_estimate)}
          definition={definitionFor(report, 'over_under')}
          onClick={drill('under_estimate')}
          selected={active === 'under_estimate'}
        />
        <KpiCard
          label="Missing or incomplete metrics"
          value={String(s.projects_metrics_unavailable + s.projects_metrics_limited)}
          caption={`${s.projects_metrics_unavailable} unavailable · ${s.projects_metrics_limited} limited · ${s.projects_not_comparable} not in hour totals`}
          definition={definitionFor(report, 'metrics_incomplete')}
          onClick={drill('metrics_incomplete')}
          selected={active === 'metrics_incomplete'}
        />
      </Box>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
        Quoted hours and approved estimates are reported separately and never added together. Variance and
        utilization use only projects with both an approved estimate above zero and known actual hours.
      </Typography>
    </Paper>
  );
}

function StageSection({
  report,
  onDrill,
}: {
  report: QuoteToDeliveryReport;
  onDrill: DrillHandler;
}) {
  const rows = ensureArray<QtdStageRow>(report.stages.rows);
  const open = (row: QtdStageRow, segment: QtdSegment) => () =>
    onDrill({ segment, stage: row.key, label: `${row.label}: ${SEGMENT_LABELS[segment]}` });
  return (
    <Paper sx={{ p: 2 }}>
      <SectionTitle title="Stage-wise estimate vs actual" subtitle={report.stages.eligibility_rule} />
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Stage</TableCell>
              <TableCell align="right">Projects with stage</TableCell>
              <TableCell align="right">Eligible</TableCell>
              <TableCell align="right">Approved estimate (h)</TableCell>
              <TableCell align="right">Actual (h)</TableCell>
              <TableCell align="right">Variance (h)</TableCell>
              <TableCell align="right">Utilization</TableCell>
              <TableCell align="right">Over estimate</TableCell>
              <TableCell align="right">Not attributable</TableCell>
              <TableCell align="right">No estimate</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.key} hover>
                <TableCell>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {row.label}
                  </Typography>
                  {row.explanation ? (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', maxWidth: 360 }}>
                      {row.explanation}
                    </Typography>
                  ) : null}
                </TableCell>
                <TableCell align="right">{row.projects_in_plan}</TableCell>
                <TableCell align="right">
                  <CountLink count={row.eligible_projects} onClick={open(row, 'stage_eligible')} label="eligible projects" />
                </TableCell>
                <TableCell align="right">{hours(row.estimate_hours)}</TableCell>
                <TableCell align="right">{hours(row.actual_hours)}</TableCell>
                <TableCell align="right" sx={{ color: varianceColor(row.variance_hours) }}>
                  {signedHours(row.variance_hours)}
                </TableCell>
                <TableCell align="right">{percent(row.utilization_percent)}</TableCell>
                <TableCell align="right">
                  <CountLink count={row.projects_over_estimate} onClick={open(row, 'stage_over')} label="projects over the stage estimate" />
                </TableCell>
                <TableCell align="right">
                  <CountLink
                    count={row.projects_missing_attribution}
                    onClick={open(row, 'stage_missing_attribution')}
                    label="projects without attributable stage hours"
                  />
                </TableCell>
                <TableCell align="right">
                  <CountLink count={row.projects_without_estimate} onClick={open(row, 'stage_no_estimate')} label="projects without a stage estimate" />
                </TableCell>
              </TableRow>
            ))}
            {!rows.length ? (
              <TableRow>
                <TableCell colSpan={10}>
                  <Typography variant="body2" color="text.secondary">
                    No project in this population has engineering stages.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </TableContainer>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
        {report.stages.source}
      </Typography>
    </Paper>
  );
}

function DeliverySection({ report, onDrill }: { report: QuoteToDeliveryReport; onDrill: DrillHandler }) {
  const h = report.delivery.historical;
  const o = report.delivery.operational;
  const historical = (segment: QtdSegment) => () =>
    onDrill({ segment, label: SEGMENT_LABELS[segment] }, 'completed');
  const operational = (segment: QtdSegment) => () =>
    onDrill({ segment, label: SEGMENT_LABELS[segment] }, 'active');
  const excluded = h.excluded_baseline_unverified + h.excluded_due_date_only + h.excluded_no_reference;
  return (
    <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' } }}>
      <Paper sx={{ p: 2 }}>
        <SectionTitle
          title="Historical delivery"
          subtitle={`Completed ${formatDate(report.period.start_date)} to ${formatDate(report.period.end_date)} · vs original approved baseline`}
        />
        <Table size="small">
          <TableBody>
            <TableRow>
              <TableCell>Completed projects in period</TableCell>
              <TableCell align="right">{h.completed_projects}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Eligible (original baseline recorded)</TableCell>
              <TableCell align="right">{h.eligible_projects}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>On or before baseline</TableCell>
              <TableCell align="right">
                <CountLink count={h.on_or_before_baseline} onClick={historical('delivered_on_or_before')} label="projects on or before baseline" />
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell>After baseline</TableCell>
              <TableCell align="right">
                <CountLink count={h.after_baseline} onClick={historical('delivered_after')} label="projects after baseline" />
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Average / median variance</TableCell>
              <TableCell align="right">
                {signedDays(h.average_variance_days)} / {signedDays(h.median_variance_days)}
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell>
                Missing original baseline
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  {h.excluded_baseline_unverified} baseline without history · {h.excluded_due_date_only} due date only ·{' '}
                  {h.excluded_no_reference} no date
                </Typography>
              </TableCell>
              <TableCell align="right">
                <CountLink count={excluded} onClick={historical('delivery_not_evaluable')} label="projects without an original baseline" />
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Completed without a completion date (any period)</TableCell>
              <TableCell align="right">{h.completed_without_completion_date}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
          {h.population_rule} {report.delivery.sign_convention}
        </Typography>
      </Paper>
      <Paper sx={{ p: 2 }}>
        <SectionTitle
          title="Current overdue work"
          subtitle={`Open projects as of ${formatDate(o.as_of)} · vs current target dates · period not applied`}
        />
        <Table size="small">
          <TableBody>
            <TableRow>
              <TableCell>Open projects</TableCell>
              <TableCell align="right">{o.active_projects}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Projects with overdue milestones</TableCell>
              <TableCell align="right">
                <CountLink count={o.projects_with_overdue_milestones} onClick={operational('overdue_milestones')} label="projects with overdue milestones" />
                {o.overdue_milestones ? ` (${o.overdue_milestones} milestones)` : ''}
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Projects past their current target</TableCell>
              <TableCell align="right">
                <CountLink count={o.projects_past_current_target} onClick={operational('past_target')} label="projects past their target" />
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Projects without a current target date</TableCell>
              <TableCell align="right">
                <CountLink count={o.projects_without_current_target} onClick={operational('no_target')} label="projects without a target" />
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Projects without an original baseline</TableCell>
              <TableCell align="right">{o.projects_without_original_baseline}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
          {o.population_rule} Missing dates are a data-quality gap, not a risk rating.
        </Typography>
      </Paper>
    </Box>
  );
}

const SORTABLE: { key: string; label: string; align?: 'right' }[] = [
  { key: 'code', label: 'Project' },
  { key: 'customer', label: 'Customer' },
  { key: 'status', label: 'Status' },
  { key: 'quoted_hours', label: 'Quoted (h)', align: 'right' },
  { key: 'current_estimate_hours', label: 'Current estimate (h)', align: 'right' },
  { key: 'actual_hours', label: 'Actual (h)', align: 'right' },
  { key: 'variance_hours', label: 'Variance (h)', align: 'right' },
  { key: 'utilization_percent', label: 'Utilization', align: 'right' },
];

function ProjectTable({
  report,
  sort,
  onSort,
  onPage,
  onPageSize,
}: {
  report: QuoteToDeliveryReport;
  sort: string;
  onSort: (key: string) => void;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
}) {
  const page = report.projects;
  const items = ensureArray<QtdProjectRow>(page.items);
  const sortKey = sort.replace(/^-/, '');
  const direction = sort.startsWith('-') ? 'desc' : 'asc';
  const completed = report.population.key === 'completed';
  const header = (key: string, label: string, align?: 'right') => (
    <TableCell key={key} align={align} sortDirection={sortKey === key ? direction : false}>
      <TableSortLabel active={sortKey === key} direction={sortKey === key ? direction : 'asc'} onClick={() => onSort(key)}>
        {label}
      </TableSortLabel>
    </TableCell>
  );
  return (
    <>
      <TableContainer sx={{ maxHeight: 640 }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              {SORTABLE.slice(0, 2).map((col) => header(col.key, col.label, col.align))}
              <TableCell>Classification / type</TableCell>
              {SORTABLE.slice(2).map((col) => header(col.key, col.label, col.align))}
              <TableCell>Original baseline</TableCell>
              {completed
                ? header('actual_completion_date', 'Completed')
                : header('current_target_date', 'Current target')}
              {completed ? header('delivery_variance_days', 'Delivery variance', 'right') : <TableCell align="right">Overdue</TableCell>}
              <TableCell>Data quality</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((row) => {
              const quality = DATA_QUALITY[row.data_quality_status];
              const warnings = row.data_quality_warnings.length
                ? row.data_quality_warnings.join(' ')
                : row.data_quality_issues.map((code) => code.replace(/_/g, ' ')).join(', ');
              return (
                <TableRow key={row.project_id} hover>
                  <TableCell>
                    <Link component={RouterLink} to={`/projects/${row.project_id}`} underline="hover" sx={{ fontWeight: 600 }}>
                      {row.code ?? row.tool_number ?? '—'}
                    </Link>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      {row.tool_number && row.code ? `${row.tool_number} · ` : ''}
                      {row.part_description ?? ''}
                    </Typography>
                  </TableCell>
                  <TableCell>{row.customer_name ?? '—'}</TableCell>
                  <TableCell>
                    {row.classification_label ?? '—'}
                    {row.project_type_name ? (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        {row.project_type_name}
                      </Typography>
                    ) : null}
                  </TableCell>
                  <TableCell>{STATUS_LABELS[row.execution_status] ?? row.execution_status}</TableCell>
                  <TableCell align="right">{hours(row.quoted_hours)}</TableCell>
                  <TableCell align="right">
                    {hours(row.current_estimate_hours)}
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      {row.estimate_source_label}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    {row.actual_status === 'missing' ? (
                      <Tooltip title="Completed work with no timesheet hours: missing, not zero.">
                        <span>Missing</span>
                      </Tooltip>
                    ) : (
                      hours(row.actual_hours)
                    )}
                  </TableCell>
                  <TableCell align="right" sx={{ color: varianceColor(row.variance_hours) }}>
                    {signedHours(row.variance_hours)}
                    {!row.comparable && row.variance_hours != null ? (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        not in totals
                      </Typography>
                    ) : null}
                  </TableCell>
                  <TableCell align="right">{percent(row.utilization_percent)}</TableCell>
                  <TableCell>{row.original_baseline_completion_date ? formatDate(row.original_baseline_completion_date) : '—'}</TableCell>
                  <TableCell>
                    {completed
                      ? formatDate(row.actual_completion_date) || '—'
                      : formatDate(row.current_target_date) || '—'}
                  </TableCell>
                  <TableCell align="right">
                    {completed ? (
                      row.delivery_variance_days == null ? (
                        <Tooltip title="Shown only against an original approved baseline.">
                          <span>—</span>
                        </Tooltip>
                      ) : (
                        signedDays(row.delivery_variance_days)
                      )
                    ) : row.days_overdue ? (
                      `${row.days_overdue} d`
                    ) : row.open_overdue_milestones ? (
                      `${row.open_overdue_milestones} milestone(s)`
                    ) : (
                      DELIVERY_STATUS_LABELS[row.delivery_status] ?? '—'
                    )}
                  </TableCell>
                  <TableCell>
                    <Tooltip title={warnings || 'No data-quality issues.'}>
                      <Chip size="small" label={quality.label} color={quality.color} variant="outlined" />
                    </Tooltip>
                  </TableCell>
                </TableRow>
              );
            })}
            {!items.length ? (
              <TableRow>
                <TableCell colSpan={14}>
                  <Typography variant="body2" color="text.secondary">
                    No projects match the current filters{page.search ? ' and search' : ''}.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination
        component="div"
        count={page.total}
        page={Math.max(0, page.page - 1)}
        onPageChange={(_, next) => onPage(next + 1)}
        rowsPerPage={page.page_size || DEFAULT_PAGE_SIZE}
        onRowsPerPageChange={(event) => onPageSize(Number(event.target.value))}
        rowsPerPageOptions={[...PAGE_SIZE_OPTIONS]}
      />
    </>
  );
}

interface QuoteToDeliveryPanelProps {
  canExport: boolean;
  includeArchived: boolean;
}

export function QuoteToDeliveryPanel({ canExport, includeArchived }: QuoteToDeliveryPanelProps) {
  const settingsQuery = useQuery({ queryKey: ['settings', 'public'], queryFn: fetchPublicSettings, staleTime: 300_000 });
  const fyStartMonth = settingsQuery.data?.company.financial_year_start_month ?? 4;
  const period = usePerformancePeriod(fyStartMonth);

  const [population, setPopulation] = useState<QtdPopulationKey>('completed');
  const [customerId, setCustomerId] = useState('');
  const [teamId, setTeamId] = useState('');
  const [projectTypeId, setProjectTypeId] = useState('');
  const [classification, setClassification] = useState('');
  const [status, setStatus] = useState('');
  const [designLeaderId, setDesignLeaderId] = useState('');
  const [designerId, setDesignerId] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 350);
  const [drill, setDrill] = useState<Drilldown | null>(null);
  const [sort, setSort] = useState<string | null>(null);
  const [pageState, setPageState] = useState({ key: '', page: 1 });
  const [pageSize, setPageSize] = useState<number>(DEFAULT_PAGE_SIZE);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

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
  const lookupError = customerQuery.error ?? teamsQuery.error ?? usersQuery.error ?? typesQuery.error;

  const filterKey = [
    population, customerId, teamId, projectTypeId, classification, status, designLeaderId, designerId, search,
    drill?.segment, drill?.stage, JSON.stringify(period.params), includeArchived, sort, pageSize,
  ].join('|');
  // Any filter, search, drill-down or sort change returns the table to page 1.
  const page = pageState.key === filterKey ? pageState.page : 1;
  const setPage = (next: number) => setPageState({ key: filterKey, page: next });

  const params = useMemo<QuoteToDeliveryParams>(
    () => ({
      ...period.params,
      population,
      customer_id: customerId || undefined,
      team_id: teamId || undefined,
      project_type_id: projectTypeId || undefined,
      project_classification: classification || undefined,
      status: population === 'active' ? status || undefined : undefined,
      design_leader_id: designLeaderId || undefined,
      designer_id: designerId || undefined,
      include_archived: includeArchived,
      search: search || undefined,
      segment: drill?.segment,
      stage: drill?.stage,
      sort: sort ?? undefined,
      page,
      page_size: pageSize,
    }),
    [
      period.params, population, customerId, teamId, projectTypeId, classification, status, designLeaderId,
      designerId, includeArchived, search, drill, sort, page, pageSize,
    ],
  );

  const periodBlocked = population === 'completed' ? period.customRangeError : null;
  const reportQuery = useQuery({
    queryKey: quoteToDeliveryQueryKeys.report(params),
    queryFn: () => fetchQuoteToDelivery(params),
    enabled: !periodBlocked && settingsQuery.isFetched,
    placeholderData: keepPreviousData,
  });
  const report = reportQuery.data;
  const isStale = reportQuery.isPlaceholderData;

  const handleDrill: DrillHandler = (next, nextPopulation) => {
    if (nextPopulation && nextPopulation !== population) {
      setPopulation(nextPopulation);
      setStatus('');
      setSort(null);
    }
    setDrill(next);
  };

  const changePopulation = (next: QtdPopulationKey) => {
    setPopulation(next);
    setStatus('');
    setSort(null);
    if (drill && (HISTORICAL_SEGMENTS.includes(drill.segment) || OPERATIONAL_SEGMENTS.includes(drill.segment))) {
      setDrill(null);
    }
  };

  const handleSort = (key: string) => {
    const current = sort ?? report?.projects.sort ?? '';
    setSort(current === key ? `-${key}` : key);
  };

  const handleDownload = async () => {
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadQuoteToDeliveryExcel(params);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : 'Export failed.');
    } finally {
      setDownloading(false);
    }
  };

  const customers = ensureArray<Customer>(customerQuery.data);
  const userOptions = ensureArray<User>(usersQuery.data).map((item) => ({
    id: item.id,
    label: userDisplayName(item) || item.email,
  }));

  const select = (
    label: string,
    value: string,
    onChange: (value: string) => void,
    options: { id: string; label: string }[],
    allLabel: string,
    disabled = false,
  ) => (
    <TextField
      select
      size="small"
      label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
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

  const grid = {
    display: 'grid',
    gap: 1.5,
    gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, minmax(0, 1fr))', md: 'repeat(4, minmax(0, 1fr))' },
    '& > *': { minWidth: 0 },
  } as const;

  return (
    <Stack spacing={2.5}>
      <Paper sx={{ p: 2 }}>
        <Stack spacing={1.5}>
          <Box>
            <Typography variant="h6">Quote-to-Delivery</Typography>
            <Typography variant="body2" color="text.secondary">
              Quoted hours, approved estimates, actual hours, stage hours and delivery dates per project, from the same
              rules as each project&apos;s Engineering metrics. No forecasts or risk scores.
            </Typography>
          </Box>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ alignItems: { md: 'center' } }}>
            <ToggleButtonGroup
              exclusive
              size="small"
              value={population}
              onChange={(_, value: QtdPopulationKey | null) => value && changePopulation(value)}
              aria-label="Project population"
            >
              <ToggleButton value="completed">Completed in period</ToggleButton>
              <ToggleButton value="active">Open now</ToggleButton>
            </ToggleButtonGroup>
            <Typography variant="caption" color="text.secondary">
              {population === 'completed'
                ? 'Historical: projects selected by actual completion date in the period.'
                : 'Operational: projects in Planning, In progress or On hold today, judged against current target dates. The period does not apply.'}
            </Typography>
          </Stack>
          <Box sx={grid}>
            <PerformancePeriodFields
              period={period}
              label="Period (completion date)"
              disabled={population === 'active'}
            />
          </Box>
          <Box sx={grid}>
            {select('Customer', customerId, setCustomerId, customers.map((item) => ({ id: item.id, label: item.name })), 'All customers')}
            {select(
              'Team',
              teamId,
              setTeamId,
              ensureArray<Team>(teamsQuery.data).map((item) => ({ id: item.id, label: item.name })),
              'All accessible teams',
            )}
            {select(
              'Classification',
              classification,
              setClassification,
              CLASSIFICATION_OPTIONS.map((item) => ({ id: item.value, label: item.label })),
              'All classifications',
            )}
            {select(
              'Project type',
              projectTypeId,
              setProjectTypeId,
              ensureArray<ProjectType>(typesQuery.data).map((item) => ({ id: item.id, label: item.name })),
              'All project types',
            )}
            {select(
              'Status',
              population === 'active' ? status : '',
              setStatus,
              OPEN_STATUS_OPTIONS.map((item) => ({ id: item.value, label: item.label })),
              population === 'active' ? 'All open statuses' : 'Completed',
              population !== 'active',
            )}
            {select('Design leader / PM', designLeaderId, setDesignLeaderId, userOptions, 'Anyone')}
            {select('Designer', designerId, setDesignerId, userOptions, 'Anyone')}
            <TextField
              size="small"
              label="Search projects"
              placeholder="Code, tool #, part, customer"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              slotProps={{ htmlInput: { maxLength: 100 }, inputLabel: { shrink: true } }}
              fullWidth
            />
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
              }}
            />
          ) : null}
          <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap', alignItems: 'center' }}>
            {canExport ? (
              <Tooltip title="Exports every project matching the filters, search and drill-down — not only the visible page.">
                <span>
                  <Button
                    variant="outlined"
                    startIcon={<DownloadRoundedIcon />}
                    disabled={!report || isStale || reportQuery.isFetching || downloading}
                    onClick={() => void handleDownload()}
                  >
                    {downloading ? 'Downloading…' : `Download Excel${report ? ` (${report.projects.total} rows)` : ''}`}
                  </Button>
                </span>
              </Tooltip>
            ) : (
              <Typography variant="caption" color="text.secondary">
                Excel export requires the export reports permission.
              </Typography>
            )}
            {drill ? (
              <Chip label={`Drill-down: ${drill.label}`} onDelete={() => setDrill(null)} color="primary" variant="outlined" />
            ) : null}
            {reportQuery.isFetching && report ? (
              <Typography variant="caption" color="text.secondary">
                Updating…
              </Typography>
            ) : null}
          </Stack>
          {downloadError ? <Alert severity="error">{downloadError}</Alert> : null}
        </Stack>
      </Paper>

      {periodBlocked ? (
        <Alert severity="info">{periodBlocked}</Alert>
      ) : reportQuery.isError ? (
        <ErrorState
          error={reportQuery.error}
          title="Unable to load the Quote-to-Delivery report"
          onRetry={() => void reportQuery.refetch()}
        />
      ) : !report ? (
        <LoadingState message="Loading quote-to-delivery report…" />
      ) : (
        <Box sx={{ opacity: isStale ? 0.6 : 1, transition: 'opacity 120ms' }}>
          <Stack spacing={2.5}>
            {ensureArray<PerformanceDataWarning>(report.warnings).map((warning) => (
              <Alert key={warning.code} severity={warning.code === 'active_consumption_to_date' ? 'info' : 'warning'}>
                {warning.message}
                {warning.project_codes.length
                  ? ` (${warning.project_codes.slice(0, 12).join(', ')}${
                      warning.project_codes.length > 12 ? `, +${warning.project_codes.length - 12} more` : ''
                    })`
                  : ''}
              </Alert>
            ))}
            {report.empty_message ? (
              <Alert severity="info">
                {report.empty_message}
                {report.population.key === 'completed'
                  ? ` (${report.period.label}: ${formatDate(report.period.start_date)} to ${formatDate(report.period.end_date)})`
                  : ''}
              </Alert>
            ) : (
              <SummarySection report={report} onDrill={handleDrill} active={drill?.segment ?? null} />
            )}
            <Paper sx={{ p: 2 }}>
              <SectionTitle
                title="Projects"
                subtitle={`${formatNumber(report.projects.total, 0) || 0} project(s)${
                  drill ? ` · ${drill.label}` : ''
                }${report.projects.search ? ` · search “${report.projects.search}”` : ''} · totals above cover the whole population`}
              />
              <ProjectTable
                report={report}
                sort={sort ?? report.projects.sort}
                onSort={handleSort}
                onPage={setPage}
                onPageSize={(size) => {
                  setPageSize(size);
                  setPage(1);
                }}
              />
            </Paper>
            {report.empty_message ? null : <StageSection report={report} onDrill={handleDrill} />}
            <DeliverySection report={report} onDrill={handleDrill} />
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
