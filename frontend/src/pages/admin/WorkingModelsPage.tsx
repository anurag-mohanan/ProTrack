import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Box, Chip, FormControlLabel, IconButton, Switch, Tooltip } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import WorkHistoryOutlinedIcon from '@mui/icons-material/WorkHistoryOutlined';
import type { GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { ClientPaginatedDataGrid } from '../../components/common/ClientPaginatedDataGrid';
import { LoadingState } from '../../components/common/LoadingState';
import { AdminDeleteButton } from '../../components/admin/AdminDeleteButton';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import {
  archiveWorkingModel,
  fetchWorkingModelStrategies,
  reorderWorkingModels,
  workingModelsApi,
} from '../../api/resources';
import type { WorkingModel, WorkingModelStrategyKey } from '../../types';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import { ContentCard } from '../../components/ui/cards';
import {
  DrawerQuickActions,
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
  RecordDetailDrawer,
  SearchToolbar,
  TableRowActions,
} from '../../components/ui/design-system';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { formatCellValue } from '../../utils/format';
import { optionalString, validateRequiredFields } from '../../utils/formValues';
import { canDeleteRecords } from '../../utils/permissions';
import { useAuth } from '../../context/AuthContext';
import { DATA_GRID_ACTIONS_COLUMN_WIDTH } from '../../theme/componentStyles';

const STRATEGY_LABELS: Record<WorkingModelStrategyKey, string> = {
  project_based: 'Project Based (Fixed Fee)',
  time_materials: 'Time & Materials (Hourly)',
  retainer: 'Retainer / Subscription',
};

interface WorkingModelFormState {
  code: string;
  strategy_key: WorkingModelStrategyKey;
  name: string;
  description: string;
  is_active: boolean;
}

const emptyForm: WorkingModelFormState = {
  code: '',
  strategy_key: 'project_based',
  name: '',
  description: '',
  is_active: true,
};

export default function WorkingModelsPage() {
  const { user } = useAuth();
  const isAdmin = canDeleteRecords(user?.role_name ?? '');
  const { showSuccess, showError } = useToast();
  const [models, setModels] = useState<WorkingModel[]>([]);
  const [strategies, setStrategies] = useState<WorkingModelStrategyKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState<WorkingModel | null>(null);
  const [editingModel, setEditingModel] = useState<WorkingModel | null>(null);
  const [form, setForm] = useState<WorkingModelFormState>(emptyForm);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [modelsData, strategyKeys] = await Promise.all([
        workingModelsApi.list({ limit: 500 }),
        fetchWorkingModelStrategies(),
      ]);
      const sorted = [...modelsData].sort(
        (left, right) => left.sort_order - right.sort_order || left.name.localeCompare(right.name),
      );
      setModels(sorted);
      setStrategies(strategyKeys as WorkingModelStrategyKey[]);
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredModels = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return models;
    return models.filter((model) => {
      const haystack = [model.name, model.code, model.description ?? '', model.strategy_key]
        .join(' ')
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [models, search]);

  const openCreate = () => {
    setEditingModel(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  useOpenCreateFromQuery(openCreate);

  const openEdit = (model: WorkingModel) => {
    setEditingModel(model);
    setForm({
      code: model.code,
      strategy_key: model.strategy_key,
      name: model.name,
      description: model.description ?? '',
      is_active: model.is_active,
    });
    setFormOpen(true);
  };

  const handleSave = async (event?: FormEvent) => {
    event?.preventDefault();
    const validationError = validateRequiredFields(
      { name: form.name, strategy_key: form.strategy_key },
      [
        { key: 'name', label: 'Name' },
        { key: 'strategy_key', label: 'Calculation strategy' },
      ],
    );
    if (validationError) {
      showError(validationError);
      return;
    }

    setSaving(true);
    try {
      const payload = {
        code: optionalString(form.code) ?? undefined,
        strategy_key: form.strategy_key,
        name: form.name.trim(),
        description: optionalString(form.description),
        is_active: form.is_active,
      };
      if (editingModel) {
        await workingModelsApi.update(editingModel.id, payload);
        showSuccess('Working model updated.');
      } else {
        await workingModelsApi.create(payload);
        showSuccess('Working model created.');
      }
      setFormOpen(false);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const moveModel = async (modelId: string, direction: 'up' | 'down') => {
    const index = models.findIndex((model) => model.id === modelId);
    if (index < 0) return;
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= models.length) return;
    const reordered = [...models];
    const [item] = reordered.splice(index, 1);
    reordered.splice(targetIndex, 0, item);
    try {
      const updated = await reorderWorkingModels(reordered.map((model) => model.id));
      setModels(
        [...updated].sort(
          (left, right) => left.sort_order - right.sort_order || left.name.localeCompare(right.name),
        ),
      );
    } catch (error) {
      showError(getErrorMessage(error));
    }
  };

  const handleArchive = async (model: WorkingModel) => {
    try {
      await archiveWorkingModel(model.id);
      showSuccess(`"${model.name}" archived.`);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    }
  };

  const columns: GridColDef<WorkingModel>[] = [
    {
      field: 'sort_order',
      headerName: 'Order',
      width: 110,
      sortable: false,
      renderCell: ({ row }) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Tooltip title="Move up">
            <span>
              <IconButton
                size="small"
                disabled={models[0]?.id === row.id}
                onClick={() => void moveModel(row.id, 'up')}
              >
                <ArrowUpwardIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Move down">
            <span>
              <IconButton
                size="small"
                disabled={models[models.length - 1]?.id === row.id}
                onClick={() => void moveModel(row.id, 'down')}
              >
                <ArrowDownwardIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      ),
    },
    { field: 'name', headerName: 'Name', flex: 1.4, minWidth: 180 },
    { field: 'code', headerName: 'Code', flex: 1, minWidth: 140 },
    {
      field: 'strategy_key',
      headerName: 'Strategy',
      flex: 1.2,
      minWidth: 180,
      valueFormatter: (value) => STRATEGY_LABELS[value as WorkingModelStrategyKey] ?? String(value),
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 1.5,
      minWidth: 180,
      valueFormatter: (value) => formatCellValue(value as string | null),
    },
    {
      field: 'is_active',
      headerName: 'Status',
      width: 120,
      renderCell: ({ row }) => (
        <Chip
          size="small"
          label={row.is_archived ? 'Archived' : row.is_active ? 'Active' : 'Inactive'}
          color={row.is_archived ? 'default' : row.is_active ? 'success' : 'warning'}
        />
      ),
    },
    {
      field: 'actions',
      headerName: '',
      width: DATA_GRID_ACTIONS_COLUMN_WIDTH,
      sortable: false,
      renderCell: ({ row }) => (
        <TableRowActions
          onEdit={() => openEdit(row)}
          onArchive={!row.is_archived ? () => void handleArchive(row) : undefined}
          deleteAction={
            isAdmin ? (
              <AdminDeleteButton
                resource="working-models"
                recordId={row.id}
                recordName={row.name}
                onDeleted={() => void loadData()}
                onArchive={!row.is_archived ? () => handleArchive(row) : undefined}
                showArchive
                showDeactivate={false}
              />
            ) : undefined
          }
        />
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading working models…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Working Models"
        subtitle="Configure engagement models and the KPI strategies applied to projects."
        action={
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
            Add Working Model
          </ProsohmButton>
        }
      />

      <SearchToolbar>
        <FormField
          label="Search working models"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, flex: 1, maxWidth: 480 }}
        />
      </SearchToolbar>

      <ContentCard noPadding>
        <ClientPaginatedDataGrid
          rows={filteredModels}
          columns={columns}
          autoHeight
          filterKey={search}
          onRowOpen={(rowId) => {
            const model = filteredModels.find((item) => item.id === rowId);
            if (model) setSelectedModel(model);
          }}
        />
      </ContentCard>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingModel ? 'Edit Working Model' : 'Add Working Model'}
        subtitle="Define how projects using this model are measured and reported."
        icon={WorkHistoryOutlinedIcon}
        formId="working-model-form"
        submitLabel={editingModel ? 'Save Changes' : 'Create Working Model'}
        loading={saving}
      >
        <Box
          component="form"
          id="working-model-form"
          onSubmit={(event) => void handleSave(event)}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
        >
          <FormSection title="Details">
            <FormField
              label="Name"
              required
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
            <FormField
              label="Code"
              value={form.code}
              helper="Optional slug. Auto-generated from the name when left blank."
              onChange={(event) => setForm((current) => ({ ...current, code: event.target.value }))}
            />
            <FormSelect
              label="Calculation Strategy"
              required
              value={form.strategy_key}
              options={strategies.map((strategy) => ({
                value: strategy,
                label: STRATEGY_LABELS[strategy] ?? strategy,
              }))}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  strategy_key: event.target.value as WorkingModelStrategyKey,
                }))
              }
            />
            <FormField
              label="Description"
              multiline
              minRows={3}
              value={form.description}
              onChange={(event) =>
                setForm((current) => ({ ...current, description: event.target.value }))
              }
            />
            <FormControlLabel
              control={
                <Switch
                  checked={form.is_active}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, is_active: event.target.checked }))
                  }
                />
              }
              label="Active"
            />
          </FormSection>
        </Box>
      </FormDrawer>

      <RecordDetailDrawer
        open={Boolean(selectedModel)}
        onClose={() => setSelectedModel(null)}
        title={selectedModel?.name ?? 'Working Model'}
        subtitle={selectedModel?.code}
        icon={WorkHistoryOutlinedIcon}
        status={
          selectedModel ? (
            <Chip
              label={
                selectedModel.is_archived
                  ? 'Archived'
                  : selectedModel.is_active
                    ? 'Active'
                    : 'Inactive'
              }
              size="small"
              color={selectedModel.is_archived ? 'default' : selectedModel.is_active ? 'success' : 'warning'}
            />
          ) : null
        }
        quickActions={
          selectedModel ? (
            <DrawerQuickActions>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => {
                  openEdit(selectedModel);
                  setSelectedModel(null);
                }}
              >
                Edit
              </ProsohmButton>
            </DrawerQuickActions>
          ) : undefined
        }
      >
        {selectedModel ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            <TypographyDetail label="Strategy" value={STRATEGY_LABELS[selectedModel.strategy_key]} />
            <TypographyDetail label="Description" value={selectedModel.description} />
            <TypographyDetail
              label="Status"
              value={
                selectedModel.is_archived
                  ? 'Archived'
                  : selectedModel.is_active
                    ? 'Active'
                    : 'Inactive'
              }
            />
          </Box>
        ) : null}
      </RecordDetailDrawer>
    </PageContainer>
  );
}

function TypographyDetail({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <Box>
      <Box sx={{ fontSize: 12, color: 'text.secondary', mb: 0.25 }}>{label}</Box>
      <Box>{formatCellValue(value)}</Box>
    </Box>
  );
}
