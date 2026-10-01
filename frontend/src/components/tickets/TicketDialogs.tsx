import { useState } from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import type { TicketCatalog, TicketDetail, TicketStatus, TicketStatusChange } from '../../types/tickets';
import { ACTION_LABELS, PENDING_STATUSES } from './ticketConstants';
import { useTicketAssignees, useTicketCapabilities } from './useTicketMeta';

interface StatusDialogProps {
  ticket: TicketDetail;
  target: TicketStatus | null;
  catalog: TicketCatalog | undefined;
  busy: boolean;
  onClose: () => void;
  onSubmit: (payload: TicketStatusChange) => void;
}

/** Collects what each transition requires before it is sent to the server. */
export function TicketStatusDialog({ ticket, target, catalog, busy, onClose, onSubmit }: StatusDialogProps) {
  return (
    <Dialog open={Boolean(target)} onClose={onClose} fullWidth maxWidth="sm">
      {target ? (
        <StatusDialogBody
          key={target}
          ticket={ticket}
          target={target}
          catalog={catalog}
          busy={busy}
          onClose={onClose}
          onSubmit={onSubmit}
        />
      ) : null}
    </Dialog>
  );
}

function StatusDialogBody({
  ticket,
  target,
  catalog,
  busy,
  onClose,
  onSubmit,
}: StatusDialogProps & { target: TicketStatus }) {
  const [resolution, setResolution] = useState(ticket.resolution ?? '');
  const [work, setWork] = useState(ticket.work_performed ?? '');
  const [category, setCategory] = useState(ticket.resolution_category ?? '');
  const [closure, setClosure] = useState('resolved');
  const [reason, setReason] = useState('');

  const isPending = PENDING_STATUSES.includes(target);
  const needsReason = isPending || target === 'cancelled' || target === 'open';
  const valid =
    target === 'resolved'
      ? resolution.trim().length > 0 && work.trim().length > 0
      : needsReason
        ? reason.trim().length > 0
        : true;

  const submit = () => {
    if (target === 'resolved') {
      onSubmit({
        status: target,
        resolution: resolution.trim(),
        work_performed: work.trim(),
        resolution_category: category || null,
      });
    } else if (target === 'closed') {
      onSubmit({ status: target, closure_reason: ticket.can_manage ? closure : null });
    } else {
      onSubmit({ status: target, reason: reason.trim() || null });
    }
  };

  const reasonLabel =
    target === 'cancelled'
      ? 'Why is this ticket being cancelled?'
      : target === 'open'
        ? 'Why is this ticket being reopened?'
        : 'What is it waiting for?';

  return (
    <>
      <DialogTitle>
        {ACTION_LABELS[target] ?? target} · {ticket.ticket_number}
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2} sx={{ mt: 0.5 }}>
          {target === 'resolved' ? (
            <>
              <TextField
                label="Resolution summary"
                required
                value={resolution}
                onChange={(event) => setResolution(event.target.value)}
                multiline
                minRows={2}
                fullWidth
                autoFocus
              />
              <TextField
                label="Work performed"
                required
                value={work}
                onChange={(event) => setWork(event.target.value)}
                multiline
                minRows={2}
                fullWidth
                helperText="Recorded on the ticket and visible to the requester."
              />
              <TextField
                select
                label="Resolution category"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                fullWidth
              >
                <MenuItem value="">Not specified</MenuItem>
                {Object.entries(catalog?.resolution_categories ?? {}).map(([value, label]) => (
                  <MenuItem key={value} value={value}>
                    {label}
                  </MenuItem>
                ))}
              </TextField>
              {ticket.linked_tasks.length > 0 ? (
                <Typography variant="body2" color="text.secondary">
                  {ticket.linked_tasks.length === 1
                    ? 'The linked onboarding task will be completed according to its rule.'
                    : `${ticket.linked_tasks.length} linked onboarding tasks will be updated.`}
                </Typography>
              ) : null}
            </>
          ) : target === 'closed' ? (
            ticket.can_manage ? (
              <TextField
                select
                label="Closure reason"
                value={closure}
                onChange={(event) => setClosure(event.target.value)}
                fullWidth
              >
                {Object.entries(catalog?.closure_reasons ?? {}).map(([value, label]) => (
                  <MenuItem key={value} value={value}>
                    {label}
                  </MenuItem>
                ))}
              </TextField>
            ) : (
              <Typography variant="body2">
                Confirm that the resolution works for you. The ticket will be closed.
              </Typography>
            )
          ) : (
            <TextField
              label={reasonLabel}
              required
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              multiline
              minRows={2}
              fullWidth
              autoFocus
            />
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Back</Button>
        <Button
          variant="contained"
          color={target === 'cancelled' ? 'error' : 'primary'}
          onClick={submit}
          disabled={!valid || busy}
        >
          {ACTION_LABELS[target] ?? 'Save'}
        </Button>
      </DialogActions>
    </>
  );
}

interface AssignDialogProps {
  ticket: TicketDetail;
  open: boolean;
  busy: boolean;
  onClose: () => void;
  onSubmit: (assigneeId: string | null, reason: string) => void;
}

export function TicketAssignDialog({ ticket, open, busy, onClose, onSubmit }: AssignDialogProps) {
  const assignees = useTicketAssignees(ticket.category, open);
  const [assignee, setAssignee] = useState(ticket.assignee_id ?? '');
  const [reason, setReason] = useState('');
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>Assign {ticket.ticket_number}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2} sx={{ mt: 0.5 }}>
          <TextField
            select
            label="Owner"
            value={assignee}
            onChange={(event) => setAssignee(event.target.value)}
            fullWidth
            helperText={
              assignees.data && assignees.data.length === 0
                ? 'Nobody is configured to work this queue.'
                : 'People who work this queue.'
            }
          >
            <MenuItem value="">Unassigned (back to queue)</MenuItem>
            {(assignees.data ?? []).map((row) => (
              <MenuItem key={row.id} value={row.id}>
                {row.name}
                {row.role_name ? ` · ${row.role_name}` : ''}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Reason (optional)"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            fullWidth
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Back</Button>
        <Button
          variant="contained"
          onClick={() => onSubmit(assignee || null, reason.trim())}
          disabled={busy || (assignee || null) === ticket.assignee_id}
        >
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}

interface TransferDialogProps {
  ticket: TicketDetail;
  open: boolean;
  catalog: TicketCatalog | undefined;
  busy: boolean;
  onClose: () => void;
  onSubmit: (payload: { category: string; subcategory: string | null; assignee_id: string | null; reason: string }) => void;
}

export function TicketTransferDialog({ ticket, open, catalog, busy, onClose, onSubmit }: TransferDialogProps) {
  const capabilities = useTicketCapabilities();
  const [category, setCategory] = useState<string>(ticket.category);
  const [subcategory, setSubcategory] = useState<string>(ticket.subcategory ?? '');
  const [assignee, setAssignee] = useState('');
  const [reason, setReason] = useState('');
  const canPickOwner = Boolean(capabilities.data?.manageable_categories.includes(category));
  const assignees = useTicketAssignees(category, open && canPickOwner);
  const subcategories = catalog?.subcategories[category] ?? {};
  const changed = category !== ticket.category || (subcategory || null) !== ticket.subcategory;

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Transfer {ticket.ticket_number}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2} sx={{ mt: 0.5 }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField
              select
              label="Queue"
              value={category}
              onChange={(event) => {
                setCategory(event.target.value);
                setSubcategory('');
                setAssignee('');
              }}
              fullWidth
            >
              {Object.entries(catalog?.categories ?? {}).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="Type"
              value={subcategory}
              onChange={(event) => setSubcategory(event.target.value)}
              fullWidth
              disabled={Object.keys(subcategories).length === 0}
            >
              <MenuItem value="">General</MenuItem>
              {Object.entries(subcategories).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          {canPickOwner ? (
            <TextField
              select
              label="Owner"
              value={assignee}
              onChange={(event) => setAssignee(event.target.value)}
              fullWidth
              helperText="Leave on automatic to use the queue's routing."
            >
              <MenuItem value="">Automatic (routing rules)</MenuItem>
              {(assignees.data ?? []).map((row) => (
                <MenuItem key={row.id} value={row.id}>
                  {row.name}
                </MenuItem>
              ))}
            </TextField>
          ) : (
            <Typography variant="body2" color="text.secondary">
              The receiving queue&apos;s routing picks the owner.
            </Typography>
          )}
          <TextField
            label="Reason"
            required
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            multiline
            minRows={2}
            fullWidth
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Back</Button>
        <Button
          variant="contained"
          onClick={() =>
            onSubmit({
              category,
              subcategory: subcategory || null,
              assignee_id: assignee || null,
              reason: reason.trim(),
            })
          }
          disabled={busy || !changed || reason.trim().length === 0}
        >
          Transfer
        </Button>
      </DialogActions>
    </Dialog>
  );
}
