import { useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../api/client';
import { fetchUsers } from '../../api/lookups';
import { commentOn, createInitiative, fetchInitiatives, managementQueryKeys, updateInitiative } from '../../api/management';
import { useToast } from '../../context/ToastContext';
import type { Initiative, ManagementCan, Objective } from '../../types/Management';
import { formatDate } from '../../utils/format';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { statusLabel } from './managementFormat';
import { DataTable, SectionHeader, StatusChip } from './ManagementParts';

const STATUSES = ['planned', 'in_progress', 'on_hold', 'at_risk', 'completed', 'cancelled'];
const NEEDS_REASON = new Set(['on_hold', 'at_risk', 'cancelled']);

function UpdateInitiativeDialog({ row, onClose }: { row: Initiative; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState(row.status);
  const [reason, setReason] = useState('');
  const [progress, setProgress] = useState(row.progress_percent);
  const [comment, setComment] = useState('');
  const save = useMutation({
    mutationFn: async () => {
      await updateInitiative(row.id, { status, status_reason: reason || null, progress_percent: progress });
      if (comment.trim()) await commentOn('initiatives', row.id, comment.trim());
    },
    onSuccess: () => {
      toast.showSuccess('Initiative updated.');
      void queryClient.invalidateQueries({ queryKey: managementQueryKeys.all });
      onClose();
    },
    onError: (e) => toast.showError(getErrorMessage(e)),
  });
  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{row.name}</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          <TextField select label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => (
              <MenuItem key={s} value={s}>
                {statusLabel(s)}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label={NEEDS_REASON.has(status) ? 'Reason (required)' : 'Reason'}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <TextField
            type="number"
            label="Reported progress %"
            value={progress}
            onChange={(e) => setProgress(Math.max(0, Math.min(100, Number(e.target.value))))}
            helperText="The owner's reported progress; project figures stay on the linked projects."
          />
          <TextField label="Comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} multiline minRows={2} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={() => save.mutate()} disabled={save.isPending || (NEEDS_REASON.has(status) && status !== row.status && !reason)}>
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function CreateInitiativeDialog({ open, onClose, objectives }: { open: boolean; onClose: () => void; objectives: Objective[] }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const users = useQuery({ queryKey: ['lookups', 'users'], queryFn: () => fetchUsers(), enabled: open });
  const blank = { name: '', objective_id: '', owner_id: '', target_date: '', priority: 'medium' };
  const [form, setForm] = useState(blank);
  const create = useMutation({
    mutationFn: () =>
      createInitiative({
        ...form,
        objective_id: form.objective_id || null,
        owner_id: form.owner_id || null,
        target_date: form.target_date || null,
      }),
    onSuccess: () => {
      toast.showSuccess('Initiative created.');
      void queryClient.invalidateQueries({ queryKey: managementQueryKeys.all });
      setForm(blank);
      onClose();
    },
    onError: (e) => toast.showError(getErrorMessage(e)),
  });
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>New initiative</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          <TextField label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <TextField select label="Objective" value={form.objective_id} onChange={(e) => setForm({ ...form, objective_id: e.target.value })}>
            <MenuItem value="">None</MenuItem>
            {objectives.map((o) => (
              <MenuItem key={o.id} value={o.id}>
                {o.title}
              </MenuItem>
            ))}
          </TextField>
          <TextField select label="Owner" value={form.owner_id} onChange={(e) => setForm({ ...form, owner_id: e.target.value })}>
            <MenuItem value="">No owner</MenuItem>
            {(users.data ?? []).map((u) => (
              <MenuItem key={u.id} value={u.id}>
                {`${u.first_name ?? ''} ${u.last_name ?? ''}`.trim() || u.email}
              </MenuItem>
            ))}
          </TextField>
          <Stack direction="row" spacing={1.5}>
            <TextField
              type="date"
              label="Target date"
              slotProps={{ inputLabel: { shrink: true } }}
              value={form.target_date}
              onChange={(e) => setForm({ ...form, target_date: e.target.value })}
              fullWidth
            />
            <TextField select label="Priority" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} fullWidth>
              {['low', 'medium', 'high', 'critical'].map((p) => (
                <MenuItem key={p} value={p}>
                  {statusLabel(p)}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={() => create.mutate()} disabled={create.isPending || form.name.length < 3}>
          Create
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function InitiativesSection({ can, objectives }: { can: ManagementCan; objectives: Objective[] }) {
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Initiative | null>(null);
  const query = useQuery({ queryKey: managementQueryKeys.initiatives, queryFn: fetchInitiatives });
  return (
    <Box sx={{ mt: 3 }}>
      <SectionHeader
        title="Initiatives"
        subtitle="Lightweight plans under an objective. They link to existing projects and never copy project data."
        action={
          can.manage_strategy ? (
            <Button size="small" variant="contained" onClick={() => setCreating(true)}>
              New initiative
            </Button>
          ) : null
        }
      />
      {query.isLoading ? <LoadingState message="Loading initiatives…" /> : null}
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      <DataTable
        rows={query.data ?? []}
        rowKey={(r) => r.id}
        onRowClick={(r) => (r.can_edit ? setEditing(r) : undefined)}
        empty="No initiatives yet."
        columns={[
          { label: 'Initiative', render: (r) => r.name },
          { label: 'Objective', render: (r) => r.objective ?? '—' },
          { label: 'Owner', render: (r) => r.owner ?? '—' },
          { label: 'Target', render: (r) => (r.target_date ? formatDate(r.target_date) : '—') },
          { label: 'Reported progress', align: 'right', render: (r) => `${r.progress_percent}%` },
          { label: 'Milestones', align: 'right', render: (r) => `${r.milestones_done}/${r.milestones.length}` },
          {
            label: 'Projects',
            align: 'right',
            render: (r) => `${r.projects.length}${r.projects_hidden ? ` (+${r.projects_hidden} outside your scope)` : ''}`,
          },
          { label: 'Status', render: (r) => <StatusChip status={r.overdue ? 'overdue' : r.status} /> },
        ]}
      />
      <CreateInitiativeDialog open={creating} onClose={() => setCreating(false)} objectives={objectives} />
      {editing ? <UpdateInitiativeDialog row={editing} onClose={() => setEditing(null)} /> : null}
    </Box>
  );
}
