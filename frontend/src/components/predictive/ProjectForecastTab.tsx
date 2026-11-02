import {
  Box,
  Button,
  Chip,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchProjectPredictions, predictiveQueryKeys } from '../../api/predictive';
import type { Prediction, ProjectPredictionDetail, ProjectRecordedFigures } from '../../types/Predictive';
import { formatStatus } from '../../utils/format';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { SectionTitle } from '../reports/ReportKpi';
import { ActualChip, ForecastChip, PredictionExplain } from './PredictionParts';
import { ProjectPicker } from './ProjectPicker';
import { dateText, daysVariance, hoursText, hoursVariance, percentOver, rangeText } from './predictiveFormat';

function Line({ label, value, note }: { label: string; value: string; note?: string | null }) {
  return (
    <Stack direction="row" spacing={2} sx={{ justifyContent: 'space-between', py: 0.5, borderBottom: 1, borderColor: 'divider' }}>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
      <Box sx={{ textAlign: 'right' }}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {value}
        </Typography>
        {note ? (
          <Typography variant="caption" color="text.secondary">
            {note}
          </Typography>
        ) : null}
      </Box>
    </Stack>
  );
}

function RecordedCard({ recorded }: { recorded: ProjectRecordedFigures | null }) {
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          Recorded figures
        </Typography>
        <ActualChip label="Actual / approved" />
      </Stack>
      {recorded ? (
        <>
          <Line label="Committed date" value={dateText(recorded.committed_date)} note={recorded.committed_source} />
          <Line label="Current target date" value={dateText(recorded.current_target)} />
          <Line label="Start date" value={dateText(recorded.start_date)} note={recorded.start_source} />
          <Line label="Quoted hours" value={hoursText(recorded.quoted_hours)} />
          <Line label="Original approved estimate" value={hoursText(recorded.original_estimate)} />
          <Line
            label="Current estimate"
            value={hoursText(recorded.current_estimate)}
            note={`${recorded.estimate_approved ? 'Approved' : 'Not approved'}${recorded.estimate_source ? ` · ${recorded.estimate_source}` : ''}`}
          />
          <Line label="Actual hours (approved timesheets)" value={hoursText(recorded.actual_hours)} note={recorded.actual_status} />
          <Line label="Hours awaiting approval" value={hoursText(recorded.unapproved_hours)} />
          <Line label="Open / overdue milestones" value={`${recorded.open_milestones} / ${recorded.overdue_milestones}`} />
        </>
      ) : (
        <Typography variant="body2" color="text.secondary">
          No recorded figures are available for this project.
        </Typography>
      )}
    </Paper>
  );
}

function ForecastCard({ detail }: { detail: ProjectPredictionDetail }) {
  const { delivery, final_hours: finalHours } = detail;
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          Forecast
        </Typography>
        <ForecastChip />
      </Stack>
      <Box sx={{ mb: 1.5 }}>
        <Typography variant="caption" color="text.secondary">
          Completion date
        </Typography>
        {delivery ? (
          delivery.status === 'predicted' ? (
            <>
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                {dateText(delivery.predicted_date)}
              </Typography>
              <Typography variant="body2">
                {daysVariance(delivery.variance_value)} against the target of {dateText(delivery.baseline_date)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {rangeText(delivery) ? `Likely range ${rangeText(delivery)}` : 'No range shown: fewer than 10 comparable outcomes.'}
              </Typography>
            </>
          ) : (
            <Typography variant="body2">Cannot be forecast: {delivery.reason}</Typography>
          )
        ) : (
          <Typography variant="body2" color="text.secondary">
            Not forecast (disabled or not yet run).
          </Typography>
        )}
        {delivery ? <PredictionExplain prediction={delivery} /> : null}
      </Box>
      <Box>
        <Typography variant="caption" color="text.secondary">
          Final engineering hours
        </Typography>
        {finalHours ? (
          finalHours.status === 'predicted' ? (
            <>
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                {hoursText(finalHours.predicted_value)}
              </Typography>
              <Typography variant="body2">
                {hoursVariance(finalHours.variance_value)}
                {percentOver(finalHours.variance_value, finalHours.baseline_value)
                  ? ` (${percentOver(finalHours.variance_value, finalHours.baseline_value)})`
                  : ''}{' '}
                against the approved {hoursText(finalHours.baseline_value)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {rangeText(finalHours, 'hours')
                  ? `Likely range ${rangeText(finalHours, 'hours')}`
                  : 'No range shown: fewer than 10 comparable outcomes.'}
              </Typography>
            </>
          ) : (
            <Typography variant="body2">Cannot be forecast: {finalHours.reason}</Typography>
          )
        ) : (
          <Typography variant="body2" color="text.secondary">
            Not forecast (disabled or not yet run).
          </Typography>
        )}
        {finalHours ? <PredictionExplain prediction={finalHours} /> : null}
      </Box>
    </Paper>
  );
}

function MilestoneTable({ rows }: { rows: Prediction[] }) {
  if (!rows.length) return null;
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <SectionTitle title="Milestones" subtitle="Forecast finish for open milestones with a plan." />
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Milestone</TableCell>
              <TableCell>Target (recorded)</TableCell>
              <TableCell>Forecast finish</TableCell>
              <TableCell>Variance</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id}>
                <TableCell>{r.subject_label}</TableCell>
                <TableCell>{dateText(r.baseline_date)}</TableCell>
                {r.status === 'predicted' ? (
                  <>
                    <TableCell>{dateText(r.predicted_date)}</TableCell>
                    <TableCell>{daysVariance(r.variance_value)}</TableCell>
                  </>
                ) : (
                  <TableCell colSpan={2}>
                    <Typography variant="caption" color="text.secondary">
                      Cannot be forecast: {r.reason}
                    </Typography>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}

function outcomeText(r: Prediction | undefined, kind: 'date' | 'hours'): string {
  if (!r) return '—';
  if (r.status !== 'predicted') return 'Not forecast';
  return kind === 'date' ? dateText(r.predicted_date) : hoursText(r.predicted_value);
}

function scoredText(r: Prediction | undefined, kind: 'date' | 'hours'): string | null {
  if (!r || r.outcome_status !== 'evaluated') return null;
  return kind === 'date'
    ? `Actual ${dateText(r.actual_date)} (error ${r.abs_error} days)`
    : `Actual ${hoursText(r.actual_value)} (error ${hoursText(r.abs_error)})`;
}

function HistoryTable({ history }: { history: ProjectPredictionDetail['history'] }) {
  const dates = [...new Set([...history.project_delivery, ...history.project_final_hours].map((r) => r.as_of))].sort().reverse();
  if (!dates.length) return null;
  const at = (rows: Prediction[], asOf: string) => rows.find((r) => r.as_of === asOf);
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <SectionTitle title="Forecast history" subtitle="Each prediction run is kept. Once the project finishes, forecasts are scored against what happened." />
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>As of</TableCell>
              <TableCell>Forecast completion</TableCell>
              <TableCell>Forecast final hours</TableCell>
              <TableCell>Outcome</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {dates.map((asOf) => {
              const d = at(history.project_delivery, asOf);
              const h = at(history.project_final_hours, asOf);
              const scored = [scoredText(d, 'date'), scoredText(h, 'hours')].filter(Boolean).join(' · ');
              return (
                <TableRow key={asOf}>
                  <TableCell>{dateText(asOf)}</TableCell>
                  <TableCell>{outcomeText(d, 'date')}</TableCell>
                  <TableCell>{outcomeText(h, 'hours')}</TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">
                      {scored || 'Not yet known'}
                    </Typography>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}

export function ProjectForecastTab({
  projectId,
  onSelectProject,
  onOpenScenarios,
}: {
  projectId: string | null;
  onSelectProject: (projectId: string | null) => void;
  onOpenScenarios: () => void;
}) {
  const query = useQuery({
    queryKey: predictiveQueryKeys.project(projectId ?? ''),
    queryFn: () => fetchProjectPredictions(projectId!),
    enabled: Boolean(projectId),
  });
  const detail = query.data;
  return (
    <Box>
      <ProjectPicker value={projectId} onChange={onSelectProject} />
      {!projectId ? (
        <Typography variant="body2" color="text.secondary">
          Choose a project, or open one from the Portfolio tab.
        </Typography>
      ) : null}
      {query.isLoading ? <LoadingState message="Loading project forecast…" /> : null}
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      {detail ? (
        <Stack spacing={2}>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              {[detail.project.tool_number, detail.project.part_description].filter(Boolean).join(' · ') || detail.project.code}
            </Typography>
            {detail.project.execution_status ? <Chip size="small" label={formatStatus(detail.project.execution_status)} /> : null}
            <Box sx={{ flex: 1 }} />
            <Button size="small" variant="outlined" onClick={onOpenScenarios}>
              What-if scenarios
            </Button>
          </Stack>
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }}>
            <RecordedCard recorded={detail.recorded} />
            <ForecastCard detail={detail} />
          </Box>
          <MilestoneTable rows={detail.milestones} />
          <HistoryTable history={detail.history} />
        </Stack>
      ) : null}
    </Box>
  );
}
