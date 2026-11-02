import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  activatePredictionModel,
  fetchPredictionAccuracy,
  predictiveQueryKeys,
  updatePredictionSetting,
} from '../../api/predictive';
import { getErrorMessage } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import type { AccuracyMetrics, AccuracyTypeReport, PredictionTypeKey } from '../../types/Predictive';
import { formatNumber } from '../../utils/format';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { dateText, shareText } from './predictiveFormat';

function unitText(unit: string): string {
  return unit === 'amount' ? '' : ` ${unit}`;
}

function MetricsLine({ metrics, unit }: { metrics: AccuracyMetrics; unit: string }) {
  if (!metrics.reportable) {
    return (
      <Typography variant="body2" color="text.secondary">
        {metrics.message ?? `Only ${metrics.evaluated} scored prediction(s).`}
      </Typography>
    );
  }
  const u = unitText(unit);
  return (
    <Stack spacing={0.5}>
      <Typography variant="body2">
        Mean absolute error <strong>{formatNumber(metrics.mean_absolute_error ?? 0, 1)}{u}</strong> · median{' '}
        {formatNumber(metrics.median_absolute_error ?? 0, 1)}{u} · bias {formatNumber(metrics.mean_bias ?? 0, 1)}{u} (positive means
        forecasts were too high or too late) · n = {metrics.evaluated}
      </Typography>
      {metrics.mean_absolute_percentage_error !== null && metrics.mean_absolute_percentage_error !== undefined ? (
        <Typography variant="body2">
          Mean absolute percentage error {formatNumber(metrics.mean_absolute_percentage_error, 1)}% (n = {metrics.percentage_error_n})
        </Typography>
      ) : null}
      {metrics.naive_baseline ? (
        <Typography variant="body2">
          Against the recorded target or estimate alone: {formatNumber(metrics.naive_baseline.model_mae ?? 0, 1)}
          {u} vs {formatNumber(metrics.naive_baseline.baseline_mae ?? 0, 1)}
          {u} ({metrics.naive_baseline.better_than_baseline ? 'the model is better' : 'the model is not better'}, n ={' '}
          {metrics.naive_baseline.n})
        </Typography>
      ) : null}
      {metrics.range_coverage ? (
        <Typography variant="body2">
          Actual inside the likely range {shareText(metrics.range_coverage.inside_share)} of the time (intended{' '}
          {shareText(metrics.range_coverage.expected_share)}, n = {metrics.range_coverage.n})
        </Typography>
      ) : null}
    </Stack>
  );
}

function TypeCard({
  report,
  canManage,
  onToggle,
  onActivate,
}: {
  report: AccuracyTypeReport;
  canManage: boolean;
  onToggle: (report: AccuracyTypeReport) => void;
  onActivate: (report: AccuracyTypeReport, version: string) => void;
}) {
  const scoredHorizons = report.by_horizon.filter((h) => h.evaluated > 0);
  const calibration = report.calibration.filter((c) => c.n > 0);
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap', mb: 1 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          {report.label}
        </Typography>
        <Chip size="small" color={report.enabled ? 'success' : 'default'} label={report.enabled ? 'Enabled' : 'Disabled'} />
        {report.active_version ? <Chip size="small" variant="outlined" label={`Active model ${report.active_version}`} /> : null}
        <Box sx={{ flex: 1 }} />
        {canManage ? (
          <Button size="small" onClick={() => onToggle(report)}>
            {report.enabled ? 'Disable' : 'Enable'}
          </Button>
        ) : null}
      </Stack>
      {!report.enabled && report.disabled_reason ? (
        <Alert severity="info" sx={{ mb: 1 }}>
          Disabled: {report.disabled_reason}. Stored predictions are kept; new runs skip this type.
        </Alert>
      ) : null}
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
        {report.overall.evaluated} scored against actual outcomes · {report.pending} awaiting an outcome · {report.not_evaluable} cannot be
        scored
      </Typography>
      <MetricsLine metrics={report.overall} unit={report.unit} />
      {report.degradation.status !== 'insufficient' ? (
        <Alert severity={report.degradation.status === 'degraded' ? 'warning' : 'success'} sx={{ mt: 1 }}>
          {report.degradation.message}
        </Alert>
      ) : null}

      {scoredHorizons.length ? (
        <TableContainer sx={{ mt: 1.5 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Forecast horizon</TableCell>
                <TableCell align="right">Scored</TableCell>
                <TableCell align="right">Mean absolute error</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {report.by_horizon.map((h) => (
                <TableRow key={h.horizon}>
                  <TableCell>{h.horizon}</TableCell>
                  <TableCell align="right">{h.evaluated}</TableCell>
                  <TableCell align="right">
                    {h.reportable ? `${formatNumber(h.mean_absolute_error ?? 0, 1)}${unitText(report.unit)}` : 'Too few to report'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      {calibration.length ? (
        <Typography variant="body2" sx={{ mt: 1 }}>
          Calibration (observed share at forecast time against how often it then happened):{' '}
          {calibration.map((c) => `${c.band}: ${c.event_rate !== undefined ? shareText(c.event_rate) : 'too few'} (n = ${c.n})`).join(' · ')}
        </Typography>
      ) : null}

      {report.examples.length ? (
        <TableContainer sx={{ mt: 1.5 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Recent scored forecast</TableCell>
                <TableCell>As of</TableCell>
                <TableCell>Forecast</TableCell>
                <TableCell>Actual</TableCell>
                <TableCell align="right">Error</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {report.examples.map((e) => (
                <TableRow key={`${e.subject}-${e.as_of}`}>
                  <TableCell>{e.subject}</TableCell>
                  <TableCell>{dateText(e.as_of)}</TableCell>
                  <TableCell>{e.predicted}</TableCell>
                  <TableCell>{e.actual}</TableCell>
                  <TableCell align="right">
                    {formatNumber(e.abs_error, 1)}
                    {unitText(report.unit)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      <TableContainer sx={{ mt: 1.5 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Model version</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Scored</TableCell>
              <TableCell align="right">Mean absolute error</TableCell>
              {canManage ? <TableCell /> : null}
            </TableRow>
          </TableHead>
          <TableBody>
            {report.versions.map((v) => (
              <TableRow key={v.version}>
                <TableCell>
                  {v.version}
                  {v.activation_note ? (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      {v.activation_note}
                    </Typography>
                  ) : null}
                </TableCell>
                <TableCell>{v.status === 'candidate' ? 'Candidate (runs in shadow)' : v.status === 'active' ? 'Active' : v.status}</TableCell>
                <TableCell align="right">{v.accuracy.evaluated}</TableCell>
                <TableCell align="right">
                  {v.accuracy.reportable ? `${formatNumber(v.accuracy.mean_absolute_error ?? 0, 1)}${unitText(report.unit)}` : 'Too few to report'}
                </TableCell>
                {canManage ? (
                  <TableCell align="right">
                    {v.status !== 'active' ? (
                      <Button size="small" onClick={() => onActivate(report, v.version)}>
                        Activate
                      </Button>
                    ) : null}
                  </TableCell>
                ) : null}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}

type PendingAction =
  | { kind: 'toggle'; type: PredictionTypeKey; label: string; enable: boolean }
  | { kind: 'activate'; type: PredictionTypeKey; label: string; version: string };

export function AccuracyTab() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: predictiveQueryKeys.accuracy, queryFn: fetchPredictionAccuracy });
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [note, setNote] = useState('');

  const mutation = useMutation({
    mutationFn: async (action: PendingAction) => {
      if (action.kind === 'toggle') {
        await updatePredictionSetting(action.type, { enabled: action.enable, reason: note.trim() || undefined });
      } else {
        await activatePredictionModel(action.type, action.version, note.trim() || undefined);
      }
    },
    onSuccess: (_, action) => {
      toast.showSuccess(
        action.kind === 'toggle'
          ? `${action.label} ${action.enable ? 'enabled' : 'disabled'}. Stored predictions are kept.`
          : `${action.version} is now the active model for ${action.label}.`,
      );
      setPending(null);
      setNote('');
      void queryClient.invalidateQueries({ queryKey: predictiveQueryKeys.all });
    },
    onError: (error) => toast.showError(getErrorMessage(error)),
  });

  if (query.isLoading) return <LoadingState message="Loading accuracy…" />;
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  const data = query.data;
  if (!data) return null;
  const needsNote = pending?.kind === 'toggle' ? !pending.enable : false;

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        Forecasts are scored once the outcome is known: the last forecast of each day, against the actual completion date or final
        hours. Error figures are shown only once at least {data.minimum_evaluated} forecasts have been scored. A model version can only
        be activated when it is not measurably worse than the active one.
      </Typography>
      {data.types.map((report) => (
        <TypeCard
          key={report.prediction_type}
          report={report}
          canManage={data.can_manage}
          onToggle={(r) => setPending({ kind: 'toggle', type: r.prediction_type, label: r.label, enable: !r.enabled })}
          onActivate={(r, version) => setPending({ kind: 'activate', type: r.prediction_type, label: r.label, version })}
        />
      ))}
      <Dialog open={Boolean(pending)} onClose={() => setPending(null)} fullWidth maxWidth="sm">
        <DialogTitle>
          {pending?.kind === 'toggle'
            ? `${pending.enable ? 'Enable' : 'Disable'} ${pending.label}`
            : `Activate ${pending?.kind === 'activate' ? pending.version : ''}`}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2 }}>
            {pending?.kind === 'toggle'
              ? pending.enable
                ? 'New prediction runs will include this type again.'
                : 'New prediction runs will skip this type and its forecasts will no longer be shown. Stored predictions are kept.'
              : 'If there are not enough scored forecasts to compare the two versions, a justification of at least 10 characters is required. A version with a higher error than the active one is refused.'}
          </Typography>
          <TextField
            fullWidth
            multiline
            minRows={2}
            label={pending?.kind === 'toggle' ? 'Reason' : 'Justification'}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            slotProps={{ htmlInput: { maxLength: 500 } }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPending(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={mutation.isPending || (needsNote && !note.trim())}
            onClick={() => pending && mutation.mutate(pending)}
          >
            Confirm
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
