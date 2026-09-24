import { useMemo, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  assignWorkstationPackage,
  findAvailableComputer,
  workstationPackageKeys,
} from '../../api/workstationPackages';
import { fetchShifts } from '../../api/resourceShifts';
import { fetchComputerTypes, itProvisioningKeys } from '../../api/itProvisioning';
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

export function FindAvailableComputerDialog({ open, onClose, defaults }: Props) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    on_date: defaults?.on_date || today,
    shift_id: defaults?.shift_id || '',
    computer_type: defaults?.computer_type || 'ENG_WS',
    monitor_quantity: defaults?.monitor_quantity ?? 2,
    mouse_3d_required: defaults?.mouse_3d_required ?? false,
  });
  const [results, setResults] = useState<{
    exact_matches: Record<string, unknown>[];
    partial_matches: Record<string, unknown>[];
    unavailable_matches: Record<string, unknown>[];
  } | null>(null);

  const shiftsQuery = useQuery({
    queryKey: ['resource-shifts', 'list', { active_only: true }],
    queryFn: () => fetchShifts({ active_only: true }),
    enabled: open,
  });
  const typesQuery = useQuery({
    queryKey: itProvisioningKeys.computerTypes(),
    queryFn: fetchComputerTypes,
    enabled: open,
  });

  const searchMutation = useMutation({
    mutationFn: () =>
      findAvailableComputer({
        on_date: form.on_date,
        shift_id: form.shift_id,
        computer_type: form.computer_type || null,
        monitor_quantity: form.monitor_quantity,
        mouse_3d_required: form.mouse_3d_required,
        user_id: defaults?.user_id || null,
        provisioning_request_id: defaults?.provisioning_request_id || null,
      }),
    onSuccess: (data) => setResults(data),
    onError: (error) => showError(getErrorMessage(error)),
  });

  const assignMutation = useMutation({
    mutationFn: (packageId: string) =>
      assignWorkstationPackage(packageId, {
        user_id: defaults?.user_id || '',
        shift_id: form.shift_id,
        effective_from: form.on_date,
        provisioning_request_id: defaults?.provisioning_request_id || null,
      }),
    onSuccess: () => {
      showSuccess(
        `Workstation package assigned${defaults?.employee_name ? ` to ${defaults.employee_name}` : ''}.`,
      );
      void queryClient.invalidateQueries({ queryKey: workstationPackageKeys.all });
      void queryClient.invalidateQueries({ queryKey: itProvisioningKeys.all });
      onClose();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const shifts = shiftsQuery.data ?? [];
  const types = typesQuery.data ?? [];

  const canSearch = Boolean(form.on_date && form.shift_id);

  const renderMatchList = (
    title: string,
    rows: Record<string, unknown>[],
    allowAssign: boolean,
  ) => (
    <Box sx={{ mb: 2 }}>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        {title} ({rows.length})
      </Typography>
      {rows.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          None
        </Typography>
      ) : (
        <Stack spacing={1}>
          {rows.map((row) => (
            <Accordion key={String(row.id)} disableGutters>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Stack
                  direction="row"
                  spacing={1}
                  sx={{ width: '100%', alignItems: 'center', pr: 1 }}
                >
                  <Typography variant="body2" sx={{ flex: 1 }}>
                    <strong>{String(row.code)}</strong> ·{' '}
                    {String(row.computer_type_label || row.computer_type || '—')} ·{' '}
                    {String(row.monitor_count)} monitors
                    {row.has_3d_mouse ? ' · 3D mouse' : ''}
                  </Typography>
                  {allowAssign && defaults?.user_id ? (
                    <ProsohmButton
                      buttonVariant="primary"
                      onClick={(e) => {
                        e.stopPropagation();
                        assignMutation.mutate(String(row.id));
                      }}
                      disabled={assignMutation.isPending}
                    >
                      Assign
                      {defaults.employee_name ? ` to ${defaults.employee_name}` : ''}
                    </ProsohmButton>
                  ) : null}
                </Stack>
              </AccordionSummary>
              <AccordionDetails>
                <Typography variant="body2">
                  Computer: {String(row.primary_computer_number || '—')}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Availability: {String(row.availability_status)}
                  {row.availability_reason ? ` — ${String(row.availability_reason)}` : ''}
                </Typography>
                {Array.isArray(row.match_reasons) && row.match_reasons.length ? (
                  <Typography variant="body2" color="warning.main">
                    {(row.match_reasons as string[]).join('; ')}
                  </Typography>
                ) : null}
                <Typography variant="caption" sx={{ display: 'block', mt: 1 }}>
                  Members:{' '}
                  {((row.members as Record<string, unknown>[]) || [])
                    .map((m) => `${m.asset_number} (${m.role})`)
                    .join(', ') || '—'}
                </Typography>
              </AccordionDetails>
            </Accordion>
          ))}
        </Stack>
      )}
    </Box>
  );

  const emptyHint = useMemo(() => {
    if (!results) return null;
    if (
      !results.exact_matches.length &&
      !results.partial_matches.length &&
      !results.unavailable_matches.length
    ) {
      return 'No complete workstation package is currently available.';
    }
    return null;
  }, [results]);

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>Find Available Computer</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          {defaults?.employee_name ? (
            <Alert severity="info">
              Searching for {defaults.employee_name}
              {defaults.shift_id ? ' using their onboarding requirements.' : '.'}
            </Alert>
          ) : null}
          <FormField
            label="Date"
            type="date"
            value={form.on_date}
            onChange={(e) => setForm((f) => ({ ...f, on_date: e.target.value }))}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <FormSelect
            label="Shift"
            value={form.shift_id}
            options={(Array.isArray(shifts) ? shifts : []).map(
              (s: { id: string; name: string; start_time?: string; end_time?: string }) => ({
                value: s.id,
                label:
                  s.start_time && s.end_time
                    ? `${s.name} (${s.start_time}–${s.end_time})`
                    : s.name,
              }),
            )}
            onChange={(e) => setForm((f) => ({ ...f, shift_id: String(e.target.value) }))}
          />
          <FormSelect
            label="Computer type"
            value={form.computer_type}
            options={types.map((t) => ({ value: t.code, label: t.label }))}
            onChange={(e) => setForm((f) => ({ ...f, computer_type: String(e.target.value) }))}
          />
          <FormSelect
            label="Monitors required"
            value={String(form.monitor_quantity)}
            options={[0, 1, 2, 3, 4].map((n) => ({ value: String(n), label: String(n) }))}
            onChange={(e) =>
              setForm((f) => ({ ...f, monitor_quantity: Number(e.target.value) }))
            }
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={form.mouse_3d_required}
                onChange={(e) =>
                  setForm((f) => ({ ...f, mouse_3d_required: e.target.checked }))
                }
              />
            }
            label="3D mouse required"
          />
          <ProsohmButton
            buttonVariant="primary"
            disabled={!canSearch || searchMutation.isPending}
            onClick={() => searchMutation.mutate()}
          >
            {searchMutation.isPending ? 'Searching…' : 'Search packages'}
          </ProsohmButton>

          {emptyHint ? <Alert severity="warning">{emptyHint}</Alert> : null}

          {results ? (
            <>
              {renderMatchList('Exact matches', results.exact_matches, true)}
              {renderMatchList('Partial matches', results.partial_matches, false)}
              {renderMatchList('Unavailable matches', results.unavailable_matches, false)}
            </>
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
