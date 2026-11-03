import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  LinearProgress,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../api/client';
import { fetchUsers } from '../../api/lookups';
import {
  approveObjectiveTarget,
  changeObjectiveTarget,
  commentOnObjective,
  createObjective,
  fetchKpiOptions,
  fetchObjective,
  fetchObjectives,
  managementQueryKeys,
  recordObjectiveMeasurement,
  updateObjective,
  type ObjectiveInput,
} from '../../api/management';
import { useToast } from '../../context/ToastContext';
import type { CockpitFilterValues, ManagementCan, Objective } from '../../types/Management';
import { formatDate, formatDateTime } from '../../utils/format';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { InitiativesSection } from './InitiativesSection';
import { statusLabel, valueText } from './managementFormat';
import { DataTable, ExportButton, KindChip, SectionHeader, StatusChip } from './ManagementParts';

const STATUSES = ['not_started', 'on_track', 'at_risk', 'delayed', 'completed', 'cancelled'];
const CATEGORIES = ['financial', 'delivery', 'efficiency', 'customer', 'workforce', 'quality', 'growth', 'other'];
const UNITS = ['currency', 'percentage', 'count', 'hours', 'days', 'ratio'];
const NEEDS_REASON = new Set(['at_risk', 'delayed', 'cancelled']);

function userName(u: { first_name: string; last_name: string; email: string }) {
  return `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim() || u.email;
}

function Progress({ o }: { o: Objective }) {
  if (o.restricted) return <Typography variant="caption">Restricted</Typography>;
  if (o.progress_percent === null) return <Typography variant="caption">—</Typography>;
  return (
    <Box sx={{ minWidth: 120 }}>
      <LinearProgress variant="determinate" value={Math.min(o.progress_percent, 100)} sx={{ height: 6, borderRadius: 3 }} />
      <Typography variant="caption">
        {o.progress_percent}% (expected {o.pace.expected_percent}%)
      </Typography>
    </Box>
  );
}

function CreateObjectiveDialog({ open, onClose, fy }: { open: boolean; onClose: () => void; fy: number }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const kpis = useQuery({ queryKey: managementQueryKeys.kpis, queryFn: fetchKpiOptions, enabled: open });
  const users = useQuery({ queryKey: ['lookups', 'users'], queryFn: () => fetchUsers(), enabled: open });
  const blank: ObjectiveInput = {
    title: '',
    fy_start_year: fy,
    period_type: 'annual',
    category: 'financial',
    unit: 'currency',
    direction: 'increase',
    measurement: 'automatic',
    metric_key: '',
    target_value: '',
    baseline_value: '',
    owner_id: '',
  };
  const [form, setForm] = useState<ObjectiveInput>(blank);
  const set = (patch: Partial<ObjectiveInput>) => setForm((f) => ({ ...f, ...patch }));
  const create = useMutation({
    mutationFn: () =>
      createObjective({
        ...form,
        metric_key: form.measurement === 'automatic' ? form.metric_key || null : null,
        baseline_value: form.baseline_value || null,
        owner_id: form.owner_id || null,
        period_index: form.period_type === 'annual' ? null : form.period_index,
      }),
    onSuccess: (o) => {
      toast.showSuccess(o.target_state === 'approved' ? 'Objective created with an approved target.' : 'Objective created; the target awaits approval.');
      void queryClient.invalidateQueries({ queryKey: managementQueryKeys.all });
      setForm(blank);
      onClose();
    },
    onError: (e) => toast.showError(getErrorMessage(e)),
  });
  const chooseKpi = (key: string) => {
    const kpi = kpis.data?.find((k) => k.key === key);
    set({ metric_key: key, unit: kpi?.unit ?? form.unit, direction: kpi?.direction ?? form.direction });
  };
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>New strategic objective</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          <TextField label="Title" value={form.title} onChange={(e) => set({ title: e.target.value })} required />
          <Stack direction="row" spacing={1.5}>
            <TextField select label="Category" value={form.category} onChange={(e) => set({ category: e.target.value })} fullWidth>
              {CATEGORIES.map((c) => (
                <MenuItem key={c} value={c}>
                  {statusLabel(c)}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="Period"
              value={form.period_type}
              onChange={(e) => set({ period_type: e.target.value as ObjectiveInput['period_type'], period_index: 1 })}
              fullWidth
            >
              <MenuItem value="annual">Financial year</MenuItem>
              <MenuItem value="quarterly">Quarter</MenuItem>
              <MenuItem value="monthly">Month</MenuItem>
            </TextField>
            {form.period_type !== 'annual' ? (
              <TextField
                type="number"
                label={form.period_type === 'quarterly' ? 'Quarter (1-4)' : 'Month of FY (1-12)'}
                value={form.period_index ?? 1}
                onChange={(e) => set({ period_index: Number(e.target.value) })}
                fullWidth
              />
            ) : null}
          </Stack>
          <TextField
            select
            label="Measurement"
            value={form.measurement}
            onChange={(e) => set({ measurement: e.target.value as ObjectiveInput['measurement'] })}
            helperText={
              form.measurement === 'automatic'
                ? 'The actual is calculated from ProTrack records and can never be typed in.'
                : 'Values are entered with evidence; every entry is kept.'
            }
          >
            <MenuItem value="automatic">Automatic KPI</MenuItem>
            <MenuItem value="manual">Manual with evidence</MenuItem>
          </TextField>
          {form.measurement === 'automatic' ? (
            <TextField select label="KPI" value={form.metric_key ?? ''} onChange={(e) => chooseKpi(e.target.value)} required>
              {(kpis.data ?? [])
                .filter((k) => !k.required_params.length)
                .map((k) => (
                  <MenuItem key={k.key} value={k.key}>
                    {k.label} ({k.unit})
                  </MenuItem>
                ))}
            </TextField>
          ) : (
            <Stack direction="row" spacing={1.5}>
              <TextField select label="Unit" value={form.unit} onChange={(e) => set({ unit: e.target.value })} fullWidth>
                {UNITS.map((u) => (
                  <MenuItem key={u} value={u}>
                    {statusLabel(u)}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                label="Direction"
                value={form.direction}
                onChange={(e) => set({ direction: e.target.value as ObjectiveInput['direction'] })}
                fullWidth
              >
                <MenuItem value="increase">Higher is better</MenuItem>
                <MenuItem value="decrease">Lower is better</MenuItem>
              </TextField>
            </Stack>
          )}
          <Stack direction="row" spacing={1.5}>
            <TextField label="Target" type="number" value={form.target_value} onChange={(e) => set({ target_value: e.target.value })} required fullWidth />
            <TextField
              label="Baseline"
              type="number"
              value={form.baseline_value ?? ''}
              onChange={(e) => set({ baseline_value: e.target.value })}
              helperText={form.direction === 'decrease' ? 'Required when lower is better' : 'Optional'}
              fullWidth
            />
          </Stack>
          <TextField select label="Owner" value={form.owner_id ?? ''} onChange={(e) => set({ owner_id: e.target.value })}>
            <MenuItem value="">No owner</MenuItem>
            {(users.data ?? []).map((u) => (
              <MenuItem key={u.id} value={u.id}>
                {userName(u)}
              </MenuItem>
            ))}
          </TextField>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={() => create.mutate()} disabled={create.isPending || !form.title || !form.target_value}>
          Create
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function ObjectiveDetail({ id, can, onClose }: { id: string; can: ManagementCan; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: managementQueryKeys.objective(id), queryFn: () => fetchObjective(id) });
  const [status, setStatus] = useState('');
  const [reason, setReason] = useState('');
  const [target, setTarget] = useState('');
  const [targetReason, setTargetReason] = useState('');
  const [measure, setMeasure] = useState({ value: '', period_start: '', period_end: '', evidence: '' });
  const [comment, setComment] = useState('');
  const done = (message: string) => {
    toast.showSuccess(message);
    void queryClient.invalidateQueries({ queryKey: managementQueryKeys.all });
  };
  const onError = (e: unknown) => toast.showError(getErrorMessage(e));
  const statusMutation = useMutation({
    mutationFn: () => updateObjective(id, { status, status_reason: reason || null }),
    onSuccess: () => done('Status updated.'),
    onError,
  });
  const targetMutation = useMutation({
    mutationFn: () => changeObjectiveTarget(id, { target_value: target, reason: targetReason }),
    onSuccess: () => done('Target changed and recorded in the history.'),
    onError,
  });
  const approveMutation = useMutation({ mutationFn: () => approveObjectiveTarget(id), onSuccess: () => done('Target approved.'), onError });
  const measureMutation = useMutation({
    mutationFn: () => recordObjectiveMeasurement(id, measure),
    onSuccess: () => done('Value recorded with its evidence.'),
    onError,
  });
  const commentMutation = useMutation({
    mutationFn: () => commentOnObjective(id, comment),
    onSuccess: () => {
      setComment('');
      done('Comment added.');
    },
    onError,
  });
  const o = query.data;
  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{o?.title ?? 'Objective'}</DialogTitle>
      <DialogContent>
        {query.isLoading ? <LoadingState /> : null}
        {query.error ? <ErrorState error={query.error} /> : null}
        {o ? (
          <Stack spacing={2}>
            <Typography variant="body2" color="text.secondary">
              {o.period.label} · {statusLabel(o.category)} · Owner: {o.owner ?? 'none'} ·{' '}
              {o.measurement === 'automatic' ? `Automatic KPI: ${o.metric_label}` : 'Manual measurement with evidence'}
            </Typography>
            {o.restricted ? (
              <Alert severity="info">{o.restricted_reason}</Alert>
            ) : (
              <Stack direction="row" spacing={3} useFlexGap sx={{ flexWrap: 'wrap' }}>
                <Box>
                  <KindChip kind="target" /> {valueText(o.target?.value, o.unit)} ({o.target_state}
                  {o.target_approved_by ? ` by ${o.target_approved_by}` : ''})
                </Box>
                {o.baseline ? (
                  <Box>
                    <KindChip kind="baseline" /> {valueText(o.baseline.value, o.unit)}
                  </Box>
                ) : null}
                <Box>
                  <KindChip kind={o.current?.kind ?? 'actual'} /> {valueText(o.current?.value, o.unit)}
                  {o.current?.note ? ` — ${o.current.note}` : ''}
                </Box>
                <Box>
                  Status: <StatusChip status={o.status} /> Suggested from figures: {statusLabel(o.pace.suggested_status)}
                </Box>
              </Stack>
            )}
            <Typography variant="caption" color="text.secondary">
              {o.pace.note} The owner sets the status; the suggestion never overwrites it.
            </Typography>

            {o.can_edit ? (
              <Stack direction="row" spacing={1.5} sx={{ alignItems: 'flex-start' }}>
                <TextField select size="small" label="Status" value={status || o.status} onChange={(e) => setStatus(e.target.value)} sx={{ minWidth: 160 }}>
                  {STATUSES.map((s) => (
                    <MenuItem key={s} value={s}>
                      {statusLabel(s)}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField
                  size="small"
                  label={NEEDS_REASON.has(status) ? 'Reason (required)' : 'Reason'}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  fullWidth
                />
                <Button variant="outlined" onClick={() => statusMutation.mutate()} disabled={!status || statusMutation.isPending}>
                  Update
                </Button>
              </Stack>
            ) : null}

            {can.approve_strategy && !o.restricted ? (
              <Stack direction="row" spacing={1.5} sx={{ alignItems: 'flex-start' }}>
                <TextField size="small" type="number" label="New target" value={target} onChange={(e) => setTarget(e.target.value)} />
                <TextField size="small" label="Reason for change" value={targetReason} onChange={(e) => setTargetReason(e.target.value)} fullWidth />
                <Button variant="outlined" onClick={() => targetMutation.mutate()} disabled={!target || targetReason.length < 5}>
                  Change target
                </Button>
                {o.target_state === 'proposed' ? (
                  <Button variant="contained" onClick={() => approveMutation.mutate()}>
                    Approve target
                  </Button>
                ) : null}
              </Stack>
            ) : null}

            {o.can_record_measurement ? (
              <Stack direction="row" spacing={1.5} sx={{ alignItems: 'flex-start' }}>
                <TextField size="small" type="number" label="Value" value={measure.value} onChange={(e) => setMeasure({ ...measure, value: e.target.value })} />
                <TextField size="small" type="date" label="From" slotProps={{ inputLabel: { shrink: true } }} value={measure.period_start} onChange={(e) => setMeasure({ ...measure, period_start: e.target.value })} />
                <TextField size="small" type="date" label="To" slotProps={{ inputLabel: { shrink: true } }} value={measure.period_end} onChange={(e) => setMeasure({ ...measure, period_end: e.target.value })} />
                <TextField size="small" label="Evidence (required)" value={measure.evidence} onChange={(e) => setMeasure({ ...measure, evidence: e.target.value })} fullWidth />
                <Button variant="outlined" onClick={() => measureMutation.mutate()} disabled={!measure.value || !measure.evidence || !measure.period_start || !measure.period_end}>
                  Record
                </Button>
              </Stack>
            ) : null}

            {o.measurements?.length ? (
              <DataTable
                rows={o.measurements}
                rowKey={(m) => m.id}
                columns={[
                  { label: 'Period', render: (m) => `${formatDate(m.period_start)} – ${formatDate(m.period_end)}` },
                  { label: 'Value', align: 'right', render: (m) => valueText(m.value, o.unit) },
                  { label: 'Evidence', render: (m) => m.evidence ?? '—' },
                  { label: 'Recorded', render: (m) => formatDateTime(m.recorded_at) },
                ]}
              />
            ) : null}

            {o.can_edit ? (
              <Stack direction="row" spacing={1.5}>
                <TextField size="small" label="Comment" value={comment} onChange={(e) => setComment(e.target.value)} fullWidth />
                <Button variant="outlined" onClick={() => commentMutation.mutate()} disabled={comment.length < 2}>
                  Add
                </Button>
              </Stack>
            ) : null}

            <SectionHeader title="History" />
            <DataTable
              rows={o.events ?? []}
              rowKey={(e) => e.id}
              columns={[
                { label: 'When', render: (e) => formatDateTime(e.created_at) },
                { label: 'Who', render: (e) => e.actor ?? '—' },
                { label: 'Event', render: (e) => e.summary },
                { label: 'Reason / text', render: (e) => e.reason ?? e.body ?? '' },
              ]}
            />
          </Stack>
        ) : null}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

export function ObjectivesTab({ filters, can, fy }: { filters: CockpitFilterValues; can: ManagementCan; fy: number }) {
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const query = useQuery({ queryKey: managementQueryKeys.objectives(fy), queryFn: () => fetchObjectives(fy) });
  if (query.isLoading) return <LoadingState message="Loading objectives…" />;
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  return (
    <Box>
      <SectionHeader
        title="Strategic objectives"
        subtitle="Automatic objectives read their actual from ProTrack records; manual objectives keep every entry with its evidence."
        action={
          <Stack direction="row" spacing={1}>
            {can.export ? <ExportButton report="objectives" filters={filters} /> : null}
            {can.manage_strategy ? (
              <Button size="small" variant="contained" onClick={() => setCreating(true)}>
                New objective
              </Button>
            ) : null}
          </Stack>
        }
      />
      <DataTable
        rows={query.data ?? []}
        rowKey={(o) => o.id}
        onRowClick={(o) => setOpenId(o.id)}
        empty="No objectives for this financial year yet."
        columns={[
          { label: 'Objective', render: (o) => o.title },
          { label: 'Owner', render: (o) => o.owner ?? '—' },
          { label: 'Period', render: (o) => o.period.label },
          { label: 'Target', align: 'right', render: (o) => (o.restricted ? 'Restricted' : `${valueText(o.target?.value, o.unit)}${o.target_state === 'proposed' ? ' (proposed)' : ''}`) },
          { label: 'Actual', align: 'right', render: (o) => (o.restricted ? 'Restricted' : valueText(o.current?.value, o.unit)) },
          { label: 'Progress', render: (o) => <Progress o={o} /> },
          { label: 'Status', render: (o) => <StatusChip status={o.status} /> },
          { label: 'Suggested', render: (o) => statusLabel(o.pace.suggested_status) },
        ]}
      />
      <InitiativesSection can={can} objectives={query.data ?? []} />
      <CreateObjectiveDialog open={creating} onClose={() => setCreating(false)} fy={fy} />
      {openId ? <ObjectiveDetail id={openId} can={can} onClose={() => setOpenId(null)} /> : null}
    </Box>
  );
}
