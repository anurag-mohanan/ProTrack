import { useState, type MouseEvent, type ReactNode } from 'react';
import {
  Alert,
  Box,
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
  Link,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import BlockRoundedIcon from '@mui/icons-material/BlockRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import DoNotDisturbOnOutlinedIcon from '@mui/icons-material/DoNotDisturbOnOutlined';
import MoreVertRoundedIcon from '@mui/icons-material/MoreVertRounded';
import PendingOutlinedIcon from '@mui/icons-material/PendingOutlined';
import RadioButtonUncheckedRoundedIcon from '@mui/icons-material/RadioButtonUncheckedRounded';
import { useQuery } from '@tanstack/react-query';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { ProsohmButton } from '../ui/ProsohmButton';
import { getErrorMessage } from '../../api/client';
import {
  onboardingApi,
  type OnboardingChecklistItem,
  type OnboardingItemStatus,
} from '../../api/onboarding';
import {
  ATTENTION_LABELS,
  actionableAttention,
  isResolved,
  requestHref,
  type TaskAction,
  type TaskActionSubmit,
} from './onboardingTaskUtils';

const REQUEST_STATUS_LABELS: Record<string, string> = {
  open: 'Open',
  in_progress: 'In progress',
  on_hold: 'On hold',
  resolved: 'Resolved',
  closed: 'Closed',
  cancelled: 'Cancelled',
};

const COMPLETION_TYPE_LABELS: Record<string, string> = {
  manual: 'Completed directly',
  request: 'Completed via linked request',
  manual_override: 'Completed with override',
};

function statusColor(status: OnboardingItemStatus) {
  switch (status) {
    case 'completed':
      return 'success' as const;
    case 'blocked':
      return 'error' as const;
    case 'in_progress':
      return 'info' as const;
    case 'not_required':
    case 'waived':
      return 'default' as const;
    default:
      return 'warning' as const;
  }
}

function StatusIcon({ status }: { status: OnboardingItemStatus }) {
  const sx = { fontSize: 16 };
  if (status === 'completed') return <CheckCircleRoundedIcon sx={{ ...sx, color: 'success.main' }} />;
  if (status === 'blocked') return <BlockRoundedIcon sx={{ ...sx, color: 'error.main' }} />;
  if (status === 'in_progress') return <PendingOutlinedIcon sx={{ ...sx, color: 'info.main' }} />;
  if (status === 'not_required' || status === 'waived')
    return <DoNotDisturbOnOutlinedIcon sx={{ ...sx, color: 'text.disabled' }} />;
  return <RadioButtonUncheckedRoundedIcon sx={{ ...sx, color: 'text.disabled' }} />;
}

function formatDate(value: string | null) {
  if (!value) return '—';
  const parsed = new Date(value.length <= 10 ? `${value}T00:00:00` : value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString();
}

function formatDateTime(value: string | null) {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function RequestChip({ item }: { item: OnboardingChecklistItem }) {
  if (!item.help_ticket_number) return null;
  const status = item.request_status ?? '';
  const color =
    status === 'cancelled' ? 'error' : status === 'resolved' || status === 'closed' ? 'success' : 'info';
  return (
    <Chip
      size="small"
      variant="outlined"
      color={color}
      component={RouterLink}
      to={requestHref(item)}
      clickable
      label={`${item.help_ticket_number} · ${REQUEST_STATUS_LABELS[status] ?? status}`}
      sx={{ height: 20, '& .MuiChip-label': { px: 0.75, fontSize: '0.68rem' } }}
    />
  );
}

export function OnboardingTaskRow({
  item,
  busy,
  onAction,
  onOpen,
}: {
  item: OnboardingChecklistItem;
  busy: boolean;
  onAction: (action: TaskAction) => void;
  onOpen: () => void;
}) {
  const navigate = useNavigate();
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const resolved = isResolved(item.status);
  const attention = actionableAttention(item);
  const openMenu = (event: MouseEvent<HTMLElement>) => setMenuAnchor(event.currentTarget);
  const closeMenu = () => setMenuAnchor(null);
  const pick = (action: TaskAction) => {
    closeMenu();
    onAction(action);
  };

  return (
    <Box
      sx={{
        px: 1,
        py: 0.6,
        display: 'grid',
        gridTemplateColumns: { xs: '18px minmax(0, 1fr)', md: '18px minmax(0, 1fr) auto' },
        columnGap: 0.75,
        rowGap: 0.5,
        alignItems: 'center',
        borderTop: '1px solid',
        borderColor: 'divider',
        bgcolor: resolved ? 'action.hover' : 'transparent',
      }}
      data-testid={`onboarding-task-${item.id}`}
    >
      <Tooltip title={item.status_label}>
        <Box sx={{ display: 'flex' }}>
          <StatusIcon status={item.status} />
        </Box>
      </Tooltip>
      <Box sx={{ minWidth: 0 }}>
        <Link
          component="button"
          type="button"
          underline="hover"
          color="inherit"
          onClick={onOpen}
          sx={{ fontWeight: 600, fontSize: '0.8125rem', textAlign: 'left', lineHeight: 1.25 }}
        >
          {item.item_text}
        </Link>
        <Stack
          direction="row"
          spacing={0.75}
          sx={{ mt: 0.25, alignItems: 'center', flexWrap: 'wrap', rowGap: 0.4 }}
        >
          <Chip
            size="small"
            label={item.status_label}
            color={statusColor(item.status)}
            variant={item.status === 'not_started' ? 'outlined' : 'filled'}
            sx={{ height: 20, '& .MuiChip-label': { px: 0.75, fontSize: '0.68rem' } }}
          />
          <Typography variant="caption" color="text.secondary">
            Owner: {item.responsibility_label}
            {item.owner_name ? ` · ${item.owner_name}` : ''}
          </Typography>
          {!resolved && item.due_date ? (
            <Typography
              variant="caption"
              color={item.is_overdue ? 'error.main' : 'text.secondary'}
              sx={{ fontWeight: item.is_overdue ? 700 : 400 }}
            >
              {item.is_overdue ? 'Overdue · ' : 'Due '}
              {formatDate(item.due_date)}
            </Typography>
          ) : null}
          <RequestChip item={item} />
          {!item.help_ticket_number && !resolved && item.request_category ? (
            <Typography variant="caption" color="text.disabled">
              No request
            </Typography>
          ) : null}
          {resolved && item.completed_by_name ? (
            <Typography variant="caption" color="text.secondary">
              {item.completed_by_name} · {formatDate(item.completion_date)}
            </Typography>
          ) : null}
        </Stack>
        {attention.length > 0 || (item.status === 'blocked' && item.status_reason) ? (
          <Typography variant="caption" color="warning.dark" sx={{ display: 'block', mt: 0.25 }}>
            {item.status === 'blocked' && item.status_reason
              ? item.status_reason
              : attention
                  .filter((code) => code !== 'blocked')
                  .map((code) => ATTENTION_LABELS[code])
                  .join(' · ')}
          </Typography>
        ) : null}
      </Box>
      <Stack
        direction="row"
        spacing={0.5}
        sx={{
          gridColumn: { xs: '1 / -1', md: 'auto' },
          pl: { xs: '26px', md: 0 },
          justifyContent: { md: 'flex-end' },
          alignItems: 'center',
        }}
      >
        {!resolved && item.can_edit ? (
          <>
            {item.can_create_request ? (
              <ProsohmButton
                size="small"
                buttonVariant="secondary"
                disabled={busy}
                onClick={() => onAction({ kind: 'request' })}
              >
                {item.help_ticket_id ? 'New request' : 'Create request'}
              </ProsohmButton>
            ) : item.help_ticket_id ? (
              <ProsohmButton
                size="small"
                buttonVariant="secondary"
                onClick={() => navigate(requestHref(item))}
              >
                Open request
              </ProsohmButton>
            ) : null}
            <ProsohmButton
              size="small"
              buttonVariant="primary"
              disabled={busy}
              onClick={() => onAction({ kind: 'complete' })}
            >
              Complete
            </ProsohmButton>
          </>
        ) : (
          <ProsohmButton size="small" buttonVariant="secondary" onClick={onOpen}>
            Details
          </ProsohmButton>
        )}
        {item.can_edit ? (
          <>
            <IconButton size="small" aria-label="More task actions" onClick={openMenu} disabled={busy}>
              <MoreVertRoundedIcon fontSize="small" />
            </IconButton>
            <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={closeMenu}>
              {resolved ? (
                <MenuItem onClick={() => pick({ kind: 'status', status: 'not_started' })}>
                  Reopen task
                </MenuItem>
              ) : null}
              {!resolved && item.status !== 'in_progress' ? (
                <MenuItem onClick={() => pick({ kind: 'status', status: 'in_progress' })}>
                  {item.status === 'blocked' ? 'Unblock (in progress)' : 'Mark in progress'}
                </MenuItem>
              ) : null}
              {!resolved && item.status !== 'blocked' ? (
                <MenuItem onClick={() => pick({ kind: 'status', status: 'blocked' })}>
                  Mark blocked…
                </MenuItem>
              ) : null}
              {!resolved ? (
                <MenuItem onClick={() => pick({ kind: 'status', status: 'not_required' })}>
                  Mark not required…
                </MenuItem>
              ) : null}
              {!resolved && item.can_waive ? (
                <MenuItem onClick={() => pick({ kind: 'status', status: 'waived' })}>Waive…</MenuItem>
              ) : null}
              <Divider />
              <MenuItem
                onClick={() => {
                  closeMenu();
                  onOpen();
                }}
              >
                View details & history
              </MenuItem>
            </Menu>
          </>
        ) : null}
      </Stack>
    </Box>
  );
}

const ACTION_COPY: Record<string, { title: string; confirm: string; reasonLabel?: string; reasonRequired?: boolean }> = {
  complete: { title: 'Complete task', confirm: 'Mark complete' },
  request: { title: 'Create request', confirm: 'Create request' },
  in_progress: { title: 'Mark in progress', confirm: 'Mark in progress' },
  not_started: { title: 'Reopen task', confirm: 'Reopen' },
  blocked: { title: 'Mark blocked', confirm: 'Mark blocked', reasonLabel: 'Blocked reason', reasonRequired: true },
  not_required: { title: 'Mark not required', confirm: 'Mark not required', reasonLabel: 'Why does this not apply? (optional)' },
  waived: { title: 'Waive task', confirm: 'Waive', reasonLabel: 'Waiver reason', reasonRequired: true },
};

export function TaskActionDialog({
  item,
  action,
  busy,
  error,
  onClose,
  onSubmit,
}: {
  item: OnboardingChecklistItem | null;
  action: TaskAction | null;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (payload: TaskActionSubmit) => void;
}) {
  const open = Boolean(item && action);
  const key = action ? (action.kind === 'status' ? action.status : action.kind) : 'complete';
  const copy = ACTION_COPY[key];
  const [reason, setReason] = useState('');
  const [notes, setNotes] = useState('');
  const [override, setOverride] = useState(false);
  const [priority, setPriority] = useState<'low' | 'medium' | 'high' | 'urgent'>('medium');
  const [details, setDetails] = useState('');

  const reset = () => {
    setReason('');
    setNotes('');
    setOverride(false);
    setPriority('medium');
    setDetails('');
  };

  const close = () => {
    reset();
    onClose();
  };

  if (!item || !action) return <Dialog open={false} />;

  const isComplete = action.kind === 'complete';
  const isRequest = action.kind === 'request';
  const needsReason = Boolean(copy.reasonRequired) || (isComplete && override);
  const canSubmit = !busy && (!needsReason || reason.trim().length > 0);

  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="sm">
      <DialogTitle sx={{ pb: 0.5 }}>{copy.title}</DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {item.item_text}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
          Owner: {item.responsibility_label}
          {item.help_ticket_number ? ` · Linked request ${item.help_ticket_number}` : ''}
        </Typography>
        <Stack spacing={1.5}>
          {isRequest ? (
            <>
              <TextField
                select
                size="small"
                label="Priority"
                value={priority}
                onChange={(event) => setPriority(event.target.value as typeof priority)}
              >
                <MenuItem value="low">Low</MenuItem>
                <MenuItem value="medium">Medium</MenuItem>
                <MenuItem value="high">High</MenuItem>
                <MenuItem value="urgent">Urgent</MenuItem>
              </TextField>
              <TextField
                size="small"
                label="Details for the request (hardware, software, licence…)"
                multiline
                minRows={3}
                value={details}
                onChange={(event) => setDetails(event.target.value)}
              />
              <Typography variant="caption" color="text.secondary">
                The request is raised in the Help Desk with the employee, department, joining date and
                due date, and linked to this task. The task moves to In progress and completes
                automatically when the request is resolved.
              </Typography>
            </>
          ) : null}
          {isComplete ? (
            <>
              <TextField
                size="small"
                label="Completion note (evidence)"
                placeholder="e.g. WS-014 assigned, 3D mouse issued and NX licence assigned."
                multiline
                minRows={2}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
              {item.validation_rule ? (
                <FormControlLabel
                  control={
                    <Checkbox
                      size="small"
                      checked={override}
                      onChange={(event) => setOverride(event.target.checked)}
                    />
                  }
                  label={
                    <Typography variant="body2">
                      Complete with override (evidence is not recorded in ProTrack)
                    </Typography>
                  }
                />
              ) : null}
            </>
          ) : null}
          {copy.reasonLabel || (isComplete && override) ? (
            <TextField
              size="small"
              required={needsReason}
              label={isComplete ? 'Override reason' : copy.reasonLabel}
              multiline
              minRows={2}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          ) : null}
          {error ? <Alert severity="error">{error}</Alert> : null}
        </Stack>
      </DialogContent>
      <DialogActions>
        <ProsohmButton buttonVariant="secondary" onClick={close} disabled={busy}>
          Cancel
        </ProsohmButton>
        <ProsohmButton
          buttonVariant="primary"
          disabled={!canSubmit}
          onClick={() =>
            onSubmit({
              action,
              reason: reason.trim() || undefined,
              notes: notes.trim() || undefined,
              override: isComplete ? override : undefined,
              priority: isRequest ? priority : undefined,
              details: isRequest ? details.trim() || undefined : undefined,
            })
          }
        >
          {copy.confirm}
        </ProsohmButton>
      </DialogActions>
    </Dialog>
  );
}

const HISTORY_STATUS_LABEL: Record<string, string> = {
  not_started: 'Not started',
  in_progress: 'In progress',
  blocked: 'Blocked',
  completed: 'Completed',
  not_required: 'Not required',
  waived: 'Waived',
};

function historyTitle(event: { event: string; old_status: string | null; new_status: string | null; ticket_number: string | null }) {
  if (event.event === 'created') return 'Task created';
  if (event.event === 'request_linked') return `Request ${event.ticket_number ?? ''} linked`;
  const from = event.old_status ? HISTORY_STATUS_LABEL[event.old_status] ?? event.old_status : '—';
  const to = event.new_status ? HISTORY_STATUS_LABEL[event.new_status] ?? event.new_status : '—';
  return `${from} → ${to}`;
}

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <Stack direction="row" spacing={1} sx={{ py: 0.35 }}>
      <Typography variant="caption" color="text.secondary" sx={{ width: 120, flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography variant="body2" component="div" sx={{ minWidth: 0, wordBreak: 'break-word' }}>
        {value}
      </Typography>
    </Stack>
  );
}

export function TaskDetailDrawer({
  checklistId,
  employeeName,
  item,
  busy,
  onClose,
  onAction,
}: {
  checklistId: string;
  employeeName: string;
  item: OnboardingChecklistItem | null;
  busy: boolean;
  onClose: () => void;
  onAction: (action: TaskAction) => void;
}) {
  const navigate = useNavigate();
  const historyQuery = useQuery({
    queryKey: ['onboarding', checklistId, 'item-history', item?.id, item?.updated_at],
    queryFn: () => onboardingApi.itemHistory(checklistId, item!.id),
    enabled: Boolean(item),
  });
  const resolved = item ? isResolved(item.status) : false;

  return (
    <Drawer anchor="right" open={Boolean(item)} onClose={onClose}>
      {item ? (
        <Box sx={{ width: { xs: '100vw', sm: 440 }, p: 2 }} data-testid="onboarding-task-drawer">
          <Stack direction="row" sx={{ alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 800, lineHeight: 1.3 }}>
                {item.item_text}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {item.section} · {employeeName}
              </Typography>
            </Box>
            <IconButton size="small" aria-label="Close task details" onClick={onClose}>
              <CloseRoundedIcon fontSize="small" />
            </IconButton>
          </Stack>

          <Stack direction="row" spacing={0.75} sx={{ my: 1.25, flexWrap: 'wrap', rowGap: 0.75 }}>
            <Chip size="small" label={item.status_label} color={statusColor(item.status)} />
            {actionableAttention(item).map((code) => (
              <Chip key={code} size="small" variant="outlined" color="warning" label={ATTENTION_LABELS[code]} />
            ))}
          </Stack>

          {item.can_edit ? (
            <Stack direction="row" spacing={0.75} sx={{ mb: 1.5, flexWrap: 'wrap', rowGap: 0.75 }}>
              {!resolved ? (
                <ProsohmButton size="small" buttonVariant="primary" disabled={busy} onClick={() => onAction({ kind: 'complete' })}>
                  Mark complete
                </ProsohmButton>
              ) : (
                <ProsohmButton
                  size="small"
                  buttonVariant="secondary"
                  disabled={busy}
                  onClick={() => onAction({ kind: 'status', status: 'not_started' })}
                >
                  Reopen
                </ProsohmButton>
              )}
              {item.can_create_request ? (
                <ProsohmButton size="small" buttonVariant="secondary" disabled={busy} onClick={() => onAction({ kind: 'request' })}>
                  Create request
                </ProsohmButton>
              ) : null}
              {item.help_ticket_id ? (
                <ProsohmButton size="small" buttonVariant="secondary" onClick={() => navigate(requestHref(item))}>
                  Open request
                </ProsohmButton>
              ) : null}
              {!resolved && item.status !== 'blocked' ? (
                <ProsohmButton size="small" buttonVariant="secondary" disabled={busy} onClick={() => onAction({ kind: 'status', status: 'blocked' })}>
                  Mark blocked
                </ProsohmButton>
              ) : null}
              {!resolved && item.status === 'blocked' ? (
                <ProsohmButton size="small" buttonVariant="secondary" disabled={busy} onClick={() => onAction({ kind: 'status', status: 'in_progress' })}>
                  Unblock
                </ProsohmButton>
              ) : null}
              {!resolved ? (
                <ProsohmButton size="small" buttonVariant="secondary" disabled={busy} onClick={() => onAction({ kind: 'status', status: 'not_required' })}>
                  Not required
                </ProsohmButton>
              ) : null}
              {!resolved && item.can_waive ? (
                <ProsohmButton size="small" buttonVariant="secondary" disabled={busy} onClick={() => onAction({ kind: 'status', status: 'waived' })}>
                  Waive
                </ProsohmButton>
              ) : null}
            </Stack>
          ) : null}

          <Divider sx={{ mb: 1 }} />
          <DetailRow label="Category" value={item.section} />
          <DetailRow
            label="Owner"
            value={`${item.responsibility_label}${item.owner_name ? ` · ${item.owner_name}` : ' · no named person'}`}
          />
          <DetailRow label="Employee" value={employeeName} />
          <DetailRow
            label="Due date"
            value={
              <>
                {formatDate(item.due_date)}
                {item.is_overdue ? (
                  <Typography component="span" variant="caption" color="error.main" sx={{ ml: 0.75, fontWeight: 700 }}>
                    Overdue
                  </Typography>
                ) : null}
              </>
            }
          />
          <DetailRow
            label="Linked request"
            value={
              item.help_ticket_number ? (
                <Link component={RouterLink} to={requestHref(item)}>
                  {item.help_ticket_number} · {REQUEST_STATUS_LABELS[item.request_status ?? ''] ?? item.request_status}
                </Link>
              ) : item.request_category ? (
                item.requires_request ? 'Required — not created yet' : 'None (can be completed directly)'
              ) : (
                'Not applicable (completed directly by the manager)'
              )
            }
          />
          <DetailRow label="Created" value={formatDateTime(item.created_at)} />
          {item.status_reason ? <DetailRow label="Reason" value={item.status_reason} /> : null}
          {item.status_changed_at ? (
            <DetailRow
              label="Last change"
              value={`${formatDateTime(item.status_changed_at)}${item.status_changed_by_name ? ` · ${item.status_changed_by_name}` : ''}`}
            />
          ) : null}
          {resolved ? (
            <>
              <DetailRow label="Resolved" value={`${formatDateTime(item.completed_at ?? item.completion_date)}${item.completed_by_name ? ` · ${item.completed_by_name}` : ''}`} />
              {item.completion_type ? (
                <DetailRow label="Completion type" value={COMPLETION_TYPE_LABELS[item.completion_type] ?? item.completion_type} />
              ) : null}
            </>
          ) : null}
          {item.notes ? <DetailRow label="Notes" value={item.notes} /> : null}

          <Divider sx={{ my: 1.25 }} />
          <Typography variant="overline" color="text.secondary">
            History
          </Typography>
          {historyQuery.isLoading ? (
            <Typography variant="body2" color="text.secondary">
              Loading history…
            </Typography>
          ) : historyQuery.isError ? (
            <Alert severity="error">{getErrorMessage(historyQuery.error)}</Alert>
          ) : (
            <Stack spacing={0.75} sx={{ mt: 0.5 }}>
              {(historyQuery.data ?? []).map((event, index) => (
                <Box key={`${event.at}-${index}`} sx={{ borderLeft: '2px solid', borderColor: 'divider', pl: 1 }}>
                  <ListItemText
                    primary={historyTitle(event)}
                    secondary={[
                      formatDateTime(event.at),
                      event.actor_name,
                      event.completion_type ? COMPLETION_TYPE_LABELS[event.completion_type] : null,
                      event.reason ? `Reason: ${event.reason}` : null,
                      event.note,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                    slotProps={{
                      primary: { variant: 'body2', sx: { fontWeight: 600 } },
                      secondary: { variant: 'caption' },
                    }}
                  />
                </Box>
              ))}
            </Stack>
          )}
        </Box>
      ) : null}
    </Drawer>
  );
}
