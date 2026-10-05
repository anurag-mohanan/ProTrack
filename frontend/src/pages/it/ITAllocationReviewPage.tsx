import { useMemo, useState } from 'react';
import { Box, Chip, Stack, Typography } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import BookmarkAddRoundedIcon from '@mui/icons-material/BookmarkAddRounded';
import FactCheckRoundedIcon from '@mui/icons-material/FactCheckRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  createReservation,
  fetchLegacyReview,
  fetchReservations,
  itAllocationKeys,
  releaseReservation,
  resolveLegacyAssignment,
} from '../../api/itAllocation';
import { getErrorMessage } from '../../api/client';
import { fetchAssets, fetchSoftwareLicenses, itOperationsKeys } from '../../api/itOperations';
import { itInventoryKeys } from '../../api/itInventory';
import { useAssignableEmployees } from '../../components/common/employeeDirectory';
import { fetchShifts } from '../../api/resourceShifts';
import { ClientPaginatedDataGrid } from '../../components/common/ClientPaginatedDataGrid';
import { ErrorState } from '../../components/common/ErrorState';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { AllocationCheckPanel } from '../../components/it/allocation/AllocationCheckPanel';
import { AllocationWindowFields } from '../../components/it/allocation/AllocationWindowFields';
import {
  NO_OVERRIDE,
  checkAllowsSave,
  emptyWindow,
  overridePayload,
  windowReady,
  windowToInput,
  type AllocationWindowState,
  type OverrideState,
} from '../../components/it/allocation/allocationWindow';
import { ITAreaTabs } from '../../components/it/ITAreaTabs';
import { IT_ASSET_AREA_TABS } from '../../components/it/itAreaTabConfig';
import { ContentCard } from '../../components/ui/cards';
import { FormDrawer, FormField, FormSelect, SearchToolbar } from '../../components/ui/design-system';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import type {
  AllocationCheckRequest,
  AllocationCheckResult,
  AllocationResourceType,
  LegacyAssignment,
  LegacyLicensePool,
  ResourceReservation,
} from '../../types/itAllocation';
import { formatDate } from '../../utils/format';
import { accessContextFromUser, canManageItAssets, canManageItSoftware } from '../../utils/permissions';

type View = 'reservations' | 'legacy';

const RESERVATION_STATUS_COLORS: Record<string, 'success' | 'default' | 'info'> = {
  ACTIVE: 'info',
  FULFILLED: 'success',
  RELEASED: 'default',
};

export function ITAllocationReviewPage() {
  const [searchParams] = useSearchParams();
  const view: View = searchParams.get('view') === 'legacy' ? 'legacy' : 'reservations';
  return (
    <PageContainer>
      <PageHeader
        title={view === 'legacy' ? 'Assignments needing review' : 'Reservations'}
        subtitle={
          view === 'legacy'
            ? 'Migrated assignments with no shift or time window block the resource for all hours until a window is set.'
            : 'Hold a computer, peripheral or license right for an employee and shift before it is assigned.'
        }
      />
      <ITAreaTabs items={IT_ASSET_AREA_TABS} />
      {view === 'legacy' ? <LegacyReviewView /> : <ReservationsView />}
    </PageContainer>
  );
}

function ReservationsView() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const access = accessContextFromUser(user);
  const canAssets = canManageItAssets(access);
  const canSoftware = canManageItSoftware(access);
  const { showSuccess, showError } = useToast();
  const [status, setStatus] = useState('ACTIVE');
  const [createOpen, setCreateOpen] = useState(false);

  const query = useQuery({
    queryKey: itAllocationKeys.reservations({ status }),
    queryFn: () => fetchReservations({ status }),
  });

  const releaseMutation = useMutation({
    mutationFn: (row: ResourceReservation) => releaseReservation(row.id),
    onSuccess: () => {
      showSuccess('Reservation released.');
      void queryClient.invalidateQueries({ queryKey: itAllocationKeys.all });
      void queryClient.invalidateQueries({ queryKey: itInventoryKeys.all });
    },
    onError: (err) => showError(getErrorMessage(err)),
  });

  const columns = useMemo<GridColDef<ResourceReservation>[]>(
    () => [
      {
        field: 'resource_label',
        headerName: 'Resource',
        flex: 1.2,
        minWidth: 200,
        renderCell: (p) => (
          <Box sx={{ lineHeight: 1.2, py: 0.5 }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {p.row.resource_label ?? '—'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {p.row.resource_type === 'asset' ? 'Asset' : 'License'}
            </Typography>
          </Box>
        ),
      },
      {
        field: 'user_name',
        headerName: 'For',
        flex: 1,
        minWidth: 160,
        valueGetter: (_v, row) => row.user_name || row.reserved_for || '—',
      },
      { field: 'window_label', headerName: 'Window', width: 170 },
      {
        field: 'start_date',
        headerName: 'Dates',
        width: 190,
        valueGetter: (_v, row) =>
          `${formatDate(row.start_date)} → ${row.end_date ? formatDate(row.end_date) : 'open'}`,
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 120,
        renderCell: (p) => (
          <Chip size="small" color={RESERVATION_STATUS_COLORS[p.row.status] ?? 'default'} label={p.row.status} />
        ),
      },
      { field: 'reason', headerName: 'Reason', flex: 1, minWidth: 160, valueGetter: (v) => v || '—' },
      { field: 'created_by_name', headerName: 'Created by', width: 150, valueGetter: (v) => v || '—' },
      {
        field: 'actions',
        headerName: '',
        width: 110,
        sortable: false,
        renderCell: (p) => {
          const allowed = p.row.resource_type === 'asset' ? canAssets : canSoftware;
          return p.row.status === 'ACTIVE' && allowed ? (
            <ProsohmButton
              size="small"
              buttonVariant="outlined"
              disabled={releaseMutation.isPending}
              onClick={(e) => {
                e.stopPropagation();
                releaseMutation.mutate(p.row);
              }}
            >
              Release
            </ProsohmButton>
          ) : null;
        },
      },
    ],
    [canAssets, canSoftware, releaseMutation],
  );

  return (
    <>
      <SearchToolbar sticky>
        <FormSelect
          label="Status"
          value={status}
          onChange={(e) => setStatus(String(e.target.value))}
          options={[
            { value: 'ACTIVE', label: 'Active' },
            { value: 'FULFILLED', label: 'Fulfilled' },
            { value: 'RELEASED', label: 'Released' },
            { value: 'ALL', label: 'All' },
          ]}
          sx={{ minWidth: 160 }}
        />
        <Box sx={{ flex: 1 }} />
        {canAssets || canSoftware ? (
          <ProsohmButton buttonVariant="primary" onClick={() => setCreateOpen(true)}>
            New reservation
          </ProsohmButton>
        ) : null}
      </SearchToolbar>
      {query.isError ? (
        <ErrorState error={query.error} title="Unable to load reservations" onRetry={() => void query.refetch()} />
      ) : (
        <ContentCard noPadding>
          <ClientPaginatedDataGrid
            rows={query.data ?? []}
            columns={columns}
            loading={query.isLoading}
            autoHeight
            getRowHeight={() => 'auto'}
            filterKey={status}
            localeText={{ noRowsLabel: 'No reservations for this filter.' }}
          />
        </ContentCard>
      )}
      <ReservationDrawer
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        canAssets={canAssets}
        canSoftware={canSoftware}
      />
    </>
  );
}

function ReservationDrawer({
  open,
  onClose,
  canAssets,
  canSoftware,
}: {
  open: boolean;
  onClose: () => void;
  canAssets: boolean;
  canSoftware: boolean;
}) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [resourceType, setResourceType] = useState<AllocationResourceType>(canAssets ? 'asset' : 'license');
  const [assetSearch, setAssetSearch] = useState('');
  const [resourceId, setResourceId] = useState('');
  const [userId, setUserId] = useState('');
  const [reservedFor, setReservedFor] = useState('');
  const [reason, setReason] = useState('');
  const [slot, setSlot] = useState<AllocationWindowState>(() => emptyWindow('shift'));
  const [override, setOverride] = useState<OverrideState>(NO_OVERRIDE);
  const [check, setCheck] = useState<AllocationCheckResult | undefined>();

  const employees = useAssignableEmployees(open);
  const shiftsQuery = useQuery({
    queryKey: ['resource-shifts', 'list', 'active'],
    queryFn: () => fetchShifts({ active_only: true }),
    enabled: open,
  });
  const assetsQuery = useQuery({
    queryKey: [...itOperationsKeys.all, 'reservation-asset-search', assetSearch],
    queryFn: () => fetchAssets({ search: assetSearch || undefined, page_size: 100 }),
    enabled: open && resourceType === 'asset',
  });
  const licensesQuery = useQuery({
    queryKey: [...itOperationsKeys.all, 'reservation-licenses'],
    queryFn: () => fetchSoftwareLicenses(),
    enabled: open && resourceType === 'license',
  });

  const resourceOptions = useMemo(
    () =>
      resourceType === 'asset'
        ? (assetsQuery.data ?? [])
            .filter((a) => !['retired', 'disposed', 'lost'].includes(String(a.status)))
            .map((a) => ({
              value: a.id,
              label: `${a.asset_number} · ${a.asset_type_name || a.asset_type_code || 'Asset'}${
                a.computer_name ? ` · ${a.computer_name}` : ''
              }`,
            }))
        : (licensesQuery.data ?? []).map((p) => ({
            value: p.id,
            label: `${p.software_name ?? 'Software'}${p.entitlement_code ? ` · ${p.entitlement_code}` : ''} — ${
              p.license_metric_label ?? 'License'
            }`,
          })),
    [resourceType, assetsQuery.data, licensesQuery.data],
  );
  const userOptions = useMemo(
    () => [
      { value: '', label: 'Not yet known (use "Reserved for")' },
      ...employees.options,
    ],
    [employees.options],
  );

  const checkRequest = useMemo<AllocationCheckRequest | null>(
    () =>
      open && resourceId && windowReady(slot)
        ? { resource_type: resourceType, resource_id: resourceId, user_id: userId || null, ...windowToInput(slot) }
        : null,
    [open, resourceId, resourceType, userId, slot],
  );

  const close = () => {
    setResourceId('');
    setUserId('');
    setReservedFor('');
    setReason('');
    setAssetSearch('');
    setSlot(emptyWindow('shift'));
    setOverride(NO_OVERRIDE);
    setCheck(undefined);
    onClose();
  };

  const mutation = useMutation({
    mutationFn: () =>
      createReservation({
        resource_type: resourceType,
        resource_id: resourceId,
        user_id: userId || null,
        reserved_for: reservedFor.trim() || null,
        reason: reason.trim() || null,
        ...windowToInput(slot),
        ...overridePayload(check, override),
      }),
    onSuccess: () => {
      showSuccess('Reservation created.');
      void queryClient.invalidateQueries({ queryKey: itAllocationKeys.all });
      void queryClient.invalidateQueries({ queryKey: itInventoryKeys.all });
      close();
    },
    onError: (err) => showError(getErrorMessage(err)),
  });

  const resetResource = () => {
    setOverride(NO_OVERRIDE);
    setCheck(undefined);
  };

  return (
    <FormDrawer
      open={open}
      onClose={close}
      title="New reservation"
      subtitle="Reservations block the window for other users until assigned or released"
      icon={BookmarkAddRoundedIcon}
      formId="it-reservation-form"
      onSubmit={() => {
        if (!resourceId || !windowReady(slot)) {
          showError('Choose a resource and a shift or time window.');
          return;
        }
        if (!userId && !reservedFor.trim()) {
          showError('Choose an employee or describe who the reservation is for.');
          return;
        }
        if (!checkAllowsSave(check, override)) {
          showError(check?.reason || 'Wait for the availability check to finish.');
          return;
        }
        mutation.mutate();
      }}
      submitLabel="Reserve"
      loading={mutation.isPending}
      width={560}
    >
      <Stack spacing={2}>
        <FormSelect
          label="Resource type"
          value={resourceType}
          onChange={(e) => {
            setResourceType(e.target.value as AllocationResourceType);
            setResourceId('');
            resetResource();
          }}
          options={[
            ...(canAssets ? [{ value: 'asset', label: 'Asset (computer, monitor, peripheral)' }] : []),
            ...(canSoftware ? [{ value: 'license', label: 'License right' }] : []),
          ]}
        />
        {resourceType === 'asset' ? (
          <FormField label="Search assets" value={assetSearch} onChange={(e) => setAssetSearch(e.target.value)} />
        ) : null}
        <FormSelect
          label={resourceType === 'asset' ? 'Asset' : 'License pool'}
          required
          searchable
          value={resourceId}
          onChange={(e) => {
            setResourceId(String(e.target.value));
            resetResource();
          }}
          options={resourceOptions}
        />
        <FormSelect
          label="Employee"
          searchable
          value={userId}
          onChange={(e) => {
            setUserId(String(e.target.value));
            resetResource();
          }}
          options={userOptions}
        />
        <FormField
          label="Reserved for"
          value={reservedFor}
          onChange={(e) => setReservedFor(e.target.value)}
          helper="e.g. new joiner name when the employee record does not exist yet"
        />
        <AllocationWindowFields
          value={slot}
          onChange={(next) => {
            setSlot(next);
            resetResource();
          }}
          shifts={shiftsQuery.data ?? []}
        />
        <FormField label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        <AllocationCheckPanel request={checkRequest} override={override} onOverrideChange={setOverride} onResult={setCheck} />
      </Stack>
    </FormDrawer>
  );
}

function LegacyReviewView() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const access = accessContextFromUser(user);
  const canResolve = canManageItAssets(access);
  const [resolving, setResolving] = useState<LegacyAssignment | null>(null);
  const query = useQuery({ queryKey: itAllocationKeys.legacy(), queryFn: fetchLegacyReview });

  const assignmentColumns = useMemo<GridColDef<LegacyAssignment>[]>(
    () => [
      {
        field: 'asset_number',
        headerName: 'Asset',
        flex: 1,
        minWidth: 170,
        renderCell: (p) => (
          <Box sx={{ lineHeight: 1.2, py: 0.5 }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {p.row.asset_number}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {[p.row.asset_type, p.row.asset_name].filter(Boolean).join(' · ')}
            </Typography>
          </Box>
        ),
      },
      { field: 'user_name', headerName: 'Employee', flex: 1, minWidth: 160, valueGetter: (v) => v || '—' },
      {
        field: 'assigned_date',
        headerName: 'Assigned',
        width: 120,
        valueFormatter: (v) => formatDate(v as string | null) || '—',
      },
      {
        field: 'shareable',
        headerName: 'Policy',
        width: 160,
        renderCell: (p) => (
          <Chip
            size="small"
            variant="outlined"
            label={p.row.shareable ? 'Shareable by shift' : 'Exclusive'}
            color={p.row.shareable ? 'info' : 'default'}
          />
        ),
      },
      { field: 'reason', headerName: 'Issue', flex: 1.4, minWidth: 220 },
      {
        field: 'actions',
        headerName: '',
        width: 120,
        sortable: false,
        renderCell: (p) =>
          canResolve ? (
            <ProsohmButton
              size="small"
              buttonVariant="outlined"
              onClick={(e) => {
                e.stopPropagation();
                setResolving(p.row);
              }}
            >
              Set window
            </ProsohmButton>
          ) : null,
      },
    ],
    [canResolve],
  );

  const poolColumns = useMemo<GridColDef<LegacyLicensePool>[]>(
    () => [
      { field: 'label', headerName: 'License pool', flex: 1.2, minWidth: 200 },
      { field: 'metric_label', headerName: 'Metric', width: 160 },
      {
        field: 'rights_owned',
        headerName: 'Rights',
        width: 140,
        valueGetter: (_v, row) => `${row.rights_allocated} / ${row.rights_owned}`,
      },
      {
        field: 'compliance_status',
        headerName: 'Compliance',
        width: 150,
        renderCell: (p) => <Chip size="small" label={p.row.compliance_status.replace(/_/g, ' ')} color="warning" />,
      },
      { field: 'issue', headerName: 'Issue', flex: 1.4, minWidth: 220 },
    ],
    [],
  );

  if (query.isError) {
    return <ErrorState error={query.error} title="Unable to load the review list" onRetry={() => void query.refetch()} />;
  }

  return (
    <Stack spacing={2}>
      <ContentCard
        title={`Assignments without a shift or window (${query.data?.counts.assignments ?? 0})`}
        noPadding
      >
        <ClientPaginatedDataGrid
          rows={query.data?.assignments ?? []}
          columns={assignmentColumns}
          getRowId={(r) => r.assignment_id}
          loading={query.isLoading}
          autoHeight
          getRowHeight={() => 'auto'}
          localeText={{ noRowsLabel: 'Every open assignment has a shift or time window.' }}
        />
      </ContentCard>
      <ContentCard title={`License pools needing attention (${query.data?.counts.license_pools ?? 0})`} noPadding>
        <ClientPaginatedDataGrid
          rows={query.data?.license_pools ?? []}
          columns={poolColumns}
          getRowId={(r) => r.license_pool_id}
          loading={query.isLoading}
          autoHeight
          getRowHeight={() => 'auto'}
          onRowClick={() => navigate('/it/software?tab=licenses')}
          localeText={{ noRowsLabel: 'All license pools have a metric and are within their rights.' }}
        />
      </ContentCard>
      <LegacyResolveDrawer row={resolving} onClose={() => setResolving(null)} />
    </Stack>
  );
}

function LegacyResolveDrawer({ row, onClose }: { row: LegacyAssignment | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [slot, setSlot] = useState<AllocationWindowState>(() => emptyWindow('shift'));
  const [override, setOverride] = useState<OverrideState>(NO_OVERRIDE);
  const [check, setCheck] = useState<AllocationCheckResult | undefined>();
  const open = Boolean(row);

  const shiftsQuery = useQuery({
    queryKey: ['resource-shifts', 'list', 'active'],
    queryFn: () => fetchShifts({ active_only: true }),
    enabled: open,
  });

  const checkRequest = useMemo<AllocationCheckRequest | null>(
    () =>
      row && windowReady(slot)
        ? {
            resource_type: 'asset',
            resource_id: row.asset_id,
            user_id: row.user_id,
            exclude_assignment_id: row.assignment_id,
            ...windowToInput(slot),
            start_date: row.assigned_date,
          }
        : null,
    [row, slot],
  );

  const close = () => {
    setSlot(emptyWindow('shift'));
    setOverride(NO_OVERRIDE);
    setCheck(undefined);
    onClose();
  };

  const mutation = useMutation({
    mutationFn: () => {
      const w = windowToInput(slot);
      return resolveLegacyAssignment(row!.assignment_id, {
        mode: slot.mode === 'custom' ? 'times' : slot.mode === 'all' ? 'all_hours' : 'shift',
        shift_id: w.shift_id,
        start_time: w.start_time,
        end_time: w.end_time,
        ...overridePayload(check, override),
      });
    },
    onSuccess: () => {
      showSuccess('Assignment window saved.');
      void queryClient.invalidateQueries({ queryKey: itAllocationKeys.all });
      void queryClient.invalidateQueries({ queryKey: itInventoryKeys.all });
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.all });
      close();
    },
    onError: (err) => showError(getErrorMessage(err)),
  });

  return (
    <FormDrawer
      open={open}
      onClose={close}
      title="Set assignment window"
      subtitle={row ? `${row.asset_number} · ${row.user_name ?? 'Unknown user'}` : undefined}
      icon={FactCheckRoundedIcon}
      formId="it-legacy-resolve-form"
      onSubmit={() => {
        if (!checkAllowsSave(check, override)) {
          showError(check?.reason || 'Wait for the availability check to finish.');
          return;
        }
        mutation.mutate();
      }}
      submitLabel="Save window"
      loading={mutation.isPending}
      width={520}
    >
      <Stack spacing={2}>
        <Typography variant="body2" color="text.secondary">
          The assignment keeps its original dates and history; only the usage window is set. Choose
          &quot;All hours&quot; to confirm the employee uses the resource exclusively.
        </Typography>
        <AllocationWindowFields
          value={slot}
          onChange={(next) => {
            setSlot(next);
            setOverride(NO_OVERRIDE);
          }}
          shifts={shiftsQuery.data ?? []}
          showDates={false}
          allModeLabel="All hours (confirm exclusive use)"
        />
        <AllocationCheckPanel request={checkRequest} override={override} onOverrideChange={setOverride} onResult={setCheck} />
      </Stack>
    </FormDrawer>
  );
}
