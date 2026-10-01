import { useState } from 'react';
import {
  Alert,
  Box,
  Checkbox,
  Chip,
  FormControlLabel,
  Switch,
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
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [showUnavailable, setShowUnavailable] = useState(false);
  const [monitorsNeeded, setMonitorsNeeded] = useState(String(defaults?.monitor_quantity ?? ''));
  const [mouse3dNeeded, setMouse3dNeeded] = useState(Boolean(defaults?.mouse_3d_required));
  const [assignUserId, setAssignUserId] = useState(defaults?.user_id || '');
  const customWindow = Boolean(startTime && endTime);
  const windowReady = Boolean(shiftId || customWindow);
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
    queryKey: [...itInventoryKeys.all, 'find-available', onDate, shiftId, seatType, startTime, endTime],
    queryFn: () =>
      fetchComputerAvailability({
        on_date: onDate,
        shift_id: shiftId || undefined,
        start_time: customWindow ? startTime : undefined,
        end_time: customWindow ? endTime : undefined,
        seat_type: seatType || undefined,
        only_available: false,
      }),
    enabled: open && Boolean(onDate) && windowReady,
  });

  const assignMutation = useMutation({
    mutationFn: (assetId: string) =>
      assignAsset(assetId, {
        user_id: resolvedUserId,
        shift_id: shiftId || null,
        start_time: customWindow ? startTime : null,
        end_time: customWindow ? endTime : null,
        assigned_date: onDate,
      }),
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
  const slotCode = availabilityQuery.data?.shifts[0]?.shift_code;
  const allComputers = availabilityQuery.data?.computers ?? [];
  const slotOf = (c: (typeof allComputers)[number]) => c.shifts[0];
  const freeComputers = allComputers.filter((c) => slotOf(c)?.status === 'AVAILABLE');
  const computers = showUnavailable ? allComputers : freeComputers;
  const peripheralFree = (role: string) =>
    slotCode
      ? availabilityQuery.data?.peripherals?.find((p) => p.role === role)?.available_by_shift[slotCode] ?? 0
      : 0;
  const monitorsRequired = Number(monitorsNeeded) || 0;
  const peripheralChecks = [
    monitorsRequired
      ? { label: `${monitorsRequired} monitor(s)`, free: peripheralFree('monitor'), need: monitorsRequired }
      : null,
    mouse3dNeeded ? { label: '3D mouse', free: peripheralFree('mouse_3d'), need: 1 } : null,
  ].filter((row): row is { label: string; free: number; need: number } => row !== null);

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
                { value: '', label: customWindow ? 'None (custom window)' : 'Select shift' },
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
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <FormField
              label="Start time (optional)"
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <FormField
              label="End time (optional)"
              type="time"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              helper="Overrides the shift hours; overnight allowed"
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <FormField
              label="Monitors needed"
              type="number"
              value={monitorsNeeded}
              onChange={(e) => setMonitorsNeeded(e.target.value)}
              slotProps={{ htmlInput: { min: 0, max: 6 } }}
            />
            <FormControlLabel
              control={<Checkbox checked={mouse3dNeeded} onChange={(e) => setMouse3dNeeded(e.target.checked)} />}
              label="3D mouse"
            />
          </Stack>
          {peripheralChecks.length && availabilityQuery.data ? (
            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
              {peripheralChecks.map((row) => (
                <Chip
                  key={row.label}
                  size="small"
                  color={row.free >= row.need ? 'success' : 'error'}
                  label={`${row.label}: ${row.free} free in this window${row.free >= row.need ? '' : ' — shortage'}`}
                />
              ))}
            </Stack>
          ) : null}

          {!windowReady ? (
            <Alert severity="info">Select a shift or enter a start and end time to see free computers.</Alert>
          ) : availabilityQuery.isLoading ? (
            <Typography variant="body2">Checking availability…</Typography>
          ) : availabilityQuery.isError ? (
            <Alert severity="error">{getErrorMessage(availabilityQuery.error)}</Alert>
          ) : (
            <>
              <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <Typography variant="body2" sx={{ flex: 1 }}>
                  {freeComputers.length} of {allComputers.length} computer(s) free
                  {availabilityQuery.data?.shifts[0] ? ` for ${availabilityQuery.data.shifts[0].shift_display}` : ''}.
                </Typography>
                <FormControlLabel
                  control={
                    <Switch checked={showUnavailable} onChange={(e) => setShowUnavailable(e.target.checked)} />
                  }
                  label="Show unavailable with reasons"
                />
              </Stack>
              {computers.length === 0 ? (
                <Alert severity="warning">No computer of this type is free for the selected window and date.</Alert>
              ) : null}
            </>
          )}
          {windowReady && !availabilityQuery.isLoading && !availabilityQuery.isError && computers.length > 0 ? (
            <Box sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Computer</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell>Make / model</TableCell>
                    <TableCell>Current occupants</TableCell>
                    <TableCell>Availability</TableCell>
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
                      <TableCell>
                        {slotOf(c)?.status === 'AVAILABLE' ? (
                          <Chip size="small" color="success" label="Available" />
                        ) : (
                          <Box>
                            <Chip
                              size="small"
                              color="error"
                              label={String(slotOf(c)?.status ?? 'UNAVAILABLE').replace(/_/g, ' ')}
                            />
                            {slotOf(c)?.reason ? (
                              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                                {slotOf(c)?.reason}
                              </Typography>
                            ) : null}
                          </Box>
                        )}
                      </TableCell>
                      <TableCell align="right">
                        <ProsohmButton
                          buttonVariant="primary"
                          disabled={!resolvedUserId || assignMutation.isPending || slotOf(c)?.status !== 'AVAILABLE'}
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
          ) : null}
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
