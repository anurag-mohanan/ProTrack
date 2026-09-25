import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import AssignmentReturnRoundedIcon from '@mui/icons-material/AssignmentReturnRounded';
import BuildRoundedIcon from '@mui/icons-material/BuildRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import FactCheckRoundedIcon from '@mui/icons-material/FactCheckRounded';
import HistoryRoundedIcon from '@mui/icons-material/HistoryRounded';
import InventoryRoundedIcon from '@mui/icons-material/InventoryRounded';
import LanRoundedIcon from '@mui/icons-material/LanRounded';
import PersonAddAlt1RoundedIcon from '@mui/icons-material/PersonAddAlt1Rounded';
import SwapHorizRoundedIcon from '@mui/icons-material/SwapHorizRounded';
import UndoRoundedIcon from '@mui/icons-material/UndoRounded';
import type { GridColDef, GridRowClassNameParams } from '@mui/x-data-grid';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  assignAsset,
  allocateIp,
  checkAssetDuplicates,
  createAsset,
  fetchAsset,
  createMasterMake,
  createMasterModel,
  createMasterSupplier,
  deleteAsset,
  fetchAssetAssignments,
  fetchAssetChildren,
  fetchAssetIds,
  fetchAssignmentPreview,
  fetchRecommendedComputers,
  fetchMasterCategories,
  fetchMasterMakes,
  fetchMasterModels,
  fetchMasterSuppliers,
  fetchMasterTypes,
  fetchNextAssetNumber,
  fetchSuggestedComputerName,
  fetchSuggestedIp,
  fetchAssetsPaginated,
  itOperationsKeys,
  returnAsset,
  returnAssetToCustomer,
  transferAsset,
  updateAsset,
} from '../../api/itOperations';
import { fetchCustomers, fetchUsers } from '../../api/lookups';
import { fetchShifts } from '../../api/resourceShifts';
import { getErrorMessage } from '../../api/client';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ITAreaTabs } from '../../components/it/ITAreaTabs';
import { IT_ASSET_AREA_TABS } from '../../components/it/itAreaTabConfig';
import { ServerPaginatedDataGrid } from '../../components/common/ServerPaginatedDataGrid';
import { AssetBulkActionBar } from '../../components/it/AssetBulkActionBar';
import { AssetLifecycleDrawer } from '../../components/it/AssetLifecycleDrawer';
import { AssignmentAvailabilityPanel } from '../../components/it/AssignmentAvailabilityPanel';
import { ResourcePlanningDataQualityPanel } from '../../components/resource-planning/ResourcePlanningDataQualityPanel';
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
  canAllocateItIps,
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
  { value: 'lost', label: 'Lost' },
  { value: 'damaged', label: 'Damaged' },
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
  computer_name: string;
  mac_address: string;
  allocate_ip: boolean;
  service_tag: string;
  computer_name_reason: string;
  purchased_by: string;
  owner_customer_id: string;
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
  computer_name: '',
  mac_address: '',
  allocate_ip: true,
  service_tag: '',
  computer_name_reason: '',
  purchased_by: 'organization',
  owner_customer_id: '',
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
  const canAllocateIp = canAllocateItIps(access);
  const canReturnToCustomer = canReturnCustomerAssets(access);
  const canOverrideNumber = canOverrideItAssetNumber(access);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState(() => searchParams.get('search') ?? searchParams.get('q') ?? '');
  const urlView = searchParams.get('view') ?? '';
  const warrantyWithinDays = Number(searchParams.get('warranty_within_days')) || undefined;
  const urlStatus = searchParams.get('status');
  const categoryFilter = searchParams.get('category') ?? '';
  const statusFilter =
    urlStatus === 'all' ? '' : urlStatus ? urlStatus : urlView === 'assignments' ? 'assigned' : '';
  const [inventoryScope, setInventoryScope] = useState(defaultInventoryScope);
  const effectiveInventoryScope =
    defaultInventoryScope === 'returned'
      ? 'returned'
      : urlView === 'history'
        ? 'all'
        : inventoryScope;
  const [ownershipFilter, setOwnershipFilter] = useState('');
  const [warrantyFilter, setWarrantyFilter] = useState(
    () => searchParams.get('warranty_status') ?? '',
  );
  const [makeFilter, setMakeFilter] = useState('');
  const [modelFilter, setModelFilter] = useState('');
  const [availabilityShiftId, setAvailabilityShiftId] = useState(
    () => searchParams.get('availability_shift_id') ?? '',
  );
  const [availabilityStatus, setAvailabilityStatus] = useState(
    () => searchParams.get('availability_status') ?? '',
  );

  const patchSearchParams = useCallback(
    (mutate: (next: URLSearchParams) => void) => {
      const next = new URLSearchParams(searchParams);
      mutate(next);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const applyCategoryFilter = useCallback(
    (value: string) => {
      patchSearchParams((next) => {
        if (value) next.set('category', value);
        else next.delete('category');
      });
    },
    [patchSearchParams],
  );

  const applyStatusFilter = useCallback(
    (value: string) => {
      patchSearchParams((next) => {
        if (!value) {
          if (urlView === 'assignments') next.set('status', 'all');
          else next.delete('status');
        } else {
          next.set('status', value);
        }
      });
    },
    [patchSearchParams, urlView],
  );
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
  const [historyTarget, setHistoryTarget] = useState<ITAsset | null>(null);
  const [qualityOpen, setQualityOpen] = useState(() => searchParams.get('data_quality') === '1');
  const [ipTarget, setIpTarget] = useState<ITAsset | null>(null);
  const [assignUserId, setAssignUserId] = useState('');
  const [assignShiftId, setAssignShiftId] = useState('');
  const [assignDate, setAssignDate] = useState(new Date().toISOString().slice(0, 10));
  const [assignNotes, setAssignNotes] = useState('');
  const [returnDate, setReturnDate] = useState(new Date().toISOString().slice(0, 10));
  const [returnCondition, setReturnCondition] = useState('good');
  const [returnNotes, setReturnNotes] = useState('');
  const [returnAssignmentId, setReturnAssignmentId] = useState('');
  const [transferUserId, setTransferUserId] = useState('');
  const [transferDate, setTransferDate] = useState(new Date().toISOString().slice(0, 10));
  const [transferNotes, setTransferNotes] = useState('');
  const [transferIncludeChildren, setTransferIncludeChildren] = useState(false);
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

  const selectedType = (typesQuery.data ?? []).find((row) => row.id === form.asset_type_id);
  const isComputerType = (selectedType?.category || form.category) === 'computer';
  const showNetworkFields =
    isComputerType || (selectedType?.category || form.category) === 'network_equipment';

  const nameSuggestQuery = useQuery({
    queryKey: itOperationsKeys.suggestComputerName(selectedType?.code),
    queryFn: () => fetchSuggestedComputerName(selectedType?.code),
    enabled: formOpen && !editing && isComputerType,
  });

  const ipSuggestQuery = useQuery({
    queryKey: itOperationsKeys.suggestIp(form.computer_name || nameSuggestQuery.data?.computer_name),
    queryFn: () =>
      fetchSuggestedIp({
        computer_name: form.computer_name || nameSuggestQuery.data?.computer_name,
      }),
    enabled: formOpen && !editing && showNetworkFields,
  });

  const duplicateQuery = useQuery({
    queryKey: itOperationsKeys.duplicates({
      asset_number: form.asset_number_override,
      computer_name: form.computer_name,
      serial_number: form.serial_number,
      service_tag: form.service_tag,
      mac_address: form.mac_address,
      ip_address: ipSuggestQuery.data?.address ?? undefined,
      exclude_asset_id: editing?.id,
    }),
    queryFn: () =>
      checkAssetDuplicates({
        asset_number: optionalString(form.asset_number_override) ?? undefined,
        computer_name: optionalString(form.computer_name) ?? undefined,
        serial_number: optionalString(form.serial_number) ?? undefined,
        service_tag: optionalString(form.service_tag) ?? undefined,
        mac_address: optionalString(form.mac_address) ?? undefined,
        ip_address: form.allocate_ip ? ipSuggestQuery.data?.address ?? undefined : undefined,
        exclude_asset_id: editing?.id,
      }),
    enabled: formOpen,
  });

  const assignPreviewQuery = useQuery({
    queryKey: itOperationsKeys.assignmentPreview(
      assignTarget?.id ?? '',
      assignUserId,
      assignShiftId,
    ),
    queryFn: () =>
      fetchAssignmentPreview(assignTarget!.id, {
        user_id: assignUserId || undefined,
        shift_id: assignShiftId || undefined,
      }),
    enabled: Boolean(assignTarget),
  });

  const ipSuggestForAssignQuery = useQuery({
    queryKey: itOperationsKeys.suggestIp(ipTarget?.computer_name ?? undefined),
    queryFn: () => fetchSuggestedIp({ computer_name: ipTarget?.computer_name ?? undefined }),
    enabled: Boolean(ipTarget),
  });

  const recommendQuery = useQuery({
    queryKey: itOperationsKeys.recommendComputers(assignUserId),
    queryFn: () => fetchRecommendedComputers(assignUserId),
    enabled: Boolean(assignTarget?.computer_id) && Boolean(assignUserId),
  });

  useEffect(() => {
    const checks = assignPreviewQuery.data?.checks ?? [];
    const needsShift = checks.some((row) => row.code === 'conflict' && !row.ok);
    const derivedShiftId = checks.find((row) => row.code === 'shift')?.shift_id;
    if (needsShift && derivedShiftId && !assignShiftId) {
      setAssignShiftId(derivedShiftId);
    }
  }, [assignPreviewQuery.data, assignShiftId]);

  useEffect(() => {
    if (editing || !nameSuggestQuery.data?.computer_name) return;
    setForm((current) =>
      current.computer_name
        ? current
        : { ...current, computer_name: nameSuggestQuery.data!.computer_name },
    );
  }, [nameSuggestQuery.data, editing]);

  const usersQuery = useQuery({
    queryKey: ['lookups', 'users'],
    queryFn: () => fetchUsers(),
    enabled: canAssign,
  });

  const shiftsQuery = useQuery({
    queryKey: ['resource-shifts', 'list', 'active'],
    queryFn: () => fetchShifts({ active_only: true }),
    enabled: Boolean(assignTarget) || Boolean(returnTarget),
  });

  const returnAssignmentsQuery = useQuery({
    queryKey: itOperationsKeys.assetAssignments(returnTarget?.id ?? ''),
    queryFn: () => fetchAssetAssignments(returnTarget!.id),
    enabled: Boolean(returnTarget?.id),
  });

  const transferChildrenQuery = useQuery({
    queryKey: itOperationsKeys.assetChildren(transferTarget?.id ?? ''),
    queryFn: () => fetchAssetChildren(transferTarget!.id),
    enabled: Boolean(transferTarget?.id),
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
      inventory_scope: statusFilter ? 'all' : effectiveInventoryScope,
      purchased_by: ownershipFilter || undefined,
      warranty_status: warrantyFilter || undefined,
      warranty_within_days: warrantyFilter ? warrantyWithinDays : undefined,
      category: categoryFilter || undefined,
      make_id: makeFilter || undefined,
      model_id: modelFilter || undefined,
      availability_shift_id: availabilityShiftId || undefined,
      availability_status: availabilityStatus || undefined,
    }),
    [
      search,
      statusFilter,
      effectiveInventoryScope,
      ownershipFilter,
      warrantyFilter,
      warrantyWithinDays,
      categoryFilter,
      makeFilter,
      modelFilter,
      availabilityShiftId,
      availabilityStatus,
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
          service_tag: optionalString(form.service_tag),
          purchased_by: optionalString(form.purchased_by) ?? 'organization',
          owner_customer_id:
            form.purchased_by === 'customer' ? optionalString(form.owner_customer_id) : null,
        };
        if (canOverrideNumber && optionalString(form.asset_number_override)) {
          payload.asset_number = optionalString(form.asset_number_override);
        }
        if (showNetworkFields) {
          payload.computer_name = optionalString(form.computer_name);
          payload.computer_name_reason = optionalString(form.computer_name_reason);
        }
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
        service_tag: optionalString(form.service_tag),
        purchased_by: optionalString(form.purchased_by) ?? 'organization',
        owner_customer_id:
          form.purchased_by === 'customer' ? optionalString(form.owner_customer_id) : null,
      };
      if (canOverrideNumber && override && override !== suggested) {
        payload.asset_number = override;
      }
      if (isComputerType || showNetworkFields) {
        payload.computer_name = optionalString(form.computer_name);
        payload.mac_address = optionalString(form.mac_address);
        payload.provision_computer = isComputerType;
        if (form.allocate_ip && ipSuggestQuery.data?.available && ipSuggestQuery.data.ip_address_id) {
          payload.ip_address_id = ipSuggestQuery.data.ip_address_id;
        }
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

  const allocateIpMutation = useMutation({
    mutationFn: () =>
      allocateIp({
        ip_address_id: ipSuggestForAssignQuery.data?.ip_address_id,
        assigned_to_asset_id: ipTarget!.id,
        hostname: ipTarget?.computer_name,
      }),
    onSuccess: () => {
      showSuccess('IP allocated to this computer.');
      setIpTarget(null);
      invalidateAssets();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const maintenanceMutation = useMutation({
    mutationFn: (asset: ITAsset) =>
      updateAsset(asset.id, {
        status: asset.status === 'maintenance' ? 'available' : 'maintenance',
      }),
    onSuccess: (row) => {
      showSuccess(
        row.status === 'maintenance'
          ? 'Asset marked as maintenance.'
          : 'Asset returned to available from maintenance.',
      );
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
        shift_id: optionalString(assignShiftId),
      }),
    onSuccess: () => {
      showSuccess('Asset assigned.');
      setAssignTarget(null);
      setAssignUserId('');
      setAssignShiftId('');
      setAssignNotes('');
      invalidateAssets();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const returnMutation = useMutation({
    mutationFn: () => {
      const openRows = (returnAssignmentsQuery.data ?? []).filter((row) => !row.returned_date);
      const resolvedAssignmentId =
        returnAssignmentId || (openRows.length === 1 ? openRows[0]?.id : undefined);
      const resolvedShift =
        openRows.length === 1 && !returnAssignmentId
          ? openRows[0]?.shift_id || undefined
          : undefined;
      return returnAsset(returnTarget!.id, {
        returned_date: optionalString(returnDate),
        return_condition: returnCondition,
        notes: optionalString(returnNotes),
        assignment_id: optionalString(resolvedAssignmentId || ''),
        shift_id: optionalString(resolvedShift || ''),
      });
    },
    onSuccess: () => {
      showSuccess('Asset returned.');
      setReturnTarget(null);
      setReturnNotes('');
      setReturnAssignmentId('');
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
        include_children: transferIncludeChildren,
      }),
    onSuccess: () => {
      showSuccess(
        transferIncludeChildren
          ? 'Asset and child assets transferred.'
          : 'Asset transferred.',
      );
      setTransferTarget(null);
      setTransferUserId('');
      setTransferNotes('');
      setTransferIncludeChildren(false);
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

  const shiftOptions = useMemo(
    () =>
      (shiftsQuery.data ?? []).map((shift) => ({
        value: shift.id,
        label: shift.display_label || shift.name || shift.code,
      })),
    [shiftsQuery.data],
  );

  const openReturnAssignments = useMemo(
    () => (returnAssignmentsQuery.data ?? []).filter((row) => !row.returned_date),
    [returnAssignmentsQuery.data],
  );

  const returnOccupantOptions = useMemo(
    () =>
      openReturnAssignments.map((row) => ({
        value: row.id,
        label: `${row.assigned_to_user_name || 'User'} — ${
          row.shift_display || row.shift_name || 'Legacy (no shift)'
        }`,
      })),
    [openReturnAssignments],
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
      computer_name: asset.computer_name ?? '',
      mac_address: asset.mac_address ?? '',
      allocate_ip: true,
      service_tag: asset.service_tag ?? '',
      computer_name_reason: '',
      purchased_by: asset.purchased_by || 'organization',
      owner_customer_id: asset.owner_customer_id ?? '',
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
    if (form.purchased_by === 'customer' && !optionalString(form.owner_customer_id)) {
      showError('Select the owner customer for a customer-owned asset.');
      return;
    }
    if (duplicateQuery.data?.ok === false) {
      showError(duplicateQuery.data.conflicts[0]?.message || 'A matching asset already exists.');
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
    ...(categoryFilter === 'peripheral'
      ? []
      : ([
          {
            field: 'computer_name',
            headerName: 'Computer',
            flex: 0.9,
            minWidth: 120,
            valueFormatter: (value) => formatCellValue(value) || '—',
          },
          {
            field: 'primary_ip',
            headerName: 'IP',
            width: 130,
            valueFormatter: (value) => formatCellValue(value) || '—',
          },
        ] as GridColDef<ITAsset>[])),
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
      headerName: 'User(s)',
      flex: 1,
      minWidth: 140,
      valueGetter: (_value, row) => assigneeName(row),
    },
    {
      field: 'current_assignee_team',
      headerName: 'Team',
      width: 120,
      valueFormatter: (value) => formatCellValue(value) || '—',
    },
    {
      field: 'virtual_seat_code',
      headerName: 'Virtual Seat',
      width: 140,
      renderCell: (params) =>
        params.row.virtual_seat_code ? (
          <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
            <Typography variant="body2">{params.row.virtual_seat_code}</Typography>
            {params.row.is_shared_seat ? (
              <Chip size="small" label="Shared" color="info" variant="outlined" />
            ) : null}
          </Stack>
        ) : (
          '—'
        ),
    },
    {
      field: 'shift_availability',
      headerName: 'Shift availability',
      flex: 1.6,
      minWidth: 280,
      sortable: false,
      renderCell: (params) => {
        const rows = params.row.shift_availability || [];
        if (!rows.length) {
          return formatCellValue(params.row.current_shift_display) || '—';
        }
        return (
          <Stack spacing={0.25} sx={{ py: 0.5 }}>
            {rows.map((s) => {
              const who =
                s.assignees
                  ?.map((a) => a.user_name)
                  .filter(Boolean)
                  .join(', ') || null;
              const color =
                s.status === 'AVAILABLE'
                  ? 'success'
                  : s.status === 'ASSIGNED'
                    ? 'info'
                    : s.status === 'CONFLICT' || s.status === 'UNAVAILABLE'
                      ? 'error'
                      : 'warning';
              return (
                <Stack
                  key={String(s.shift_code || s.shift_id || s.shift_name)}
                  direction="row"
                  spacing={0.5}
                  sx={{ alignItems: 'center' }}
                >
                  <Typography variant="caption" sx={{ minWidth: 72 }}>
                    {s.shift_name || s.shift_code}:
                  </Typography>
                  <Chip
                    size="small"
                    color={color}
                    label={who && s.status === 'ASSIGNED' ? `${s.status} — ${who}` : s.status}
                  />
                </Stack>
              );
            })}
          </Stack>
        );
      },
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width:
        DATA_GRID_ACTIONS_COLUMN_WIDTH +
        40 +
        (canAssign ? 72 : 0) +
        (canReturnToCustomer ? 40 : 0) +
        (canAllocateIp ? 40 : 0) +
        (canManage ? 40 : 0),
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Stack direction="row" spacing={0.25} onClick={(e) => e.stopPropagation()} sx={{ alignItems: 'center' }}>
          <ProsohmButton
            buttonVariant="outlined"
            size="small"
            aria-label="Asset lifecycle"
            title="Asset lifecycle"
            onClick={() => setHistoryTarget(params.row)}
            sx={{ minWidth: 0, px: 0.75 }}
          >
            <HistoryRoundedIcon fontSize="small" />
          </ProsohmButton>
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
              title="Assign"
              onClick={() => {
                setAssignTarget(params.row);
                setAssignUserId('');
                setAssignShiftId('');
                setAssignDate(new Date().toISOString().slice(0, 10));
                setAssignNotes('');
              }}
              sx={{ minWidth: 0, px: 0.75 }}
            >
              <PersonAddAlt1RoundedIcon fontSize="small" />
            </ProsohmButton>
          ) : null}
          {canAllocateIp && params.row.computer_id && !params.row.primary_ip ? (
            <ProsohmButton
              buttonVariant="outlined"
              size="small"
              aria-label="Assign IP"
              title="Assign IP"
              onClick={() => setIpTarget(params.row)}
              sx={{ minWidth: 0, px: 0.75 }}
            >
              <LanRoundedIcon fontSize="small" />
            </ProsohmButton>
          ) : null}
          {canManage &&
          !['retired', 'disposed', 'returned_to_customer'].includes(String(params.row.status)) ? (
            <ProsohmButton
              buttonVariant="outlined"
              size="small"
              aria-label={
                params.row.status === 'maintenance' ? 'Return from maintenance' : 'Mark maintenance'
              }
              title={
                params.row.status === 'maintenance' ? 'Return from maintenance' : 'Mark maintenance'
              }
              onClick={() => maintenanceMutation.mutate(params.row)}
              sx={{ minWidth: 0, px: 0.75 }}
            >
              <BuildRoundedIcon fontSize="small" />
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
                  setTransferIncludeChildren(false);
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

  const inventoryTitle =
    defaultInventoryScope === 'returned'
      ? 'Returned Assets'
      : urlView === 'assignments'
        ? 'Asset Assignments'
        : urlView === 'history'
          ? 'Asset History'
          : categoryFilter === 'peripheral'
            ? 'Peripherals & Equipment'
            : categoryFilter === 'network_equipment'
              ? 'Network Devices'
              : categoryFilter === 'computer'
                ? 'Computers'
                : 'Inventory';
  const inventorySubtitle =
    defaultInventoryScope === 'returned'
      ? 'Customer-owned assets returned from Prosohm custody (historical record retained).'
      : urlView === 'assignments'
        ? 'Current assignments from the authoritative asset relationship. Ownership is separate from who uses the asset.'
        : urlView === 'history'
          ? 'Current and historical assets. Open lifecycle on a row to see assignment, ownership, IP, and status history.'
          : categoryFilter === 'computer'
            ? 'Computer assets with name, IP, user, team, and shift on the same inventory record. Network/IP is not a separate module.'
            : 'Physical IT assets in one register. Filter by type and status instead of switching modules.';

  return (
    <PageContainer>
      <PageHeader
        title={inventoryTitle}
        subtitle={inventorySubtitle}
        action={
          <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
            <ProsohmButton
              buttonVariant="outlined"
              startIcon={<FactCheckRoundedIcon />}
              onClick={() => setQualityOpen(true)}
            >
              Data quality
            </ProsohmButton>
            {canManage && defaultInventoryScope !== 'returned' ? (
              <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
                {categoryFilter === 'computer' ? 'Add computer' : 'Add asset'}
              </ProsohmButton>
            ) : null}
          </Stack>
        }
      />
      <ITAreaTabs items={IT_ASSET_AREA_TABS} />

      <SearchToolbar sticky>
        <FormField
          label="Search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Asset number, serial, make…"
          sx={{ minWidth: 240, flex: 1, maxWidth: 420 }}
        />
        {defaultInventoryScope !== 'returned' && urlView !== 'history' ? (
          <FormSelect
            label="Inventory"
            value={effectiveInventoryScope}
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
          onChange={(event) => applyStatusFilter(String(event.target.value))}
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
          onChange={(event) => applyCategoryFilter(String(event.target.value))}
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
        <FormSelect
          label="Availability shift"
          value={availabilityShiftId}
          onChange={(event) => setAvailabilityShiftId(String(event.target.value))}
          options={[
            { value: '', label: 'Any shift' },
            ...(shiftsQuery.data ?? []).map((s) => ({
              value: s.id,
              label: `${s.name} (${s.start_time}–${s.end_time})`,
            })),
          ]}
          sx={{ minWidth: 220 }}
        />
        <FormSelect
          label="Shift availability"
          value={availabilityStatus}
          onChange={(event) => setAvailabilityStatus(String(event.target.value))}
          options={[
            { value: '', label: 'All' },
            { value: 'AVAILABLE', label: 'Available' },
            { value: 'ASSIGNED', label: 'Assigned' },
            { value: 'CONFLICT', label: 'Conflict' },
            { value: 'PARTIALLY_AVAILABLE', label: 'Partially available' },
            { value: 'UNAVAILABLE', label: 'Unavailable' },
          ]}
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
                helper={
                  nextNumberQuery.data?.message ||
                  'Assigned automatically on create. Serial number is separate.'
                }
              />
            ) : canOverrideNumber ? (
              <FormField
                label="Asset number"
                value={form.asset_number_override || editing.asset_number}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    asset_number_override: event.target.value,
                  }))
                }
                helper="Internal asset ID stays the same. Changing the number records history."
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
            <FormField
              label="Service tag"
              value={form.service_tag}
              onChange={(event) =>
                setForm((current) => ({ ...current, service_tag: event.target.value }))
              }
            />
            {(duplicateQuery.data?.conflicts ?? []).length > 0 ? (
              <Stack spacing={1}>
                {duplicateQuery.data!.conflicts.map((row) => (
                  <Alert key={`${row.field}-${row.value}`} severity="warning">
                    {row.message}
                    {row.href ? (
                      <>
                        {' '}
                        <RouterLink to={row.href}>Open existing record</RouterLink>
                      </>
                    ) : null}
                  </Alert>
                ))}
              </Stack>
            ) : null}
            {showNetworkFields ? (
              <>
                <FormField
                  label="Computer name"
                  value={form.computer_name}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, computer_name: event.target.value }))
                  }
                  helper={
                    !editing
                      ? nameSuggestQuery.data?.message || 'Suggested from existing computer names.'
                      : undefined
                  }
                  placeholder={nameSuggestQuery.data?.computer_name ?? ''}
                />
                {editing ? (
                  <FormField
                    label="Reason for name change"
                    value={form.computer_name_reason}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        computer_name_reason: event.target.value,
                      }))
                    }
                    helper="Recorded in computer name history. The internal asset ID does not change."
                  />
                ) : null}
                <FormField
                  label="MAC address"
                  value={form.mac_address}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, mac_address: event.target.value }))
                  }
                  placeholder="AA:BB:CC:DD:EE:FF"
                />
                {!editing ? (
                  <>
                    <FormField
                      label="Suggested IP"
                      value={
                        ipSuggestQuery.data?.address ??
                        (ipSuggestQuery.isFetching ? 'Loading…' : '')
                      }
                      slotProps={{ input: { readOnly: true } }}
                      helper={ipSuggestQuery.data?.message}
                    />
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={form.allocate_ip && Boolean(ipSuggestQuery.data?.available)}
                          disabled={!ipSuggestQuery.data?.available}
                          onChange={(event) =>
                            setForm((current) => ({
                              ...current,
                              allocate_ip: event.target.checked,
                            }))
                          }
                        />
                      }
                      label="Allocate the suggested IP on create"
                    />
                  </>
                ) : (
                  <FormField
                    label="Primary IP"
                    value={editing?.primary_ip ?? ''}
                    slotProps={{ input: { readOnly: true } }}
                    helper={editing?.network_cidr ? `Network ${editing.network_cidr}` : undefined}
                  />
                )}
              </>
            ) : null}
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
            <FormSelect
              label="Ownership"
              value={form.purchased_by}
              onChange={(event) => {
                const purchased_by = String(event.target.value);
                setForm((current) => ({
                  ...current,
                  purchased_by,
                  owner_customer_id: purchased_by === 'customer' ? current.owner_customer_id : '',
                }));
              }}
              options={OWNERSHIP_OPTIONS.filter((opt) => opt.value)}
            />
            {form.purchased_by === 'customer' ? (
              <FormSelect
                label="Owner customer"
                required
                value={form.owner_customer_id}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    owner_customer_id: String(event.target.value),
                  }))
                }
                options={customerOptions}
                placeholder="Select customer"
              />
            ) : null}
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
          <AssignmentAvailabilityPanel
            preview={assignPreviewQuery.data}
            loading={assignPreviewQuery.isFetching}
            recommendations={recommendQuery.data?.recommendations}
            currentAssetId={assignTarget?.id}
            onSelectRecommendation={(row) => {
              void fetchAsset(row.asset_id)
                .then((asset) => {
                  setAssignTarget(asset);
                  setAssignShiftId('');
                })
                .catch((error) => showError(getErrorMessage(error)));
            }}
          />
          <FormSelect
            label="Assignee"
            required
            value={assignUserId}
            onChange={(event) => {
              setAssignUserId(String(event.target.value));
              setAssignShiftId('');
            }}
            options={userOptions}
          />
          <FormSelect
            label="Shift slot (shared desk)"
            value={assignShiftId}
            onChange={(event) => setAssignShiftId(String(event.target.value))}
            options={[{ value: '', label: 'None (single assignee)' }, ...shiftOptions]}
            helper="Defaults from this person’s Resource Planning shift. Change only for a shared-desk slot."
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
            disabled={!assignUserId || (Boolean(assignUserId) && assignPreviewQuery.data?.ok === false)}
            onClick={() => assignMutation.mutate()}
          >
            Assign
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(ipTarget)} onClose={() => setIpTarget(null)} fullWidth maxWidth="sm">
        <DialogTitle>Assign IP</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <Typography variant="body2">
            {ipTarget?.computer_name || ipTarget?.asset_number}
            {ipTarget?.mac_address ? ` · MAC ${ipTarget.mac_address}` : ''}
          </Typography>
          {ipSuggestForAssignQuery.isFetching ? (
            <Typography variant="body2" color="text.secondary">
              Looking up the next free IP…
            </Typography>
          ) : ipSuggestForAssignQuery.data?.available && ipSuggestForAssignQuery.data.address ? (
            <Alert severity="info">
              Suggested {ipSuggestForAssignQuery.data.address}
              {ipSuggestForAssignQuery.data.network_cidr
                ? ` on ${ipSuggestForAssignQuery.data.network_name || ipSuggestForAssignQuery.data.network_cidr}`
                : ''}
              . {ipSuggestForAssignQuery.data.message}
            </Alert>
          ) : (
            <Alert severity="warning">
              {ipSuggestForAssignQuery.data?.message || 'No free IP is available to allocate.'}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setIpTarget(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={allocateIpMutation.isPending}
            disabled={!ipSuggestForAssignQuery.data?.ip_address_id}
            onClick={() => allocateIpMutation.mutate()}
          >
            Allocate suggested IP
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(returnTarget)} onClose={() => setReturnTarget(null)} fullWidth maxWidth="sm">
        <DialogTitle>Return asset</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          {openReturnAssignments.length > 1 ? (
            <FormSelect
              label="Return which occupant"
              required
              value={returnAssignmentId}
              onChange={(event) => setReturnAssignmentId(String(event.target.value))}
              options={returnOccupantOptions}
              helper="Shared desk has multiple open assignments — pick one."
            />
          ) : null}
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
            disabled={openReturnAssignments.length > 1 && !returnAssignmentId}
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
          {(transferChildrenQuery.data ?? []).length > 0 ? (
            <Box>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={transferIncludeChildren}
                    onChange={(event) => setTransferIncludeChildren(event.target.checked)}
                  />
                }
                label={`Also transfer ${transferChildrenQuery.data!.length} child asset(s)`}
              />
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                {(transferChildrenQuery.data ?? [])
                  .map((child) => child.asset_number)
                  .join(', ')}
              </Typography>
            </Box>
          ) : null}
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

      <Dialog
        open={qualityOpen}
        onClose={() => setQualityOpen(false)}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle>IT / Resource data quality</DialogTitle>
        <DialogContent dividers>
          {qualityOpen ? <ResourcePlanningDataQualityPanel /> : null}
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setQualityOpen(false)}>
            Close
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <AssetLifecycleDrawer asset={historyTarget} onClose={() => setHistoryTarget(null)} />
    </PageContainer>
  );
}
