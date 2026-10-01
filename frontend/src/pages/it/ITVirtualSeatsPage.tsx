import { useMemo, useState } from 'react';
import { Box, Chip, FormControlLabel, Stack, Switch, Tooltip, Typography } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import ComputerRoundedIcon from '@mui/icons-material/ComputerRounded';
import EventSeatRoundedIcon from '@mui/icons-material/EventSeatRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import ReportProblemRoundedIcon from '@mui/icons-material/ReportProblemRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchInventoryReference, fetchVirtualSeats, itInventoryKeys } from '../../api/itInventory';
import { useAuth } from '../../context/AuthContext';
import { ClientPaginatedDataGrid } from '../../components/common/ClientPaginatedDataGrid';
import { ErrorState } from '../../components/common/ErrorState';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ITAreaTabs } from '../../components/it/ITAreaTabs';
import { IT_ASSET_AREA_TABS } from '../../components/it/itAreaTabConfig';
import { SEAT_STATUS_META } from '../../components/it/inventory/inventoryFormat';
import { SearchField } from '../../components/it/inventory/SearchField';
import { SetupAssignDrawer } from '../../components/it/allocation/SetupAssignDrawer';
import { SeatRequirementsDialog } from '../../components/it/seats/SeatRequirementsDialog';
import { VirtualSeatDetailDrawer } from '../../components/it/seats/VirtualSeatDetailDrawer';
import { ContentCard } from '../../components/ui/cards';
import { FormField, FormSelect, KpiMetricCard, SearchToolbar } from '../../components/ui/design-system';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import type { VirtualSeatRow } from '../../types/itInventory';
import { formatCellValue } from '../../utils/format';
import { accessContextFromUser, canManageItAssets, canManageItSettings } from '../../utils/permissions';

const MAIN_ROLES = new Set(['monitor', 'mouse_3d']);

function seatKey(seat: VirtualSeatRow): string {
  return seat.seat_id ?? `${seat.user_id}:${seat.primary?.asset_id ?? 'none'}`;
}

export function ITVirtualSeatsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const access = accessContextFromUser(user);
  const canEditRequirements = canManageItSettings(access) || canManageItAssets(access);
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [setupStatus, setSetupStatus] = useState(() => searchParams.get('setup_status') ?? '');
  const [seatType, setSeatType] = useState('');
  const [shiftId, setShiftId] = useState('');
  const [sharedOnly, setSharedOnly] = useState(false);
  const [onDate, setOnDate] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const [requirementsOpen, setRequirementsOpen] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);
  const canAssign = canManageItAssets(access);

  const filters = {
    search: search || undefined,
    setup_status: setupStatus || undefined,
    seat_type: seatType || undefined,
    shift_id: shiftId || undefined,
    shared_only: sharedOnly || undefined,
    on_date: onDate || undefined,
  };
  const seatsQuery = useQuery({ queryKey: itInventoryKeys.seats(filters), queryFn: () => fetchVirtualSeats(filters) });
  const referenceQuery = useQuery({ queryKey: itInventoryKeys.reference(), queryFn: fetchInventoryReference });
  const seats = useMemo(() => seatsQuery.data?.seats ?? [], [seatsQuery.data]);
  const summary = seatsQuery.data?.summary;
  const selectedSeat = seats.find((s) => seatKey(s) === selected) ?? null;

  const columns = useMemo<GridColDef<VirtualSeatRow>[]>(
    () => [
      {
        field: 'user_name',
        headerName: 'Employee',
        flex: 1.1,
        minWidth: 180,
        renderCell: (p) => (
          <Box sx={{ lineHeight: 1.2, py: 0.5 }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {p.row.user_name ?? '—'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {[p.row.employee_code, p.row.seat_code].filter(Boolean).join(' · ')}
            </Typography>
          </Box>
        ),
      },
      {
        field: 'shift_display',
        headerName: 'Shift',
        width: 170,
        valueFormatter: (v) => formatCellValue(v),
      },
      {
        field: 'primary',
        headerName: 'Primary device',
        flex: 1,
        minWidth: 190,
        sortComparator: (a, b) =>
          String((a as VirtualSeatRow['primary'])?.asset_number ?? '').localeCompare(
            String((b as VirtualSeatRow['primary'])?.asset_number ?? ''),
          ),
        renderCell: (p) =>
          p.row.primary ? (
            <Box sx={{ lineHeight: 1.2, py: 0.5 }}>
              <Typography variant="body2">
                {p.row.primary.asset_number}
                {p.row.shared_with.length ? (
                  <Tooltip
                    title={`Shared with ${p.row.shared_with.map((s) => `${s.user_name ?? 'unknown'} (${s.shift_display ?? 'no shift'})`).join(', ')}`}
                  >
                    <GroupsRoundedIcon sx={{ fontSize: 16, ml: 0.5, verticalAlign: 'middle', color: 'info.main' }} />
                  </Tooltip>
                ) : null}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {p.row.seat_type_label}
                {p.row.primary.computer_name ? ` · ${p.row.primary.computer_name}` : ''}
              </Typography>
            </Box>
          ) : (
            <Typography variant="body2" color="error.main">
              No primary device
            </Typography>
          ),
      },
      {
        field: 'monitors',
        headerName: 'Monitors',
        type: 'number',
        width: 90,
        valueGetter: (_v, row) => row.counts.monitor ?? 0,
      },
      {
        field: 'mouse_3d',
        headerName: '3D mouse',
        width: 90,
        valueGetter: (_v, row) => row.counts.mouse_3d ?? 0,
        renderCell: (p) => (p.value ? (p.value > 1 ? `Yes (${p.value})` : 'Yes') : '—'),
      },
      {
        field: 'other',
        headerName: 'Other',
        flex: 1,
        minWidth: 180,
        sortable: false,
        valueGetter: (_v, row) => {
          const parts: string[] = [];
          const labels = new Map(row.components.map((c) => [c.role, c.role_label]));
          for (const c of row.consumables) labels.set(c.kind, c.name);
          for (const [role, count] of Object.entries(row.counts)) {
            if (MAIN_ROLES.has(role) || !count) continue;
            const label = labels.get(role) ?? role;
            parts.push(count > 1 ? `${label} ×${count}` : label);
          }
          return parts.join(', ') || '—';
        },
      },
      {
        field: 'setup_status',
        headerName: 'Status',
        width: 170,
        renderCell: (p) => {
          const meta = SEAT_STATUS_META[p.row.setup_status];
          const tip = p.row.missing_required.length
            ? `Missing: ${p.row.missing_required.join(', ')}`
            : p.row.missing_optional.length
              ? `Below recommended: ${p.row.missing_optional.join(', ')}`
              : '';
          return (
            <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
              <Tooltip title={tip}>
                <Chip size="small" label={meta?.label ?? p.row.setup_status} color={meta?.color ?? 'default'} />
              </Tooltip>
              {p.row.conflicts.length ? (
                <Tooltip title="Overlapping shift assignment on this device">
                  <ReportProblemRoundedIcon color="error" sx={{ fontSize: 18 }} />
                </Tooltip>
              ) : null}
            </Stack>
          );
        },
      },
    ],
    [],
  );

  return (
    <PageContainer>
      <PageHeader
        title="Virtual seats"
        subtitle="Logical workstations derived from each employee's assigned computer and peripherals"
        action={
          <Stack direction="row" spacing={1}>
            {canAssign ? (
              <ProsohmButton buttonVariant="primary" onClick={() => setSetupOpen(true)}>
                Assign setup
              </ProsohmButton>
            ) : null}
            <ProsohmButton buttonVariant="outlined" onClick={() => navigate('/it/inventory?view=availability')}>
              Find available computer
            </ProsohmButton>
            <ProsohmButton buttonVariant="outlined" onClick={() => setRequirementsOpen(true)}>
              Setup requirements
            </ProsohmButton>
          </Stack>
        }
      />
      <ITAreaTabs items={IT_ASSET_AREA_TABS} />
      {summary ? (
        <Box
          sx={{
            display: 'grid',
            gap: 1.5,
            mb: 2,
            gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(6, 1fr)' },
          }}
        >
          <KpiMetricCard dense title="Seats" value={String(summary.total_seats)} icon={EventSeatRoundedIcon} onClick={() => setSetupStatus('')} selected={!setupStatus} />
          <KpiMetricCard dense title="Complete" value={String(summary.complete)} icon={CheckCircleRoundedIcon} accent="success" onClick={() => setSetupStatus('complete')} selected={setupStatus === 'complete'} />
          <KpiMetricCard dense title="Incomplete" value={String(summary.incomplete)} icon={WarningAmberRoundedIcon} accent="warning" onClick={() => setSetupStatus('incomplete')} selected={setupStatus === 'incomplete'} />
          <KpiMetricCard dense title="No primary device" value={String(summary.no_primary_device)} icon={ComputerRoundedIcon} accent="error" onClick={() => setSetupStatus('no_primary_device')} selected={setupStatus === 'no_primary_device'} />
          <KpiMetricCard dense title="Shared devices" value={String(summary.shared_devices)} icon={GroupsRoundedIcon} accent="info" onClick={() => setSharedOnly((v) => !v)} selected={sharedOnly} />
          <KpiMetricCard dense title="Conflicts" value={String(summary.conflicts)} icon={ReportProblemRoundedIcon} accent={summary.conflicts ? 'error' : undefined} />
        </Box>
      ) : null}
      <SearchToolbar sticky>
        <SearchField value={search} onChange={setSearch} placeholder="Search employee, seat, device…" />
        <FormSelect
          label="Status"
          value={setupStatus}
          onChange={(e) => setSetupStatus(String(e.target.value))}
          options={[
            { value: '', label: 'All' },
            ...Object.entries(SEAT_STATUS_META).map(([value, meta]) => ({ value, label: meta.label })),
          ]}
          sx={{ minWidth: 170 }}
        />
        <FormSelect
          label="Computer type"
          value={seatType}
          onChange={(e) => setSeatType(String(e.target.value))}
          options={[
            { value: '', label: 'All types' },
            ...(referenceQuery.data?.seat_types ?? []).map((t) => ({ value: t.code, label: t.label })),
          ]}
          sx={{ minWidth: 190 }}
        />
        <FormSelect
          label="Shift"
          value={shiftId}
          onChange={(e) => setShiftId(String(e.target.value))}
          options={[
            { value: '', label: 'All shifts' },
            ...(referenceQuery.data?.shifts ?? []).map((s) => ({ value: s.id, label: s.label })),
          ]}
          sx={{ minWidth: 190 }}
        />
        <FormField
          label="On date"
          type="date"
          size="small"
          value={onDate}
          onChange={(e) => setOnDate(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <FormControlLabel
          control={<Switch checked={sharedOnly} onChange={(e) => setSharedOnly(e.target.checked)} />}
          label="Shared only"
        />
      </SearchToolbar>
      {seatsQuery.isError ? (
        <ErrorState error={seatsQuery.error} title="Unable to load virtual seats" onRetry={() => void seatsQuery.refetch()} />
      ) : (
        <ContentCard noPadding>
          <ClientPaginatedDataGrid
            rows={seats}
            columns={columns}
            getRowId={seatKey}
            loading={seatsQuery.isLoading}
            autoHeight
            getRowHeight={() => 'auto'}
            onRowClick={(p) => setSelected(String(p.id))}
            filterKey={JSON.stringify(filters)}
            localeText={{
              noRowsLabel: 'No virtual seats. Seats appear automatically when a computer is assigned to an employee.',
            }}
          />
        </ContentCard>
      )}
      <VirtualSeatDetailDrawer seat={selectedSeat} onClose={() => setSelected(null)} />
      <SeatRequirementsDialog
        open={requirementsOpen}
        onClose={() => setRequirementsOpen(false)}
        canEdit={canEditRequirements}
      />
      {canAssign ? <SetupAssignDrawer open={setupOpen} onClose={() => setSetupOpen(false)} /> : null}
    </PageContainer>
  );
}
