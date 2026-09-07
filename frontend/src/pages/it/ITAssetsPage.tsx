import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
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
  createMasterMake,
  createMasterModel,
  createMasterSupplier,
  deleteAsset,
  fetchAssetIds,
  fetchMasterCategories,
  fetchMasterMakes,
  fetchMasterModels,
  fetchMasterSuppliers,
  fetchMasterTypes,
  fetchNextAssetNumber,
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
import type { ITAsset, ITAssetCreate, ITAssetUpdate } from '../../types/itOperations';
import { formatCellValue, formatDate, userDisplayName } from '../../utils/format';
import { optionalString, validateRequiredFields } from '../../utils/formValues';
import {
  accessContextFromUser,
  canAssignItAssets,
  canManageItAssets,
  canOverrideItAssetNumber,
  canReturnCustomerAssets,
} from '../../utils/permissions';

const ADD_NEW_MAKE = '__add_new_make__';
const ADD_NEW_MODEL = '__add_new_model__';
const ADD_NEW_SUPPLIER = '__add_new_supplier__';
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
  category: string;
  asset_type_id: string;
  make_id: string;
  model_id: string;
  supplier_id: string;
  serial_number: string;
  asset_number_override: string;
  purchase_date: string;
  purchase_cost: string;
  warranty_expiry: string;
  location: string;
  notes: string;
  status: string;
};

const emptyForm: AssetFormState = {
  category: '',
  asset_type_id: '',
  make_id: '',
  model_id: '',
  supplier_id: '',
  serial_number: '',
  asset_number_override: '',
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
  const canOverrideNumber = canOverrideItAssetNumber(access);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [inventoryScope, setInventoryScope] = useState(defaultInventoryScope);
  const [ownershipFilter, setOwnershipFilter] = useState('');
  const [warrantyFilter, setWarrantyFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [makeFilter, setMakeFilter] = useState('');
  const [modelFilter, setModelFilter] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ITAsset | null>(null);
  const [form, setForm] = useState<AssetFormState>(emptyForm);
  const [addMakeOpen, setAddMakeOpen] = useState(false);
  const [addModelOpen, setAddModelOpen] = useState(false);
  const [addSupplierOpen, setAddSupplierOpen] = useState(false);
  const [newMakeName, setNewMakeName] = useState('');
  const [newModelName, setNewModelName] = useState('');
  const [newSupplierName, setNewSupplierName] = useState('');
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

  const categoriesQuery = useQuery({
    queryKey: itOperationsKeys.masterCategories(),
    queryFn: () => fetchMasterCategories({ active_only: true }),
    enabled: formOpen,
  });

  const typesQuery = useQuery({
    queryKey: itOperationsKeys.masterTypes(form.category || undefined),
    queryFn: () =>
      fetchMasterTypes({
        category: form.category || undefined,
        active_only: true,
      }),
    enabled: formOpen && Boolean(form.category),
  });

  const makesQuery = useQuery({
    queryKey: itOperationsKeys.masterMakes(form.asset_type_id || undefined),
    queryFn: () =>
      fetchMasterMakes({
        asset_type_id: form.asset_type_id || undefined,
        active_only: true,
      }),
    enabled: formOpen && Boolean(form.asset_type_id),
  });

  const modelsQuery = useQuery({
    queryKey: itOperationsKeys.masterModels(
      form.make_id || undefined,
      form.asset_type_id || undefined,
    ),
    queryFn: () =>
      fetchMasterModels({
        make_id: form.make_id || undefined,
        asset_type_id: form.asset_type_id || undefined,
        active_only: true,
      }),
    enabled: formOpen && Boolean(form.make_id) && Boolean(form.asset_type_id),
  });

  const suppliersQuery = useQuery({
    queryKey: itOperationsKeys.masterSuppliers(),
    queryFn: () => fetchMasterSuppliers({ active_only: true }),
    enabled: formOpen,
  });

  const nextNumberQuery = useQuery({
    queryKey: itOperationsKeys.nextAssetNumber(form.asset_type_id),
    queryFn: () => fetchNextAssetNumber(form.asset_type_id),
    enabled: formOpen && !editing && Boolean(form.asset_type_id),
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

  const filterCategoriesQuery = useQuery({
    queryKey: itOperationsKeys.masterCategories(),
    queryFn: () => fetchMasterCategories({ active_only: true }),
  });

  const filterMakesQuery = useQuery({
    queryKey: itOperationsKeys.masterMakes(),
    queryFn: () => fetchMasterMakes({ active_only: true }),
  });

  const filterModelsQuery = useQuery({
    queryKey: itOperationsKeys.masterModels(makeFilter || undefined),
    queryFn: () =>
      fetchMasterModels({ make_id: makeFilter || undefined, active_only: true }),
  });

  const categoryFilterOptions = useMemo(
    () => [
      { value: '', label: 'All categories' },
      ...(filterCategoriesQuery.data ?? []).map((row) => ({
        value: row.code,
        label: row.name,
      })),
    ],
    [filterCategoriesQuery.data],
  );

  const makeFilterOptions = useMemo(
    () => [
      { value: '', label: 'All makes' },
      ...(filterMakesQuery.data ?? []).map((row) => ({ value: row.id, label: row.name })),
    ],
    [filterMakesQuery.data],
  );

  const modelFilterOptions = useMemo(
    () => [
      { value: '', label: 'All models' },
      ...(filterModelsQuery.data ?? []).map((row) => ({ value: row.id, label: row.name })),
    ],
    [filterModelsQuery.data],
  );

  const listFilters = useMemo(
    () => ({
      status: statusFilter || undefined,
      q: search.trim() || undefined,
      inventory_scope: statusFilter ? 'all' : inventoryScope,
      purchased_by: ownershipFilter || undefined,
      warranty_status: warrantyFilter || undefined,
      category: categoryFilter || undefined,
      make_id: makeFilter || undefined,
      model_id: modelFilter || undefined,
    }),
    [
      search,
      statusFilter,
      inventoryScope,
      ownershipFilter,
      warrantyFilter,
      categoryFilter,
      makeFilter,
      modelFilter,
    ],
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
      const makeName =
        (makesQuery.data ?? []).find((m) => m.id === form.make_id)?.name ?? null;
      const modelName =
        (modelsQuery.data ?? []).find((m) => m.id === form.model_id)?.name ?? null;

      if (editing) {
        const payload: ITAssetUpdate = {
          asset_type_id: form.asset_type_id,
          serial_number: optionalString(form.serial_number),
          make: makeName,
          model: modelName,
          supplier_id: optionalString(form.supplier_id),
          purchase_date: optionalString(form.purchase_date),
          purchase_cost: form.purchase_cost.trim()
            ? Number(form.purchase_cost)
            : null,
          warranty_expiry: optionalString(form.warranty_expiry),
          location: optionalString(form.location),
          notes: optionalString(form.notes),
          status: optionalString(form.status) ?? 'available',
        };
        return updateAsset(editing.id, payload);
      }

      const override = optionalString(form.asset_number_override);
      const suggested = nextNumberQuery.data?.asset_number?.trim() || '';
      const payload: ITAssetCreate = {
        asset_type_id: form.asset_type_id,
        serial_number: optionalString(form.serial_number),
        make_id: optionalString(form.make_id),
        model_id: optionalString(form.model_id),
        supplier_id: optionalString(form.supplier_id),
        make: makeName,
        model: modelName,
        purchase_date: optionalString(form.purchase_date),
        purchase_cost: form.purchase_cost.trim()
          ? Number(form.purchase_cost)
          : null,
        warranty_expiry: optionalString(form.warranty_expiry),
        location: optionalString(form.location),
        notes: optionalString(form.notes),
      };
      if (canOverrideNumber && override && override !== suggested) {
        payload.asset_number = override;
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

  const createMakeMutation = useMutation({
    mutationFn: () =>
      createMasterMake({
        name: newMakeName.trim(),
        asset_type_id: form.asset_type_id || null,
      }),
    onSuccess: (created) => {
      showSuccess('Make added.');
      setAddMakeOpen(false);
      setNewMakeName('');
      setForm((current) => ({ ...current, make_id: created.id, model_id: '' }));
      void queryClient.invalidateQueries({
        queryKey: itOperationsKeys.masterMakes(form.asset_type_id || undefined),
      });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const createModelMutation = useMutation({
    mutationFn: () =>
      createMasterModel({
        name: newModelName.trim(),
        make_id: form.make_id,
        asset_type_id: form.asset_type_id,
      }),
    onSuccess: (created) => {
      showSuccess('Model added.');
      setAddModelOpen(false);
      setNewModelName('');
      setForm((current) => ({ ...current, model_id: created.id }));
      void queryClient.invalidateQueries({
        queryKey: itOperationsKeys.masterModels(
          form.make_id || undefined,
          form.asset_type_id || undefined,
        ),
      });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const createSupplierMutation = useMutation({
    mutationFn: () => createMasterSupplier({ name: newSupplierName.trim() }),
    onSuccess: (created) => {
      showSuccess('Supplier added.');
      setAddSupplierOpen(false);
      setNewSupplierName('');
      setForm((current) => ({ ...current, supplier_id: created.id }));
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.masterSuppliers() });
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

  const categoryOptions = useMemo(
    () =>
      (categoriesQuery.data ?? []).map((category) => ({
        value: category.code,
        label: category.name,
      })),
    [categoriesQuery.data],
  );

  const assetTypeOptions = useMemo(
    () =>
      (typesQuery.data ?? [])
        .filter((type) => type.is_active !== false)
        .map((type) => ({ value: type.id, label: `${type.name} (${type.code})` })),
    [typesQuery.data],
  );

  const makeOptions = useMemo(() => {
    const rows = (makesQuery.data ?? []).map((make) => ({
      value: make.id,
      label: make.name,
    }));
    return [...rows, { value: ADD_NEW_MAKE, label: '+ Add new make' }];
  }, [makesQuery.data]);

  const modelOptions = useMemo(() => {
    const rows = (modelsQuery.data ?? []).map((model) => ({
      value: model.id,
      label: model.name,
    }));
    return [...rows, { value: ADD_NEW_MODEL, label: '+ Add new model' }];
  }, [modelsQuery.data]);

  const supplierOptions = useMemo(() => {
    const rows = (suppliersQuery.data ?? []).map((supplier) => ({
      value: supplier.id,
      label: supplier.name,
    }));
    return [...rows, { value: ADD_NEW_SUPPLIER, label: '+ Add new supplier' }];
  }, [suppliersQuery.data]);

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
      category: '',
      asset_type_id: asset.asset_type_id,
      make_id: asset.make_id ?? '',
      model_id: asset.model_id ?? '',
      supplier_id: asset.supplier_id ?? '',
      serial_number: asset.serial_number ?? '',
      asset_number_override: '',
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

  const editTypesBootstrapQuery = useQuery({
    queryKey: [...itOperationsKeys.masterTypes(), 'edit-bootstrap'],
    queryFn: () => fetchMasterTypes({ active_only: true }),
    enabled: formOpen && Boolean(editing) && !form.category && Boolean(form.asset_type_id),
  });

  useEffect(() => {
    if (!editing || !formOpen) return;
    const bootstrapType = (editTypesBootstrapQuery.data ?? []).find(
      (t) => t.id === editing.asset_type_id,
    );
    const typedType = (typesQuery.data ?? []).find((t) => t.id === editing.asset_type_id);
    const categoryCode = String(
      typedType?.category || bootstrapType?.category || '',
    );
    if (categoryCode && !form.category) {
      setForm((current) =>
        current.category ? current : { ...current, category: categoryCode },
      );
    }
  }, [
    editing,
    formOpen,
    form.category,
    editTypesBootstrapQuery.data,
    typesQuery.data,
  ]);

  useEffect(() => {
    if (!editing || !formOpen) return;
    if (!form.make_id && editing.make && makesQuery.data?.length) {
      const matchedMake = makesQuery.data.find(
        (m) => m.name.toLowerCase() === editing.make!.toLowerCase(),
      );
      if (matchedMake) {
        setForm((current) =>
          current.make_id ? current : { ...current, make_id: matchedMake.id },
        );
      }
    }
  }, [editing, formOpen, form.make_id, makesQuery.data]);

  useEffect(() => {
    if (!editing || !formOpen) return;
    if (!form.model_id && editing.model && modelsQuery.data?.length) {
      const matchedModel = modelsQuery.data.find(
        (m) => m.name.toLowerCase() === editing.model!.toLowerCase(),
      );
      if (matchedModel) {
        setForm((current) =>
          current.model_id ? current : { ...current, model_id: matchedModel.id },
        );
      }
    }
  }, [editing, formOpen, form.model_id, modelsQuery.data]);

  const handleSave = (event?: FormEvent) => {
    event?.preventDefault();
    const validationError = validateRequiredFields(
      {
        category: form.category,
        asset_type_id: form.asset_type_id,
      },
      [
        { key: 'category', label: 'Category' },
        { key: 'asset_type_id', label: 'Asset type' },
      ],
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
        <FormSelect
          label="Category"
          value={categoryFilter}
          onChange={(event) => setCategoryFilter(String(event.target.value))}
          options={categoryFilterOptions}
          sx={{ minWidth: 180 }}
        />
        <FormSelect
          label="Make"
          value={makeFilter}
          onChange={(event) => {
            setMakeFilter(String(event.target.value));
            setModelFilter('');
          }}
          options={makeFilterOptions}
          sx={{ minWidth: 180 }}
        />
        <FormSelect
          label="Model"
          value={modelFilter}
          onChange={(event) => setModelFilter(String(event.target.value))}
          options={modelFilterOptions}
          sx={{ minWidth: 180 }}
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
        subtitle={
          editing
            ? 'Update identity and purchase details.'
            : 'Select category and type to suggest the next asset number.'
        }
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
              label="Category"
              required
              value={form.category}
              onChange={(event) => {
                const category = String(event.target.value);
                setForm((current) => ({
                  ...current,
                  category,
                  asset_type_id: '',
                  make_id: '',
                  model_id: '',
                  asset_number_override: '',
                }));
              }}
              options={categoryOptions}
              placeholder="Select category"
            />
            <FormSelect
              label="Asset type"
              required
              value={form.asset_type_id}
              disabled={!form.category}
              onChange={(event) => {
                const asset_type_id = String(event.target.value);
                setForm((current) => ({
                  ...current,
                  asset_type_id,
                  make_id: '',
                  model_id: '',
                  asset_number_override: '',
                }));
              }}
              options={assetTypeOptions}
              placeholder={form.category ? 'Select type' : 'Select category first'}
            />
            {!editing ? (
              <FormField
                label="Suggested asset number"
                value={
                  form.asset_type_id
                    ? nextNumberQuery.data?.asset_number ??
                      (nextNumberQuery.isFetching ? 'Loading…' : '')
                    : ''
                }
                slotProps={{ input: { readOnly: true } }}
                helper="Assigned automatically on create. Serial number is separate."
              />
            ) : (
              <FormField
                label="Asset number"
                value={editing.asset_number}
                slotProps={{ input: { readOnly: true } }}
              />
            )}
            {!editing && canOverrideNumber ? (
              <FormField
                label="Override asset number"
                value={form.asset_number_override}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    asset_number_override: event.target.value,
                  }))
                }
                helper="Leave blank to use the suggested number."
                placeholder={nextNumberQuery.data?.asset_number ?? ''}
              />
            ) : null}
            <FormField
              label="Serial number"
              value={form.serial_number}
              onChange={(event) =>
                setForm((current) => ({ ...current, serial_number: event.target.value }))
              }
            />
            <FormSelect
              label="Make"
              value={form.make_id}
              disabled={!form.asset_type_id}
              onChange={(event) => {
                const value = String(event.target.value);
                if (value === ADD_NEW_MAKE) {
                  setAddMakeOpen(true);
                  return;
                }
                setForm((current) => ({ ...current, make_id: value, model_id: '' }));
              }}
              options={makeOptions}
              placeholder={form.asset_type_id ? 'Select make' : 'Select type first'}
            />
            <FormSelect
              label="Model"
              value={form.model_id}
              disabled={!form.make_id}
              onChange={(event) => {
                const value = String(event.target.value);
                if (value === ADD_NEW_MODEL) {
                  setAddModelOpen(true);
                  return;
                }
                setForm((current) => ({ ...current, model_id: value }));
              }}
              options={modelOptions}
              placeholder={form.make_id ? 'Select model' : 'Select make first'}
            />
            <FormSelect
              label="Supplier"
              value={form.supplier_id}
              onChange={(event) => {
                const value = String(event.target.value);
                if (value === ADD_NEW_SUPPLIER) {
                  setAddSupplierOpen(true);
                  return;
                }
                setForm((current) => ({ ...current, supplier_id: value }));
              }}
              options={supplierOptions}
              placeholder="Select supplier"
            />
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

      <Dialog open={addMakeOpen} onClose={() => setAddMakeOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Add make</DialogTitle>
        <DialogContent>
          <FormField
            label="Make / brand"
            value={newMakeName}
            onChange={(event) => setNewMakeName(event.target.value)}
            autoFocus
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setAddMakeOpen(false)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={createMakeMutation.isPending}
            disabled={!newMakeName.trim() || !form.asset_type_id}
            onClick={() => createMakeMutation.mutate()}
          >
            Add make
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <Dialog open={addModelOpen} onClose={() => setAddModelOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Add model</DialogTitle>
        <DialogContent>
          <FormField
            label="Model"
            value={newModelName}
            onChange={(event) => setNewModelName(event.target.value)}
            autoFocus
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setAddModelOpen(false)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={createModelMutation.isPending}
            disabled={!newModelName.trim() || !form.make_id || !form.asset_type_id}
            onClick={() => createModelMutation.mutate()}
          >
            Add model
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <Dialog
        open={addSupplierOpen}
        onClose={() => setAddSupplierOpen(false)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>Add supplier</DialogTitle>
        <DialogContent>
          <FormField
            label="Supplier name"
            value={newSupplierName}
            onChange={(event) => setNewSupplierName(event.target.value)}
            autoFocus
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setAddSupplierOpen(false)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={createSupplierMutation.isPending}
            disabled={!newSupplierName.trim()}
            onClick={() => createSupplierMutation.mutate()}
          >
            Add supplier
          </ProsohmButton>
        </DialogActions>
      </Dialog>

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
