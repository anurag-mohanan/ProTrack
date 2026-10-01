import { useMemo, useState } from 'react';
import { Box, Checkbox, Chip, FormControlLabel, IconButton, Stack, Typography } from '@mui/material';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import EventSeatRoundedIcon from '@mui/icons-material/EventSeatRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { assignSetup, itAllocationKeys } from '../../../api/itAllocation';
import { getErrorMessage } from '../../../api/client';
import { fetchAssets, fetchSoftwareLicenses, itOperationsKeys } from '../../../api/itOperations';
import { itInventoryKeys } from '../../../api/itInventory';
import { fetchUsers } from '../../../api/lookups';
import { fetchShifts } from '../../../api/resourceShifts';
import { useToast } from '../../../context/ToastContext';
import type { AllocationResourceType, SetupAssignResult, SetupLineInput } from '../../../types/itAllocation';
import { userDisplayName } from '../../../utils/format';
import { FormDrawer, FormField, FormSelect } from '../../ui/design-system';
import { ProsohmButton } from '../../ui/ProsohmButton';
import { AllocationWindowFields } from './AllocationWindowFields';
import { emptyWindow, windowReady, windowToInput, type AllocationWindowState } from './allocationWindow';

type Line = SetupLineInput & { label: string };

type Props = { open: boolean; onClose: () => void };

const RESULT_COLORS: Record<string, 'success' | 'error' | 'warning' | 'default' | 'info'> = {
  AVAILABLE: 'success',
  ASSIGNED: 'success',
  FAILED: 'error',
  CONFLICT: 'error',
  NOT_ALLOWED: 'error',
  UNAVAILABLE: 'error',
  RESERVED: 'warning',
  ROLLED_BACK: 'warning',
};

/**
 * Assign a complete setup (computer, monitors, 3D mouse, licenses) to one employee for one
 * shift/window in a single transaction. The server re-validates every line; nothing is saved
 * unless every line passes or the user explicitly chooses partial fulfilment.
 */
export function SetupAssignDrawer({ open, onClose }: Props) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [userId, setUserId] = useState('');
  const [slot, setSlot] = useState<AllocationWindowState>(() => emptyWindow('shift'));
  const [purpose, setPurpose] = useState('');
  const [allowPartial, setAllowPartial] = useState(false);
  const [lines, setLines] = useState<Line[]>([]);
  const [lineType, setLineType] = useState<AllocationResourceType>('asset');
  const [assetSearch, setAssetSearch] = useState('');
  const [pick, setPick] = useState('');
  const [result, setResult] = useState<SetupAssignResult | null>(null);

  const usersQuery = useQuery({ queryKey: ['lookups', 'users'], queryFn: () => fetchUsers(), enabled: open });
  const shiftsQuery = useQuery({
    queryKey: ['resource-shifts', 'list', 'active'],
    queryFn: () => fetchShifts({ active_only: true }),
    enabled: open,
  });
  const assetsQuery = useQuery({
    queryKey: [...itOperationsKeys.all, 'setup-asset-search', assetSearch],
    queryFn: () => fetchAssets({ search: assetSearch || undefined, page_size: 100 }),
    enabled: open && lineType === 'asset',
  });
  const licensesQuery = useQuery({
    queryKey: [...itOperationsKeys.all, 'setup-licenses'],
    queryFn: () => fetchSoftwareLicenses(),
    enabled: open && lineType === 'license',
  });

  const userOptions = useMemo(
    () => (usersQuery.data ?? []).map((u) => ({ value: u.id, label: userDisplayName(u) || u.email || u.id })),
    [usersQuery.data],
  );
  const pickOptions = useMemo(() => {
    const taken = new Set(lines.map((l) => `${l.resource_type}:${l.resource_id}`));
    if (lineType === 'asset') {
      return (assetsQuery.data ?? [])
        .filter((a) => !taken.has(`asset:${a.id}`) && !['retired', 'disposed', 'lost'].includes(String(a.status)))
        .map((a) => ({
          value: a.id,
          label: `${a.asset_number} · ${a.asset_type_name || a.asset_type_code || 'Asset'}${
            a.computer_name ? ` · ${a.computer_name}` : ''
          } (${String(a.status).replace(/_/g, ' ')})`,
        }));
    }
    return (licensesQuery.data ?? [])
      .filter((p) => !taken.has(`license:${p.id}`) && !['terminated', 'expired'].includes(String(p.status)))
      .map((p) => ({
        value: p.id,
        label: `${p.software_name ?? 'Software'}${p.entitlement_code ? ` · ${p.entitlement_code}` : ''} — ${
          p.license_metric_label ?? 'License'
        }`,
      }));
  }, [lineType, assetsQuery.data, licensesQuery.data, lines]);

  const reset = () => {
    setUserId('');
    setSlot(emptyWindow('shift'));
    setPurpose('');
    setAllowPartial(false);
    setLines([]);
    setPick('');
    setAssetSearch('');
    setResult(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  const body = (dryRun: boolean) => ({
    user_id: userId,
    lines: lines.map(({ resource_type, resource_id }) => ({ resource_type, resource_id })),
    ...windowToInput(slot),
    purpose: purpose.trim() || null,
    assignment_type: 'shift',
    allow_partial: allowPartial,
    dry_run: dryRun,
  });

  const checkMutation = useMutation({
    mutationFn: () => assignSetup(body(true)),
    onSuccess: setResult,
    onError: (err) => showError(getErrorMessage(err)),
  });

  const commitMutation = useMutation({
    mutationFn: () => assignSetup(body(false)),
    onSuccess: (data) => {
      setResult(data);
      void queryClient.invalidateQueries({ queryKey: itAllocationKeys.all });
      void queryClient.invalidateQueries({ queryKey: itInventoryKeys.all });
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.all });
      if (data.committed) {
        showSuccess(data.partial ? 'Setup partially assigned — see the per-line results.' : 'Setup assigned.');
        if (!data.partial) close();
      } else {
        showError('Nothing was saved: at least one line is not available. Review the results.');
      }
    },
    onError: (err) => showError(getErrorMessage(err)),
  });

  const ready = Boolean(userId && lines.length && windowReady(slot));
  const lineResult = (line: Line) =>
    result?.lines.find((r) => r.resource_type === line.resource_type && r.resource_id === line.resource_id);

  const addLine = () => {
    const option = pickOptions.find((o) => o.value === pick);
    if (!option) return;
    setLines((current) => [...current, { resource_type: lineType, resource_id: option.value, label: option.label }]);
    setPick('');
    setResult(null);
  };

  return (
    <FormDrawer
      open={open}
      onClose={close}
      title="Assign setup"
      subtitle="Computer, peripherals and licenses for one employee and shift — saved in one transaction"
      icon={EventSeatRoundedIcon}
      formId="it-setup-assign-form"
      onSubmit={() => {
        if (!ready) {
          showError('Choose an employee, a shift or time window, and at least one resource.');
          return;
        }
        commitMutation.mutate();
      }}
      submitLabel={allowPartial ? 'Assign available lines' : 'Assign all'}
      loading={commitMutation.isPending}
      submitDisabled={!ready || !result || result.committed || (!result.all_available && !allowPartial)}
      width={620}
    >
      <Stack spacing={2}>
        <FormSelect
          label="Employee"
          required
          searchable
          value={userId}
          onChange={(e) => {
            setUserId(String(e.target.value));
            setResult(null);
          }}
          options={userOptions}
        />
        <AllocationWindowFields
          value={slot}
          onChange={(next) => {
            setSlot(next);
            setResult(null);
          }}
          shifts={shiftsQuery.data ?? []}
        />
        <FormField label="Purpose" value={purpose} onChange={(e) => setPurpose(e.target.value)} />

        <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
            Resources
          </Typography>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start', mb: 1 }}>
            <FormSelect
              label="Type"
              value={lineType}
              onChange={(e) => {
                setLineType(e.target.value as AllocationResourceType);
                setPick('');
              }}
              options={[
                { value: 'asset', label: 'Asset' },
                { value: 'license', label: 'License' },
              ]}
              sx={{ minWidth: 120 }}
            />
            {lineType === 'asset' ? (
              <FormField
                label="Search assets"
                value={assetSearch}
                onChange={(e) => setAssetSearch(e.target.value)}
                sx={{ minWidth: 150 }}
              />
            ) : null}
          </Stack>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
            <FormSelect
              label={lineType === 'asset' ? 'Asset' : 'License pool'}
              searchable
              value={pick}
              onChange={(e) => setPick(String(e.target.value))}
              options={pickOptions}
              sx={{ flex: 1 }}
            />
            <ProsohmButton buttonVariant="outlined" onClick={addLine} disabled={!pick || lines.length >= 20}>
              Add
            </ProsohmButton>
          </Stack>
          <Stack spacing={1} sx={{ mt: 1.5 }}>
            {lines.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                Add the computer, monitors, 3D mouse and any licenses this employee needs.
              </Typography>
            ) : (
              lines.map((line) => {
                const r = lineResult(line);
                return (
                  <Box
                    key={`${line.resource_type}:${line.resource_id}`}
                    sx={{ border: 1, borderColor: 'divider', borderRadius: 1, px: 1.25, py: 0.75 }}
                  >
                    <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                      <Chip size="small" variant="outlined" label={line.resource_type === 'asset' ? 'Asset' : 'License'} />
                      <Typography variant="body2" sx={{ flex: 1 }}>
                        {line.label}
                      </Typography>
                      {r ? (
                        <Chip size="small" color={RESULT_COLORS[r.result] ?? 'default'} label={r.result.replace(/_/g, ' ')} />
                      ) : null}
                      <IconButton
                        size="small"
                        aria-label="Remove line"
                        onClick={() => {
                          setLines((current) => current.filter((l) => l !== line));
                          setResult(null);
                        }}
                      >
                        <DeleteOutlineRoundedIcon fontSize="small" />
                      </IconButton>
                    </Stack>
                    {r && !r.ok ? (
                      <Typography variant="caption" color="error.main">
                        {r.reason}
                      </Typography>
                    ) : null}
                  </Box>
                );
              })
            )}
          </Stack>
        </Box>

        <FormControlLabel
          control={
            <Checkbox
              checked={allowPartial}
              onChange={(e) => {
                setAllowPartial(e.target.checked);
                setResult(null);
              }}
            />
          }
          label="Allow partial fulfilment (assign the lines that are available, skip the rest)"
        />

        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <ProsohmButton
            buttonVariant="secondary"
            onClick={() => checkMutation.mutate()}
            disabled={!ready || checkMutation.isPending}
          >
            {checkMutation.isPending ? 'Checking…' : 'Check availability'}
          </ProsohmButton>
          {result ? (
            <Typography variant="body2" color={result.all_available || result.committed ? 'success.main' : 'error.main'}>
              {result.committed
                ? result.partial
                  ? 'Partially assigned.'
                  : 'Assigned.'
                : result.all_available
                  ? `All lines available for ${result.window}.`
                  : result.rolled_back
                    ? 'Not saved — every line was rolled back.'
                    : `Some lines are not available for ${result.window}.`}
            </Typography>
          ) : (
            <Typography variant="body2" color="text.secondary">
              Run the check before assigning; the server validates again on save.
            </Typography>
          )}
        </Stack>
      </Stack>
    </FormDrawer>
  );
}
