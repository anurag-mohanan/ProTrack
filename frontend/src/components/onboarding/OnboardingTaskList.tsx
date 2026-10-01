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
import HourglassEmptyRoundedIcon from '@mui/icons-material/HourglassEmptyRounded';
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
  type OnboardingTaskActionCode,
} from '../../api/onboarding';
import {
  ACTION_CODE_LABELS,
  ACTION_FOR_CODE,
  ATTENTION_LABELS,
  actionableAttention,
  completionNeedsOverride,
  isResolved,
  requestHref,
  type TaskAction,
  type TaskActionSubmit,
} from './onboardingTaskUtils';

const COMPLETION_TYPE_LABELS: Record<string, string> = {
  manual: 'Completed directly',
  request: 'Completed via linked ticket',
  manual_override: 'Completed with override',
  evidence: 'Completed with evidence',
  automated: 'Completed automatically',
  approved: 'Approved',
};

const CHIP_SX = { height: 20, '& .MuiChip-label': { px: 0.75, fontSize: '0.68rem' } };

function statusColor(status: OnboardingItemStatus) {
  switch (status) {
    case 'completed':
      return 'success' as const;
    case 'blocked':
      return 'error' as const;
    case 'in_progress':
    case 'ready':
      return 'info' as const;
    case 'not_required':
    case 'waived':
    case 'cancelled':
      return 'default' as const;
    default:
      return 'warning' as const;
  }
}

function StatusIcon({ status }: { status: OnboardingItemStatus }) {
  const sx = { fontSize: 16 };
  if (status === 'completed') return <CheckCircleRoundedIcon sx={{ ...sx, color: 'success.main' }} />;
  if (status === 'blocked') return <BlockRoundedIcon sx={{ ...sx, color: 'error.main' }} />;
  if (status === 'waiting') return <HourglassEmptyRoundedIcon sx={{ ...sx, color: 'warning.main' }} />;
  if (status === 'in_progress') return <PendingOutlinedIcon sx={{ ...sx, color: 'info.main' }} />;
  if (status === 'not_required' || status === 'waived' || status === 'cancelled')
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

function actionLabel(item: OnboardingChecklistItem, code: OnboardingTaskActionCode) {
  if (code === 'complete' && item.execution_type === 'APPROVAL_REQUIRED') return 'Approve';
  return ACTION_CODE_LABELS[code].replace('…', '');
}

function ticketOwnerText(item: OnboardingChecklistItem) {
  if (item.request_needs_owner) return 'needs owner';
  return item.request_assignee_name ?? '';
}

function RequestChip({ item }: { item: OnboardingChecklistItem }) {
  if (item.link_broken) {
    return <Chip size="small" variant="outlined" color="error" label="Ticket link broken" sx={CHIP_SX} />;
  }
  if (!item.help_ticket_number) return null;
  const status = item.request_status ?? '';
  const color =
    status === 'cancelled' ? 'error' : status === 'resolved' || status === 'closed' ? 'success' : 'info';
  const owner = ticketOwnerText(item);
  return (
    <Chip
      size="small"
      variant="outlined"
      color={color}
      component={RouterLink}
      to={requestHref(item)}
      clickable
      label={`${item.help_ticket_number} · ${item.request_status_label ?? status}${owner ? ` · ${owner}` : ''}`}
      sx={CHIP_SX}
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
  const actions = item.allowed_actions;
  const primaryCode: OnboardingTaskActionCode | null = actions.includes('complete')
    ? 'complete'
    : actions.includes('reopen')
      ? 'reopen'
      : null;
  const menuCodes = actions.filter((code) => code !== primaryCode);
  const needsRepair = item.can_repair_link && (item.link_broken || item.attention.includes('legacy_grouped'));
  const reasonShown = (item.status === 'blocked' || item.status === 'waiting') && item.status_reason;
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
            sx={CHIP_SX}
          />
          {item.execution_type !== 'CHECKLIST_ONLY' ? (
            <Chip size="small" variant="outlined" label={item.execution_type_label} sx={CHIP_SX} />
          ) : null}
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
          {!item.help_ticket_number && !item.link_broken && !resolved && item.execution_type === 'TICKET_REQUIRED' ? (
            <Typography variant="caption" color="warning.dark">
              No ticket yet
            </Typography>
          ) : null}
          {resolved && item.completed_by_name ? (
            <Typography variant="caption" color="text.secondary">
              {item.completed_by_name} · {formatDate(item.completion_date)}
            </Typography>
          ) : null}
        </Stack>
        {attention.length > 0 || reasonShown ? (
          <Typography variant="caption" color="warning.dark" sx={{ display: 'block', mt: 0.25 }}>
            {reasonShown
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
        {needsRepair ? (
          <ProsohmButton size="small" buttonVariant="secondary" disabled={busy} onClick={() => onAction({ kind: 'repair' })}>
            Repair link
          </ProsohmButton>
        ) : item.can_create_request ? (
          <ProsohmButton size="small" buttonVariant="secondary" disabled={busy} onClick={() => onAction({ kind: 'request' })}>
            {item.help_ticket_id ? 'New ticket' : 'Create ticket'}
          </ProsohmButton>
        ) : item.help_ticket_id && !item.link_broken ? (
          <ProsohmButton size="small" buttonVariant="secondary" onClick={() => navigate(requestHref(item))}>
            Open ticket
          </ProsohmButton>
        ) : null}
        {primaryCode ? (
          <ProsohmButton
            size="small"
            buttonVariant={primaryCode === 'complete' ? 'primary' : 'secondary'}
            disabled={busy}
            onClick={() => onAction(ACTION_FOR_CODE[primaryCode])}
          >
            {actionLabel(item, primaryCode)}
          </ProsohmButton>
        ) : (
          <ProsohmButton size="small" buttonVariant="secondary" onClick={onOpen}>
            Details
          </ProsohmButton>
        )}
        {menuCodes.length > 0 ? (
          <>
            <IconButton size="small" aria-label="More task actions" onClick={openMenu} disabled={busy}>
              <MoreVertRoundedIcon fontSize="small" />
            </IconButton>
            <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={closeMenu}>
              {menuCodes.map((code) => (
                <MenuItem key={code} onClick={() => pick(ACTION_FOR_CODE[code])}>
                  {ACTION_CODE_LABELS[code]}
                </MenuItem>
              ))}
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
  request: { title: 'Create ticket', confirm: 'Create ticket' },
  repair: { title: 'Repair ticket link', confirm: 'Repair' },
  in_progress: { title: 'Start task', confirm: 'Start' },
  not_started: { title: 'Reopen task', confirm: 'Reopen' },
  waiting: { title: 'Mark waiting', confirm: 'Mark waiting', reasonLabel: 'What is the task waiting for?', reasonRequired: true },
  blocked: { title: 'Mark blocked', confirm: 'Mark blocked', reasonLabel: 'Blocked reason', reasonRequired: true },
  not_required: { title: 'Mark not required', confirm: 'Mark not required', reasonLabel: 'Why does this not apply? (optional)' },
  waived: { title: 'Waive task', confirm: 'Waive', reasonLabel: 'Waiver reason', reasonRequired: true },
  cancelled: { title: 'Cancel task', confirm: 'Cancel task', reasonLabel: 'Cancellation reason', reasonRequired: true },
};

function overrideHint(item: OnboardingChecklistItem) {
  if (item.execution_type === 'AUTOMATED')
    return 'This task is completed by a system check. Completing it by hand needs an override reason.';
  if (item.execution_type === 'TICKET_REQUIRED')
    return 'This task completes when its ticket is resolved. To complete it now, use an override and give a reason.';
  return 'The system check for this task has not passed. Record evidence or use an override.';
}

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
  const copy = ACTION_COPY[key] ?? ACTION_COPY.complete;
  const [reason, setReason] = useState('');
  const [notes, setNotes] = useState('');
  const [override, setOverride] = useState(false);
  const [priority, setPriority] = useState<'low' | 'normal' | 'high' | 'urgent'>('normal');
  const [details, setDetails] = useState('');

  const reset = () => {
    setReason('');
    setNotes('');
    setOverride(false);
    setPriority('normal');
    setDetails('');
  };

  const close = () => {
    reset();
    onClose();
  };

  if (!item || !action) return <Dialog open={false} />;

  const isComplete = action.kind === 'complete';
  const isRequest = action.kind === 'request';
  const isRepair = action.kind === 'repair';
  const offerOverride =
    isComplete &&
    (item.execution_type === 'TICKET_REQUIRED' || item.execution_type === 'AUTOMATED' || Boolean(item.validation_rule));
  const needsReason = Boolean(copy.reasonRequired) || (isComplete && override);
  const evidenceRequired = isComplete && item.evidence_required && !override;
  const canSubmit =
    !busy && (!needsReason || reason.trim().length > 0) && (!evidenceRequired || notes.trim().length > 0);
  const title = isComplete && item.execution_type === 'APPROVAL_REQUIRED' ? 'Approve task' : copy.title;

  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="sm">
      <DialogTitle sx={{ pb: 0.5 }}>{title}</DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {item.item_text}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
          Owner: {item.responsibility_label}
          {item.execution_type !== 'CHECKLIST_ONLY' ? ` · ${item.execution_type_label}` : ''}
          {item.help_ticket_number ? ` · Ticket ${item.help_ticket_number}` : ''}
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
                <MenuItem value="normal">Normal</MenuItem>
                <MenuItem value="high">High</MenuItem>
                <MenuItem value="urgent">Urgent</MenuItem>
              </TextField>
              <TextField
                size="small"
                label="Details for the ticket (hardware, software, licence…)"
                multiline
                minRows={3}
                value={details}
                onChange={(event) => setDetails(event.target.value)}
              />
              <Typography variant="caption" color="text.secondary">
                One ticket is raised for this task with the employee, department, joining date and due
                date, and routed to the configured owner. The task then follows the ticket: waiting
                while the ticket waits, completed when it is resolved.
              </Typography>
            </>
          ) : null}
          {isRepair ? (
            <Typography variant="body2" color="text.secondary">
              {item.link_broken
                ? 'The linked ticket no longer exists. The dangling link is cleared (kept in history) and a ticket is raised for this task.'
                : 'This task shares a legacy ticket with other tasks. A dedicated ticket is raised for it; the shared ticket stays linked to the others.'}
            </Typography>
          ) : null}
          {offerOverride && completionNeedsOverride(item) ? <Alert severity="info">{overrideHint(item)}</Alert> : null}
          {isComplete ? (
            <>
              <TextField
                size="small"
                required={evidenceRequired}
                label={item.evidence_required ? 'Evidence' : 'Completion note (evidence)'}
                placeholder="e.g. WS-014 assigned, 3D mouse issued and NX licence assigned."
                multiline
                minRows={2}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
              {offerOverride ? (
                <FormControlLabel
                  control={
                    <Checkbox
                      size="small"
                      checked={override}
                      onChange={(event) => setOverride(event.target.checked)}
                    />
                  }
                  label={<Typography variant="body2">Complete with override (recorded in the audit trail)</Typography>}
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
          {isComplete && item.execution_type === 'APPROVAL_REQUIRED' ? 'Approve & complete' : copy.confirm}
        </ProsohmButton>
      </DialogActions>
    </Dialog>
  );
}

const HISTORY_STATUS_LABEL: Record<string, string> = {
  not_started: 'Not started',
  ready: 'Ready',
  in_progress: 'In progress',
  waiting: 'Waiting',
  blocked: 'Blocked',
  completed: 'Completed',
  not_required: 'Not required',
  waived: 'Waived',
  cancelled: 'Cancelled',
};

function historyTitle(event: { event: string; old_status: string | null; new_status: string | null; ticket_number: string | null }) {
  if (event.event === 'created') return 'Task created';
  if (event.event === 'request_linked') return `Ticket ${event.ticket_number ?? ''} linked`;
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

function executionSummary(item: OnboardingChecklistItem) {
  return [
    item.execution_type_label,
    item.mandatory ? 'mandatory' : 'optional',
    item.blocks_completion ? null : 'does not block completion',
    item.evidence_required ? 'evidence required' : null,
    item.confirm_by_label ? `confirmed by ${item.confirm_by_label.toLowerCase()}` : null,
  ]
    .filter(Boolean)
    .join(' · ');
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

          {item.allowed_actions.length > 0 || item.can_create_request || item.can_repair_link || item.help_ticket_id ? (
            <Stack direction="row" spacing={0.75} sx={{ mb: 1.5, flexWrap: 'wrap', rowGap: 0.75 }}>
              {item.allowed_actions.map((code) => (
                <ProsohmButton
                  key={code}
                  size="small"
                  buttonVariant={code === 'complete' ? 'primary' : 'secondary'}
                  disabled={busy}
                  onClick={() => onAction(ACTION_FOR_CODE[code])}
                >
                  {actionLabel(item, code)}
                </ProsohmButton>
              ))}
              {item.can_create_request ? (
                <ProsohmButton size="small" buttonVariant="secondary" disabled={busy} onClick={() => onAction({ kind: 'request' })}>
                  Create ticket
                </ProsohmButton>
              ) : null}
              {item.can_repair_link ? (
                <ProsohmButton size="small" buttonVariant="secondary" disabled={busy} onClick={() => onAction({ kind: 'repair' })}>
                  Repair link
                </ProsohmButton>
              ) : null}
              {item.help_ticket_id && !item.link_broken ? (
                <ProsohmButton size="small" buttonVariant="secondary" onClick={() => navigate(requestHref(item))}>
                  Open ticket
                </ProsohmButton>
              ) : null}
            </Stack>
          ) : null}

          <Divider sx={{ mb: 1 }} />
          <DetailRow label="Category" value={item.section} />
          <DetailRow label="Execution" value={executionSummary(item)} />
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
            label="Ticket"
            value={
              item.link_broken ? (
                'Link broken — the ticket no longer exists'
              ) : item.help_ticket_number ? (
                <Link component={RouterLink} to={requestHref(item)}>
                  {item.help_ticket_number} · {item.request_status_label ?? item.request_status}
                  {ticketOwnerText(item) ? ` · ${ticketOwnerText(item)}` : ''}
                </Link>
              ) : item.execution_type === 'TICKET_REQUIRED' ? (
                'Required — not created yet'
              ) : (
                'Not needed for this task'
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
          {item.evidence_note ? <DetailRow label="Evidence" value={item.evidence_note} /> : null}
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
