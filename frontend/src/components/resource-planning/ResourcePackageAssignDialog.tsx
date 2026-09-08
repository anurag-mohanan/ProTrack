import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Stack,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  assignResourcePackage,
  fetchPlanningPackages,
  previewResourcePackage,
  resourcePlanningQueryKeys,
} from '../../api/resourcePlanning';
import { fetchShifts } from '../../api/resourceShifts';
import { getErrorMessage } from '../../api/client';
import { itOperationsKeys } from '../../api/itOperations';
import { ProsohmButton } from '../ui/ProsohmButton';
import { LoadingState } from '../common/LoadingState';
import { useToast } from '../../context/ToastContext';
import {
  accessContextFromUser,
  canAllocateItIps,
  canAssignResourceShifts,
  canManageItSoftware,
} from '../../utils/permissions';
import { useAuth } from '../../context/AuthContext';

const WIZARD_STEPS = [
  'Shift',
  'Package',
  'Requirements',
  'Inventory availability',
  'License availability',
  'Pick hardware',
  'Pick licenses',
  'IP',
  'Review',
  'Confirm',
] as const;

type Props = {
  open: boolean;
  userId: string;
  userName?: string;
  onClose: () => void;
};

export function ResourcePackageAssignDialog({ open, userId, userName, onClose }: Props) {
  const { user } = useAuth();
  const access = accessContextFromUser(user);
  const canShift = canAssignResourceShifts(access);
  const canIp = canAllocateItIps(access);
  const canSoftware = canManageItSoftware(access);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const [activeStep, setActiveStep] = useState(0);
  const [packageId, setPackageId] = useState('');
  const [shiftId, setShiftId] = useState('');
  const [selectedAssets, setSelectedAssets] = useState<Record<string, string[]>>({});
  const [selectedPools, setSelectedPools] = useState<Record<string, string>>({});
  const [ipId, setIpId] = useState('');

  const packagesQuery = useQuery({
    queryKey: resourcePlanningQueryKeys.packages(),
    queryFn: fetchPlanningPackages,
    enabled: open,
  });
  const shiftsQuery = useQuery({
    queryKey: ['resource-shifts', 'active'],
    queryFn: () => fetchShifts({ active_only: true }),
    enabled: open && canShift,
  });
  const previewQuery = useQuery({
    queryKey: resourcePlanningQueryKeys.packagePreview(packageId, userId),
    queryFn: () => previewResourcePackage(packageId, userId),
    enabled: open && Boolean(packageId) && Boolean(userId),
  });

  useEffect(() => {
    if (!open) {
      setActiveStep(0);
      setPackageId('');
      setShiftId('');
      setSelectedAssets({});
      setSelectedPools({});
      setIpId('');
    }
  }, [open]);

  useEffect(() => {
    const preview = previewQuery.data;
    if (!preview) return;
    const assets: Record<string, string[]> = {};
    preview.hardware.forEach((line) => {
      assets[line.asset_type_id] = line.candidates.slice(0, line.quantity).map((row) => row.id);
    });
    const pools: Record<string, string> = {};
    preview.software.forEach((line) => {
      const pool = line.pools.find((item) => item.available_seats > 0);
      if (pool) pools[line.software_id] = pool.id;
    });
    setSelectedAssets(assets);
    setSelectedPools(pools);
    setIpId(preview.ip.candidates[0]?.id ?? '');
  }, [previewQuery.data]);

  const assignMutation = useMutation({
    mutationFn: () =>
      assignResourcePackage(packageId, {
        user_id: userId,
        asset_ids: Object.values(selectedAssets).flat(),
        license_pool_ids: canSoftware ? Object.values(selectedPools).filter(Boolean) : [],
        shift_id: canShift && shiftId ? shiftId : null,
        ip_address_id: canIp && ipId ? ipId : null,
      }),
    onSuccess: () => {
      showSuccess('Resources assigned');
      void queryClient.invalidateQueries({ queryKey: ['resource-planning'] });
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.all });
      onClose();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const preview = previewQuery.data;
  const packages = packagesQuery.data ?? [];
  const selectedPackage = packages.find((row) => row.id === packageId);
  const lastStep = WIZARD_STEPS.length - 1;
  const selectedShift = (shiftsQuery.data ?? []).find((row) => row.id === shiftId);

  const canAdvance = useMemo(() => {
    if (activeStep === 1) return Boolean(packageId);
    if (activeStep >= 2 && activeStep <= 7) return Boolean(preview) && !previewQuery.isFetching;
    return true;
  }, [activeStep, packageId, preview, previewQuery.isFetching]);

  const hardwareSummary = (preview?.hardware ?? []).map((line) => {
    const picked = selectedAssets[line.asset_type_id] ?? [];
    return `${line.asset_type_name}: ${picked.length}/${line.quantity} selected (${line.available_count} available)`;
  });
  const licenseSummary = (preview?.software ?? []).map((line) => {
    const poolId = selectedPools[line.software_id];
    const pool = line.pools.find((item) => item.id === poolId);
    return `${line.software_name}: ${pool ? `${pool.license_type || 'Pool'} (${pool.available_seats} free)` : 'No license'}`;
  });

  const stepBody = () => {
    switch (activeStep) {
      case 0:
        return canShift ? (
          <TextField
            select
            label="Shift"
            value={shiftId}
            onChange={(e) => setShiftId(e.target.value)}
            fullWidth
          >
            <MenuItem value="">Keep current / unassigned</MenuItem>
            {(shiftsQuery.data ?? []).map((shift) => (
              <MenuItem key={shift.id} value={shift.id}>
                {shift.name}
              </MenuItem>
            ))}
          </TextField>
        ) : (
          <Alert severity="info">You do not have permission to change this person’s shift.</Alert>
        );
      case 1:
        return (
          <TextField
            select
            label="Resource package"
            value={packageId}
            onChange={(e) => setPackageId(e.target.value)}
            fullWidth
          >
            <MenuItem value="">Select package</MenuItem>
            {packages.map((row) => (
              <MenuItem key={row.id} value={row.id}>
                {row.name} ({row.code})
              </MenuItem>
            ))}
          </TextField>
        );
      case 2:
        return preview ? (
          <Stack spacing={1}>
            <Typography variant="body2">
              {preview.package_name} for {preview.user_name || userName || 'this person'}
            </Typography>
            {preview.hardware.map((line) => (
              <Typography key={line.asset_type_id} variant="body2">
                Hardware: {line.quantity}× {line.asset_type_name}
                {line.is_required ? ' (required)' : ''}
              </Typography>
            ))}
            {preview.software.map((line) => (
              <Typography key={line.software_id} variant="body2">
                Software: {line.software_name} · {line.requirement_level} · {line.seats} seat
                {line.seats === 1 ? '' : 's'}
              </Typography>
            ))}
            {preview.requires_ip ? (
              <Typography variant="body2">IP address required</Typography>
            ) : (
              <Typography variant="body2" color="text.secondary">
                IP not required by this package
              </Typography>
            )}
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary">
            Select a package first.
          </Typography>
        );
      case 3:
        return preview ? (
          <Stack spacing={1}>
            {preview.hardware.map((line) => (
              <Alert
                key={line.asset_type_id}
                severity={line.available_count >= line.quantity ? 'success' : 'warning'}
              >
                {line.asset_type_name}: {line.available_count} available, need {line.quantity}
              </Alert>
            ))}
            {!preview.hardware.length ? (
              <Typography variant="body2" color="text.secondary">
                No hardware lines on this package.
              </Typography>
            ) : null}
          </Stack>
        ) : (
          <LoadingState message="Checking inventory…" />
        );
      case 4:
        return preview ? (
          <Stack spacing={1}>
            {preview.software.map((line) => (
              <Alert
                key={line.software_id}
                severity={line.available_seats >= line.seats ? 'success' : 'warning'}
              >
                {line.software_name}: {line.available_seats} seats free, need {line.seats}
              </Alert>
            ))}
            {!preview.software.length ? (
              <Typography variant="body2" color="text.secondary">
                No software lines on this package.
              </Typography>
            ) : null}
          </Stack>
        ) : (
          <LoadingState message="Checking licenses…" />
        );
      case 5:
        return preview ? (
          <Stack spacing={1.5}>
            {preview.hardware.map((line) => (
              <Stack key={line.asset_type_id} spacing={0.5}>
                <Typography variant="subtitle2">
                  {line.asset_type_name} — need {line.quantity}, available {line.available_count}
                </Typography>
                {line.candidates.map((asset) => {
                  const selected = selectedAssets[line.asset_type_id] ?? [];
                  return (
                    <FormControlLabel
                      key={asset.id}
                      control={
                        <Checkbox
                          checked={selected.includes(asset.id)}
                          onChange={(e) => {
                            setSelectedAssets((prev) => {
                              const current = new Set(prev[line.asset_type_id] ?? []);
                              if (e.target.checked) current.add(asset.id);
                              else current.delete(asset.id);
                              return { ...prev, [line.asset_type_id]: [...current] };
                            });
                          }}
                        />
                      }
                      label={`${asset.asset_number}${asset.make ? ` · ${asset.make}` : ''}${asset.model ? ` ${asset.model}` : ''}`}
                    />
                  );
                })}
              </Stack>
            ))}
            {!preview.hardware.length ? (
              <Typography variant="body2" color="text.secondary">
                Nothing to pick.
              </Typography>
            ) : null}
          </Stack>
        ) : (
          <LoadingState message="Loading hardware…" />
        );
      case 6:
        if (!canSoftware) {
          return <Alert severity="info">You do not have permission to assign licenses.</Alert>;
        }
        return preview ? (
          <Stack spacing={1.5}>
            {preview.software.map((line) => (
              <TextField
                key={line.software_id}
                select
                label={`${line.software_name} (${line.available_seats} seats free)`}
                value={selectedPools[line.software_id] ?? ''}
                onChange={(e) =>
                  setSelectedPools((prev) => ({ ...prev, [line.software_id]: e.target.value }))
                }
                fullWidth
              >
                <MenuItem value="">No license</MenuItem>
                {line.pools.map((pool) => (
                  <MenuItem key={pool.id} value={pool.id} disabled={pool.available_seats < 1}>
                    {pool.license_type || 'Pool'} · {pool.available_seats} available
                  </MenuItem>
                ))}
              </TextField>
            ))}
            {!preview.software.length ? (
              <Typography variant="body2" color="text.secondary">
                Nothing to pick.
              </Typography>
            ) : null}
          </Stack>
        ) : (
          <LoadingState message="Loading licenses…" />
        );
      case 7:
        if (!preview?.requires_ip) {
          return (
            <Alert severity="info">This package does not require an IP address.</Alert>
          );
        }
        if (!canIp) {
          return <Alert severity="info">You do not have permission to allocate IPs.</Alert>;
        }
        return (
          <TextField
            select
            label={`IP address (${preview.ip.available_count} available)`}
            value={ipId}
            onChange={(e) => setIpId(e.target.value)}
            fullWidth
          >
            <MenuItem value="">None</MenuItem>
            {preview.ip.candidates.map((ip) => (
              <MenuItem key={ip.id} value={ip.id}>
                {ip.address}
              </MenuItem>
            ))}
          </TextField>
        );
      case 8:
      case 9:
        return (
          <Stack spacing={1}>
            <Typography variant="body2">
              Person: <strong>{userName || preview?.user_name || userId}</strong>
            </Typography>
            <Typography variant="body2">
              Package:{' '}
              <strong>
                {selectedPackage
                  ? `${selectedPackage.name} (${selectedPackage.code})`
                  : 'Not selected'}
              </strong>
            </Typography>
            <Typography variant="body2">
              Shift: <strong>{selectedShift?.name || 'Keep current / unassigned'}</strong>
            </Typography>
            {hardwareSummary.map((row) => (
              <Typography key={row} variant="body2">
                {row}
              </Typography>
            ))}
            {licenseSummary.map((row) => (
              <Typography key={row} variant="body2">
                {row}
              </Typography>
            ))}
            <Typography variant="body2">
              IP:{' '}
              <strong>
                {preview?.requires_ip
                  ? preview.ip.candidates.find((row) => row.id === ipId)?.address || 'None'
                  : 'Not required'}
              </strong>
            </Typography>
            {activeStep === 9 ? (
              <Alert severity="info">
                Confirm writes shift, hardware, licenses, and IP in one transaction.
              </Alert>
            ) : null}
          </Stack>
        );
      default:
        return null;
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="lg">
      <DialogTitle>Assign resources{userName ? ` — ${userName}` : ''}</DialogTitle>
      <DialogContent>
        <Stepper activeStep={activeStep} alternativeLabel sx={{ mt: 1, mb: 2 }}>
          {WIZARD_STEPS.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>
        <Stack spacing={2}>
          {previewQuery.isFetching && activeStep >= 2 ? (
            <LoadingState message="Checking availability…" />
          ) : null}
          {preview?.shortages?.length ? (
            <Alert severity="warning">
              {preview.shortages.map((item) => (
                <div key={item}>{item}</div>
              ))}
            </Alert>
          ) : null}
          <Box>{stepBody()}</Box>
        </Stack>
      </DialogContent>
      <DialogActions>
        <ProsohmButton buttonVariant="secondary" onClick={onClose}>
          Cancel
        </ProsohmButton>
        <ProsohmButton
          buttonVariant="outlined"
          onClick={() => setActiveStep((step) => Math.max(0, step - 1))}
          disabled={activeStep === 0}
        >
          Back
        </ProsohmButton>
        {activeStep < lastStep ? (
          <ProsohmButton onClick={() => setActiveStep((step) => step + 1)} disabled={!canAdvance}>
            Next
          </ProsohmButton>
        ) : (
          <ProsohmButton
            onClick={() => assignMutation.mutate()}
            disabled={!packageId || assignMutation.isPending}
          >
            Confirm assignment
          </ProsohmButton>
        )}
      </DialogActions>
    </Dialog>
  );
}
