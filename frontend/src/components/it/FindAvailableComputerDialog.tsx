import { useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchComputerAvailability, fetchInventoryReference, itInventoryKeys } from '../../api/itInventory';
import { assignAsset, fetchItPeoplePaginated } from '../../api/itOperations';
import { itProvisioningKeys } from '../../api/itProvisioning';
import { getErrorMessage } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { FormField, FormSelect } from '../ui/design-system';
import { ProsohmButton } from '../ui/ProsohmButton';

type Props = {
  open: boolean;
  onClose: () => void;
  /** Prefill from onboarding / IT request */
  defaults?: {
    on_date?: string;
    shift_id?: string;
    computer_type?: string;
    monitor_quantity?: number;
    mouse_3d_required?: boolean;
    user_id?: string;
    employee_name?: string;
    provisioning_request_id?: string;
  };
};

const SEAT_TYPE_OPTIONS = [
  { value: '', label: 'Any type' },
  { value: 'ENG_WS', label: 'Engineering Workstation' },
  { value: 'GENERAL_WS', label: 'General Workstation' },
  { value: 'IT_WS', label: 'IT Workstation' },
  { value: 'ENG_LAPTOP', label: 'Engineering Laptop' },
  { value: 'GENERAL_LAPTOP', label: 'General Laptop' },
  { value: 'DESKTOP', label: 'Workstation (type not set)' },
  { value: 'LAPTOP', label: 'Laptop (type not set)' },
];

export function FindAvailableComputerDialog({ open, onClose, defaults }: Props) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const today = new Date().toISOString().slice(0, 10);
  const [onDate, setOnDate] = useState(defaults?.on_date || today);
  const [shiftId, setShiftId] = useState(defaults?.shift_id || '');
  const [seatType, setSeatType] = useState(defaults?.computer_type || '');
  const [assignUserId, setAssignUserId] = useState(defaults?.user_id || '');
  const resolvedUserId = defaults?.user_id || assignUserId;

  const referenceQuery = useQuery({
    queryKey: itInventoryKeys.reference(),
    queryFn: fetchInventoryReference,
    enabled: open,
  });
  const peopleQuery = useQuery({
    queryKey: ['it-people', 'find-available'],
    queryFn: () => fetchItPeoplePaginated({ page: 1, page_size: 200 }),
    enabled: open && !defaults?.user_id,
  });
  const availabilityQuery = useQuery({
    queryKey: [...itInventoryKeys.all, 'find-available', onDate, shiftId, seatType],
    queryFn: () =>
      fetchComputerAvailability({
        on_date: onDate,
        shift_id: shiftId,
        seat_type: seatType || undefined,
        only_available: true,
      }),
    enabled: open && Boolean(onDate && shiftId),
  });

  const assignMutation = useMutation({
    mutationFn: (assetId: string) =>
      assignAsset(assetId, { user_id: resolvedUserId, shift_id: shiftId, assigned_date: onDate }),
    onSuccess: (asset) => {
      const name =
        defaults?.employee_name ||
        (peopleQuery.data?.items || []).find((p) => p.user_id === resolvedUserId)?.full_name;
      showSuccess(`${asset.asset_number} assigned${name ? ` to ${name}` : ''}.`);
      void queryClient.invalidateQueries({ queryKey: itInventoryKeys.all });
      void queryClient.invalidateQueries({ queryKey: itProvisioningKeys.all });
      void queryClient.invalidateQueries({ queryKey: ['it-assets'] });
      onClose();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const shifts = referenceQuery.data?.shifts ?? [];
  const computers = availabilityQuery.data?.computers ?? [];
  const peripheralsNeeded = [
    defaults?.monitor_quantity ? `${defaults.monitor_quantity} monitor(s)` : null,
    defaults?.mouse_3d_required ? '3D mouse' : null,
  ].filter(Boolean);

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>Find Available Computer</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          {defaults?.employee_name ? (
            <Alert severity="info">Searching for {defaults.employee_name}.</Alert>
          ) : (
            <FormSelect
              label="Assign to employee"
              value={assignUserId}
              options={[
                { value: '', label: 'Select employee to enable Assign' },
                ...(peopleQuery.data?.items || []).map((p) => ({ value: p.user_id, label: p.full_name })),
              ]}
              onChange={(e) => setAssignUserId(String(e.target.value))}
            />
          )}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <FormField
              label="Date"
              type="date"
              value={onDate}
              onChange={(e) => setOnDate(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <FormSelect
              label="Shift"
              value={shiftId}
              options={[
                { value: '', label: 'Select shift' },
                ...shifts.map((s) => ({ value: s.id, label: s.label })),
              ]}
              onChange={(e) => setShiftId(String(e.target.value))}
            />
            <FormSelect
              label="Computer type"
              value={seatType}
              options={SEAT_TYPE_OPTIONS}
              onChange={(e) => setSeatType(String(e.target.value))}
            />
          </Stack>
          {peripheralsNeeded.length ? (
            <Typography variant="body2" color="text.secondary">
              Also required: {peripheralsNeeded.join(', ')}. Assign peripherals to the employee after the
              computer; the virtual seat shows what is still missing.
            </Typography>
          ) : null}

          {!shiftId ? (
            <Alert severity="info">Select a shift to see computers free for that shift.</Alert>
          ) : availabilityQuery.isLoading ? (
            <Typography variant="body2">Checking availability…</Typography>
          ) : availabilityQuery.isError ? (
            <Alert severity="error">{getErrorMessage(availabilityQuery.error)}</Alert>
          ) : computers.length === 0 ? (
            <Alert severity="warning">No computer of this type is free for the selected shift and date.</Alert>
          ) : (
            <Box sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Computer</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell>Make / model</TableCell>
                    <TableCell>Current occupants</TableCell>
                    <TableCell align="right" />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {computers.map((c) => (
                    <TableRow key={c.asset_id}>
                      <TableCell>
                        <strong>{c.asset_number}</strong>
                        {c.computer_name ? ` · ${c.computer_name}` : ''}
                      </TableCell>
                      <TableCell>{c.seat_type_label}</TableCell>
                      <TableCell>{[c.make, c.model].filter(Boolean).join(' ') || '—'}</TableCell>
                      <TableCell>
                        {c.occupants.length ? (
                          <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap' }}>
                            {c.occupants.map((o) => (
                              <Chip
                                key={o.user_id}
                                size="small"
                                label={`${o.user_name ?? '—'}${o.shift_display ? ` (${o.shift_display})` : ''}`}
                              />
                            ))}
                          </Stack>
                        ) : (
                          'Unassigned'
                        )}
                      </TableCell>
                      <TableCell align="right">
                        <ProsohmButton
                          buttonVariant="primary"
                          disabled={!resolvedUserId || assignMutation.isPending}
                          onClick={() => assignMutation.mutate(c.asset_id)}
                        >
                          Assign
                        </ProsohmButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <ProsohmButton buttonVariant="secondary" onClick={onClose}>
          Close
        </ProsohmButton>
      </DialogActions>
    </Dialog>
  );
}
