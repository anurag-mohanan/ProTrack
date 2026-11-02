import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  IconButton,
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
  Tooltip,
  Typography,
} from '@mui/material';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createScenario,
  deleteScenario,
  fetchPredictions,
  fetchProjectPredictions,
  fetchScenarios,
  predictiveQueryKeys,
  previewScenario,
  updateScenario,
} from '../../api/predictive';
import { getErrorMessage } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import type { SavedScenario, ScenarioAssumptions, ScenarioResult } from '../../types/Predictive';
import { formatDateTime } from '../../utils/format';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { SectionTitle } from '../reports/ReportKpi';
import { ProjectPicker } from './ProjectPicker';

interface FormState {
  scope: string;
  extraDelay: string;
  targetShift: string;
  addedHours: string;
  startDate: string;
  designerId: string;
  milestoneDelays: Array<{ milestoneId: string; days: string }>;
}

const EMPTY_FORM: FormState = {
  scope: '0',
  extraDelay: '0',
  targetShift: '0',
  addedHours: '0',
  startDate: '',
  designerId: '',
  milestoneDelays: [],
};

function toAssumptions(form: FormState): ScenarioAssumptions {
  const delays: Record<string, number> = {};
  for (const row of form.milestoneDelays) {
    if (row.milestoneId && Number(row.days) > 0) delays[row.milestoneId] = Math.round(Number(row.days));
  }
  return {
    scope_change_percent: form.scope || '0',
    extra_delay_days: Math.round(Number(form.extraDelay) || 0),
    target_shift_days: Math.round(Number(form.targetShift) || 0),
    added_hours_per_week: form.addedHours || '0',
    start_date: form.startDate || null,
    designer_id: form.designerId || null,
    milestone_delays: delays,
  };
}

function fromAssumptions(a: ScenarioAssumptions): FormState {
  return {
    scope: String(a.scope_change_percent ?? '0'),
    extraDelay: String(a.extra_delay_days ?? 0),
    targetShift: String(a.target_shift_days ?? 0),
    addedHours: String(a.added_hours_per_week ?? '0'),
    startDate: a.start_date ?? '',
    designerId: a.designer_id ?? '',
    milestoneDelays: Object.entries(a.milestone_delays ?? {}).map(([milestoneId, days]) => ({ milestoneId, days: String(days) })),
  };
}

function describe(a: ScenarioAssumptions, milestoneLabels: Map<string, string>, designerLabels: Map<string, string>): string {
  const parts: string[] = [];
  if (Number(a.scope_change_percent)) parts.push(`scope ${Number(a.scope_change_percent) > 0 ? '+' : ''}${a.scope_change_percent}%`);
  if (a.extra_delay_days) parts.push(`${a.extra_delay_days} days customer or approval delay`);
  if (a.target_shift_days) parts.push(`target moved ${a.target_shift_days > 0 ? '+' : ''}${a.target_shift_days} days`);
  if (a.designer_id) parts.push(`designer ${designerLabels.get(a.designer_id) ?? 'changed'}`);
  if (Number(a.added_hours_per_week)) parts.push(`+${a.added_hours_per_week} h/week support`);
  if (a.start_date) parts.push(`start ${a.start_date}`);
  for (const [id, days] of Object.entries(a.milestone_delays ?? {})) {
    parts.push(`${milestoneLabels.get(id) ?? 'milestone'} +${days} days`);
  }
  return parts.join(' · ') || 'No assumptions';
}

function ResultView({ result }: { result: ScenarioResult }) {
  return (
    <Stack spacing={1.5}>
      <Alert severity="warning">{result.label}</Alert>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Measure</TableCell>
              <TableCell>Baseline forecast</TableCell>
              <TableCell>Scenario forecast</TableCell>
              <TableCell>Difference</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {result.comparison.map((row) => (
              <TableRow key={row.measure}>
                <TableCell>{row.measure}</TableCell>
                <TableCell>{row.baseline}</TableCell>
                <TableCell>{row.scenario}</TableCell>
                <TableCell>{row.difference ?? '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {[result.scenario.delivery, result.scenario.final_hours]
        .filter((o) => o && o.status !== 'predicted')
        .map((o) => (
          <Typography key={o!.label + (o!.reason ?? '')} variant="body2" color="text.secondary">
            Cannot be forecast: {o!.reason}
          </Typography>
        ))}
      <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
        {result.warnings.map((w) => (
          <li key={w}>
            <Typography variant="caption">{w}</Typography>
          </li>
        ))}
      </Box>
      <Typography variant="caption" color="text.secondary">
        As of {result.as_of}. Models: {Object.values(result.model_versions).join(', ')}.
      </Typography>
    </Stack>
  );
}

export function ScenariosTab({
  projectId,
  onSelectProject,
  canCapacity,
}: {
  projectId: string | null;
  onSelectProject: (projectId: string | null) => void;
  canCapacity: boolean;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [name, setName] = useState('');
  const [editing, setEditing] = useState<SavedScenario | null>(null);
  const [result, setResult] = useState<{ title: string; data: ScenarioResult } | null>(null);
  const [deleting, setDeleting] = useState<SavedScenario | null>(null);
  const [formProject, setFormProject] = useState(projectId);

  if (formProject !== projectId) {
    setFormProject(projectId);
    setForm(EMPTY_FORM);
    setName('');
    setEditing(null);
    setResult(null);
  }

  const detail = useQuery({
    queryKey: predictiveQueryKeys.project(projectId ?? ''),
    queryFn: () => fetchProjectPredictions(projectId!),
    enabled: Boolean(projectId),
  });
  const saved = useQuery({
    queryKey: predictiveQueryKeys.scenarios(projectId ?? ''),
    queryFn: () => fetchScenarios(projectId!),
    enabled: Boolean(projectId),
  });
  const people = useQuery({
    queryKey: predictiveQueryKeys.list('resource_demand', 4),
    queryFn: () => fetchPredictions({ prediction_type: 'resource_demand', weeks: 4 }),
    enabled: canCapacity,
  });

  const milestoneOptions = useMemo(
    () =>
      (detail.data?.milestones ?? [])
        .filter((m) => m.milestone_id)
        .map((m) => ({ id: m.milestone_id as string, label: m.subject_label })),
    [detail.data],
  );
  const designerOptions = useMemo(
    () =>
      (people.data?.predictions ?? [])
        .filter((r) => r.subject_type === 'person')
        .map((r) => ({ id: r.subject_key.split(':')[1], label: r.subject_label }))
        .sort((a, b) => a.label.localeCompare(b.label)),
    [people.data],
  );
  const milestoneLabels = useMemo(() => new Map(milestoneOptions.map((m) => [m.id, m.label])), [milestoneOptions]);
  const designerLabels = useMemo(() => new Map(designerOptions.map((d) => [d.id, d.label])), [designerOptions]);

  const refresh = () => void queryClient.invalidateQueries({ queryKey: predictiveQueryKeys.scenarios(projectId ?? '') });

  const preview = useMutation({
    mutationFn: () => previewScenario(projectId!, toAssumptions(form)),
    onSuccess: (data) => setResult({ title: 'Preview (not saved)', data }),
    onError: (error) => toast.showError(getErrorMessage(error)),
  });
  const save = useMutation({
    mutationFn: () => {
      const body = { name: name.trim(), assumptions: toAssumptions(form) };
      return editing ? updateScenario(editing.id, body) : createScenario(projectId!, body);
    },
    onSuccess: (row) => {
      toast.showSuccess('Scenario saved. The project itself was not changed.');
      setEditing(row);
      setResult({ title: row.name, data: row.result });
      refresh();
    },
    onError: (error) => toast.showError(getErrorMessage(error)),
  });
  const remove = useMutation({
    mutationFn: (row: SavedScenario) => deleteScenario(row.id),
    onSuccess: (_, row) => {
      toast.showSuccess('Scenario deleted.');
      if (editing?.id === row.id) setEditing(null);
      setDeleting(null);
      refresh();
    },
    onError: (error) => toast.showError(getErrorMessage(error)),
  });

  const set = (patch: Partial<FormState>) => setForm((prev) => ({ ...prev, ...patch }));
  const canEdit = saved.data?.can_edit ?? false;

  return (
    <Box>
      <ProjectPicker value={projectId} onChange={onSelectProject} />
      {!projectId ? (
        <Typography variant="body2" color="text.secondary">
          Choose an open project to compare hypothetical changes against its baseline forecast.
        </Typography>
      ) : null}
      {projectId && (detail.isLoading || saved.isLoading) ? <LoadingState message="Loading scenarios…" /> : null}
      {detail.error ? <ErrorState error={detail.error} onRetry={() => void detail.refetch()} /> : null}
      {projectId && detail.data ? (
        <Stack spacing={2}>
          <Alert severity="info">
            Scenarios are hypothetical. They use the same comparable history and models as the stored forecasts and never change the
            project&apos;s dates, estimates, assignments or capacity.
          </Alert>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <SectionTitle
              title={editing ? `Edit scenario: ${editing.name}` : 'Assumptions'}
              subtitle="Leave a field at 0 or empty to keep the recorded value."
            />
            <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: 'repeat(3, 1fr)' } }}>
              <TextField
                size="small"
                type="number"
                label="Scope change (%)"
                value={form.scope}
                onChange={(e) => set({ scope: e.target.value })}
                helperText="Scales the remaining work; −50 to +200"
                slotProps={{ htmlInput: { min: -50, max: 200 } }}
              />
              <TextField
                size="small"
                type="number"
                label="Customer or approval delay (days)"
                value={form.extraDelay}
                onChange={(e) => set({ extraDelay: e.target.value })}
                helperText="Added to the forecast completion"
                slotProps={{ htmlInput: { min: 0, max: 365 } }}
              />
              <TextField
                size="small"
                type="number"
                label="Move target date (days)"
                value={form.targetShift}
                onChange={(e) => set({ targetShift: e.target.value })}
                helperText="Changes what the forecast is compared against"
                slotProps={{ htmlInput: { min: -365, max: 365 } }}
              />
              {canCapacity ? (
                <TextField
                  size="small"
                  select
                  label="Different designer"
                  value={form.designerId}
                  onChange={(e) => set({ designerId: e.target.value })}
                  helperText="Changes the capacity check only"
                >
                  <MenuItem value="">Keep the assigned designer</MenuItem>
                  {designerOptions.map((d) => (
                    <MenuItem key={d.id} value={d.id}>
                      {d.label}
                    </MenuItem>
                  ))}
                </TextField>
              ) : null}
              <TextField
                size="small"
                type="number"
                label="Additional designer support (h/week)"
                value={form.addedHours}
                onChange={(e) => set({ addedHours: e.target.value })}
                helperText="Extra capacity on the designer's working days"
                slotProps={{ htmlInput: { min: 0, max: 80 } }}
              />
              <TextField
                size="small"
                type="date"
                label="Start date (only if none recorded)"
                value={form.startDate}
                onChange={(e) => set({ startDate: e.target.value })}
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Box>

            {milestoneOptions.length ? (
              <Box sx={{ mt: 2 }}>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    Milestone delays
                  </Typography>
                  <Button
                    size="small"
                    startIcon={<AddRoundedIcon />}
                    onClick={() => set({ milestoneDelays: [...form.milestoneDelays, { milestoneId: '', days: '7' }] })}
                  >
                    Add
                  </Button>
                </Stack>
                <Stack spacing={1}>
                  {form.milestoneDelays.map((row, index) => (
                    <Stack key={index} direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                      <TextField
                        size="small"
                        select
                        label="Milestone"
                        value={row.milestoneId}
                        onChange={(e) =>
                          set({
                            milestoneDelays: form.milestoneDelays.map((r, i) => (i === index ? { ...r, milestoneId: e.target.value } : r)),
                          })
                        }
                        sx={{ minWidth: 280 }}
                      >
                        {milestoneOptions.map((m) => (
                          <MenuItem key={m.id} value={m.id}>
                            {m.label}
                          </MenuItem>
                        ))}
                      </TextField>
                      <TextField
                        size="small"
                        type="number"
                        label="Days"
                        value={row.days}
                        onChange={(e) =>
                          set({ milestoneDelays: form.milestoneDelays.map((r, i) => (i === index ? { ...r, days: e.target.value } : r)) })
                        }
                        sx={{ width: 100 }}
                        slotProps={{ htmlInput: { min: 0, max: 365 } }}
                      />
                      <IconButton
                        size="small"
                        aria-label="Remove milestone delay"
                        onClick={() => set({ milestoneDelays: form.milestoneDelays.filter((_, i) => i !== index) })}
                      >
                        <DeleteOutlineRoundedIcon fontSize="small" />
                      </IconButton>
                    </Stack>
                  ))}
                </Stack>
              </Box>
            ) : null}

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mt: 2, alignItems: { sm: 'center' } }}>
              <Button variant="outlined" onClick={() => preview.mutate()} disabled={preview.isPending}>
                Compare with baseline
              </Button>
              {canEdit ? (
                <>
                  <TextField
                    size="small"
                    label="Scenario name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    slotProps={{ htmlInput: { maxLength: 200 } }}
                    sx={{ minWidth: 240 }}
                  />
                  <Button variant="contained" onClick={() => save.mutate()} disabled={save.isPending || !name.trim()}>
                    {editing ? 'Save changes' : 'Save scenario'}
                  </Button>
                </>
              ) : null}
              {editing ? (
                <Button
                  onClick={() => {
                    setEditing(null);
                    setForm(EMPTY_FORM);
                    setName('');
                  }}
                >
                  New scenario
                </Button>
              ) : null}
            </Stack>
          </Paper>

          {result ? (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <SectionTitle title={result.title} />
              <ResultView result={result.data} />
            </Paper>
          ) : null}

          {saved.data?.scenarios.length ? (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <SectionTitle title="Saved scenarios" subtitle="Each scenario records who created and last changed it." />
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Name</TableCell>
                      <TableCell>Assumptions</TableCell>
                      <TableCell>Created</TableCell>
                      <TableCell>Last changed</TableCell>
                      <TableCell />
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {saved.data.scenarios.map((s) => (
                      <TableRow key={s.id} selected={editing?.id === s.id}>
                        <TableCell>{s.name}</TableCell>
                        <TableCell>
                          <Typography variant="caption">{describe(s.assumptions, milestoneLabels, designerLabels)}</Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption">
                            {s.created_by ?? '—'}
                            <br />
                            {s.created_at ? formatDateTime(s.created_at) : ''}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption">
                            {s.updated_by ?? '—'}
                            <br />
                            {s.updated_by && s.updated_at ? formatDateTime(s.updated_at) : ''}
                          </Typography>
                        </TableCell>
                        <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                          <Button size="small" onClick={() => setResult({ title: `${s.name} (saved ${s.as_of})`, data: s.result })}>
                            View
                          </Button>
                          {canEdit ? (
                            <>
                              <Button
                                size="small"
                                onClick={() => {
                                  setEditing(s);
                                  setName(s.name);
                                  setForm(fromAssumptions(s.assumptions));
                                }}
                              >
                                Edit
                              </Button>
                              <Tooltip title="Delete scenario">
                                <IconButton size="small" aria-label="Delete scenario" onClick={() => setDeleting(s)}>
                                  <DeleteOutlineRoundedIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </>
                          ) : null}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          ) : null}
        </Stack>
      ) : null}
      <ConfirmDialog
        open={Boolean(deleting)}
        title="Delete scenario"
        message="The scenario is removed from this list. The project is not affected."
        recordName={deleting?.name}
        confirmLabel="Delete"
        danger
        loading={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting)}
        onClose={() => setDeleting(null)}
      />
    </Box>
  );
}
