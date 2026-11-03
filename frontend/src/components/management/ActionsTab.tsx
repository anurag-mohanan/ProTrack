import { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Stack,
  Switch,
  TextField,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../api/client';
import { fetchUsers } from '../../api/lookups';
import { commentOn, createAction, fetchActions, managementQueryKeys, updateAction } from '../../api/management';
import { useToast } from '../../context/ToastContext';
import type { ActionStatus, CockpitFilterValues, ManagementAction, ManagementCan } from '../../types/Management';
import { formatDate } from '../../utils/format';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { statusLabel } from './managementFormat';
import { DataTable, ExportButton, SectionHeader, StatusChip } from './ManagementParts';

const STATUSES: ActionStatus[] = ['open', 'in_progress', 'blocked', 'completed', 'cancelled'];

function UpdateActionDialog({ action, onClose }: { action: ManagementAction; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<ActionStatus>(action.status);
  const [reason, setReason] = useState('');
  const [evidence, setEvidence] = useState(action.completion_evidence ?? '');
  const [comment, setComment] = useState('');
  const save = useMutation({
    mutationFn: async () => {
      if (status !== action.status) {
        await updateAction(action.id, {
          status,
          status_reason: reason || null,
          completion_evidence: status === 'completed' ? evidence : undefined,
        });
      }
      if (comment.trim()) await commentOn('actions', action.id, comment.trim());
    },
    onSuccess: () => {
      toast.showSuccess('Action updated.');
      void queryClient.invalidateQueries({ queryKey: managementQueryKeys.all });
      onClose();
    },
    onError: (e) => toast.showError(getErrorMessage(e)),
  });
  const changed = status !== action.status;
  const needsReason = changed && (status === 'blocked' || status === 'cancelled');
  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{action.title}</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          <TextField select label="Status" value={status} onChange={(e) => setStatus(e.target.value as ActionStatus)}>
            {STATUSES.map((s) => (
              <MenuItem key={s} value={s}>
                {statusLabel(s)}
              </MenuItem>
            ))}
          </TextField>
          <TextField label={needsReason ? 'Reason (required)' : 'Reason'} value={reason} onChange={(e) => setReason(e.target.value)} />
          {status === 'completed' ? (
            <TextField
              label="Completion evidence (required)"
              value={evidence}
              onChange={(e) => setEvidence(e.target.value)}
              multiline
              minRows={2}
            />
          ) : null}
          <TextField label="Comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} multiline minRows={2} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={() => save.mutate()}
          disabled={
            save.isPending ||
            (!changed && !comment.trim()) ||
            (needsReason && !reason) ||
            (changed && status === 'completed' && evidence.length < 3)
          }
        >
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function CreateActionDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const users = useQuery({ queryKey: ['lookups', 'users'], queryFn: () => fetchUsers(), enabled: open });
  const [form, setForm] = useState({ title: '', owner_id: '', due_date: '', priority: 'medium' });
  const create = useMutation({
    mutationFn: () => createAction({ ...form, due_date: form.due_date || null }),
    onSuccess: () => {
      toast.showSuccess('Action created and the owner notified.');
      void queryClient.invalidateQueries({ queryKey: managementQueryKeys.all });
      setForm({ title: '', owner_id: '', due_date: '', priority: 'medium' });
      onClose();
    },
    onError: (e) => toast.showError(getErrorMessage(e)),
  });
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>New management action</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          <TextField label="Action" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
          <TextField select label="Owner" value={form.owner_id} onChange={(e) => setForm({ ...form, owner_id: e.target.value })} required>
            {(users.data ?? []).map((u) => (
              <MenuItem key={u.id} value={u.id}>
                {`${u.first_name ?? ''} ${u.last_name ?? ''}`.trim() || u.email}
              </MenuItem>
            ))}
          </TextField>
          <Stack direction="row" spacing={1.5}>
            <TextField
              type="date"
              label="Due date"
              slotProps={{ inputLabel: { shrink: true } }}
              value={form.due_date}
              onChange={(e) => setForm({ ...form, due_date: e.target.value })}
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
        <Button variant="contained" onClick={() => create.mutate()} disabled={create.isPending || form.title.length < 3 || !form.owner_id}>
          Create
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function ActionsTab({ filters, can }: { filters: CockpitFilterValues; can: ManagementCan }) {
  const [openOnly, setOpenOnly] = useState(true);
  const [mine, setMine] = useState(false);
  const [editing, setEditing] = useState<ManagementAction | null>(null);
  const [creating, setCreating] = useState(false);
  const params = { open_only: openOnly, mine };
  const query = useQuery({ queryKey: managementQueryKeys.actions(params), queryFn: () => fetchActions(params) });
  if (query.isLoading) return <LoadingState message="Loading actions…" />;
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  const data = query.data;
  if (!data) return null;
  return (
    <Box>
      <SectionHeader
        title="Management actions"
        subtitle="Follow-ups from reviews and objectives. Project work stays in Projects; completing an action needs evidence."
        action={
          <Stack direction="row" spacing={1}>
            {can.export ? <ExportButton report="actions" filters={filters} /> : null}
            {can.manage_strategy ? (
              <Button size="small" variant="contained" onClick={() => setCreating(true)}>
                New action
              </Button>
            ) : null}
          </Stack>
        }
      />
      <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap', alignItems: 'center', mb: 2 }}>
        <Chip label={`Open: ${data.summary.open}`} />
        <Chip color={data.summary.overdue ? 'error' : 'default'} label={`Overdue: ${data.summary.overdue}`} />
        <Chip color={data.summary.blocked ? 'warning' : 'default'} label={`Blocked: ${data.summary.blocked}`} />
        <Chip label={`Due in 14 days: ${data.summary.due_next_14_days}`} />
        <FormControlLabel control={<Switch checked={openOnly} onChange={(e) => setOpenOnly(e.target.checked)} />} label="Open only" />
        <FormControlLabel control={<Switch checked={mine} onChange={(e) => setMine(e.target.checked)} />} label="Mine" />
      </Stack>
      <DataTable
        rows={data.actions}
        rowKey={(a) => a.id}
        onRowClick={(a) => (a.can_edit ? setEditing(a) : undefined)}
        empty="No actions match."
        columns={[
          { label: 'Action', render: (a) => a.title },
          { label: 'Owner', render: (a) => a.owner ?? '—' },
          { label: 'Priority', render: (a) => statusLabel(a.priority) },
          { label: 'Due', render: (a) => (a.due_date ? formatDate(a.due_date) : '—') },
          {
            label: 'Status',
            render: (a) => (
              <Stack direction="row" spacing={0.5}>
                <StatusChip status={a.status} />
                {a.overdue ? <StatusChip status="overdue" /> : null}
              </Stack>
            ),
          },
          { label: 'From', render: (a) => a.review?.title ?? a.objective?.title ?? (a.project?.code ? `Project ${a.project.code}` : '—') },
        ]}
      />
      {editing ? <UpdateActionDialog action={editing} onClose={() => setEditing(null)} /> : null}
      <CreateActionDialog open={creating} onClose={() => setCreating(false)} />
    </Box>
  );
}
