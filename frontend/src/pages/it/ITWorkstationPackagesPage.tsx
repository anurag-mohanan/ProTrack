import { useMemo, useState } from 'react';
import {
  Box,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import SyncRoundedIcon from '@mui/icons-material/SyncRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchVirtualSeatsGroupedByUser,
  fetchWorkstationPackages,
  reconcileVirtualSeats,
  workstationPackageKeys,
} from '../../api/workstationPackages';
import { fetchShifts } from '../../api/resourceShifts';
import { fetchComputerTypes, itProvisioningKeys } from '../../api/itProvisioning';
import { getErrorMessage } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ITSectionSubnav, IT_INVENTORY_TABS } from '../../components/it/ITSectionSubnav';
import { FindAvailableComputerDialog } from '../../components/it/FindAvailableComputerDialog';
import { ContentCard } from '../../components/ui/cards';
import { FormSelect } from '../../components/ui/design-system';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { formatCellValue } from '../../utils/format';

type PackageRow = {
  id: string;
  code: string;
  name: string;
  status: string;
  computer_type?: string | null;
  computer_type_label?: string | null;
  primary_computer_number?: string | null;
  monitor_count?: number;
  has_3d_mouse?: boolean;
  shift_availability?: {
    shift_code: string;
    shift_name: string;
    status: string;
    reason?: string | null;
    assignees?: { user_name?: string | null }[];
  }[];
};

const AVAIL_FILTERS = [
  { value: '', label: 'All' },
  { value: 'AVAILABLE', label: 'Available (selected shift)' },
  { value: 'ASSIGNED', label: 'Fully Assigned' },
  { value: 'PARTIALLY_AVAILABLE', label: 'Partially Available' },
  { value: 'CONFLICT', label: 'Conflict' },
  { value: 'UNAVAILABLE', label: 'Unavailable' },
] as const;

function statusChipColor(
  status: string,
): 'default' | 'success' | 'warning' | 'error' | 'info' {
  switch (status) {
    case 'AVAILABLE':
      return 'success';
    case 'ASSIGNED':
      return 'info';
    case 'PARTIAL':
    case 'PARTIALLY_AVAILABLE':
      return 'warning';
    case 'CONFLICT':
    case 'UNAVAILABLE':
      return 'error';
    default:
      return 'default';
  }
}

export function ITWorkstationPackagesPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const today = new Date().toISOString().slice(0, 10);
  const [findOpen, setFindOpen] = useState(false);
  const [viewMode, setViewMode] = useState<'seat' | 'user'>('seat');
  const [computerType, setComputerType] = useState('');
  const [shiftId, setShiftId] = useState('');
  const [availability, setAvailability] = useState('');
  const [minMonitors, setMinMonitors] = useState('');
  const [mouse3d, setMouse3d] = useState<'all' | 'yes' | 'no'>('all');

  const shiftsQuery = useQuery({
    queryKey: ['resource-shifts', 'list', { active_only: true }],
    queryFn: () => fetchShifts({ active_only: true }),
  });
  const typesQuery = useQuery({
    queryKey: itProvisioningKeys.computerTypes(),
    queryFn: fetchComputerTypes,
  });

  const filters = useMemo(
    () => ({
      computer_type: computerType || undefined,
      shift_id: shiftId || undefined,
      on_date: today,
      availability: availability || undefined,
      min_monitors: minMonitors ? Number(minMonitors) : undefined,
      mouse_3d: mouse3d === 'all' ? undefined : mouse3d === 'yes',
    }),
    [computerType, shiftId, today, availability, minMonitors, mouse3d],
  );

  const packagesQuery = useQuery({
    queryKey: workstationPackageKeys.list(filters),
    queryFn: () => fetchWorkstationPackages(filters),
    enabled: viewMode === 'seat',
  });

  const groupedQuery = useQuery({
    queryKey: workstationPackageKeys.groupedByUser(today),
    queryFn: () => fetchVirtualSeatsGroupedByUser(today),
    enabled: viewMode === 'user',
  });

  const reconcileMutation = useMutation({
    mutationFn: reconcileVirtualSeats,
    onSuccess: (data) => {
      showSuccess(
        `Reconciled ${data.seats_created} virtual seat(s)` +
          (data.flagged_for_review.length
            ? `; ${data.flagged_for_review.length} flagged for review`
            : ''),
      );
      void queryClient.invalidateQueries({ queryKey: workstationPackageKeys.all });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const packages = (packagesQuery.data || []) as PackageRow[];
  const shifts = shiftsQuery.data || [];
  const grouped = groupedQuery.data || [];

  return (
    <PageContainer>
      <PageHeader
        title="Virtual Seats"
        subtitle="Logical workstation setups (computer + peripherals) assigned per employee and shift."
        action={
          <Stack direction="row" spacing={1}>
            <ProsohmButton
              buttonVariant="outlined"
              startIcon={<SyncRoundedIcon />}
              onClick={() => reconcileMutation.mutate()}
              disabled={reconcileMutation.isPending}
            >
              Reconcile from assignments
            </ProsohmButton>
            <ProsohmButton
              startIcon={<SearchRoundedIcon />}
              onClick={() => setFindOpen(true)}
            >
              Find Available Computer
            </ProsohmButton>
          </Stack>
        }
      />
      <ITSectionSubnav items={IT_INVENTORY_TABS} />

      <ToggleButtonGroup
        exclusive
        size="small"
        value={viewMode}
        onChange={(_, v) => v && setViewMode(v)}
        sx={{ mb: 1 }}
      >
        <ToggleButton value="seat">Group by Virtual Seat</ToggleButton>
        <ToggleButton value="user">Group by User</ToggleButton>
      </ToggleButtonGroup>

      {viewMode === 'seat' ? (
        <>
          <ContentCard
            title="Filters"
            subtitle="Availability is calculated from seat assignments and shift time windows — not from a static Available flag."
          >
            <Stack spacing={1.5}>
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
                <FormSelect
                  label="Computer Type"
                  value={computerType}
                  onChange={(e) => setComputerType(String(e.target.value))}
                  options={[
                    { value: '', label: 'All types' },
                    ...(typesQuery.data || []).map((t) => ({
                      value: t.code,
                      label: t.label,
                    })),
                  ]}
                />
                <FormSelect
                  label="Shift"
                  value={shiftId}
                  onChange={(e) => setShiftId(String(e.target.value))}
                  options={[
                    { value: '', label: 'Any / all shifts' },
                    ...shifts.map((s) => ({
                      value: s.id,
                      label: `${s.name} (${s.start_time}–${s.end_time})`,
                    })),
                  ]}
                />
                <FormSelect
                  label="Availability"
                  value={availability}
                  onChange={(e) => setAvailability(String(e.target.value))}
                  options={AVAIL_FILTERS.map((f) => ({ value: f.value, label: f.label }))}
                />
                <FormSelect
                  label="Min monitors"
                  value={minMonitors}
                  onChange={(e) => setMinMonitors(String(e.target.value))}
                  options={[
                    { value: '', label: 'Any' },
                    { value: '0', label: '0' },
                    { value: '1', label: '1' },
                    { value: '2', label: '2' },
                    { value: '3', label: '3' },
                    { value: '4', label: '4+' },
                  ]}
                />
              </Stack>
              <ToggleButtonGroup
                exclusive
                size="small"
                value={mouse3d}
                onChange={(_, v) => v && setMouse3d(v)}
              >
                <ToggleButton value="all">3D Mouse: Any</ToggleButton>
                <ToggleButton value="yes">Yes</ToggleButton>
                <ToggleButton value="no">No</ToggleButton>
              </ToggleButtonGroup>
            </Stack>
          </ContentCard>

          {packagesQuery.isLoading ? (
            <LoadingState message="Loading virtual seats…" />
          ) : packagesQuery.error ? (
            <ErrorState
              error={packagesQuery.error}
              onRetry={() => void packagesQuery.refetch()}
            />
          ) : (
            <ContentCard
              title={`${packages.length} virtual seat${packages.length === 1 ? '' : 's'}`}
              subtitle="Same physical assets can appear under multiple shift users when the seat is shared."
            >
              {packages.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No virtual seats match these filters. Use Reconcile or Find Available Computer to
                  create seats from physical assets.
                </Typography>
              ) : (
                <Box sx={{ overflowX: 'auto' }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Virtual Seat</TableCell>
                        <TableCell>Computer</TableCell>
                        <TableCell>Type</TableCell>
                        <TableCell>Monitors</TableCell>
                        <TableCell>3D Mouse</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Shift availability</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {packages.map((pkg) => (
                        <TableRow key={pkg.id}>
                          <TableCell>
                            <Typography sx={{ fontWeight: 600 }}>{pkg.code}</Typography>
                            <Typography variant="caption" color="text.secondary">
                              {pkg.name}
                            </Typography>
                          </TableCell>
                          <TableCell>{formatCellValue(pkg.primary_computer_number)}</TableCell>
                          <TableCell>
                            {formatCellValue(pkg.computer_type_label || pkg.computer_type)}
                          </TableCell>
                          <TableCell>{pkg.monitor_count ?? 0}</TableCell>
                          <TableCell>{pkg.has_3d_mouse ? 'Yes' : 'No'}</TableCell>
                          <TableCell>
                            <Chip size="small" label={pkg.status} variant="outlined" />
                          </TableCell>
                          <TableCell>
                            <Stack spacing={0.5}>
                              {(pkg.shift_availability || []).map((s) => {
                                const who =
                                  s.assignees
                                    ?.map((a) => a.user_name)
                                    .filter(Boolean)
                                    .join(', ') || null;
                                return (
                                  <Stack
                                    key={s.shift_code}
                                    direction="row"
                                    spacing={0.75}
                                    sx={{ alignItems: 'center', flexWrap: 'wrap' }}
                                  >
                                    <Typography variant="caption" sx={{ minWidth: 88 }}>
                                      {s.shift_name || s.shift_code}:
                                    </Typography>
                                    <Chip
                                      size="small"
                                      color={statusChipColor(s.status)}
                                      label={
                                        who && s.status === 'ASSIGNED'
                                          ? `${s.status} — ${who}`
                                          : s.status
                                      }
                                    />
                                  </Stack>
                                );
                              })}
                            </Stack>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Box>
              )}
            </ContentCard>
          )}
        </>
      ) : groupedQuery.isLoading ? (
        <LoadingState message="Loading user groupings…" />
      ) : groupedQuery.error ? (
        <ErrorState error={groupedQuery.error} onRetry={() => void groupedQuery.refetch()} />
      ) : (
        <ContentCard
          title="Group by User"
          subtitle="Repeated physical assets under different users mean a Shared Virtual Seat — not duplicates."
        >
          {grouped.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No active virtual seat assignments.
            </Typography>
          ) : (
            <Stack spacing={2}>
              {grouped.map((g) => (
                <Box
                  key={`${g.user_id}-${g.virtual_seat_id}-${g.shift_id}`}
                  sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5 }}
                >
                  <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
                    <Typography variant="subtitle2">{g.user_name || g.user_id}</Typography>
                    <Chip size="small" label={g.shift_display || 'Shift'} />
                    <Chip size="small" label={g.virtual_seat_code} variant="outlined" />
                    {g.shared ? (
                      <Chip size="small" color="info" label="Shared Virtual Seat" />
                    ) : null}
                  </Stack>
                  {g.shared && g.other_users.length ? (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      Other shift users:{' '}
                      {g.other_users.map((u) => u.user_name || u.user_id).join(', ')}
                    </Typography>
                  ) : null}
                  <Typography variant="body2" sx={{ mt: 0.5 }}>
                    {(g.assets || [])
                      .map((a) => `${a.asset_number || a.asset_id} (${a.role})`)
                      .join(' · ') || 'No members'}
                  </Typography>
                </Box>
              ))}
            </Stack>
          )}
        </ContentCard>
      )}

      <FindAvailableComputerDialog open={findOpen} onClose={() => setFindOpen(false)} />
    </PageContainer>
  );
}
