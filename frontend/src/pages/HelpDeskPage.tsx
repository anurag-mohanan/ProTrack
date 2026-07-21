import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Drawer,
  FormControlLabel,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import ConfirmationNumberRoundedIcon from '@mui/icons-material/ConfirmationNumberRounded';
import HourglassEmptyRoundedIcon from '@mui/icons-material/HourglassEmptyRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import AssignmentIndRoundedIcon from '@mui/icons-material/AssignmentIndRounded';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import { ticketsApi } from '../api/resources';
import { fetchUsers } from '../api/lookups';
import { PageContainer } from '../components/common/PageContainer';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { KpiMetricCard, ModernPageHeader } from '../components/ui/design-system';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { isTicketAgentRole } from '../utils/permissions';
import type {
  Ticket,
  TicketCategory,
  TicketDetail,
  TicketPriority,
  TicketStatus,
} from '../types';

const CATEGORY_OPTIONS: { value: TicketCategory; label: string }[] = [
  { value: 'it', label: 'IT Support' },
  { value: 'facility', label: 'Facility / Infrastructure' },
  { value: 'admin', label: 'Administration' },
  { value: 'hr', label: 'Human Resources' },
  { value: 'other', label: 'Other' },
];

const PRIORITY_OPTIONS: { value: TicketPriority; label: string }[] = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'urgent', label: 'Urgent' },
];

const STATUS_OPTIONS: { value: TicketStatus; label: string }[] = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'on_hold', label: 'On Hold' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
  { value: 'cancelled', label: 'Cancelled' },
];

type ChipColor = 'default' | 'primary' | 'info' | 'warning' | 'error' | 'success';

const PRIORITY_COLOR: Record<TicketPriority, ChipColor> = {
  low: 'default',
  medium: 'info',
  high: 'warning',
  urgent: 'error',
};

const STATUS_COLOR: Record<TicketStatus, ChipColor> = {
  open: 'info',
  in_progress: 'primary',
  on_hold: 'warning',
  resolved: 'success',
  closed: 'default',
  cancelled: 'default',
};

function priorityLabel(priority: TicketPriority): string {
  return PRIORITY_OPTIONS.find((option) => option.value === priority)?.label ?? priority;
}

function formatWhen(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const emptyForm = {
  title: '',
  category: 'it' as TicketCategory,
  priority: 'medium' as TicketPriority,
  description: '',
  location: '',
  due_date: '',
};

export function HelpDeskPage() {
  const { user } = useAuth();
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const isAgent = isTicketAgentRole(user?.role_name);

  const [statusFilter, setStatusFilter] = useState<string>('open');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [scope, setScope] = useState<string>(isAgent ? 'all' : 'mine');
  const [search, setSearch] = useState('');

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const [selectedId, setSelectedId] = useState<string | null>(null);

  const statsQuery = useQuery({
    queryKey: ['tickets', 'stats'],
    queryFn: () => ticketsApi.stats(),
  });

  const listParams = useMemo(
    () => ({
      status: statusFilter === 'all' ? undefined : statusFilter,
      category: categoryFilter === 'all' ? undefined : categoryFilter,
      scope: scope === 'all' ? undefined : scope,
      q: search.trim() || undefined,
    }),
    [statusFilter, categoryFilter, scope, search],
  );

  const listQuery = useQuery({
    queryKey: ['tickets', 'list', listParams],
    queryFn: () => ticketsApi.list(listParams),
  });

  const detailQuery = useQuery({
    queryKey: ['tickets', 'detail', selectedId],
    queryFn: () => ticketsApi.get(selectedId as string),
    enabled: Boolean(selectedId),
  });

  const usersQuery = useQuery({
    queryKey: ['lookups', 'users'],
    queryFn: fetchUsers,
    enabled: isAgent && Boolean(selectedId),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['tickets'] });
  };

  const createMutation = useMutation({
    mutationFn: () =>
      ticketsApi.create({
        title: form.title.trim(),
        category: form.category,
        priority: form.priority,
        description: form.description.trim() || null,
        location: form.location.trim() || null,
        due_date: form.due_date || null,
      }),
    onSuccess: (ticket) => {
      showSuccess(`Ticket ${ticket.ticket_number} created.`);
      setCreateOpen(false);
      setForm(emptyForm);
      invalidate();
      setSelectedId(ticket.id);
    },
    onError: () => showError('Could not create the ticket. Please try again.'),
  });

  const handleError = () => showError('Update failed. Please try again.');

  const updateMutation = useMutation({
    mutationFn: (payload: Parameters<typeof ticketsApi.update>[1]) =>
      ticketsApi.update(selectedId as string, payload),
    onSuccess: () => {
      showSuccess('Ticket updated.');
      invalidate();
    },
    onError: handleError,
  });

  const assignMutation = useMutation({
    mutationFn: (assigneeId: string | null) =>
      ticketsApi.assign(selectedId as string, assigneeId),
    onSuccess: () => {
      showSuccess('Assignment updated.');
      invalidate();
    },
    onError: handleError,
  });

  const statusMutation = useMutation({
    mutationFn: (vars: { status: TicketStatus; resolution?: string | null }) =>
      ticketsApi.setStatus(selectedId as string, vars.status, vars.resolution),
    onSuccess: () => {
      showSuccess('Status updated.');
      invalidate();
    },
    onError: handleError,
  });

  const [commentBody, setCommentBody] = useState('');
  const [commentInternal, setCommentInternal] = useState(false);
  const commentMutation = useMutation({
    mutationFn: () =>
      ticketsApi.addComment(selectedId as string, commentBody.trim(), commentInternal),
    onSuccess: () => {
      setCommentBody('');
      setCommentInternal(false);
      queryClient.invalidateQueries({ queryKey: ['tickets', 'detail', selectedId] });
      queryClient.invalidateQueries({ queryKey: ['tickets', 'list'] });
    },
    onError: () => showError('Could not post your comment.'),
  });

  const stats = statsQuery.data;
  const tickets = listQuery.data ?? [];

  return (
    <PageContainer>
      <ModernPageHeader
        title="Help Desk"
        subtitle="Raise and track IT, facility, administration, and HR requests."
        actions={
          <Button
            variant="contained"
            startIcon={<AddRoundedIcon />}
            onClick={() => setCreateOpen(true)}
          >
            New Ticket
          </Button>
        }
        summary={
          <Box
            sx={{
              display: 'grid',
              gap: 1.5,
              gridTemplateColumns: {
                xs: 'repeat(2, 1fr)',
                sm: 'repeat(3, 1fr)',
                md: 'repeat(5, 1fr)',
              },
            }}
          >
            <KpiMetricCard
              title="Open"
              value={String(stats?.open ?? 0)}
              icon={ConfirmationNumberRoundedIcon}
              accent="info"
              compact
              onClick={() => setStatusFilter('open')}
              selected={statusFilter === 'open'}
            />
            <KpiMetricCard
              title="In Progress"
              value={String(stats?.in_progress ?? 0)}
              icon={HourglassEmptyRoundedIcon}
              accent="primary"
              compact
              onClick={() => setStatusFilter('in_progress')}
              selected={statusFilter === 'in_progress'}
            />
            <KpiMetricCard
              title="Resolved"
              value={String(stats?.resolved ?? 0)}
              icon={CheckCircleRoundedIcon}
              accent="success"
              compact
              onClick={() => setStatusFilter('resolved')}
              selected={statusFilter === 'resolved'}
            />
            <KpiMetricCard
              title="Assigned to me"
              value={String(stats?.assigned_to_me ?? 0)}
              icon={AssignmentIndRoundedIcon}
              accent="warning"
              compact
              onClick={() => {
                setScope('assigned');
                setStatusFilter('all');
              }}
              selected={scope === 'assigned'}
            />
            <KpiMetricCard
              title="Raised by me"
              value={String(stats?.raised_by_me ?? 0)}
              icon={ConfirmationNumberRoundedIcon}
              compact
              onClick={() => {
                setScope('mine');
                setStatusFilter('all');
              }}
              selected={scope === 'mine'}
            />
          </Box>
        }
      />

      <Paper
        variant="outlined"
        sx={{ p: 1.5, mb: 2, display: 'flex', flexWrap: 'wrap', gap: 1.5, alignItems: 'center' }}
      >
        <TextField
          select
          size="small"
          label="Status"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          sx={{ minWidth: 150 }}
        >
          <MenuItem value="all">All statuses</MenuItem>
          {STATUS_OPTIONS.map((option) => (
            <MenuItem key={option.value} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="Category"
          value={categoryFilter}
          onChange={(event) => setCategoryFilter(event.target.value)}
          sx={{ minWidth: 170 }}
        >
          <MenuItem value="all">All categories</MenuItem>
          {CATEGORY_OPTIONS.map((option) => (
            <MenuItem key={option.value} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="Scope"
          value={scope}
          onChange={(event) => setScope(event.target.value)}
          sx={{ minWidth: 150 }}
        >
          {isAgent && <MenuItem value="all">All I manage</MenuItem>}
          <MenuItem value="mine">Raised by me</MenuItem>
          <MenuItem value="assigned">Assigned to me</MenuItem>
        </TextField>
        <TextField
          size="small"
          label="Search"
          placeholder="Title or ticket #"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 200, flexGrow: 1 }}
        />
      </Paper>

      {listQuery.isLoading ? (
        <LoadingState />
      ) : listQuery.isError ? (
        <ErrorState error={listQuery.error} onRetry={() => listQuery.refetch()} />
      ) : tickets.length === 0 ? (
        <EmptyState
          title="No tickets found"
          description="Adjust the filters, or raise a new ticket to get started."
        />
      ) : (
        <Stack spacing={1.25}>
          {tickets.map((ticket) => (
            <TicketRow key={ticket.id} ticket={ticket} onOpen={() => setSelectedId(ticket.id)} />
          ))}
        </Stack>
      )}

      <CreateTicketDialog
        open={createOpen}
        form={form}
        setForm={setForm}
        onClose={() => setCreateOpen(false)}
        onSubmit={() => createMutation.mutate()}
        submitting={createMutation.isPending}
      />

      <Drawer
        anchor="right"
        open={Boolean(selectedId)}
        onClose={() => setSelectedId(null)}
        slotProps={{ paper: { sx: { width: { xs: '100%', sm: 520 }, p: 0 } } }}
      >
        {detailQuery.isLoading ? (
          <Box sx={{ p: 3 }}>
            <LoadingState />
          </Box>
        ) : detailQuery.data ? (
          <TicketDetailPanel
            ticket={detailQuery.data}
            currentUserId={user?.id ?? ''}
            assignableUsers={usersQuery.data ?? []}
            onClose={() => setSelectedId(null)}
            onUpdate={(payload) => updateMutation.mutate(payload)}
            onAssign={(assigneeId) => assignMutation.mutate(assigneeId)}
            onStatus={(status, resolution) => statusMutation.mutate({ status, resolution })}
            commentBody={commentBody}
            setCommentBody={setCommentBody}
            commentInternal={commentInternal}
            setCommentInternal={setCommentInternal}
            onComment={() => commentMutation.mutate()}
            commenting={commentMutation.isPending}
            busy={updateMutation.isPending || assignMutation.isPending || statusMutation.isPending}
          />
        ) : null}
      </Drawer>
    </PageContainer>
  );
}

function TicketRow({ ticket, onOpen }: { ticket: Ticket; onOpen: () => void }) {
  return (
    <Paper
      variant="outlined"
      onClick={onOpen}
      sx={{
        p: 1.5,
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        cursor: 'pointer',
        transition: 'border-color 0.15s, box-shadow 0.15s',
        '&:hover': { borderColor: 'primary.main', boxShadow: 1 },
      }}
    >
      <Box sx={{ minWidth: 0, flexGrow: 1 }}>
        <Stack direction="row" spacing={1} sx={{ mb: 0.25, alignItems: 'center' }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
            {ticket.ticket_number}
          </Typography>
          <Chip label={ticket.category_label} size="small" variant="outlined" />
        </Stack>
        <Typography variant="body2" noWrap title={ticket.title} sx={{ fontWeight: 600 }}>
          {ticket.title}
        </Typography>
        <Typography variant="caption" color="text.secondary" noWrap>
          {ticket.requester_name ?? 'Unknown'}
          {ticket.assignee_name ? ` → ${ticket.assignee_name}` : ' · Unassigned'} ·{' '}
          {formatWhen(ticket.updated_at)}
        </Typography>
      </Box>
      <Stack direction="row" spacing={0.75} sx={{ flexShrink: 0 }}>
        <Chip
          label={priorityLabel(ticket.priority)}
          size="small"
          color={PRIORITY_COLOR[ticket.priority]}
          variant={ticket.priority === 'low' ? 'outlined' : 'filled'}
        />
        <Chip label={ticket.status_label} size="small" color={STATUS_COLOR[ticket.status]} />
      </Stack>
    </Paper>
  );
}

interface CreateDialogProps {
  open: boolean;
  form: typeof emptyForm;
  setForm: (form: typeof emptyForm) => void;
  onClose: () => void;
  onSubmit: () => void;
  submitting: boolean;
}

function CreateTicketDialog({ open, form, setForm, onClose, onSubmit, submitting }: CreateDialogProps) {
  const canSubmit = form.title.trim().length >= 3;
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Raise a Ticket</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2} sx={{ mt: 0.5 }}>
          <TextField
            label="Title"
            required
            value={form.title}
            onChange={(event) => setForm({ ...form, title: event.target.value })}
            placeholder="Short summary of the issue"
            fullWidth
            autoFocus
          />
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField
              select
              label="Category"
              value={form.category}
              onChange={(event) =>
                setForm({ ...form, category: event.target.value as TicketCategory })
              }
              fullWidth
            >
              {CATEGORY_OPTIONS.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="Priority"
              value={form.priority}
              onChange={(event) =>
                setForm({ ...form, priority: event.target.value as TicketPriority })
              }
              fullWidth
            >
              {PRIORITY_OPTIONS.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          <TextField
            label="Description"
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
            placeholder="Describe the issue, steps to reproduce, impact…"
            multiline
            minRows={3}
            fullWidth
          />
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField
              label="Location / Asset"
              value={form.location}
              onChange={(event) => setForm({ ...form, location: event.target.value })}
              placeholder="e.g. 2nd floor, Meeting Room B, Laptop tag…"
              fullWidth
            />
            <TextField
              label="Needed by"
              type="date"
              value={form.due_date}
              onChange={(event) => setForm({ ...form, due_date: event.target.value })}
              slotProps={{ inputLabel: { shrink: true } }}
              fullWidth
            />
          </Stack>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={onSubmit} disabled={!canSubmit || submitting}>
          Submit Ticket
        </Button>
      </DialogActions>
    </Dialog>
  );
}

interface DetailPanelProps {
  ticket: TicketDetail;
  currentUserId: string;
  assignableUsers: { id: string; first_name: string; last_name: string }[];
  onClose: () => void;
  onUpdate: (payload: Parameters<typeof ticketsApi.update>[1]) => void;
  onAssign: (assigneeId: string | null) => void;
  onStatus: (status: TicketStatus, resolution?: string | null) => void;
  commentBody: string;
  setCommentBody: (value: string) => void;
  commentInternal: boolean;
  setCommentInternal: (value: boolean) => void;
  onComment: () => void;
  commenting: boolean;
  busy: boolean;
}

function TicketDetailPanel({
  ticket,
  currentUserId,
  assignableUsers,
  onClose,
  onUpdate,
  onAssign,
  onStatus,
  commentBody,
  setCommentBody,
  commentInternal,
  setCommentInternal,
  onComment,
  commenting,
  busy,
}: DetailPanelProps) {
  const canManage = ticket.can_manage;
  const isRequester = ticket.requester_id === currentUserId;
  const [resolution, setResolution] = useState(ticket.resolution ?? '');

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Box
        sx={{
          p: 2,
          borderBottom: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          alignItems: 'flex-start',
          gap: 1,
        }}
      >
        <Box sx={{ minWidth: 0, flexGrow: 1 }}>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
              {ticket.ticket_number}
            </Typography>
            <Chip label={ticket.status_label} size="small" color={STATUS_COLOR[ticket.status]} />
            <Chip
              label={priorityLabel(ticket.priority)}
              size="small"
              color={PRIORITY_COLOR[ticket.priority]}
              variant={ticket.priority === 'low' ? 'outlined' : 'filled'}
            />
          </Stack>
          <Typography variant="h6" sx={{ mt: 0.5, fontWeight: 700, lineHeight: 1.25 }}>
            {ticket.title}
          </Typography>
        </Box>
        <IconButton onClick={onClose} size="small">
          <CloseRoundedIcon />
        </IconButton>
      </Box>

      <Box sx={{ p: 2, overflowY: 'auto', flexGrow: 1 }}>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 1.25,
            mb: 2,
          }}
        >
          <MetaField label="Category" value={ticket.category_label} />
          <MetaField label="Requester" value={ticket.requester_name ?? '—'} />
          <MetaField label="Assignee" value={ticket.assignee_name ?? 'Unassigned'} />
          <MetaField label="Location / Asset" value={ticket.location ?? '—'} />
          <MetaField label="Created" value={formatWhen(ticket.created_at)} />
          <MetaField label="Needed by" value={ticket.due_date ?? '—'} />
        </Box>

        {ticket.description ? (
          <Paper variant="outlined" sx={{ p: 1.5, mb: 2, bgcolor: 'action.hover' }}>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
              {ticket.description}
            </Typography>
          </Paper>
        ) : null}

        {ticket.resolution ? (
          <Paper
            variant="outlined"
            sx={{ p: 1.5, mb: 2, borderColor: 'success.light', bgcolor: 'success.50' }}
          >
            <Typography variant="caption" color="success.main" sx={{ fontWeight: 700 }}>
              Resolution
            </Typography>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
              {ticket.resolution}
            </Typography>
          </Paper>
        ) : null}

        {canManage ? (
          <Paper variant="outlined" sx={{ p: 1.5, mb: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 1.25 }}>
              Agent actions
            </Typography>
            <Stack spacing={1.5}>
              <Stack direction="row" spacing={1.5}>
                <TextField
                  select
                  size="small"
                  label="Status"
                  value={ticket.status}
                  onChange={(event) => onStatus(event.target.value as TicketStatus)}
                  fullWidth
                  disabled={busy}
                >
                  {STATUS_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField
                  select
                  size="small"
                  label="Priority"
                  value={ticket.priority}
                  onChange={(event) =>
                    onUpdate({ priority: event.target.value as TicketPriority })
                  }
                  fullWidth
                  disabled={busy}
                >
                  {PRIORITY_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </TextField>
              </Stack>
              <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                <TextField
                  select
                  size="small"
                  label="Assignee"
                  value={ticket.assignee_id ?? ''}
                  onChange={(event) => onAssign(event.target.value || null)}
                  fullWidth
                  disabled={busy}
                >
                  <MenuItem value="">Unassigned</MenuItem>
                  {assignableUsers.map((candidate) => (
                    <MenuItem key={candidate.id} value={candidate.id}>
                      {candidate.first_name} {candidate.last_name}
                    </MenuItem>
                  ))}
                </TextField>
                {ticket.assignee_id !== currentUserId ? (
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => onAssign(currentUserId)}
                    disabled={busy}
                    sx={{ whiteSpace: 'nowrap' }}
                  >
                    To me
                  </Button>
                ) : null}
              </Stack>
              <TextField
                size="small"
                label="Resolution note"
                value={resolution}
                onChange={(event) => setResolution(event.target.value)}
                multiline
                minRows={2}
                fullWidth
                disabled={busy}
              />
              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  variant="contained"
                  color="success"
                  onClick={() => onStatus('resolved', resolution || null)}
                  disabled={busy}
                >
                  Mark Resolved
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => onStatus('closed', resolution || null)}
                  disabled={busy}
                >
                  Close
                </Button>
              </Stack>
            </Stack>
          </Paper>
        ) : isRequester ? (
          <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
            {['open', 'in_progress', 'on_hold'].includes(ticket.status) ? (
              <Button
                size="small"
                variant="outlined"
                color="error"
                onClick={() => onStatus('cancelled')}
                disabled={busy}
              >
                Cancel Ticket
              </Button>
            ) : null}
            {ticket.status === 'resolved' ? (
              <Button
                size="small"
                variant="outlined"
                onClick={() => onStatus('open')}
                disabled={busy}
              >
                Reopen
              </Button>
            ) : null}
          </Stack>
        ) : null}

        <Divider sx={{ my: 1.5 }} />
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Activity ({ticket.comments.length})
        </Typography>
        <Stack spacing={1.25}>
          {ticket.comments.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No comments yet.
            </Typography>
          ) : (
            ticket.comments.map((comment) => (
              <Paper
                key={comment.id}
                variant="outlined"
                sx={{
                  p: 1.25,
                  bgcolor: comment.is_internal ? 'warning.50' : 'background.paper',
                  borderColor: comment.is_internal ? 'warning.light' : 'divider',
                }}
              >
                <Stack direction="row" spacing={1} sx={{ mb: 0.5, alignItems: 'center' }}>
                  <Typography variant="caption" sx={{ fontWeight: 700 }}>
                    {comment.author_name ?? 'Unknown'}
                  </Typography>
                  {comment.is_internal ? (
                    <Chip label="Internal" size="small" color="warning" variant="outlined" />
                  ) : null}
                  <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
                    {formatWhen(comment.created_at)}
                  </Typography>
                </Stack>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                  {comment.body}
                </Typography>
              </Paper>
            ))
          )}
        </Stack>
      </Box>

      <Box sx={{ p: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
        <TextField
          size="small"
          placeholder="Add a comment…"
          value={commentBody}
          onChange={(event) => setCommentBody(event.target.value)}
          multiline
          maxRows={4}
          fullWidth
        />
        <Stack direction="row" spacing={1} sx={{ mt: 1, alignItems: 'center' }}>
          {canManage ? (
            <FormControlLabel
              control={
                <Checkbox
                  size="small"
                  checked={commentInternal}
                  onChange={(event) => setCommentInternal(event.target.checked)}
                />
              }
              label={<Typography variant="caption">Internal note</Typography>}
            />
          ) : null}
          <Button
            size="small"
            variant="contained"
            endIcon={<SendRoundedIcon />}
            onClick={onComment}
            disabled={commenting || commentBody.trim().length === 0}
            sx={{ ml: 'auto' }}
          >
            Send
          </Button>
        </Stack>
      </Box>
    </Box>
  );
}

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {label}
      </Typography>
      <Typography variant="body2" noWrap title={value} sx={{ fontWeight: 600 }}>
        {value}
      </Typography>
    </Box>
  );
}

export default HelpDeskPage;
