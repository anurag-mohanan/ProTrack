import { useCallback, useMemo, useState, type FormEvent } from 'react';
import {
  Box,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import AssignmentReturnRoundedIcon from '@mui/icons-material/AssignmentReturnRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import InventoryRoundedIcon from '@mui/icons-material/InventoryRounded';
import PersonAddAlt1RoundedIcon from '@mui/icons-material/PersonAddAlt1Rounded';
import SwapHorizRoundedIcon from '@mui/icons-material/SwapHorizRounded';
import UndoRoundedIcon from '@mui/icons-material/UndoRounded';
import type { GridColDef, GridRowClassNameParams } from '@mui/x-data-grid';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  assignAsset,
  createAsset,
  deleteAsset,
  fetchAssetIds,
  fetchAssetTypes,
  fetchAssetsPaginated,
  itOperationsKeys,
  returnAsset,
  returnAssetToCustomer,
  transferAsset,
  updateAsset,
} from '../../api/itOperations';
import { fetchCustomers, fetchUsers } from '../../api/lookups';
import { getErrorMessage } from '../../api/client';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ServerPaginatedDataGrid } from '../../components/common/ServerPaginatedDataGrid';
import { AssetBulkActionBar } from '../../components/it/AssetBulkActionBar';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
  SearchToolbar,
  TableRowActions,
} from '../../components/ui/design-system';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { DATA_GRID_ACTIONS_COLUMN_WIDTH } from '../../theme/componentStyles';
import type { ITAsset, ITAssetCreate } from '../../types/itOperations';
import { formatCellValue, formatDate, userDisplayName } from '../../utils/format';
import { optionalString, validateRequiredFields } from '../../utils/formValues';
import {
  accessContextFromUser,
  canAssignItAssets,
  canManageItAssets,
  canReturnCustomerAssets,
} from '../../utils/permissions';

const ASSET_STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'available', label: 'Available' },
  { value: 'assigned', label: 'Assigned' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'awaiting_return', label: 'Awaiting return' },
  { value: 'returned_to_customer', label: 'Returned to customer' },
  { value: 'retired', label: 'Retired' },
  { value: 'disposed', label: 'Disposed' },
];

const INVENTORY_SCOPE_OPTIONS = [
  { value: 'current', label: 'Current assets' },
  { value: 'returned', label: 'Returned to customer' },
  { value: 'historical', label: 'Historical (returned / retired / disposed)' },
  { value: 'all', label: 'Include all (incl. historical)' },
];

const OWNERSHIP_OPTIONS = [
  { value: '', label: 'All ownership' },
  { value: 'organization', label: 'Organization owned' },
  { value: 'customer', label: 'Customer owned' },
];

const WARRANTY_STATUS_OPTIONS = [
  { value: '', label: 'All warranties' },
  { value: 'active', label: 'Warranty active' },
  { value: 'expiring_soon', label: 'Expiring soon (30 days)' },
  { value: 'expired', label: 'Warranty expired' },
  { value: 'none', label: 'No warranty date' },
];

const RETURN_CONDITION_OPTIONS = [
  { value: 'good', label: 'Good' },
  { value: 'damaged', label: 'Damaged' },
  { value: 'needs_repair', label: 'Needs repair' },
];

const CUSTOMER_RETURN_REASON_OPTIONS = [
  { value: '', label: 'Select reason' },
  { value: 'project_ended', label: 'Project ended' },
  { value: 'contract_complete', label: 'Contract complete' },
  { value: 'customer_request', label: 'Customer request' },
  { value: 'replaced', label: 'Replaced' },
  { value: 'other', label: 'Other' },
];

type AssetFormState = {
  asset_type_id: string;
  serial_number: string;
  make: string;
  model: string;
  purchase_date: string;
  purchase_cost: string;
  warranty_expiry: string;
  location: string;
  notes: string;
  status: string;
};

const emptyForm: AssetFormState = {
  asset_type_id: '',
  serial_number: '',
  make: '',
  model: '',
  purchase_date: '',
  purchase_cost: '',
  warranty_expiry: '',
  location: '',
  notes: '',
  status: 'available',
};

function statusColor(
  status: string,
): 'default' | 'success' | 'info' | 'warning' | 'error' {
  switch (status) {
    case 'available':
      return 'success';
    case 'assigned':
      return 'info';
    case 'maintenance':
    case 'awaiting_return':
      return 'warning';
    case 'returned_to_customer':
    case 'retired':
    case 'disposed':
      return 'default';
    default:
      return 'default';
  }
}

function warrantyStatusColor(
  status: string,
): 'default' | 'success' | 'warning' | 'error' {
  switch (status) {
    case 'active':
      return 'success';
    case 'expiring_soon':
      return 'warning';
    case 'expired':
      return 'error';
    default:
      return 'default';
  }
}

function warrantyStatusLabel(status: string | null | undefined): string {
  switch (status) {
    case 'active':
      return 'Active';
    case 'expiring_soon':
      return 'Expiring soon';
    case 'expired':
      return 'Expired';
    case 'none':
      return 'None';
    default:
      return '—';
  }
}

function assigneeName(asset: ITAsset): string {
  return (
    asset.assigned_to_user_name ||
    asset.current_assignee_name ||
    '—'
  );
}

export function ITAssetsPage({
  defaultInventoryScope = 'current',
}: {
  defaultInventoryScope?: 'current' | 'returned' | 'historical' | 'all';
}) {
  const { user } = useAuth();
  const access = accessContextFromUser(user);
  const canManage = canManageItAssets(access);
  const canAssign = canAssignItAssets(access);
  const canReturnToCustomer = canReturnCustomerAssets(access);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [inventoryScope, setInventoryScope] = useState(defaultInventoryScope);
  const [ownershipFilter, setOwnershipFilter] = useState('');
  const [warrantyFilter, setWarrantyFilter] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ITAsset | null>(null);
  const [form, setForm] = useState<AssetFormState>(emptyForm);
  const [deleteTarget, setDeleteTarget] = useState<ITAsset | null>(null);
  const [assignTarget, setAssignTarget] = useState<ITAsset | null>(null);
  const [returnTarget, setReturnTarget] = useState<ITAsset | null>(null);
  const [transferTarget, setTransferTarget] = useState<ITAsset | null>(null);
  const [customerReturnTarget, setCustomerReturnTarget] = useState<ITAsset | null>(null);
  const [assignUserId, setAssignUserId] = useState('');
  const [assignDate, setAssignDate] = useState(new Date().toISOString().slice(0, 10));
  const [assignNotes, setAssignNotes] = useState('');
  const [returnDate, setReturnDate] = useState(new Date().toISOString().slice(0, 10));
  const [returnCondition, setReturnCondition] = useState('good');
  const [returnNotes, setReturnNotes] = useState('');
  const [transferUserId, setTransferUserId] = useState('');
  const [transferDate, setTransferDate] = useState(new Date().toISOString().slice(0, 10));
  const [transferNotes, setTransferNotes] = useState('');
  const [customerReturnDate, setCustomerReturnDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [customerReturnOwnerId, setCustomerReturnOwnerId] = useState('');
  const [customerReturnReceivedBy, setCustomerReturnReceivedBy] = useState('');
  const [customerReturnCondition, setCustomerReturnCondition] = useState('good');
  const [customerReturnReason, setCustomerReturnReason] = useState('');
  const [customerReturnNotes, setCustomerReturnNotes] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [pageRows, setPageRows] = useState<ITAsset[]>([]);
  const [matchingTotal, setMatchingTotal] = useState(0);

  const assetTypesQuery = useQuery({
    queryKey: itOperationsKeys.assetTypes(),
    queryFn: fetchAssetTypes,
  });

  const usersQuery = useQuery({
    queryKey: ['lookups', 'users'],
    queryFn: () => fetchUsers(),
    enabled: canAssign,
  });

  const customersQuery = useQuery({
    queryKey: ['lookups', 'customers'],
    queryFn: fetchCustomers,
    enabled: canReturnToCustomer || canManage,
  });

  const listFilters = useMemo(
    () => ({
      status: statusFilter || undefined,
      q: search.trim() || undefined,
      inventory_scope: statusFilter ? 'all' : inventoryScope,
      purchased_by: ownershipFilter || undefined,
      warranty_status: warrantyFilter || undefined,
    }),
    [search, statusFilter, inventoryScope, ownershipFilter, warrantyFilter],
  );

  const clearSelection = useCallback(() => setSelectedIds(new Set()), []);

  const toggleAssetSelection = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const pageIds = useMemo(() => pageRows.map((r) => r.id), [pageRows]);
  const selectedOnPage = useMemo(
    () => pageIds.filter((id) => selectedIds.has(id)),
    [pageIds, selectedIds],
  );
  const allPageSelected = pageIds.length > 0 && selectedOnPage.length === pageIds.length;
  const somePageSelected = selectedOnPage.length > 0 && !allPageSelected;

  const selectAllVisible = useCallback(() => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      for (const id of pageIds) next.add(id);
      return next;
    });
  }, [pageIds]);

  const deselectAllVisible = useCallback(() => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      for (const id of pageIds) next.delete(id);
      return next;
    });
  }, [pageIds]);

  const selectAllMatching = useCallback(async () => {
    const res = await fetchAssetIds(listFilters);
    setSelectedIds(new Set(res.ids));
    setMatchingTotal(res.total);
    if (res.truncated) {
      showError(
        `Only the first ${res.ids.length} of ${res.total} matching assets were selected.`,
      );
    }
  }, [listFilters, showError]);

  const handlePageDataChange = useCallback(
    (info: { items: ITAsset[]; total: number }) => {
      setPageRows(info.items);
      setMatchingTotal(info.total);
    },
    [],
  );

  const invalidateAssets = () => {
    void queryClient.invalidateQueries({ queryKey: itOperationsKeys.all });
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload: ITAssetCreate = {
        asset_type_id: form.asset_type_id,
        serial_number: optionalString(form.serial_number),
        make: optionalString(form.make),
        model: optionalString(form.model),
        purchase_date: optionalString(form.purchase_date),
        purchase_cost: form.purchase_cost.trim()
          ? Number(form.purchase_cost)
          : null,
        warranty_expiry: optionalString(form.warranty_expiry),
        location: optionalString(form.location),
        notes: optionalString(form.notes),
        status: optionalString(form.status) ?? 'available',
      };
      if (editing) {
        return updateAsset(editing.id, payload);
      }
      return createAsset(payload);
    },
    onSuccess: () => {
      showSuccess(editing ? 'Asset updated.' : 'Asset created.');
      setFormOpen(false);
      setEditing(null);
      setForm(emptyForm);
      invalidateAssets();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAsset(id),
    onSuccess: () => {
      showSuccess('Asset deleted.');
      setDeleteTarget(null);
      invalidateAssets();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const assignMutation = useMutation({
    mutationFn: () =>
      assignAsset(assignTarget!.id, {
        user_id: assignUserId,
        assigned_date: optionalString(assignDate),
        notes: optionalString(assignNotes),
      }),
    onSuccess: () => {
      showSuccess('Asset assigned.');
      setAssignTarget(null);
      setAssignUserId('');
      setAssignNotes('');
      invalidateAssets();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const returnMutation = useMutation({
    mutationFn: () =>
      returnAsset(returnTarget!.id, {
        returned_date: optionalString(returnDate),
        return_condition: returnCondition,
        notes: optionalString(returnNotes),
      }),
    onSuccess: () => {
      showSuccess('Asset returned.');
      setReturnTarget(null);
      setReturnNotes('');
      invalidateAssets();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const transferMutation = useMutation({
    mutationFn: () =>
      transferAsset(transferTarget!.id, {
        to_user_id: transferUserId,
        assigned_date: optionalString(transferDate),
        notes: optionalString(transferNotes),
      }),
    onSuccess: () => {
      showSuccess('Asset transferred.');
      setTransferTarget(null);
      setTransferUserId('');
      setTransferNotes('');
      invalidateAssets();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const customerReturnMutation = useMutation({
    mutationFn: () =>
      returnAssetToCustomer(customerReturnTarget!.id, {
        return_date: optionalString(customerReturnDate),
        owner_customer_id: optionalString(customerReturnOwnerId),
        received_by_name: optionalString(customerReturnReceivedBy),
        condition_at_return: customerReturnCondition,
        return_reason: optionalString(customerReturnReason),
        notes: optionalString(customerReturnNotes),
      }),
    onSuccess: () => {
      showSuccess('Asset returned to customer and removed from current inventory.');
      setCustomerReturnTarget(null);
      setCustomerReturnReceivedBy('');
      setCustomerReturnReason('');
      setCustomerReturnNotes('');
      invalidateAssets();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const assetTypeOptions = useMemo(
    () =>
      (assetTypesQuery.data ?? [])
        .filter((type) => type.is_active !== false)
        .map((type) => ({ value: type.id, label: `${type.name} (${type.code})` })),
    [assetTypesQuery.data],
  );

  const userOptions = useMemo(
    () =>
      (usersQuery.data ?? []).map((u) => ({
        value: u.id,
        label: userDisplayName(u) || u.email || u.id,
      })),
    [usersQuery.data],
  );

  const customerOptions = useMemo(
    () =>
      (customersQuery.data ?? []).map((customer) => ({
        value: customer.id,
        label: customer.name,
      })),
    [customersQuery.data],
  );

  const openCustomerReturn = (asset: ITAsset) => {
    setCustomerReturnTarget(asset);
    setCustomerReturnDate(new Date().toISOString().slice(0, 10));
    setCustomerReturnOwnerId(asset.owner_customer_id ?? '');
    setCustomerReturnReceivedBy('');
    setCustomerReturnCondition('good');
    setCustomerReturnReason('');
    setCustomerReturnNotes('');
  };

  const canShowCustomerReturn = (asset: ITAsset) =>
    canReturnToCustomer &&
    defaultInventoryScope !== 'returned' &&
    asset.purchased_by === 'customer' &&
    asset.status !== 'returned_to_customer';

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  const openEdit = (asset: ITAsset) => {
    setEditing(asset);
    setForm({
      asset_type_id: asset.asset_type_id,
      serial_number: asset.serial_number ?? '',
      make: asset.make ?? '',
      model: asset.model ?? '',
      purchase_date: asset.purchase_date ?? '',
      purchase_cost:
        asset.purchase_cost === null || asset.purchase_cost === undefined
          ? ''
          : String(asset.purchase_cost),
      warranty_expiry: asset.warranty_expiry ?? '',
      location: asset.location ?? '',
      notes: asset.notes ?? '',
      status: asset.status || 'available',
    });
    setFormOpen(true);
  };

  const handleSave = (event?: FormEvent) => {
    event?.preventDefault();
    const validationError = validateRequiredFields(
      { asset_type_id: form.asset_type_id },
      [{ key: 'asset_type_id', label: 'Asset type' }],
    );
    if (validationError) {
      showError(validationError);
      return;
    }
    saveMutation.mutate();
  };

  const columns: GridColDef<ITAsset>[] = [
    {
      field: '__select',
      headerName: '',
      width: 48,
      sortable: false,
      filterable: false,
      disableColumnMenu: true,
      renderHeader: () => (
        <Checkbox
          size="small"
          checked={allPageSelected}
          indeterminate={somePageSelected}
          onChange={() => {
            if (allPageSelected) deselectAllVisible();
            else selectAllVisible();
          }}
          slotProps={{ input: { 'aria-label': 'Select all on this page' } }}
          onClick={(e) => e.stopPropagation()}
        />
      ),
      renderCell: (params) => (
        <Checkbox
          size="small"
          checked={selectedIds.has(params.row.id)}
          onChange={() => toggleAssetSelection(params.row.id)}
          slotProps={{ input: { 'aria-label': `Select ${params.row.asset_number}` } }}
          onClick={(e) => e.stopPropagation()}
        />
      ),
    },
    {
      field: 'asset_number',
      headerName: 'Asset #',
      flex: 0.9,
      minWidth: 120,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'asset_type_name',
      headerName: 'Type',
      flex: 0.9,
      minWidth: 120,
      valueGetter: (_value, row) => row.asset_type_name || row.asset_type_code || '—',
    },
    {
      field: 'make_model',
      headerName: 'Make / Model',
      flex: 1.2,
      minWidth: 160,
      valueGetter: (_value, row) =>
        [row.make, row.model].filter(Boolean).join(' ') || '—',
    },
    {
      field: 'purchased_by',
      headerName: 'Owned by',
      width: 140,
      valueGetter: (_value, row) =>
        row.purchased_by === 'customer'
          ? row.owner_customer_name || 'Customer'
          : row.purchased_by === 'organization'
            ? 'Organization'
            : row.purchased_by || '—',
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 130,
      renderCell: (params) => (
        <Chip
          size="small"
          label={String(params.value || '—').replace(/_/g, ' ')}
          color={statusColor(String(params.value || ''))}
          variant="outlined"
        />
      ),
    },
    {
      field: 'warranty_status',
      headerName: 'Warranty',
      width: 130,
      renderCell: (params) => {
        const value = String(params.row.warranty_status || 'none');
        return (
          <Chip
            size="small"
            label={warrantyStatusLabel(value)}
            color={warrantyStatusColor(value)}
            variant="outlined"
          />
        );
      },
    },
    {
      field: 'warranty_expiry',
      headerName: 'Warranty upto',
      width: 130,
      valueFormatter: (value) => formatDate(value as string | null | undefined),
    },
    {
      field: 'location',
      headerName: 'Location',
      flex: 0.9,
      minWidth: 120,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'assignee',
      headerName: 'Assignee',
      flex: 1,
      minWidth: 140,
      valueGetter: (_value, row) => assigneeName(row),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width:
        DATA_GRID_ACTIONS_COLUMN_WIDTH +
        (canAssign ? 72 : 0) +
        (canReturnToCustomer ? 40 : 0),
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Stack direction="row" spacing={0.25} onClick={(e) => e.stopPropagation()} sx={{ alignItems: 'center' }}>
          {canManage ? (
            <TableRowActions
              onEdit={() => openEdit(params.row)}
              deleteAction={
                <ProsohmButton
                  buttonVariant="outlined"
                  size="small"
                  aria-label="Delete asset"
                  onClick={() => setDeleteTarget(params.row)}
                  sx={{ minWidth: 0, px: 0.75 }}
                >
                  <DeleteOutlineRoundedIcon fontSize="small" />
                </ProsohmButton>
              }
            />
          ) : null}
          {canAssign && params.row.status === 'available' ? (
            <ProsohmButton
              buttonVariant="outlined"
              size="small"
              aria-label="Assign"
              onClick={() => {
                setAssignTarget(params.row);
                setAssignUserId('');
                setAssignDate(new Date().toISOString().slice(0, 10));
                setAssignNotes('');
              }}
              sx={{ minWidth: 0, px: 0.75 }}
            >
              <PersonAddAlt1RoundedIcon fontSize="small" />
            </ProsohmButton>
          ) : null}
          {canAssign && params.row.status === 'assigned' ? (
            <>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                aria-label="Return"
                onClick={() => {
                  setReturnTarget(params.row);
                  setReturnDate(new Date().toISOString().slice(0, 10));
                  setReturnCondition('good');
                  setReturnNotes('');
                }}
                sx={{ minWidth: 0, px: 0.75 }}
              >
                <UndoRoundedIcon fontSize="small" />
              </ProsohmButton>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                aria-label="Transfer"
                onClick={() => {
                  setTransferTarget(params.row);
                  setTransferUserId('');
                  setTransferDate(new Date().toISOString().slice(0, 10));
                  setTransferNotes('');
                }}
                sx={{ minWidth: 0, px: 0.75 }}
              >
                <SwapHorizRoundedIcon fontSize="small" />
              </ProsohmButton>
            </>
          ) : null}
          {canShowCustomerReturn(params.row) ? (
            <ProsohmButton
              buttonVariant="outlined"
              size="small"
              aria-label="Return to customer"
              title="Return to customer"
              onClick={() => openCustomerReturn(params.row)}
              sx={{ minWidth: 0, px: 0.75 }}
            >
              <AssignmentReturnRoundedIcon fontSize="small" />
            </ProsohmButton>
          ) : null}
        </Stack>
      ),
    },
  ];

  return (
    <PageContainer>
      <PageHeader
        title={
          defaultInventoryScope === 'returned' ? 'Returned Assets' : 'Assets & Inventory'
        }
        subtitle={
          defaultInventoryScope === 'returned'
            ? 'Customer-owned assets returned from Prosohm custody (historical record retained).'
            : 'Current inventory by default. Ownership is separate from who uses the asset.'
        }
        action={
          canManage && defaultInventoryScope !== 'returned' ? (
            <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
              Add asset
            </ProsohmButton>
          ) : undefined
        }
      />

      <SearchToolbar sticky>
        <FormField
          label="Search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Asset number, serial, make…"
          sx={{ minWidth: 240, flex: 1, maxWidth: 420 }}
        />
        {defaultInventoryScope !== 'returned' ? (
          <FormSelect
            label="Inventory"
            value={inventoryScope}
            onChange={(event) =>
              setInventoryScope(String(event.target.value) as typeof inventoryScope)
            }
            options={INVENTORY_SCOPE_OPTIONS}
            sx={{ minWidth: 220 }}
          />
        ) : null}
        <FormSelect
          label="Ownership"
          value={ownershipFilter}
          onChange={(event) => setOwnershipFilter(String(event.target.value))}
          options={OWNERSHIP_OPTIONS}
          sx={{ minWidth: 180 }}
        />
        <FormSelect
          label="Status"
          value={statusFilter}
          onChange={(event) => setStatusFilter(String(event.target.value))}
          options={ASSET_STATUS_OPTIONS}
          sx={{ minWidth: 180 }}
        />
        <FormSelect
          label="Warranty"
          value={warrantyFilter}
          onChange={(event) => setWarrantyFilter(String(event.target.value))}
          options={WARRANTY_STATUS_OPTIONS}
          sx={{ minWidth: 200 }}
        />
      </SearchToolbar>

      {selectedIds.size > 0 ? (
        <AssetBulkActionBar
          selectedIds={Array.from(selectedIds)}
          matchingTotal={matchingTotal}
          pageSelectedCount={selectedOnPage.length}
          canManage={canManage}
          canAssign={canAssign}
          canReturnToCustomer={canReturnToCustomer}
          onClearSelection={clearSelection}
          onSelectAllMatching={selectAllMatching}
          onComplete={() => {
            invalidateAssets();
          }}
        />
      ) : null}

      <ContentCard noPadding>
        <ServerPaginatedDataGrid<ITAsset, ITAsset>
          queryKey={['it', 'assets']}
          fetcher={fetchAssetsPaginated}
          filters={listFilters}
          columns={columns}
          getRowId={(row) => row.id}
          autoHeight
          onPageDataChange={handlePageDataChange}
          getRowClassName={(params: GridRowClassNameParams<ITAsset>) =>
            selectedIds.has(params.id as string) ? 'ProTrack-row--selected' : ''
          }
          sx={{
            '& .ProTrack-row--selected': {
              bgcolor: 'action.selected',
            },
          }}
        />
      </ContentCard>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? 'Edit asset' : 'Add asset'}
        subtitle="Asset numbers are generated by the server."
        icon={InventoryRoundedIcon}
        formId="it-asset-form"
        width={560}
        submitLabel={editing ? 'Save changes' : 'Create asset'}
        loading={saveMutation.isPending}
      >
        <Box
          component="form"
          id="it-asset-form"
          onSubmit={handleSave}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}
        >
          <FormSection title="Identity">
            <FormSelect
              label="Asset type"
              required
              value={form.asset_type_id}
              onChange={(event) =>
                setForm((current) => ({ ...current, asset_type_id: String(event.target.value) }))
              }
              options={assetTypeOptions}
            />
            <FormField
              label="Serial number"
              value={form.serial_number}
              onChange={(event) =>
                setForm((current) => ({ ...current, serial_number: event.target.value }))
              }
            />
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <FormField
                label="Make"
                value={form.make}
                onChange={(event) =>
                  setForm((current) => ({ ...current, make: event.target.value }))
                }
                sx={{ flex: 1 }}
              />
              <FormField
                label="Model"
                value={form.model}
                onChange={(event) =>
                  setForm((current) => ({ ...current, model: event.target.value }))
                }
                sx={{ flex: 1 }}
              />
            </Stack>
            {editing ? (
              <FormSelect
                label="Status"
                value={form.status}
                onChange={(event) =>
                  setForm((current) => ({ ...current, status: String(event.target.value) }))
                }
                options={ASSET_STATUS_OPTIONS.filter((opt) => opt.value)}
              />
            ) : null}
          </FormSection>
          <FormSection title="Purchase & location">
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <FormField
                label="Purchase date"
                type="date"
                value={form.purchase_date}
                onChange={(event) =>
                  setForm((current) => ({ ...current, purchase_date: event.target.value }))
                }
                slotProps={{ inputLabel: { shrink: true } }}
                sx={{ flex: 1 }}
              />
              <FormField
                label="Purchase cost"
                value={form.purchase_cost}
                onChange={(event) =>
                  setForm((current) => ({ ...current, purchase_cost: event.target.value }))
                }
                sx={{ flex: 1 }}
              />
            </Stack>
            <FormField
              label="Warranty upto"
              type="date"
              value={form.warranty_expiry}
              onChange={(event) =>
                setForm((current) => ({ ...current, warranty_expiry: event.target.value }))
              }
              slotProps={{ inputLabel: { shrink: true } }}
              helper="Status is calculated from this date (active / expiring soon within 30 days / expired)."
            />
            <FormField
              label="Location"
              value={form.location}
              onChange={(event) =>
                setForm((current) => ({ ...current, location: event.target.value }))
              }
            />
            <FormField
              label="Notes"
              value={form.notes}
              onChange={(event) =>
                setForm((current) => ({ ...current, notes: event.target.value }))
              }
              multiline
              minRows={3}
            />
          </FormSection>
        </Box>
      </FormDrawer>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete asset"
        message="This permanently removes the asset from the register."
        recordName={deleteTarget?.asset_number}
        confirmLabel="Delete"
        danger
        loading={deleteMutation.isPending}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
      />

      <Dialog open={Boolean(assignTarget)} onClose={() => setAssignTarget(null)} fullWidth maxWidth="sm">
        <DialogTitle>Assign asset</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <FormSelect
            label="Assignee"
            required
            value={assignUserId}
            onChange={(event) => setAssignUserId(String(event.target.value))}
            options={userOptions}
          />
          <FormField
            label="Assigned date"
            type="date"
            value={assignDate}
            onChange={(event) => setAssignDate(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <FormField
            label="Notes"
            value={assignNotes}
            onChange={(event) => setAssignNotes(event.target.value)}
            multiline
            minRows={2}
          />
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setAssignTarget(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={assignMutation.isPending}
            disabled={!assignUserId}
            onClick={() => assignMutation.mutate()}
          >
            Assign
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(returnTarget)} onClose={() => setReturnTarget(null)} fullWidth maxWidth="sm">
        <DialogTitle>Return asset</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <FormField
            label="Returned date"
            type="date"
            value={returnDate}
            onChange={(event) => setReturnDate(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <FormSelect
            label="Condition"
            value={returnCondition}
            onChange={(event) => setReturnCondition(String(event.target.value))}
            options={RETURN_CONDITION_OPTIONS}
          />
          <FormField
            label="Notes"
            value={returnNotes}
            onChange={(event) => setReturnNotes(event.target.value)}
            multiline
            minRows={2}
          />
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setReturnTarget(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={returnMutation.isPending}
            onClick={() => returnMutation.mutate()}
          >
            Return
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(transferTarget)} onClose={() => setTransferTarget(null)} fullWidth maxWidth="sm">
        <DialogTitle>Transfer asset</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <FormSelect
            label="Transfer to"
            required
            value={transferUserId}
            onChange={(event) => setTransferUserId(String(event.target.value))}
            options={userOptions}
          />
          <FormField
            label="Assigned date"
            type="date"
            value={transferDate}
            onChange={(event) => setTransferDate(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <FormField
            label="Notes"
            value={transferNotes}
            onChange={(event) => setTransferNotes(event.target.value)}
            multiline
            minRows={2}
          />
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setTransferTarget(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={transferMutation.isPending}
            disabled={!transferUserId}
            onClick={() => transferMutation.mutate()}
          >
            Transfer
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(customerReturnTarget)}
        onClose={() => setCustomerReturnTarget(null)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Return to customer</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <Box sx={{ color: 'text.secondary', fontSize: 14 }}>
            Removes {customerReturnTarget?.asset_number ?? 'this asset'} from current inventory.
            The asset and this return event stay in history forever.
          </Box>
          <FormSelect
            label="Customer owner"
            required
            value={customerReturnOwnerId}
            onChange={(event) => setCustomerReturnOwnerId(String(event.target.value))}
            options={customerOptions}
          />
          <FormField
            label="Return date"
            type="date"
            value={customerReturnDate}
            onChange={(event) => setCustomerReturnDate(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <FormSelect
            label="Condition at return"
            value={customerReturnCondition}
            onChange={(event) => setCustomerReturnCondition(String(event.target.value))}
            options={RETURN_CONDITION_OPTIONS}
          />
          <FormField
            label="Received by (customer contact)"
            value={customerReturnReceivedBy}
            onChange={(event) => setCustomerReturnReceivedBy(event.target.value)}
            placeholder="Name of person who received the asset"
          />
          <FormSelect
            label="Return reason"
            value={customerReturnReason}
            onChange={(event) => setCustomerReturnReason(String(event.target.value))}
            options={CUSTOMER_RETURN_REASON_OPTIONS}
          />
          <FormField
            label="Notes"
            value={customerReturnNotes}
            onChange={(event) => setCustomerReturnNotes(event.target.value)}
            multiline
            minRows={2}
          />
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setCustomerReturnTarget(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={customerReturnMutation.isPending}
            disabled={!customerReturnOwnerId}
            onClick={() => customerReturnMutation.mutate()}
          >
            Return to customer
          </ProsohmButton>
        </DialogActions>
      </Dialog>
    </PageContainer>
  );
}
