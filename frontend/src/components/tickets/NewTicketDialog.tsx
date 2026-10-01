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
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ticketsApi } from '../../api/tickets';
import { fetchUsers } from '../../api/lookups';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';
import type { TicketCategory, TicketDetail, TicketPriority } from '../../types/tickets';
import { useTicketCapabilities, useTicketCatalog } from './useTicketMeta';

interface NewTicketDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: (ticket: TicketDetail) => void;
  defaultCategory?: TicketCategory;
}

const emptyForm = {
  title: '',
  category: 'it' as TicketCategory,
  subcategory: '',
  priority: 'normal' as TicketPriority,
  description: '',
  location: '',
  due_date: '',
  affected_user_id: '',
};

export function NewTicketDialog({ open, onClose, onCreated, defaultCategory }: NewTicketDialogProps) {
  const catalog = useTicketCatalog();
  const capabilities = useTicketCapabilities();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [form, setForm] = useState({ ...emptyForm, category: defaultCategory ?? emptyForm.category });
  const isAgentForCategory = Boolean(capabilities.data?.manageable_categories.includes(form.category));
  const users = useQuery({
    queryKey: ['lookups', 'users'],
    queryFn: fetchUsers,
    enabled: open && isAgentForCategory,
  });
  const subcategories = catalog.data?.subcategories[form.category] ?? {};

  const mutation = useMutation({
    mutationFn: () =>
      ticketsApi.create({
        title: form.title.trim(),
        category: form.category,
        subcategory: form.subcategory || null,
        priority: form.priority,
        description: form.description.trim() || null,
        location: form.location.trim() || null,
        due_date: form.due_date || null,
        affected_user_id: isAgentForCategory && form.affected_user_id ? form.affected_user_id : null,
      }),
    onSuccess: (ticket) => {
      showSuccess(`Ticket ${ticket.ticket_number} created.`);
      setForm({ ...emptyForm, category: defaultCategory ?? emptyForm.category });
      queryClient.invalidateQueries({ queryKey: ['tickets'] });
      onCreated(ticket);
    },
    onError: (error) => showError(apiErrorMessage(error, 'Could not create the ticket.')),
  });

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Raise a ticket</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2} sx={{ mt: 0.5 }}>
          <TextField
            label="Title"
            required
            value={form.title}
            onChange={(event) => setForm({ ...form, title: event.target.value })}
            placeholder="Short summary of the request"
            fullWidth
            autoFocus
          />
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField
              select
              label="Category"
              value={form.category}
              onChange={(event) =>
                setForm({ ...form, category: event.target.value as TicketCategory, subcategory: '' })
              }
              fullWidth
            >
              {Object.entries(catalog.data?.categories ?? {}).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="Type"
              value={form.subcategory}
              onChange={(event) => setForm({ ...form, subcategory: event.target.value })}
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
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField
              select
              label="Priority"
              value={form.priority}
              onChange={(event) => setForm({ ...form, priority: event.target.value as TicketPriority })}
              fullWidth
            >
              {Object.entries(catalog.data?.priorities ?? {}).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Needed by"
              type="date"
              value={form.due_date}
              onChange={(event) => setForm({ ...form, due_date: event.target.value })}
              slotProps={{ inputLabel: { shrink: true } }}
              fullWidth
            />
          </Stack>
          {isAgentForCategory ? (
            <TextField
              select
              label="Affected employee (optional)"
              value={form.affected_user_id}
              onChange={(event) => setForm({ ...form, affected_user_id: event.target.value })}
              fullWidth
            >
              <MenuItem value="">Not for a specific employee</MenuItem>
              {(users.data ?? []).map((row) => (
                <MenuItem key={row.id} value={row.id}>
                  {row.first_name} {row.last_name}
                </MenuItem>
              ))}
            </TextField>
          ) : null}
          <TextField
            label="Description"
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
            placeholder="What is needed, steps to reproduce, impact…"
            multiline
            minRows={3}
            fullWidth
          />
          <TextField
            label="Location / asset"
            value={form.location}
            onChange={(event) => setForm({ ...form, location: event.target.value })}
            placeholder="e.g. 2nd floor, Meeting Room B, laptop tag…"
            fullWidth
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={() => mutation.mutate()}
          disabled={form.title.trim().length < 3 || mutation.isPending}
        >
          Submit ticket
        </Button>
      </DialogActions>
    </Dialog>
  );
}
