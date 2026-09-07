import {
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
  type SyntheticEvent,
} from 'react';
import {
  Box,
  Stack,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CategoryRoundedIcon from '@mui/icons-material/CategoryRounded';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createAssetType,
  createMasterCategory,
  createMasterMake,
  createMasterModel,
  createMasterSupplier,
  fetchAssetTypes,
  fetchMasterCategories,
  fetchMasterMakes,
  fetchMasterModels,
  fetchMasterSuppliers,
  itOperationsKeys,
  mergeMasterMake,
  mergeMasterModel,
  setMasterActive,
} from '../../api/itOperations';
import { getErrorMessage } from '../../api/client';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingState } from '../../components/common/LoadingState';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
} from '../../components/ui/design-system';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import type { AssetTypeCategory, MasterKind } from '../../types/itOperations';
import { formatCellValue } from '../../utils/format';
import { validateRequiredFields } from '../../utils/formValues';
import {
  accessContextFromUser,
  canManageItAssets,
  userHasSpecial,
} from '../../utils/permissions';
import { SPECIAL_MANAGE_IT_SUPPLIERS } from '../../config/accessControl';

type TabKey = 'categories' | 'types' | 'makes' | 'models' | 'suppliers';

const TAB_KEYS: TabKey[] = ['categories', 'types', 'makes', 'models', 'suppliers'];

type MergeKind = 'makes' | 'models';

type MergeSource = { id: string; name: string; assetTypeId?: string };

type MasterTableRow = { key: string; cells: string[]; actions?: ReactNode };

const CATEGORY_OPTIONS: { value: AssetTypeCategory; label: string }[] = [
  { value: 'computer', label: 'Computer' },
  { value: 'peripheral', label: 'Peripheral' },
  { value: 'network_equipment', label: 'Network equipment' },
  { value: 'other', label: 'Other' },
];

export function ITMasterDataPage() {
  const { user } = useAuth();
  const access = accessContextFromUser(user);
  const canManageAssets = canManageItAssets(access);
  const canManageSuppliers =
    userHasSpecial(access, SPECIAL_MANAGE_IT_SUPPLIERS) || canManageAssets;
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const initialTab = searchParams.get('tab');
  const [tab, setTab] = useState<TabKey>(
    TAB_KEYS.includes(initialTab as TabKey) ? (initialTab as TabKey) : 'categories',
  );
  const [formOpen, setFormOpen] = useState(false);

  const [categoryName, setCategoryName] = useState('');
  const [categoryCode, setCategoryCode] = useState('');

  const [typeCode, setTypeCode] = useState('');
  const [typeName, setTypeName] = useState('');
  const [typeCategory, setTypeCategory] = useState<AssetTypeCategory>('other');
  const [typePrefix, setTypePrefix] = useState('');

  const [makeName, setMakeName] = useState('');
  const [makeAssetTypeId, setMakeAssetTypeId] = useState('');

  const [modelName, setModelName] = useState('');
  const [modelMakeId, setModelMakeId] = useState('');
  const [modelAssetTypeId, setModelAssetTypeId] = useState('');

  const [supplierName, setSupplierName] = useState('');
  const [supplierWebsite, setSupplierWebsite] = useState('');
  const [supplierPhone, setSupplierPhone] = useState('');
  const [supplierEmail, setSupplierEmail] = useState('');

  const [mergeKind, setMergeKind] = useState<MergeKind | null>(null);
  const [mergeSource, setMergeSource] = useState<MergeSource | null>(null);
  const [mergeTargetId, setMergeTargetId] = useState('');

  const categoriesQuery = useQuery({
    queryKey: itOperationsKeys.masterCategories(),
    queryFn: () => fetchMasterCategories({ active_only: false }),
  });

  const typesQuery = useQuery({
    queryKey: itOperationsKeys.assetTypes(),
    queryFn: fetchAssetTypes,
  });

  const makesQuery = useQuery({
    queryKey: itOperationsKeys.masterMakes(),
    queryFn: () => fetchMasterMakes({ active_only: false }),
  });

  const modelsQuery = useQuery({
    queryKey: itOperationsKeys.masterModels(),
    queryFn: () => fetchMasterModels({ active_only: false }),
  });

  const suppliersQuery = useQuery({
    queryKey: itOperationsKeys.masterSuppliers(),
    queryFn: () => fetchMasterSuppliers({ active_only: false }),
  });

  const typeOptions = useMemo(
    () =>
      (typesQuery.data ?? []).map((type) => ({
        value: type.id,
        label: `${type.name} (${type.code})`,
      })),
    [typesQuery.data],
  );

  const makeOptions = useMemo(
    () =>
      (makesQuery.data ?? []).map((make) => ({
        value: make.id,
        label: make.name,
      })),
    [makesQuery.data],
  );

  const typeNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const type of typesQuery.data ?? []) {
      map.set(type.id, type.name);
    }
    return map;
  }, [typesQuery.data]);

  const makeNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const make of makesQuery.data ?? []) {
      map.set(make.id, make.name);
    }
    return map;
  }, [makesQuery.data]);

  const invalidateMasters = () => {
    void queryClient.invalidateQueries({ queryKey: [...itOperationsKeys.all, 'master'] });
    void queryClient.invalidateQueries({ queryKey: itOperationsKeys.assetTypes() });
  };

  const resetForm = () => {
    setCategoryName('');
    setCategoryCode('');
    setTypeCode('');
    setTypeName('');
    setTypeCategory('other');
    setTypePrefix('');
    setMakeName('');
    setMakeAssetTypeId('');
    setModelName('');
    setModelMakeId('');
    setModelAssetTypeId('');
    setSupplierName('');
    setSupplierWebsite('');
    setSupplierPhone('');
    setSupplierEmail('');
  };

  const openAdd = () => {
    resetForm();
    setFormOpen(true);
  };

  const createMutation = useMutation({
    mutationFn: async () => {
      switch (tab) {
        case 'categories':
          return createMasterCategory({
            name: categoryName.trim(),
            code: categoryCode.trim() || undefined,
          });
        case 'types':
          return createAssetType({
            code: typeCode.trim(),
            name: typeName.trim(),
            category: typeCategory,
            numbering_prefix: typePrefix.trim() || null,
          });
        case 'makes':
          return createMasterMake({
            name: makeName.trim(),
            asset_type_id: makeAssetTypeId || null,
          });
        case 'models':
          return createMasterModel({
            name: modelName.trim(),
            make_id: modelMakeId,
            asset_type_id: modelAssetTypeId,
          });
        case 'suppliers':
          return createMasterSupplier({
            name: supplierName.trim(),
            website: supplierWebsite.trim() || null,
            phone: supplierPhone.trim() || null,
            email: supplierEmail.trim() || null,
          });
        default:
          return null;
      }
    },
    onSuccess: () => {
      showSuccess('Master record added.');
      setFormOpen(false);
      resetForm();
      invalidateMasters();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const activeMutation = useMutation({
    mutationFn: ({ kind, id, isActive }: { kind: MasterKind; id: string; isActive: boolean }) =>
      setMasterActive(kind, id, isActive),
    onSuccess: (_result, variables) => {
      showSuccess(
        variables.isActive
          ? 'Master record activated.'
          : 'Master record deactivated. Existing assets keep their history.',
      );
      invalidateMasters();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const closeMerge = () => {
    setMergeKind(null);
    setMergeSource(null);
    setMergeTargetId('');
  };

  const openMerge = (kind: MergeKind, source: MergeSource) => {
    setMergeKind(kind);
    setMergeSource(source);
    setMergeTargetId('');
  };

  const mergeMutation = useMutation({
    mutationFn: async () => {
      if (!mergeKind || !mergeSource || !mergeTargetId) return null;
      return mergeKind === 'makes'
        ? mergeMasterMake(mergeSource.id, mergeTargetId)
        : mergeMasterModel(mergeSource.id, mergeTargetId);
    },
    onSuccess: (result) => {
      showSuccess(result?.message ?? 'Master records merged.');
      closeMerge();
      invalidateMasters();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const mergeTargetOptions = useMemo(() => {
    if (!mergeKind || !mergeSource) return [];
    if (mergeKind === 'makes') {
      return (makesQuery.data ?? [])
        .filter((make) => make.id !== mergeSource.id && make.is_active !== false)
        .map((make) => ({ value: make.id, label: make.name }));
    }
    return (modelsQuery.data ?? [])
      .filter(
        (model) =>
          model.id !== mergeSource.id &&
          model.is_active !== false &&
          model.asset_type_id === mergeSource.assetTypeId,
      )
      .map((model) => ({
        value: model.id,
        label: `${makeNameById.get(model.make_id) || ''} ${model.name}`.trim(),
      }));
  }, [mergeKind, mergeSource, makesQuery.data, modelsQuery.data, makeNameById]);

  const renderActiveAction = (
    kind: MasterKind,
    row: { id: string; is_active?: boolean },
    allowed: boolean,
  ): ReactNode =>
    allowed ? (
      <ProsohmButton
        buttonVariant="outlined"
        size="small"
        disabled={activeMutation.isPending}
        onClick={() =>
          activeMutation.mutate({ kind, id: row.id, isActive: row.is_active === false })
        }
      >
        {row.is_active === false ? 'Activate' : 'Deactivate'}
      </ProsohmButton>
    ) : null;

  const canAdd =
    tab === 'suppliers' ? canManageSuppliers : canManageAssets;

  const handleSave = (event?: FormEvent) => {
    event?.preventDefault();
    let validationError: string | null = null;
    if (tab === 'categories') {
      validationError = validateRequiredFields({ name: categoryName }, [
        { key: 'name', label: 'Name' },
      ]);
    } else if (tab === 'types') {
      validationError = validateRequiredFields(
        { code: typeCode, name: typeName },
        [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
        ],
      );
    } else if (tab === 'makes') {
      validationError = validateRequiredFields({ name: makeName }, [
        { key: 'name', label: 'Name' },
      ]);
    } else if (tab === 'models') {
      validationError = validateRequiredFields(
        { name: modelName, make_id: modelMakeId, asset_type_id: modelAssetTypeId },
        [
          { key: 'name', label: 'Name' },
          { key: 'make_id', label: 'Make' },
          { key: 'asset_type_id', label: 'Asset type' },
        ],
      );
    } else {
      validationError = validateRequiredFields({ name: supplierName }, [
        { key: 'name', label: 'Name' },
      ]);
    }
    if (validationError) {
      showError(validationError);
      return;
    }
    createMutation.mutate();
  };

  const handleTabChange = (_event: SyntheticEvent, value: TabKey) => {
    setTab(value);
    setFormOpen(false);
    setSearchParams(value === 'categories' ? {} : { tab: value }, { replace: true });
  };

  const loading =
    categoriesQuery.isLoading ||
    typesQuery.isLoading ||
    makesQuery.isLoading ||
    modelsQuery.isLoading ||
    suppliersQuery.isLoading;

  const error =
    categoriesQuery.error ||
    typesQuery.error ||
    makesQuery.error ||
    modelsQuery.error ||
    suppliersQuery.error;

  if (loading) {
    return <LoadingState message="Loading master data…" />;
  }

  if (error) {
    return (
      <ErrorState
        error={error}
        title="Unable to load IT master data"
        onRetry={() => {
          void categoriesQuery.refetch();
          void typesQuery.refetch();
          void makesQuery.refetch();
          void modelsQuery.refetch();
          void suppliersQuery.refetch();
        }}
      />
    );
  }

  const addLabel =
    tab === 'categories'
      ? 'Add category'
      : tab === 'types'
        ? 'Add type'
        : tab === 'makes'
          ? 'Add make'
          : tab === 'models'
            ? 'Add model'
            : 'Add supplier';

  return (
    <PageContainer>
      <PageHeader
        title="IT Master Data"
        subtitle="Categories, types, makes, models, and suppliers used when registering assets."
        action={
          canAdd ? (
            <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openAdd}>
              {addLabel}
            </ProsohmButton>
          ) : undefined
        }
      />

      <ContentCard noPadding>
        <Tabs
          value={tab}
          onChange={handleTabChange}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ px: 2, borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab value="categories" label="Categories" />
          <Tab value="types" label="Types" />
          <Tab value="makes" label="Makes" />
          <Tab value="models" label="Models" />
          <Tab value="suppliers" label="Suppliers" />
        </Tabs>

        <Box sx={{ p: 2 }}>
          {tab === 'categories' ? (
            <MasterTable
              emptyTitle="No categories yet"
              headers={['Name', 'Code', 'Active', 'Usage']}
              actionsLabel={canManageAssets ? 'Actions' : undefined}
              rows={(categoriesQuery.data ?? []).map((row) => ({
                key: row.id,
                cells: [
                  row.name,
                  row.code,
                  row.is_active === false ? 'No' : 'Yes',
                  String(row.usage_count ?? 0),
                ],
                actions: renderActiveAction('categories', row, canManageAssets),
              }))}
            />
          ) : null}

          {tab === 'types' ? (
            <MasterTable
              emptyTitle="No asset types yet"
              headers={['Name', 'Code', 'Category', 'Prefix', 'Active']}
              actionsLabel={canManageAssets ? 'Actions' : undefined}
              rows={(typesQuery.data ?? []).map((row) => ({
                key: row.id,
                cells: [
                  row.name,
                  row.code,
                  String(row.category || '—'),
                  row.numbering_prefix || '—',
                  row.is_active === false ? 'No' : 'Yes',
                ],
                actions: renderActiveAction('types', row, canManageAssets),
              }))}
            />
          ) : null}

          {tab === 'makes' ? (
            <MasterTable
              emptyTitle="No makes yet"
              headers={['Name', 'Active', 'Usage']}
              actionsLabel={canManageAssets ? 'Actions' : undefined}
              rows={(makesQuery.data ?? []).map((row) => ({
                key: row.id,
                cells: [
                  row.name,
                  row.is_active === false ? 'No' : 'Yes',
                  String(row.usage_count ?? 0),
                ],
                actions: canManageAssets ? (
                  <Stack direction="row" spacing={1} sx={{ justifyContent: 'flex-end' }}>
                    <ProsohmButton
                      buttonVariant="outlined"
                      size="small"
                      disabled={row.is_active === false}
                      onClick={() => openMerge('makes', { id: row.id, name: row.name })}
                    >
                      Merge into…
                    </ProsohmButton>
                    {renderActiveAction('makes', row, canManageAssets)}
                  </Stack>
                ) : null,
              }))}
            />
          ) : null}

          {tab === 'models' ? (
            <MasterTable
              emptyTitle="No models yet"
              headers={['Name', 'Make', 'Asset type', 'Active', 'Usage']}
              actionsLabel={canManageAssets ? 'Actions' : undefined}
              rows={(modelsQuery.data ?? []).map((row) => ({
                key: row.id,
                cells: [
                  row.name,
                  makeNameById.get(row.make_id) || row.make_id,
                  typeNameById.get(row.asset_type_id) || row.asset_type_id,
                  row.is_active === false ? 'No' : 'Yes',
                  String(row.usage_count ?? 0),
                ],
                actions: canManageAssets ? (
                  <Stack direction="row" spacing={1} sx={{ justifyContent: 'flex-end' }}>
                    <ProsohmButton
                      buttonVariant="outlined"
                      size="small"
                      disabled={row.is_active === false}
                      onClick={() =>
                        openMerge('models', {
                          id: row.id,
                          name: row.name,
                          assetTypeId: row.asset_type_id,
                        })
                      }
                    >
                      Merge into…
                    </ProsohmButton>
                    {renderActiveAction('models', row, canManageAssets)}
                  </Stack>
                ) : null,
              }))}
            />
          ) : null}

          {tab === 'suppliers' ? (
            <MasterTable
              emptyTitle="No suppliers yet"
              headers={['Name', 'Website', 'Phone', 'Email', 'Active', 'Usage']}
              actionsLabel={canManageSuppliers ? 'Actions' : undefined}
              rows={(suppliersQuery.data ?? []).map((row) => ({
                key: row.id,
                cells: [
                  row.name,
                  row.website || '—',
                  row.phone || '—',
                  row.email || '—',
                  row.is_active === false ? 'No' : 'Yes',
                  String(row.usage_count ?? 0),
                ],
                actions: renderActiveAction('suppliers', row, canManageSuppliers),
              }))}
            />
          ) : null}
        </Box>
      </ContentCard>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={addLabel}
        subtitle="Master records cascade into the asset register."
        icon={CategoryRoundedIcon}
        formId="it-master-form"
        width={520}
        submitLabel="Save"
        loading={createMutation.isPending}
      >
        <Box
          component="form"
          id="it-master-form"
          onSubmit={handleSave}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}
        >
          {tab === 'categories' ? (
            <FormSection title="Category">
              <FormField
                label="Name"
                required
                value={categoryName}
                onChange={(event) => setCategoryName(event.target.value)}
              />
              <FormField
                label="Code"
                value={categoryCode}
                onChange={(event) => setCategoryCode(event.target.value)}
                helper="Optional. Defaults from the name (e.g. network_equipment)."
              />
            </FormSection>
          ) : null}

          {tab === 'types' ? (
            <FormSection title="Asset type">
              <FormField
                label="Code"
                required
                value={typeCode}
                onChange={(event) => setTypeCode(event.target.value)}
              />
              <FormField
                label="Name"
                required
                value={typeName}
                onChange={(event) => setTypeName(event.target.value)}
              />
              <FormSelect
                label="Category"
                value={typeCategory}
                onChange={(event) =>
                  setTypeCategory(String(event.target.value) as AssetTypeCategory)
                }
                options={CATEGORY_OPTIONS}
              />
              <FormField
                label="Numbering prefix"
                value={typePrefix}
                onChange={(event) => setTypePrefix(event.target.value)}
              />
            </FormSection>
          ) : null}

          {tab === 'makes' ? (
            <FormSection title="Make">
              <FormField
                label="Name"
                required
                value={makeName}
                onChange={(event) => setMakeName(event.target.value)}
              />
              <FormSelect
                label="Link to asset type"
                value={makeAssetTypeId}
                onChange={(event) => setMakeAssetTypeId(String(event.target.value))}
                options={typeOptions}
                placeholder="Optional"
              />
            </FormSection>
          ) : null}

          {tab === 'models' ? (
            <FormSection title="Model">
              <FormField
                label="Name"
                required
                value={modelName}
                onChange={(event) => setModelName(event.target.value)}
              />
              <FormSelect
                label="Make"
                required
                value={modelMakeId}
                onChange={(event) => setModelMakeId(String(event.target.value))}
                options={makeOptions}
                placeholder="Select make"
              />
              <FormSelect
                label="Asset type"
                required
                value={modelAssetTypeId}
                onChange={(event) => setModelAssetTypeId(String(event.target.value))}
                options={typeOptions}
                placeholder="Select type"
              />
            </FormSection>
          ) : null}

          {tab === 'suppliers' ? (
            <FormSection title="Supplier">
              <FormField
                label="Name"
                required
                value={supplierName}
                onChange={(event) => setSupplierName(event.target.value)}
              />
              <FormField
                label="Website"
                value={supplierWebsite}
                onChange={(event) => setSupplierWebsite(event.target.value)}
              />
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                <FormField
                  label="Phone"
                  value={supplierPhone}
                  onChange={(event) => setSupplierPhone(event.target.value)}
                  sx={{ flex: 1 }}
                />
                <FormField
                  label="Email"
                  value={supplierEmail}
                  onChange={(event) => setSupplierEmail(event.target.value)}
                  sx={{ flex: 1 }}
                />
              </Stack>
            </FormSection>
          ) : null}
        </Box>
      </FormDrawer>

      <FormDrawer
        open={Boolean(mergeKind && mergeSource)}
        onClose={closeMerge}
        title={mergeKind === 'models' ? 'Merge model' : 'Merge make'}
        subtitle={
          mergeSource
            ? `Assets on “${mergeSource.name}” move to the target. The source is deactivated, not deleted.`
            : undefined
        }
        icon={CategoryRoundedIcon}
        formId="it-master-merge-form"
        width={480}
        submitLabel="Merge"
        loading={mergeMutation.isPending}
      >
        <Box
          component="form"
          id="it-master-merge-form"
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            if (!mergeTargetId) {
              showError('Select the record to merge into.');
              return;
            }
            mergeMutation.mutate();
          }}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}
        >
          <FormSection title="Merge into">
            <FormSelect
              label={mergeKind === 'models' ? 'Target model' : 'Target make'}
              required
              value={mergeTargetId}
              onChange={(event) => setMergeTargetId(String(event.target.value))}
              options={mergeTargetOptions}
              placeholder="Select target"
            />
          </FormSection>
        </Box>
      </FormDrawer>
    </PageContainer>
  );
}

function MasterTable({
  headers,
  rows,
  emptyTitle,
  actionsLabel,
}: {
  headers: string[];
  rows: MasterTableRow[];
  emptyTitle: string;
  actionsLabel?: string;
}) {
  if (rows.length === 0) {
    return <EmptyState title={emptyTitle} description="Use Add to create the first record." />;
  }

  return (
    <Table size="small">
      <TableHead>
        <TableRow>
          {headers.map((header) => (
            <TableCell key={header}>{header}</TableCell>
          ))}
          {actionsLabel ? <TableCell align="right">{actionsLabel}</TableCell> : null}
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.key}>
            {row.cells.map((cell, cellIndex) => (
              <TableCell key={`${headers[cellIndex]}-${cellIndex}`}>
                <Typography variant="body2">{formatCellValue(cell)}</Typography>
              </TableCell>
            ))}
            {actionsLabel ? <TableCell align="right">{row.actions}</TableCell> : null}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
