import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Box, Chip, FormControlLabel, Switch } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import AssignmentOutlinedIcon from '@mui/icons-material/AssignmentOutlined';
import type { GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { AdminDeleteButton } from '../../components/admin/AdminDeleteButton';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { streamsApi, taskTypesApi } from '../../api/resources';
import type { Stream, TaskType } from '../../types';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  DrawerQuickActions,
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
  ProsohmDataGrid,
  RecordDetailDrawer,
  SearchToolbar,
  TableRowActions,
} from '../../components/ui/design-system';
import { formatCellValue } from '../../utils/format';
import { optionalString, validateRequiredFields } from '../../utils/formValues';
import { canDeleteRecords } from '../../utils/permissions';
import { useAuth } from '../../context/AuthContext';
import { DATA_GRID_ACTIONS_COLUMN_WIDTH } from '../../theme/componentStyles';

interface TaskTypeFormState {
  name: string;
  stream_id: string;
  description: string;
  is_billable: boolean;
  is_active: boolean;
}

const emptyForm: TaskTypeFormState = {
  name: '',
  stream_id: '',
  description: '',
  is_billable: true,
  is_active: true,
};

export default function TaskTypesPage() {
  const { user } = useAuth();
  const isAdmin = canDeleteRecords(user?.role_name ?? '');
  const { showSuccess, showError } = useToast();
  const [taskTypes, setTaskTypes] = useState<TaskType[]>([]);
  const [streams, setStreams] = useState<Stream[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [selectedTaskType, setSelectedTaskType] = useState<TaskType | null>(null);
  const [editingTaskType, setEditingTaskType] = useState<TaskType | null>(null);
  const [form, setForm] = useState<TaskTypeFormState>(emptyForm);

  const streamMap = useMemo(
    () => new Map(streams.map((stream) => [stream.id, stream.name])),
    [streams],
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [taskTypesData, streamsData] = await Promise.all([
        taskTypesApi.list(),
        streamsApi.list(),
      ]);
      setTaskTypes(taskTypesData);
      setStreams(streamsData);
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredTaskTypes = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return taskTypes;
    return taskTypes.filter((taskType) => {
      const streamName = streamMap.get(taskType.stream_id) ?? '';
      const haystack = [taskType.name, taskType.description ?? '', streamName]
        .join(' ')
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [search, streamMap, taskTypes]);

  const openCreate = () => {
    setEditingTaskType(null);
    setForm({
      ...emptyForm,
      stream_id: streams[0]?.id ?? '',
    });
    setFormOpen(true);
  };

  useOpenCreateFromQuery(openCreate);

  const openEdit = (taskType: TaskType) => {
    setEditingTaskType(taskType);
    setForm({
      name: taskType.name,
      stream_id: taskType.stream_id,
      description: taskType.description ?? '',
      is_billable: taskType.is_billable,
      is_active: taskType.is_active,
    });
    setFormOpen(true);
  };

  const handleSave = async (event?: FormEvent) => {
    event?.preventDefault();
    const validationError = validateRequiredFields(form, [
      { key: 'name', label: 'Name' },
      { key: 'stream_id', label: 'Stream' },
    ]);
    if (validationError) {
      showError(validationError);
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        stream_id: form.stream_id,
        description: optionalString(form.description),
        is_billable: form.is_billable,
        is_active: form.is_active,
      };
      if (editingTaskType) {
        await taskTypesApi.update(editingTaskType.id, payload);
        showSuccess('Task type updated successfully.');
      } else {
        await taskTypesApi.create(payload);
        showSuccess('Task type created successfully.');
      }
      setFormOpen(false);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const columns: GridColDef<TaskType>[] = [
    { field: 'name', headerName: 'Name', flex: 1.2, minWidth: 140 },
    {
      field: 'stream_id',
      headerName: 'Stream',
      flex: 1,
      minWidth: 120,
      renderCell: (params) => (
        <Chip
          label={formatCellValue(streamMap.get(params.value as string))}
          size="small"
          variant="outlined"
        />
      ),
    },
    {
      field: 'is_billable',
      headerName: 'Billable',
      width: 100,
      renderCell: (params) => (
        <Chip
          label={params.value ? 'Yes' : 'No'}
          size="small"
          color={params.value ? 'primary' : 'default'}
        />
      ),
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 1.5,
      minWidth: 160,
      valueFormatter: (value) => formatCellValue(value as string | null),
    },
    {
      field: 'is_active',
      headerName: 'Active',
      width: 100,
      renderCell: (params) => (
        <Chip
          label={params.value ? 'Active' : 'Inactive'}
          size="small"
          color={params.value ? 'success' : 'default'}
        />
      ),
    },
    {
      field: 'actions',
      headerName: '',
      width: isAdmin ? DATA_GRID_ACTIONS_COLUMN_WIDTH + 40 : DATA_GRID_ACTIONS_COLUMN_WIDTH,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <TableRowActions
          onEdit={() => openEdit(params.row)}
          deleteAction={
            isAdmin ? (
              <AdminDeleteButton
                resource="task-types"
                recordId={params.row.id}
                recordName={params.row.name}
                onDeleted={() => void loadData()}
                onDeactivate={async () => {
                  await taskTypesApi.update(params.row.id, { is_active: false });
                  showSuccess('Task type deactivated.');
                  await loadData();
                }}
              />
            ) : undefined
          }
        />
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading task types…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Task Types"
        subtitle="Manage billable task types by stream"
        action={
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
            Create Task Type
          </ProsohmButton>
        }
      />

      <SearchToolbar>
        <FormField
          label="Search by name, stream, or description"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, flex: 1, maxWidth: 480 }}
        />
      </SearchToolbar>

      <ContentCard noPadding>
        <ProsohmDataGrid
          rows={filteredTaskTypes}
          columns={columns}
          autoHeight
          pageSizeOptions={[10, 25, 50]}
          initialState={{
            pagination: { paginationModel: { pageSize: 10 } },
          }}
          onRowOpen={(rowId) => {
            const taskType = filteredTaskTypes.find((item) => item.id === rowId);
            if (taskType) setSelectedTaskType(taskType);
          }}
        />
      </ContentCard>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingTaskType ? 'Edit Task Type' : 'Create Task Type'}
        subtitle="Billable task type configuration"
        icon={AssignmentOutlinedIcon}
        formId="task-type-form"
        submitLabel={editingTaskType ? 'Save Changes' : 'Create Task Type'}
        loading={saving}
      >
        <Box
          component="form"
          id="task-type-form"
          onSubmit={(event) => void handleSave(event)}
          sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
        >
          <FormSection title="Task Type Details" icon={AssignmentOutlinedIcon}>
            <FormField
              label="Name"
              required
              value={form.name}
              onChange={(event) =>
                setForm((current) => ({ ...current, name: event.target.value }))
              }
            />
            <FormSelect
              label="Stream"
              required
              value={form.stream_id}
              options={streams.map((stream) => ({ value: stream.id, label: stream.name }))}
              onChange={(event) =>
                setForm((current) => ({ ...current, stream_id: String(event.target.value) }))
              }
            />
            <FormField
              label="Description"
              value={form.description}
              onChange={(event) =>
                setForm((current) => ({ ...current, description: event.target.value }))
              }
              multiline
              minRows={3}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={form.is_billable}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, is_billable: event.target.checked }))
                  }
                />
              }
              label="Billable"
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
        open={Boolean(selectedTaskType)}
        onClose={() => setSelectedTaskType(null)}
        title={selectedTaskType?.name ?? 'Task Type'}
        subtitle="Billable task type"
        icon={AssignmentOutlinedIcon}
        status={
          selectedTaskType ? (
            <Chip
              label={selectedTaskType.is_active ? 'Active' : 'Inactive'}
              size="small"
              color={selectedTaskType.is_active ? 'success' : 'default'}
            />
          ) : null
        }
        quickActions={
          selectedTaskType ? (
            <DrawerQuickActions>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => {
                  openEdit(selectedTaskType);
                  setSelectedTaskType(null);
                }}
              >
                Edit
              </ProsohmButton>
              {isAdmin ? (
                <AdminDeleteButton
                  mode="button"
                  resource="task-types"
                  recordId={selectedTaskType.id}
                  recordName={selectedTaskType.name}
                  onDeleted={() => {
                    setSelectedTaskType(null);
                    void loadData();
                  }}
                  onDeactivate={async () => {
                    await taskTypesApi.update(selectedTaskType.id, { is_active: false });
                    showSuccess('Task type deactivated.');
                    setSelectedTaskType(null);
                    await loadData();
                  }}
                />
              ) : null}
            </DrawerQuickActions>
          ) : null
        }
      >
        {selectedTaskType ? (
          <FormSection title="Overview" icon={AssignmentOutlinedIcon}>
            <FormField label="Name" value={selectedTaskType.name} slotProps={{ input: { readOnly: true } }} />
            <FormField
              label="Stream"
              value={formatCellValue(streamMap.get(selectedTaskType.stream_id)) || '—'}
              slotProps={{ input: { readOnly: true } }}
            />
            <FormField
              label="Billable"
              value={selectedTaskType.is_billable ? 'Yes' : 'No'}
              slotProps={{ input: { readOnly: true } }}
            />
            <FormField
              label="Description"
              value={formatCellValue(selectedTaskType.description) || '—'}
              multiline
              minRows={2}
              slotProps={{ input: { readOnly: true } }}
            />
          </FormSection>
        ) : null}
      </RecordDetailDrawer>
    </PageContainer>
  );
}
