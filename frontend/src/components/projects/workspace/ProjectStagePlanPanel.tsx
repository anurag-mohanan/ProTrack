import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../../api/client';
import { commandCenterQueryKeys } from '../../../api/commandCenter';
import {
  configureStageEstimates,
  fetchProjectStagePlan,
  projectPlanningQueryKeys,
  reviseProjectBaseline,
  reviseStageEstimate,
  setMilestoneScheduleOverride,
} from '../../../api/projectPlanning';
import { useToast } from '../../../context/ToastContext';
import { projectQueryKeys } from '../../../services/projectService';
import { MILESTONE_STATUS_LABELS } from '../../../types/common';
import type { ProjectStagePlan, StagePlanMilestone } from '../../../types/projectPlanning';
import { PLANNED_STAGE_OPTIONS } from '../../../types/ProjectTemplate';
import { formatDate, formatDateTime, formatNumber } from '../../../utils/format';
import { ErrorState } from '../../common/ErrorState';
import { LoadingState } from '../../common/LoadingState';

interface ProjectStagePlanPanelProps {
  projectId: string;
  canEdit: boolean;
  canRevise: boolean;
  canApproveBaseline: boolean;
}

type Hours = number | string | null | undefined;

const hours = (value: Hours) =>
  value === null || value === undefined || value === '' ? '—' : `${formatNumber(value, 1)} h`;

function variance(value: Hours, percent: Hours) {
  if (value === null || value === undefined || value === '') return '—';
  const numeric = Number(value);
  const sign = numeric > 0 ? '+' : '';
  const pct =
    percent === null || percent === undefined || percent === ''
      ? ''
      : ` (${sign}${formatNumber(percent, 1)}%)`;
  return `${sign}${formatNumber(numeric, 1)} h${pct}`;
}

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Box sx={{ minWidth: 140 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {label}
      </Typography>
      <Typography variant="body1" sx={{ fontWeight: 600 }}>
        {value}
      </Typography>
      {hint ? (
        <Typography variant="caption" color="text.secondary">
          {hint}
        </Typography>
      ) : null}
    </Box>
  );
}

export function ProjectStagePlanPanel({
  projectId,
  canEdit,
  canRevise,
  canApproveBaseline,
}: ProjectStagePlanPanelProps) {
  const queryClient = useQueryClient();
  const { showSuccess } = useToast();
  const [configureHours, setConfigureHours] = useState<Record<string, string>>({});
  const [reviseOpen, setReviseOpen] = useState(false);
  const [reviseStage, setReviseStage] = useState('preliminary');
  const [reviseHours, setReviseHours] = useState('');
  const [reviseReason, setReviseReason] = useState('');
  const [baselineOpen, setBaselineOpen] = useState(false);
  const [baselineStart, setBaselineStart] = useState('');
  const [baselineReason, setBaselineReason] = useState('');
  const [overrideTarget, setOverrideTarget] = useState<StagePlanMilestone | null>(null);
  const [overrideStart, setOverrideStart] = useState('');
  const [overrideFinish, setOverrideFinish] = useState('');
  const [overrideReason, setOverrideReason] = useState('');

  const query = useQuery({
    queryKey: projectPlanningQueryKeys.stagePlan(projectId),
    queryFn: () => fetchProjectStagePlan(projectId),
  });

  const onPlanSaved = (plan: ProjectStagePlan, message: string) => {
    queryClient.setQueryData(projectPlanningQueryKeys.stagePlan(projectId), plan);
    void queryClient.invalidateQueries({ queryKey: commandCenterQueryKeys.detail(projectId) });
    void queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
    showSuccess(message);
  };

  const configureMutation = useMutation({
    mutationFn: () =>
      configureStageEstimates(projectId, {
        preliminary: Number(configureHours.preliminary || 0),
        intermediate: Number(configureHours.intermediate || 0),
        final: Number(configureHours.final || 0),
      }),
    onSuccess: (plan) => {
      setConfigureHours({});
      onPlanSaved(plan, 'Stage hours saved and baseline calculated.');
    },
  });

  const reviseMutation = useMutation({
    mutationFn: () =>
      reviseStageEstimate(projectId, {
        stage: reviseStage,
        new_hours: Number(reviseHours),
        reason: reviseReason.trim(),
      }),
    onSuccess: (plan) => {
      setReviseOpen(false);
      setReviseHours('');
      setReviseReason('');
      onPlanSaved(plan, 'Estimate revised. The original estimate is kept for reporting.');
    },
  });

  const baselineMutation = useMutation({
    mutationFn: () =>
      reviseProjectBaseline(projectId, {
        reason: baselineReason.trim(),
        new_start_date: baselineStart || null,
      }),
    onSuccess: (plan) => {
      setBaselineOpen(false);
      setBaselineReason('');
      setBaselineStart('');
      onPlanSaved(plan, `Baseline revision ${plan.baseline_version} saved.`);
    },
  });

  const overrideMutation = useMutation({
    mutationFn: (clear: boolean) => {
      if (!overrideTarget) throw new Error('No milestone selected');
      return setMilestoneScheduleOverride(projectId, overrideTarget.id, {
        override_start_date: clear ? null : overrideStart || null,
        override_finish_date: clear ? null : overrideFinish || null,
        reason: clear ? null : overrideReason.trim() || null,
      });
    },
    onSuccess: (plan, clear) => {
      setOverrideTarget(null);
      onPlanSaved(plan, clear ? 'Schedule override removed.' : 'Schedule override saved.');
    },
  });

  if (query.isLoading) return <LoadingState message="Loading stage plan…" />;
  if (query.error) {
    return (
      <ErrorState
        error={query.error}
        title="Unable to load the stage plan"
        onRetry={() => void query.refetch()}
      />
    );
  }
  const plan = query.data;
  if (!plan) return null;

  const openOverride = (milestone: StagePlanMilestone) => {
    setOverrideTarget(milestone);
    setOverrideStart(milestone.override_start_date ?? '');
    setOverrideFinish(milestone.override_finish_date ?? '');
    setOverrideReason(milestone.override_reason ?? '');
    overrideMutation.reset();
  };

  const openRevise = () => {
    const firstStage = plan.stages.find((stage) => stage.configured)?.key ?? 'preliminary';
    setReviseStage(firstStage);
    const current = plan.stages.find((stage) => stage.key === firstStage)?.current_hours;
    setReviseHours(current === null || current === undefined ? '' : String(Number(current)));
    setReviseReason('');
    reviseMutation.reset();
    setReviseOpen(true);
  };

  const configureTotal = PLANNED_STAGE_OPTIONS.reduce(
    (sum, option) => sum + Number(configureHours[option.value] || 0),
    0,
  );
  const forecastLabel =
    plan.forecast_status === 'provisional'
      ? 'Provisional forecast'
      : plan.forecast_status === 'completed'
        ? 'Completed'
        : 'Forecast';

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Card sx={{ p: 2 }}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5, flexWrap: 'wrap', gap: 1 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Dates
          </Typography>
          <Stack direction="row" spacing={1}>
            {canRevise && plan.stage_estimates_configured ? (
              <Button size="small" variant="outlined" onClick={openRevise}>
                Revise estimate
              </Button>
            ) : null}
            {canApproveBaseline && plan.baseline_version > 0 ? (
              <Button
                size="small"
                variant="outlined"
                onClick={() => {
                  setBaselineStart(plan.baseline_start_date ?? '');
                  setBaselineReason('');
                  baselineMutation.reset();
                  setBaselineOpen(true);
                }}
              >
                Revise baseline
              </Button>
            ) : null}
          </Stack>
        </Stack>
        <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 3 }}>
          <Metric label="Project start" value={formatDate(plan.start_date)} />
          <Metric
            label={`Original baseline${plan.baseline_version > 1 ? ` (rev ${plan.baseline_version})` : ''}`}
            value={
              plan.baseline_version > 0
                ? `${formatDate(plan.baseline_start_date)} → ${formatDate(plan.baseline_completion_date)}`
                : 'Not set'
            }
            hint={plan.baseline_version > 0 ? undefined : 'Set a start date and stage hours to create it.'}
          />
          <Metric label={forecastLabel} value={formatDate(plan.forecast_completion_date)} />
          <Metric label="Actual start" value={formatDate(plan.actual_start_date)} />
          <Metric label="Actual completion" value={formatDate(plan.actual_completion_date)} />
          <Metric label="Customer due date" value={formatDate(plan.due_date)} />
        </Stack>
        {plan.forecast_note ? (
          <Alert severity={plan.forecast_status === 'invalid' ? 'warning' : 'info'} sx={{ mt: 1.5 }}>
            {plan.forecast_note}
            {plan.forecast_calculated_at ? ` Calculated ${formatDateTime(plan.forecast_calculated_at)}.` : ''}
          </Alert>
        ) : null}
      </Card>

      <Card sx={{ p: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
          Hours
        </Typography>
        <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 3 }}>
          <Metric label="Original estimate" value={hours(plan.original_total_hours)} />
          <Metric label="Current estimate" value={hours(plan.current_total_hours)} />
          <Metric label="Actual (timesheets)" value={hours(plan.actual_total_hours)} />
          <Metric label="Forecast remaining" value={hours(plan.forecast_remaining_hours)} />
          <Metric label="Estimate at completion" value={hours(plan.eac_hours)} />
          <Metric
            label="Variance vs original"
            value={variance(plan.variance_hours, plan.variance_percent)}
          />
        </Stack>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
          Forecast dates assume {formatNumber(plan.effort_hours_per_day, 1)} effort hours per working
          day ({plan.effort_source}).
        </Typography>
      </Card>

      {!plan.stage_estimates_configured ? (
        <Card sx={{ p: 2 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Stage hours not set
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Enter planned hours for each stage. They become the original estimate (kept for
            reporting) and are spread over the open milestones of each stage.
          </Typography>
          {canEdit ? (
            <Grid container spacing={2} sx={{ alignItems: 'center' }}>
              {PLANNED_STAGE_OPTIONS.map((option) => (
                <Grid key={option.value} size={{ xs: 12, sm: 3 }}>
                  <TextField
                    size="small"
                    label={`${option.label} hours`}
                    type="number"
                    value={configureHours[option.value] ?? ''}
                    slotProps={{ htmlInput: { min: 0, step: 0.5 } }}
                    onChange={(event) =>
                      setConfigureHours((current) => ({ ...current, [option.value]: event.target.value }))
                    }
                    fullWidth
                  />
                </Grid>
              ))}
              <Grid size={{ xs: 12, sm: 3 }}>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                  <Typography variant="body2">Total {formatNumber(configureTotal, 1)} h</Typography>
                  <Button
                    variant="contained"
                    size="small"
                    disabled={
                      configureMutation.isPending ||
                      PLANNED_STAGE_OPTIONS.every((option) => !configureHours[option.value]) ||
                      PLANNED_STAGE_OPTIONS.some((option) => Number(configureHours[option.value] || 0) < 0)
                    }
                    onClick={() => configureMutation.mutate()}
                  >
                    Save stage hours
                  </Button>
                </Stack>
              </Grid>
            </Grid>
          ) : (
            <Alert severity="info">You do not have permission to set stage hours on this project.</Alert>
          )}
          {configureMutation.error ? (
            <Alert severity="error" sx={{ mt: 1.5 }}>
              {getErrorMessage(configureMutation.error)}
            </Alert>
          ) : null}
        </Card>
      ) : null}

      {plan.stages.map((stage) => (
        <Card key={stage.key} sx={{ p: 2 }}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1, mb: 1 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              {stage.label}
            </Typography>
            <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 2 }}>
              <Typography variant="body2">Original {hours(stage.original_hours)}</Typography>
              <Typography variant="body2">Current {hours(stage.current_hours ?? stage.milestone_planned_hours)}</Typography>
              <Typography variant="body2">Actual {hours(stage.actual_hours)}</Typography>
              <Typography variant="body2">Remaining {hours(stage.forecast_remaining_hours)}</Typography>
              <Typography variant="body2">EAC {hours(stage.eac_hours)}</Typography>
              <Typography variant="body2">
                Variance {variance(stage.variance_hours, stage.variance_percent)}
              </Typography>
            </Stack>
          </Stack>
          {stage.allocation_mismatch ? (
            <Alert severity="warning" sx={{ mb: 1 }}>
              Milestone hours ({hours(stage.milestone_planned_hours)}) do not add up to the stage
              estimate ({hours(stage.current_hours)}). Revise the estimate or the milestone hours.
            </Alert>
          ) : null}
          {stage.milestones.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No milestones in this stage.
            </Typography>
          ) : (
            <Box sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Milestone</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell align="right">Original</TableCell>
                    <TableCell align="right">Current</TableCell>
                    <TableCell align="right">Actual</TableCell>
                    <TableCell align="right">Remaining</TableCell>
                    <TableCell>Baseline finish</TableCell>
                    <TableCell>Forecast</TableCell>
                    <TableCell>Actual finish</TableCell>
                    {canEdit ? <TableCell /> : null}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {stage.milestones.map((milestone) => (
                    <TableRow key={milestone.id}>
                      <TableCell>
                        {milestone.name}
                        {!milestone.is_required ? (
                          <Chip size="small" label="Optional" sx={{ ml: 1 }} />
                        ) : null}
                      </TableCell>
                      <TableCell>
                        {MILESTONE_STATUS_LABELS[milestone.status] ?? milestone.status}
                        {milestone.overdue ? (
                          <Chip size="small" color="error" label="Overdue" sx={{ ml: 1 }} />
                        ) : null}
                      </TableCell>
                      <TableCell align="right">{hours(milestone.original_planned_hours)}</TableCell>
                      <TableCell align="right">{hours(milestone.planned_hours)}</TableCell>
                      <TableCell align="right">{hours(milestone.actual_hours)}</TableCell>
                      <TableCell align="right">{hours(milestone.forecast_remaining_hours)}</TableCell>
                      <TableCell>{formatDate(milestone.baseline_finish_date)}</TableCell>
                      <TableCell>
                        {milestone.override_finish_date || milestone.override_start_date ? (
                          <Tooltip title={`Override: ${milestone.override_reason ?? ''}`}>
                            <span>
                              {formatDate(milestone.forecast_finish_date)}{' '}
                              <Chip size="small" label="Override" />
                            </span>
                          </Tooltip>
                        ) : (
                          formatDate(milestone.forecast_finish_date)
                        )}
                        {milestone.forecast_late ? (
                          <Chip size="small" color="warning" label="Late" sx={{ ml: 1 }} />
                        ) : null}
                      </TableCell>
                      <TableCell>{formatDate(milestone.actual_finish_date)}</TableCell>
                      {canEdit ? (
                        <TableCell>
                          {milestone.status !== 'completed' ? (
                            <Button size="small" onClick={() => openOverride(milestone)}>
                              Override dates
                            </Button>
                          ) : null}
                        </TableCell>
                      ) : null}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          )}
        </Card>
      ))}

      <Card sx={{ p: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
          Estimate revisions
        </Typography>
        {plan.estimate_revisions.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No estimate revisions yet.
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>When</TableCell>
                <TableCell>Stage</TableCell>
                <TableCell align="right">Previous</TableCell>
                <TableCell align="right">New</TableCell>
                <TableCell>Reason</TableCell>
                <TableCell>By</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {plan.estimate_revisions.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{formatDateTime(row.revised_at)}</TableCell>
                  <TableCell>{row.stage_label}</TableCell>
                  <TableCell align="right">{hours(row.previous_hours)}</TableCell>
                  <TableCell align="right">{hours(row.new_hours)}</TableCell>
                  <TableCell>{row.reason}</TableCell>
                  <TableCell>{row.revised_by_name ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <Card sx={{ p: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
          Baseline history
        </Typography>
        {plan.baseline_revisions.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No baseline yet.
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Revision</TableCell>
                <TableCell>When</TableCell>
                <TableCell>Previous</TableCell>
                <TableCell>New</TableCell>
                <TableCell>Reason</TableCell>
                <TableCell>By</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {plan.baseline_revisions.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>#{row.revision_number}</TableCell>
                  <TableCell>{formatDateTime(row.revised_at)}</TableCell>
                  <TableCell>
                    {row.previous_start_date || row.previous_completion_date
                      ? `${formatDate(row.previous_start_date)} → ${formatDate(row.previous_completion_date)}`
                      : '—'}
                  </TableCell>
                  <TableCell>
                    {formatDate(row.new_start_date)} → {formatDate(row.new_completion_date)}
                  </TableCell>
                  <TableCell>{row.reason}</TableCell>
                  <TableCell>{row.revised_by_name ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <Dialog open={reviseOpen} onClose={() => setReviseOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Revise stage estimate</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '8px !important' }}>
          <Typography variant="body2" color="text.secondary">
            The original estimate is never changed. The new value is spread over the open milestones
            of the stage and recorded with your name and reason.
          </Typography>
          <FormControl fullWidth>
            <InputLabel>Stage</InputLabel>
            <Select
              label="Stage"
              value={reviseStage}
              onChange={(event) => {
                const next = String(event.target.value);
                setReviseStage(next);
                const current = plan.stages.find((stage) => stage.key === next)?.current_hours;
                setReviseHours(current === null || current === undefined ? '' : String(Number(current)));
              }}
            >
              {plan.stages
                .filter((stage) => stage.configured)
                .map((stage) => (
                  <MenuItem key={stage.key} value={stage.key}>
                    {stage.label} (current {hours(stage.current_hours)})
                  </MenuItem>
                ))}
            </Select>
          </FormControl>
          <TextField
            label="New estimate (hours)"
            type="number"
            value={reviseHours}
            slotProps={{ htmlInput: { min: 0, step: 0.5 } }}
            onChange={(event) => setReviseHours(event.target.value)}
          />
          <TextField
            label="Reason"
            value={reviseReason}
            onChange={(event) => setReviseReason(event.target.value)}
            multiline
            minRows={2}
            required
            helperText="At least 5 characters."
          />
          {reviseMutation.error ? (
            <Alert severity="error">{getErrorMessage(reviseMutation.error)}</Alert>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReviseOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={
              reviseMutation.isPending ||
              reviseHours === '' ||
              Number(reviseHours) < 0 ||
              reviseReason.trim().length < 5
            }
            onClick={() => reviseMutation.mutate()}
          >
            Save revision
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={baselineOpen} onClose={() => setBaselineOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Revise baseline</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '8px !important' }}>
          <Typography variant="body2" color="text.secondary">
            Recalculates the baseline from the current estimates. The previous baseline stays in the
            history with your name and reason.
          </Typography>
          <TextField
            label="Baseline start date"
            type="date"
            value={baselineStart}
            onChange={(event) => setBaselineStart(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            helperText="Leave unchanged to keep the current baseline start."
          />
          <TextField
            label="Reason"
            value={baselineReason}
            onChange={(event) => setBaselineReason(event.target.value)}
            multiline
            minRows={2}
            required
            helperText="At least 5 characters."
          />
          {baselineMutation.error ? (
            <Alert severity="error">{getErrorMessage(baselineMutation.error)}</Alert>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBaselineOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={baselineMutation.isPending || baselineReason.trim().length < 5}
            onClick={() => baselineMutation.mutate()}
          >
            Save baseline revision
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(overrideTarget)} onClose={() => setOverrideTarget(null)} fullWidth maxWidth="sm">
        <DialogTitle>Override forecast dates — {overrideTarget?.name}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '8px !important' }}>
          <Typography variant="body2" color="text.secondary">
            Overrides replace the calculated forecast for this milestone only. Later milestones are
            re-forecast from it. The baseline does not change.
          </Typography>
          <Stack direction="row" spacing={2}>
            <TextField
              label="Start"
              type="date"
              value={overrideStart}
              onChange={(event) => setOverrideStart(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              fullWidth
            />
            <TextField
              label="Finish"
              type="date"
              value={overrideFinish}
              onChange={(event) => setOverrideFinish(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              fullWidth
            />
          </Stack>
          <TextField
            label="Reason"
            value={overrideReason}
            onChange={(event) => setOverrideReason(event.target.value)}
            multiline
            minRows={2}
            required
          />
          {overrideMutation.error ? (
            <Alert severity="error">{getErrorMessage(overrideMutation.error)}</Alert>
          ) : null}
        </DialogContent>
        <DialogActions>
          {overrideTarget?.override_start_date || overrideTarget?.override_finish_date ? (
            <Button
              color="warning"
              disabled={overrideMutation.isPending}
              onClick={() => overrideMutation.mutate(true)}
            >
              Remove override
            </Button>
          ) : null}
          <Box sx={{ flex: 1 }} />
          <Button onClick={() => setOverrideTarget(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={
              overrideMutation.isPending ||
              (!overrideStart && !overrideFinish) ||
              !overrideReason.trim() ||
              Boolean(overrideStart && overrideFinish && overrideFinish < overrideStart)
            }
            onClick={() => overrideMutation.mutate(false)}
          >
            Save override
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
