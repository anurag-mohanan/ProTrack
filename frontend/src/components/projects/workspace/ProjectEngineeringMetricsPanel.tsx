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
import type { MetricValue, ProjectEngineeringMetrics } from '../../../types/projectPlanning';
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
            <Tooltip title={definition('stage_hours') ?? ''}>
              <InfoOutlinedIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
            </Tooltip>
          </Stack>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Stage</TableCell>
                <TableCell align="right">Original estimate</TableCell>
                <TableCell align="right">Current estimate</TableCell>
                <TableCell align="right">Actual</TableCell>
                <TableCell align="right">Variance</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {stages.rows.map((row) => (
                <TableRow key={row.key}>
                  <TableCell>{row.label}</TableCell>
                  <TableCell align="right">{hours(row.original_estimate_hours)}</TableCell>
                  <TableCell align="right">{hours(row.current_estimate_hours)}</TableCell>
                  <TableCell align="right">{hours(row.actual_hours)}</TableCell>
                  <TableCell align="right">{signedHours(row.variance_hours)}</TableCell>
                </TableRow>
              ))}
              {stages.status === 'partial' ? (
                <TableRow>
                  <TableCell colSpan={3}>
                    <Typography variant="body2" color="text.secondary">
                      Not attributed to a stage
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    {hours(
                      Number(stages.other_stage_hours) +
                        Number(stages.no_stage_hours) +
                        Number(stages.no_milestone_hours) +
                        Number(stages.invalid_milestone_hours),
                    )}
                  </TableCell>
                  <TableCell />
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
          <Typography variant="caption" color="text.secondary">
            {formatNumber(stages.coverage_percent, 1)}% of actual hours are linked to a staged milestone.
          </Typography>
        </Box>
      ) : null}

      <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 3, mb: data.issues.length ? 2 : 0 }}>
        <Metric label="Current due date" value={formatDate(milestones.current_target_date) || '—'} />
        <Metric
          label="Original baseline completion"
          value={formatDate(milestones.original_baseline_completion_date) || 'Not recorded'}
          hint={
            milestones.baseline_revision_count > 0
              ? `Current baseline ${formatDate(milestones.baseline_completion_date)} after ${milestones.baseline_revision_count} revision(s)`
              : null
          }
        />
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
