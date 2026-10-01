import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  Divider,
  FormControlLabel,
  IconButton,
  Link,
  MenuItem,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import { ticketsApi } from '../../api/tickets';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';
import { formatDate, formatDateTime } from '../../utils/format';
import type { TicketDetail, TicketPriority, TicketStatus, TicketStatusChange } from '../../types/tickets';
import { ACTION_LABELS, NEEDS_DIALOG, PRIORITY_COLOR, STATUS_COLOR, ticketHref } from './ticketConstants';
import { TicketAssignDialog, TicketStatusDialog, TicketTransferDialog } from './TicketDialogs';
import { useTicketCatalog } from './useTicketMeta';

interface TicketDetailViewProps {
  ticketId: string;
  /** Shown in drawers: renders a close button and an "open full page" link. */
  onClose?: () => void;
}

export function TicketDetailView({ ticketId, onClose }: TicketDetailViewProps) {
  const query = useQuery({
    queryKey: ['tickets', 'detail', ticketId],
    queryFn: () => ticketsApi.get(ticketId),
  });
  if (query.isLoading) return <LoadingState />;
  if (query.isError || !query.data) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  }
  return <TicketDetailBody ticket={query.data} onClose={onClose} />;
}

function TicketDetailBody({ ticket, onClose }: { ticket: TicketDetail; onClose?: () => void }) {
  const { user } = useAuth();
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const catalog = useTicketCatalog();
  const [statusTarget, setStatusTarget] = useState<TicketStatus | null>(null);
  const [assignOpen, setAssignOpen] = useState(false);
  const [transferOpen, setTransferOpen] = useState(false);
  const [tab, setTab] = useState<'conversation' | 'timeline' | 'assignment' | 'notifications'>(
    'conversation',
  );
  const [comment, setComment] = useState('');
  const [internal, setInternal] = useState(false);
  const [reviewNote, setReviewNote] = useState('');

  const refresh = (data?: TicketDetail) => {
    if (data) queryClient.setQueryData(['tickets', 'detail', ticket.id], data);
    queryClient.invalidateQueries({ queryKey: ['tickets'] });
    queryClient.invalidateQueries({ queryKey: ['onboarding'] });
    queryClient.invalidateQueries({ queryKey: ['it'] });
  };
  const fail = (fallback: string) => (error: unknown) => showError(apiErrorMessage(error, fallback));

  const statusMutation = useMutation({
    mutationFn: (payload: TicketStatusChange) => ticketsApi.setStatus(ticket.id, payload),
    onSuccess: (data) => {
      setStatusTarget(null);
      showSuccess(`${data.ticket_number} is now ${data.status_label.toLowerCase()}.`);
      refresh(data);
    },
    onError: fail('Could not change the status.'),
  });
  const takeMutation = useMutation({
    mutationFn: () => ticketsApi.take(ticket.id),
    onSuccess: (data) => {
      showSuccess('You own this ticket now.');
      refresh(data);
    },
    onError: fail('Could not take the ticket.'),
  });
  const assignMutation = useMutation({
    mutationFn: (vars: { assigneeId: string | null; reason: string }) =>
      ticketsApi.assign(ticket.id, vars.assigneeId, vars.reason),
    onSuccess: (data) => {
      setAssignOpen(false);
      showSuccess('Assignment updated.');
      refresh(data);
    },
    onError: fail('Could not change the assignment.'),
  });
  const transferMutation = useMutation({
    mutationFn: (payload: { category: string; subcategory: string | null; assignee_id: string | null; reason: string }) =>
      ticketsApi.transfer(ticket.id, payload),
    onSuccess: (data) => {
      setTransferOpen(false);
      showSuccess(`Transferred to ${data.category_label}.`);
      refresh(data);
    },
    onError: fail('Could not transfer the ticket.'),
  });
  const priorityMutation = useMutation({
    mutationFn: (priority: TicketPriority) => ticketsApi.update(ticket.id, { priority }),
    onSuccess: (data) => {
      showSuccess('Priority updated.');
      refresh(data);
    },
    onError: fail('Could not change the priority.'),
  });
  const commentMutation = useMutation({
    mutationFn: () => ticketsApi.addComment(ticket.id, comment.trim(), internal),
    onSuccess: () => {
      setComment('');
      setInternal(false);
      refresh();
    },
    onError: fail('Could not post the comment.'),
  });
  const reviewMutation = useMutation({
    mutationFn: () => ticketsApi.review(ticket.id, reviewNote.trim()),
    onSuccess: (data) => {
      setReviewNote('');
      showSuccess('Marked as reviewed.');
      refresh(data);
    },
    onError: fail('Could not save the review.'),
  });
  const retryMutation = useMutation({
    mutationFn: () => ticketsApi.retryNotifications(ticket.id),
    onSuccess: (data) => {
      showSuccess(data.sent ? `${data.sent} notification(s) re-sent.` : 'Nothing to re-send.');
      refresh();
    },
    onError: fail('Could not re-send notifications.'),
  });

  const busy =
    statusMutation.isPending ||
    takeMutation.isPending ||
    assignMutation.isPending ||
    transferMutation.isPending ||
    priorityMutation.isPending;
  const canManage = ticket.can_manage;
  const isOpen = !['resolved', 'closed', 'cancelled'].includes(ticket.status);
  const transitions = ticket.allowed_transitions.filter(
    (status) => !(status === 'in_progress' && canManage && ticket.assignee_id !== user?.id && isOpen),
  );

  const runTransition = (status: TicketStatus) => {
    if (NEEDS_DIALOG.has(status)) setStatusTarget(status);
    else statusMutation.mutate({ status });
  };

  const failedNotifications = ticket.notifications.filter((row) => row.status === 'failed').length;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
        <Box sx={{ minWidth: 0, flexGrow: 1 }}>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap', rowGap: 0.5 }}>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
              {ticket.ticket_number}
            </Typography>
            <Chip label={ticket.status_label} size="small" color={STATUS_COLOR[ticket.status]} />
            <Chip
              label={ticket.priority_label}
              size="small"
              color={PRIORITY_COLOR[ticket.priority]}
              variant={ticket.priority === 'low' ? 'outlined' : 'filled'}
            />
            {ticket.is_overdue ? <Chip label="Overdue" size="small" color="error" variant="outlined" /> : null}
            {ticket.needs_owner && isOpen ? (
              <Chip label="Needs owner" size="small" color="warning" variant="outlined" />
            ) : null}
            {ticket.escalation_level > 0 ? (
              <Chip label="Escalated" size="small" color="error" variant="outlined" />
            ) : null}
          </Stack>
          <Typography variant="h6" sx={{ mt: 0.5, fontWeight: 700, lineHeight: 1.25 }}>
            {ticket.title}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {ticket.category_label}
            {ticket.subcategory_label ? ` · ${ticket.subcategory_label}` : ''}
            {ticket.source_label ? ` · from ${ticket.source_label}` : ''}
          </Typography>
        </Box>
        {onClose ? (
          <>
            <IconButton component={RouterLink} to={ticketHref(ticket.id)} size="small" title="Open full page">
              <OpenInNewRoundedIcon fontSize="small" />
            </IconButton>
            <IconButton onClick={onClose} size="small" title="Close">
              <CloseRoundedIcon />
            </IconButton>
          </>
        ) : null}
      </Box>

      {transitions.length > 0 || (canManage && isOpen) ? (
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', rowGap: 1 }}>
          {canManage && isOpen && ticket.assignee_id !== user?.id ? (
            <Button size="small" variant="contained" onClick={() => takeMutation.mutate()} disabled={busy}>
              Take &amp; start
            </Button>
          ) : null}
          {transitions.map((status) => (
            <Button
              key={status}
              size="small"
              variant={status === 'resolved' ? 'contained' : 'outlined'}
              color={status === 'cancelled' ? 'error' : status === 'resolved' ? 'success' : 'primary'}
              onClick={() => runTransition(status)}
              disabled={busy}
            >
              {ACTION_LABELS[status] ?? status}
            </Button>
          ))}
          {canManage && isOpen ? (
            <>
              <Button size="small" variant="text" onClick={() => setAssignOpen(true)} disabled={busy}>
                Assign
              </Button>
              <Button size="small" variant="text" onClick={() => setTransferOpen(true)} disabled={busy}>
                Transfer
              </Button>
            </>
          ) : null}
        </Stack>
      ) : null}

      {ticket.needs_review && canManage ? (
        <Alert severity="warning">
          <Typography variant="body2" sx={{ mb: 1 }}>
            {ticket.review_note ?? 'This legacy ticket needs a person to review it.'}
          </Typography>
          <Stack direction="row" spacing={1}>
            <TextField
              size="small"
              placeholder="What did you check?"
              value={reviewNote}
              onChange={(event) => setReviewNote(event.target.value)}
              fullWidth
            />
            <Button
              size="small"
              variant="outlined"
              onClick={() => reviewMutation.mutate()}
              disabled={!reviewNote.trim() || reviewMutation.isPending}
            >
              Mark reviewed
            </Button>
          </Stack>
        </Alert>
      ) : null}

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 1.5 }}>
        <MetaField label="Requester" value={ticket.requester_name ?? '—'} />
        <MetaField label="Affected employee" value={ticket.affected_user_name ?? '—'} />
        <MetaField
          label="Owner"
          value={ticket.assignee_name ?? (isOpen ? 'Unassigned — in queue' : 'Unassigned')}
        />
        <MetaField label="Queue" value={ticket.category_label} />
        <MetaField label="Created" value={formatDateTime(ticket.created_at)} />
        <MetaField label="Needed by" value={ticket.due_date ? formatDate(ticket.due_date) : '—'} />
        <MetaField label="SLA due" value={ticket.sla_due_at ? formatDateTime(ticket.sla_due_at) : '—'} />
        {canManage && isOpen ? (
          <TextField
            select
            size="small"
            label="Priority"
            value={ticket.priority === 'medium' ? 'normal' : ticket.priority}
            onChange={(event) => priorityMutation.mutate(event.target.value as TicketPriority)}
            disabled={busy}
          >
            {Object.entries(catalog.data?.priorities ?? {}).map(([value, label]) => (
              <MenuItem key={value} value={value}>
                {label}
              </MenuItem>
            ))}
          </TextField>
        ) : (
          <MetaField label="Location / asset" value={ticket.location ?? '—'} />
        )}
      </Box>

      {ticket.description ? (
        <Paper variant="outlined" sx={{ p: 1.5, bgcolor: 'action.hover' }}>
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
            {ticket.description}
          </Typography>
        </Paper>
      ) : null}

      {ticket.pending_reason && ['pending_requester', 'pending_internal', 'pending_vendor', 'on_hold'].includes(ticket.status) ? (
        <Alert severity="info">Waiting: {ticket.pending_reason}</Alert>
      ) : null}

      {ticket.resolution || ticket.cancellation_reason ? (
        <Paper
          variant="outlined"
          sx={{ p: 1.5, borderColor: ticket.resolution ? 'success.light' : 'divider' }}
        >
          {ticket.resolution ? (
            <>
              <Typography variant="caption" color="success.main" sx={{ fontWeight: 700 }}>
                Resolution
                {ticket.resolution_category && catalog.data
                  ? ` · ${catalog.data.resolution_categories[ticket.resolution_category] ?? ticket.resolution_category}`
                  : ''}
              </Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                {ticket.resolution}
              </Typography>
              {ticket.work_performed ? (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75, whiteSpace: 'pre-wrap' }}>
                  Work performed: {ticket.work_performed}
                </Typography>
              ) : null}
              {ticket.closure_reason && catalog.data ? (
                <Typography variant="caption" color="text.secondary">
                  Closed: {catalog.data.closure_reasons[ticket.closure_reason] ?? ticket.closure_reason}
                </Typography>
              ) : null}
            </>
          ) : (
            <Typography variant="body2">Cancelled: {ticket.cancellation_reason}</Typography>
          )}
        </Paper>
      ) : null}

      {ticket.related_records.length > 0 || ticket.linked_tasks.length > 0 ? (
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 0.75 }}>
            Related records
          </Typography>
          <Stack spacing={0.5}>
            {ticket.related_records.map((record) => (
              <Typography key={`${record.kind}-${record.id}`} variant="body2">
                <Typography component="span" variant="caption" color="text.secondary" sx={{ mr: 1 }}>
                  {record.kind.replace(/_/g, ' ')}
                </Typography>
                {record.href ? (
                  <Link component={RouterLink} to={record.href}>
                    {record.label}
                  </Link>
                ) : (
                  record.label
                )}
              </Typography>
            ))}
            {ticket.linked_tasks.map((task) => (
              <Typography key={task.item_id} variant="body2">
                <Typography component="span" variant="caption" color="text.secondary" sx={{ mr: 1 }}>
                  onboarding task
                </Typography>
                <Link component={RouterLink} to={`/hr/onboarding?id=${task.checklist_id}&task=${task.item_id}`}>
                  {task.employee_name ? `${task.employee_name} · ` : ''}
                  {task.item_text}
                </Link>{' '}
                <Chip label={task.status_label} size="small" variant="outlined" sx={{ ml: 0.5 }} />
              </Typography>
            ))}
          </Stack>
        </Box>
      ) : null}

      <Divider />

      <Tabs value={tab} onChange={(_, value) => setTab(value)} variant="scrollable" allowScrollButtonsMobile>
        <Tab value="conversation" label={`Conversation (${ticket.comments.length})`} />
        <Tab value="timeline" label="History" />
        {canManage ? <Tab value="assignment" label="Assignment" /> : null}
        {canManage ? (
          <Tab value="notifications" label={`Notifications${failedNotifications ? ` (${failedNotifications} failed)` : ''}`} />
        ) : null}
      </Tabs>

      {tab === 'conversation' ? (
        <Stack spacing={1.25}>
          {ticket.comments.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No comments yet.
            </Typography>
          ) : (
            ticket.comments.map((row) => (
              <Paper
                key={row.id}
                variant="outlined"
                sx={{
                  p: 1.25,
                  bgcolor: row.is_internal ? 'warning.50' : 'background.paper',
                  borderColor: row.is_internal ? 'warning.light' : 'divider',
                }}
              >
                <Stack direction="row" spacing={1} sx={{ mb: 0.5, alignItems: 'center' }}>
                  <Typography variant="caption" sx={{ fontWeight: 700 }}>
                    {row.author_name ?? 'Unknown'}
                  </Typography>
                  {row.is_internal ? (
                    <Chip label="Internal" size="small" color="warning" variant="outlined" />
                  ) : null}
                  <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
                    {formatDateTime(row.created_at)}
                  </Typography>
                </Stack>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                  {row.body}
                </Typography>
              </Paper>
            ))
          )}
          <Box>
            <TextField
              size="small"
              placeholder={ticket.status === 'pending_requester' && !canManage ? 'Reply to the agent…' : 'Add a comment…'}
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              multiline
              minRows={2}
              maxRows={6}
              fullWidth
            />
            <Stack direction="row" spacing={1} sx={{ mt: 1, alignItems: 'center' }}>
              {ticket.can_comment_internal ? (
                <FormControlLabel
                  control={
                    <Checkbox size="small" checked={internal} onChange={(event) => setInternal(event.target.checked)} />
                  }
                  label={<Typography variant="caption">Internal note (agents only)</Typography>}
                />
              ) : null}
              <Button
                size="small"
                variant="contained"
                endIcon={<SendRoundedIcon />}
                onClick={() => commentMutation.mutate()}
                disabled={commentMutation.isPending || comment.trim().length === 0}
                sx={{ ml: 'auto' }}
              >
                Send
              </Button>
            </Stack>
          </Box>
        </Stack>
      ) : null}

      {tab === 'timeline' ? (
        <Stack spacing={1}>
          {ticket.timeline.map((event, index) => (
            <Box key={`${event.kind}-${index}`} sx={{ display: 'flex', gap: 1.5 }}>
              <Typography variant="caption" color="text.secondary" sx={{ minWidth: 120, flexShrink: 0 }}>
                {formatDateTime(event.at)}
              </Typography>
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {event.summary}
                  {event.is_internal ? (
                    <Chip label="Internal" size="small" color="warning" variant="outlined" sx={{ ml: 1 }} />
                  ) : null}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {event.actor_name ?? 'System'}
                </Typography>
                {event.detail ? (
                  <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                    {event.detail}
                  </Typography>
                ) : null}
              </Box>
            </Box>
          ))}
        </Stack>
      ) : null}

      {tab === 'assignment' ? (
        <Stack spacing={1}>
          {ticket.assignment_history.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No assignment changes recorded.
            </Typography>
          ) : (
            ticket.assignment_history.map((row, index) => (
              <Box key={index} sx={{ display: 'flex', gap: 1.5 }}>
                <Typography variant="caption" color="text.secondary" sx={{ minWidth: 120, flexShrink: 0 }}>
                  {formatDateTime(row.at)}
                </Typography>
                <Box>
                  <Typography variant="body2">
                    {row.previous_assignee_name ?? 'Queue'} → {row.new_assignee_name ?? 'Queue'}
                    {row.previous_group && row.new_group && row.previous_group !== row.new_group
                      ? ` (${row.previous_group} → ${row.new_group})`
                      : ''}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {row.change_type.replace(/[_:]/g, ' ')} · {row.changed_by_name ?? 'System'}
                    {row.reason ? ` · ${row.reason}` : ''}
                  </Typography>
                </Box>
              </Box>
            ))
          )}
        </Stack>
      ) : null}

      {tab === 'notifications' ? (
        <Stack spacing={1}>
          {failedNotifications ? (
            <Box>
              <Button size="small" variant="outlined" onClick={() => retryMutation.mutate()} disabled={retryMutation.isPending}>
                Re-send failed notifications
              </Button>
            </Box>
          ) : null}
          {ticket.notifications.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No notifications sent for this ticket.
            </Typography>
          ) : (
            ticket.notifications.map((row, index) => (
              <Typography key={index} variant="body2">
                <Typography component="span" variant="caption" color="text.secondary" sx={{ mr: 1 }}>
                  {formatDateTime(row.at)}
                </Typography>
                {row.event_key.replace(/_/g, ' ')} → {row.user_name ?? 'Unknown'}{' '}
                <Chip
                  label={row.status}
                  size="small"
                  color={row.status === 'failed' ? 'error' : 'default'}
                  variant="outlined"
                />
                {row.error ? ` ${row.error}` : ''}
              </Typography>
            ))
          )}
        </Stack>
      ) : null}

      <TicketStatusDialog
        ticket={ticket}
        target={statusTarget}
        catalog={catalog.data}
        busy={statusMutation.isPending}
        onClose={() => setStatusTarget(null)}
        onSubmit={(payload) => statusMutation.mutate(payload)}
      />
      {assignOpen ? (
        <TicketAssignDialog
          ticket={ticket}
          open={assignOpen}
          busy={assignMutation.isPending}
          onClose={() => setAssignOpen(false)}
          onSubmit={(assigneeId, reason) => assignMutation.mutate({ assigneeId, reason })}
        />
      ) : null}
      {transferOpen ? (
        <TicketTransferDialog
          ticket={ticket}
          open={transferOpen}
          catalog={catalog.data}
          busy={transferMutation.isPending}
          onClose={() => setTransferOpen(false)}
          onSubmit={(payload) => transferMutation.mutate(payload)}
        />
      ) : null}
    </Box>
  );
}

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {label}
      </Typography>
      <Typography variant="body2" noWrap title={value} sx={{ fontWeight: 600 }}>
        {value}
      </Typography>
    </Box>
  );
}
