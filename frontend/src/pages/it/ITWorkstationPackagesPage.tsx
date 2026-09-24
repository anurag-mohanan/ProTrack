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
import { useQuery } from '@tanstack/react-query';
import {
  fetchWorkstationPackages,
  workstationPackageKeys,
} from '../../api/workstationPackages';
import { fetchShifts } from '../../api/resourceShifts';
import { fetchComputerTypes, itProvisioningKeys } from '../../api/itProvisioning';
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
  const today = new Date().toISOString().slice(0, 10);
  const [findOpen, setFindOpen] = useState(false);
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
  });

  const packages = (packagesQuery.data || []) as PackageRow[];
  const shifts = shiftsQuery.data || [];

  return (
    <PageContainer>
      <PageHeader
        title="Workstation Packages"
        subtitle="Shift-aware physical equipment packages — computer + monitors + peripherals."
        action={
          <ProsohmButton
            startIcon={<SearchRoundedIcon />}
            onClick={() => setFindOpen(true)}
          >
            Find Available Computer
          </ProsohmButton>
        }
      />
      <ITSectionSubnav items={IT_INVENTORY_TABS} />

      <ContentCard title="Filters" subtitle="Combine computer type with shift availability.">
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
        <LoadingState message="Loading workstation packages…" />
      ) : packagesQuery.error ? (
        <ErrorState error={packagesQuery.error} onRetry={() => void packagesQuery.refetch()} />
      ) : (
        <ContentCard
          title={`${packages.length} package${packages.length === 1 ? '' : 's'}`}
          subtitle="Availability is calculated per shift from assignments and asset status."
        >
          {packages.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No packages match these filters.
            </Typography>
          ) : (
            <Box sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Package</TableCell>
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

      <FindAvailableComputerDialog open={findOpen} onClose={() => setFindOpen(false)} />
    </PageContainer>
  );
}
