import {
  Alert,
  Box,
  Card,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { useQuery } from '@tanstack/react-query';
import {
  fetchProjectEngineeringMetrics,
  projectPlanningQueryKeys,
} from '../../../api/projectPlanning';
import type {
  DeliveryMetrics,
  DeliveryStatus,
  MetricValue,
  ProjectEngineeringMetrics,
  StageHoursRow,
} from '../../../types/projectPlanning';
import { formatDate, formatNumber } from '../../../utils/format';
import { ErrorState } from '../../common/ErrorState';
import { LoadingState } from '../../common/LoadingState';

type Hours = number | string | null | undefined;

const hours = (value: Hours) =>
  value === null || value === undefined || value === '' ? '—' : `${formatNumber(value, 1)} h`;

const signedHours = (value: Hours) => {
  if (value === null || value === undefined || value === '') return '—';
  const numeric = Number(value);
  return `${numeric > 0 ? '+' : ''}${formatNumber(numeric, 1)} h`;
};

const QUALITY_CHIP: Record<
  ProjectEngineeringMetrics['data_quality_status'],
  { label: string; color: 'success' | 'warning' | 'default' }
> = {
  available: { label: 'Data complete', color: 'success' },
  available_with_limitations: { label: 'Available with limitations', color: 'warning' },
  unavailable: { label: 'Metrics unavailable', color: 'default' },
};

function metricText(metric: MetricValue, format: (value: Hours) => string) {
  if (metric.status === 'available') return format(metric.value);
  return metric.status === 'not_applicable' ? 'Not applicable' : 'Unavailable';
}

function Metric({
  label,
  value,
  definition,
  hint,
}: {
  label: string;
  value: string;
  definition?: string;
  hint?: string | null;
}) {
  return (
    <Box sx={{ minWidth: 150 }}>
      <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
        {definition ? (
          <Tooltip title={definition}>
            <InfoOutlinedIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
          </Tooltip>
        ) : null}
      </Stack>
      <Typography variant="body1" sx={{ fontWeight: 600 }}>
        {value}
      </Typography>
      {hint ? (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', maxWidth: 220 }}>
          {hint}
        </Typography>
      ) : null}
    </Box>
  );
}

const STAGE_QUALITY: Record<
  StageHoursRow['data_quality'],
  { label: string; color: 'success' | 'warning' | 'default' }
> = {
  complete: { label: 'Complete', color: 'success' },
  limited: { label: 'Limited', color: 'warning' },
  unavailable: { label: 'Unavailable', color: 'default' },
};

const DELIVERY_STATUS: Record<
  DeliveryStatus,
  { label: string; color: 'success' | 'warning' | 'error' | 'default' }
> = {
  early: { label: 'Early', color: 'success' },
  on_time: { label: 'On time', color: 'success' },
  late: { label: 'Late', color: 'error' },
  overdue: { label: 'Overdue', color: 'error' },
  not_due: { label: 'Not yet due', color: 'default' },
  no_target: { label: 'No target date', color: 'default' },
  completion_date_missing: { label: 'Completion date missing', color: 'warning' },
  not_applicable: { label: 'Not applicable', color: 'default' },
};

const signedDays = (value: number | null) =>
  value === null ? '—' : `${value > 0 ? '+' : ''}${value} day${Math.abs(value) === 1 ? '' : 's'}`;

function DeliveryChip({ status }: { status: DeliveryStatus }) {
  const meta = DELIVERY_STATUS[status];
  return <Chip size="small" variant="outlined" label={meta.label} color={meta.color} />;
}

function ProjectDeliverySection({
  delivery,
  definition,
}: {
  delivery: DeliveryMetrics;
  definition?: string;
}) {
  const project = delivery.project;
  const milestones = delivery.milestones.filter((row) => row.status !== 'not_applicable');
  const variance =
    project.schedule_variance_days !== null
      ? signedDays(project.schedule_variance_days)
      : project.days_overdue !== null
        ? `${project.days_overdue} day${project.days_overdue === 1 ? '' : 's'} overdue`
        : '—';
  const targetHint = [
    project.current_due_date
      ? 'Project due date'
      : project.current_baseline_completion_date
        ? 'Current baseline (no due date set)'
        : null,
    project.baseline_revision_count > 1
      ? `Re-baselined ${project.baseline_revision_count - 1} time(s); current baseline ${formatDate(project.current_baseline_completion_date)}`
      : null,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <Box sx={{ mb: 2 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Delivery
        </Typography>
        {definition ? (
          <Tooltip title={definition}>
            <InfoOutlinedIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
          </Tooltip>
        ) : null}
        <DeliveryChip status={project.status} />
      </Stack>
      <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 3, mb: 1 }}>
        <Metric
          label="Original baseline completion"
          value={formatDate(project.original_baseline_completion_date) || 'Not recorded'}
          hint={
            project.reference_source === 'baseline_unverified'
              ? 'No revision history — may not be the original'
              : project.reference_source === 'original_baseline'
                ? null
                : 'No baseline; original commitment unknown'
          }
        />
        <Metric
          label="Current target date"
          value={formatDate(project.current_target_date) || 'Not set'}
          hint={targetHint || null}
        />
        <Metric
          label="Actual completion"
          value={
            formatDate(project.actual_completion_date) ||
            (project.status === 'completion_date_missing' ? 'Missing' : 'Not completed')
          }
        />
        <Metric label="Schedule variance" value={variance} hint={`Against: ${project.reference_label}`} />
      </Stack>
      {milestones.length > 0 ? (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Milestone</TableCell>
              <TableCell>Stage</TableCell>
              <TableCell>Original baseline</TableCell>
              <TableCell>Current target</TableCell>
              <TableCell>Actual completion</TableCell>
              <TableCell align="right">Variance</TableCell>
              <TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {milestones.map((row) => (
              <TableRow key={row.milestone_id}>
                <TableCell>{row.name}</TableCell>
                <TableCell>{row.stage_label ?? '—'}</TableCell>
                <TableCell>
                  {formatDate(row.original_baseline_finish_date) || 'Not recorded'}
                  {row.reference_source === 'current_due_date' ? (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      No baseline; due date used
                    </Typography>
                  ) : null}
                </TableCell>
                <TableCell>{formatDate(row.current_target_date) || '—'}</TableCell>
                <TableCell>{formatDate(row.actual_completion_date) || '—'}</TableCell>
                <TableCell align="right">
                  {row.days_overdue !== null
                    ? `${row.days_overdue} d overdue`
                    : signedDays(row.schedule_variance_days)}
                </TableCell>
                <TableCell>
                  <DeliveryChip status={row.status} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
      <Typography variant="caption" color="text.secondary">
        {delivery.sign_convention}
      </Typography>
    </Box>
  );
}

export function ProjectEngineeringMetricsPanel({ projectId }: { projectId: string }) {
  const query = useQuery({
    queryKey: projectPlanningQueryKeys.engineeringMetrics(projectId),
    queryFn: () => fetchProjectEngineeringMetrics(projectId),
  });

  if (query.isLoading) return <LoadingState message="Loading engineering hours…" />;
  if (query.error) {
    return (
      <ErrorState
        error={query.error}
        title="Unable to load engineering hours"
        onRetry={() => void query.refetch()}
      />
    );
  }
  const data = query.data;
  if (!data) return null;

  const definition = (key: string) => data.definitions.find((item) => item.key === key)?.definition;
  const chip = QUALITY_CHIP[data.data_quality_status];
  const { actual, estimate, stage_attribution: stages, milestones, quote_linkage: quote } = data;
  const pendingHours = Number(actual.draft_hours) + Number(actual.submitted_hours);
  const actualHint =
    actual.status === 'missing'
      ? 'No timesheet hours recorded although work has been completed.'
      : actual.status === 'none_recorded'
        ? 'No hours booked yet.'
        : [
            `${formatNumber(actual.approved_hours, 1)} h approved`,
            pendingHours > 0 ? `${formatNumber(pendingHours, 1)} h not yet approved` : null,
            Number(actual.rejected_hours) > 0
              ? `${formatNumber(actual.rejected_hours, 1)} h on rejected timesheets`
              : null,
          ]
            .filter(Boolean)
            .join(' · ');
  const quoteText =
    quote.status === 'unlinked'
      ? 'No active Finance quote linked'
      : quote.status === 'ambiguous'
        ? `${quote.active_quote_count} active quotes linked (unresolved)`
        : quote.details_visible
          ? `${quote.quote_reference ?? 'Quote'} rev ${quote.quote_version}${quote.quote_revision} · ${hours(quote.quote_hours)} quoted`
          : 'Finance quote linked';

  return (
    <Card sx={{ p: 2 }}>
      <Stack
        direction="row"
        sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 1.5, flexWrap: 'wrap', gap: 1 }}
      >
        <Box>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Engineering hours
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Actual hours against the approved estimate. Performance indicators only — not a forecast.
          </Typography>
        </Box>
        <Chip size="small" label={chip.label} color={chip.color} variant="outlined" />
      </Stack>

      <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 3, mb: 2 }}>
        <Metric
          label="Current approved estimate"
          value={hours(estimate.current_estimate_hours)}
          definition={definition('current_estimate')}
          hint={estimate.estimate_source_label}
        />
        <Metric
          label="Original estimate"
          value={hours(estimate.original_estimate_hours)}
          definition={definition('original_estimate')}
          hint={
            estimate.revision_count > 0
              ? `${estimate.revision_count} approved revision${estimate.revision_count === 1 ? '' : 's'}`
              : null
          }
        />
        <Metric
          label="Actual hours"
          value={actual.status === 'missing' ? 'Missing' : hours(actual.total_hours)}
          definition={definition('actual_hours')}
          hint={actualHint}
        />
        <Metric
          label="Hour variance"
          value={metricText(data.variance_hours, signedHours)}
          definition={definition('variance')}
          hint={data.variance_hours.reason}
        />
        <Metric
          label="Estimate utilization"
          value={metricText(data.utilization_percent, (v) => `${formatNumber(v, 1)}%`)}
          definition={definition('utilization')}
          hint={data.utilization_percent.status === 'available' ? null : data.utilization_percent.reason}
        />
        <Metric
          label="Remaining estimated hours"
          value={metricText(data.remaining_hours, hours)}
          definition={definition('remaining')}
          hint={
            data.remaining_hours.status === 'available' && Number(data.remaining_hours.value) < 0
              ? 'Estimate overrun'
              : null
          }
        />
      </Stack>

      {stages.rows.length > 0 ? (
        <Box sx={{ mb: 2 }}>
          <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center', mb: 0.5 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              Actual hours by stage
            </Typography>
            <Tooltip title={`${definition('stage_hours') ?? ''} ${definition('stage_variance') ?? ''}`}>
              <InfoOutlinedIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
            </Tooltip>
          </Stack>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Stage</TableCell>
                <TableCell align="right">Approved estimate</TableCell>
                <TableCell align="right">Actual hours</TableCell>
                <TableCell align="right">Variance</TableCell>
                <TableCell align="right">Utilization</TableCell>
                <TableCell>Data quality</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {stages.rows.map((row) => (
                <TableRow key={row.key}>
                  <TableCell>{row.label}</TableCell>
                  <TableCell align="right">
                    {row.has_approved_estimate ? hours(row.current_estimate_hours) : 'No approved estimate'}
                    {row.has_approved_estimate &&
                    row.original_estimate_hours !== null &&
                    Number(row.original_estimate_hours) !== Number(row.current_estimate_hours) ? (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        Original {hours(row.original_estimate_hours)}
                      </Typography>
                    ) : null}
                  </TableCell>
                  <TableCell align="right">
                    {row.actual_hours === null ? 'Unavailable' : hours(row.actual_hours)}
                    {row.percent_of_project_actual !== null ? (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        {formatNumber(row.percent_of_project_actual, 1)}% of project
                      </Typography>
                    ) : null}
                  </TableCell>
                  <TableCell align="right">{metricText(row.variance, signedHours)}</TableCell>
                  <TableCell align="right">
                    {metricText(row.utilization_percent, (v) => `${formatNumber(v, 1)}%`)}
                  </TableCell>
                  <TableCell>
                    <Tooltip title={row.data_quality_notes.join(' ')}>
                      <Chip
                        size="small"
                        variant="outlined"
                        label={STAGE_QUALITY[row.data_quality].label}
                        color={STAGE_QUALITY[row.data_quality].color}
                      />
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
              {Number(stages.unattributed_hours) > 0 && stages.total_hours !== null ? (
                <TableRow>
                  <TableCell colSpan={2}>
                    <Typography variant="body2" color="text.secondary">
                      Not attributed to a stage
                    </Typography>
                  </TableCell>
                  <TableCell align="right">{hours(stages.unattributed_hours)}</TableCell>
                  <TableCell colSpan={3} />
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
          <Typography variant="caption" color="text.secondary">
            {stages.coverage_percent !== null
              ? `${formatNumber(stages.coverage_percent, 1)}% of ${hours(stages.total_hours)} actual hours are linked to a staged milestone. `
              : ''}
            Variance = actual − approved estimate (positive means over). Hours are never spread across stages.
          </Typography>
        </Box>
      ) : null}

      <ProjectDeliverySection delivery={data.delivery} definition={definition('delivery_variance')} />

      <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 3, mb: data.issues.length ? 2 : 0 }}>
        <Metric
          label="Milestones"
          value={`${milestones.completed} of ${milestones.total - milestones.skipped} completed`}
          hint={
            milestones.open_overdue > 0
              ? `${milestones.open_overdue} open milestone(s) past their target date`
              : null
          }
        />
        <Metric label="Finance quote" value={quoteText} />
      </Stack>

      {data.issues.length ? (
        <Stack spacing={0.75}>
          {data.issues.map((issue) => (
            <Alert key={issue.code} severity={issue.severity} variant="outlined" sx={{ py: 0 }}>
              {issue.message}
            </Alert>
          ))}
        </Stack>
      ) : null}
    </Card>
  );
}
