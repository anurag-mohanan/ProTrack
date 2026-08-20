import { useMemo, useState, type FormEvent } from 'react';
import {
  Box,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import InventoryRoundedIcon from '@mui/icons-material/InventoryRounded';
import PersonAddAlt1RoundedIcon from '@mui/icons-material/PersonAddAlt1Rounded';
import SwapHorizRoundedIcon from '@mui/icons-material/SwapHorizRounded';
import UndoRoundedIcon from '@mui/icons-material/UndoRounded';
import type { GridColDef } from '@mui/x-data-grid';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  assignAsset,
  createAsset,
  deleteAsset,
  fetchAssetTypes,
  fetchAssetsPaginated,
  itOperationsKeys,
  returnAsset,
  transferAsset,
  updateAsset,
} from '../../api/itOperations';
import { fetchUsers } from '../../api/lookups';
import { getErrorMessage } from '../../api/client';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ServerPaginatedDataGrid } from '../../components/common/ServerPaginatedDataGrid';
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
import { formatCellValue, userDisplayName } from '../../utils/format';
import { optionalString, validateRequiredFields } from '../../utils/formValues';
import {
  accessContextFromUser,
  canAssignItAssets,
  canManageItAssets,
} from '../../utils/permissions';

const ASSET_STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'available', label: 'Available' },
  { value: 'assigned', label: 'Assigned' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'retired', label: 'Retired' },
  { value: 'disposed', label: 'Disposed' },
];

const RETURN_CONDITION_OPTIONS = [
  { value: 'good', label: 'Good' },
  { value: 'damaged', label: 'Damaged' },
  { value: 'needs_repair', label: 'Needs repair' },
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
      return 'warning';
    case 'retired':
    case 'disposed':
      return 'default';
    default:
      return 'default';
  }
}

function assigneeName(asset: ITAsset): string {
  return (
    asset.assigned_to_user_name ||
    asset.current_assignee_name ||
    '—'
  );
}

export function ITAssetsPage() {
  const { user } = useAuth();
  const access = accessContextFromUser(user);
  const canManage = canManageItAssets(access);
  const canAssign = canAssignItAssets(access);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ITAsset | null>(null);
  const [form, setForm] = useState<AssetFormState>(emptyForm);
  const [deleteTarget, setDeleteTarget] = useState<ITAsset | null>(null);
  const [assignTarget, setAssignTarget] = useState<ITAsset | null>(null);
  const [returnTarget, setReturnTarget] = useState<ITAsset | null>(null);
  const [transferTarget, setTransferTarget] = useState<ITAsset | null>(null);
  const [assignUserId, setAssignUserId] = useState('');
  const [assignDate, setAssignDate] = useState(new Date().toISOString().slice(0, 10));
  const [assignNotes, setAssignNotes] = useState('');
  const [returnDate, setReturnDate] = useState(new Date().toISOString().slice(0, 10));
  const [returnCondition, setReturnCondition] = useState('good');
  const [returnNotes, setReturnNotes] = useState('');
  const [transferUserId, setTransferUserId] = useState('');
  const [transferDate, setTransferDate] = useState(new Date().toISOString().slice(0, 10));
  const [transferNotes, setTransferNotes] = useState('');

  const assetTypesQuery = useQuery({
    queryKey: itOperationsKeys.assetTypes(),
    queryFn: fetchAssetTypes,
  });

  const usersQuery = useQuery({
    queryKey: ['lookups', 'users'],
    queryFn: () => fetchUsers(),
    enabled: canAssign,
  });

  const listFilters = useMemo(
    () => ({
      status: statusFilter || undefined,
      q: search.trim() || undefined,
    }),
    [search, statusFilter],
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
      width: DATA_GRID_ACTIONS_COLUMN_WIDTH + (canAssign ? 72 : 0),
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Stack direction="row" spacing={0.25} alignItems="center" onClick={(e) => e.stopPropagation()}>
          {canManage ? (
            <TableRowActions
              onEdit={() => openEdit(params.row)}
              deleteAction={
                <ProsohmButton
                  buttonVariant="ghost"
                  size="small"
                  aria-label="Delete asset"
                  onClick={() => setDeleteTarget(params.row)}
                  sx={{ minWidth: 0, px: 0.75 }}
                >
                  <DeleteOutlineIcon fontSize="small" />
                </ProsohmButton>
              }
            />
          ) : null}
          {canAssign && params.row.status === 'available' ? (
            <ProsohmButton
              buttonVariant="ghost"
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
                buttonVariant="ghost"
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
                buttonVariant="ghost"
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
        </Stack>
      ),
    },
  ];

  return (
    <PageContainer>
      <PageHeader
        title="IT Assets"
        subtitle="Track hardware inventory, ownership, and lifecycle status."
        action={
          canManage ? (
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
        <FormSelect
          label="Status"
          value={statusFilter}
          onChange={(event) => setStatusFilter(String(event.target.value))}
          options={ASSET_STATUS_OPTIONS}
          sx={{ minWidth: 180 }}
        />
      </SearchToolbar>

      <ContentCard noPadding>
        <ServerPaginatedDataGrid<ITAsset, ITAsset>
          queryKey={['it', 'assets']}
          fetcher={fetchAssetsPaginated}
          filters={listFilters}
          columns={columns}
          getRowId={(row) => row.id}
          autoHeight
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
                InputLabelProps={{ shrink: true }}
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
              label="Warranty expiry"
              type="date"
              value={form.warranty_expiry}
              onChange={(event) =>
                setForm((current) => ({ ...current, warranty_expiry: event.target.value }))
              }
              InputLabelProps={{ shrink: true }}
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
            InputLabelProps={{ shrink: true }}
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
          <ProsohmButton buttonVariant="ghost" onClick={() => setAssignTarget(null)}>
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
            InputLabelProps={{ shrink: true }}
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
          <ProsohmButton buttonVariant="ghost" onClick={() => setReturnTarget(null)}>
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
            InputLabelProps={{ shrink: true }}
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
          <ProsohmButton buttonVariant="ghost" onClick={() => setTransferTarget(null)}>
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
    </PageContainer>
  );
}
