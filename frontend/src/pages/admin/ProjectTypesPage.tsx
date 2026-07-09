import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Box, Chip, FormControlLabel, Switch } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CategoryOutlinedIcon from '@mui/icons-material/CategoryOutlined';
import type { GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { AdminDeleteButton } from '../../components/admin/AdminDeleteButton';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import {
  createProjectType,
  fetchAdminProjectTypes,
  updateProjectType,
} from '../../api/projectTemplates';
import type { ProjectType } from '../../types/ProjectTemplate';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  DrawerQuickActions,
  FormDrawer,
  FormField,
  FormSection,
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

interface ProjectTypeFormState {
  name: string;
  description: string;
  is_active: boolean;
}

const emptyForm: ProjectTypeFormState = {
  name: '',
  description: '',
  is_active: true,
};

export default function ProjectTypesPage() {
  const { user } = useAuth();
  const isAdmin = canDeleteRecords(user?.role_name ?? '');
  const { showSuccess, showError } = useToast();
  const [projectTypes, setProjectTypes] = useState<ProjectType[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [selectedType, setSelectedType] = useState<ProjectType | null>(null);
  const [editingType, setEditingType] = useState<ProjectType | null>(null);
  const [form, setForm] = useState<ProjectTypeFormState>(emptyForm);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      setProjectTypes(await fetchAdminProjectTypes());
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredTypes = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return projectTypes;
    return projectTypes.filter((projectType) => {
      const haystack = [projectType.name, projectType.description ?? ''].join(' ').toLowerCase();
      return haystack.includes(term);
    });
  }, [projectTypes, search]);

  const openCreate = () => {
    setEditingType(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  useOpenCreateFromQuery(openCreate);

  const openEdit = (projectType: ProjectType) => {
    setEditingType(projectType);
    setForm({
      name: projectType.name,
      description: projectType.description ?? '',
      is_active: projectType.is_active,
    });
    setFormOpen(true);
  };

  const handleSave = async (event?: FormEvent) => {
    event?.preventDefault();
    const validationError = validateRequiredFields(form, [{ key: 'name', label: 'Name' }]);
    if (validationError) {
      showError(validationError);
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        description: optionalString(form.description),
        is_active: form.is_active,
      };
      if (editingType) {
        await updateProjectType(editingType.id, payload);
        showSuccess('Project type updated successfully.');
      } else {
        await createProjectType(payload);
        showSuccess('Project type created successfully.');
      }
      setFormOpen(false);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const columns: GridColDef<ProjectType>[] = [
    { field: 'name', headerName: 'Name', flex: 1.2, minWidth: 160 },
    {
      field: 'description',
      headerName: 'Description',
      flex: 2,
      minWidth: 180,
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
                resource="project-types"
                recordId={params.row.id}
                recordName={params.row.name}
                onDeleted={() => void loadData()}
                onDeactivate={async () => {
                  await updateProjectType(params.row.id, { is_active: false });
                  showSuccess('Project type deactivated.');
                  await loadData();
                }}
              />
            ) : undefined
          }
        />
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading project types…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Project Types"
        subtitle="Manage project classification types used by templates"
        action={
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
            Create Project Type
          </ProsohmButton>
        }
      />

      <SearchToolbar>
        <FormField
          label="Search by name or description"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, flex: 1, maxWidth: 480 }}
        />
      </SearchToolbar>

      <ContentCard noPadding>
        <ProsohmDataGrid
          rows={filteredTypes}
          columns={columns}
          autoHeight
          pageSizeOptions={[25, 50, 100]}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          onRowOpen={(rowId) => {
            const projectType = filteredTypes.find((item) => item.id === rowId);
            if (projectType) setSelectedType(projectType);
          }}
        />
      </ContentCard>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingType ? 'Edit Project Type' : 'Create Project Type'}
        subtitle="Project classification configuration"
        icon={CategoryOutlinedIcon}
        formId="project-type-form"
        submitLabel={editingType ? 'Save Changes' : 'Create Project Type'}
        loading={saving}
      >
        <Box
          component="form"
          id="project-type-form"
          onSubmit={(event) => void handleSave(event)}
          sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
        >
          <FormSection title="Project Type Details" icon={CategoryOutlinedIcon}>
            <FormField
              label="Name"
              required
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
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
        open={Boolean(selectedType)}
        onClose={() => setSelectedType(null)}
        title={selectedType?.name ?? 'Project Type'}
        subtitle="Project classification"
        icon={CategoryOutlinedIcon}
        status={
          selectedType ? (
            <Chip
              label={selectedType.is_active ? 'Active' : 'Inactive'}
              size="small"
              color={selectedType.is_active ? 'success' : 'default'}
            />
          ) : null
        }
        quickActions={
          selectedType ? (
            <DrawerQuickActions>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => {
                  openEdit(selectedType);
                  setSelectedType(null);
                }}
              >
                Edit
              </ProsohmButton>
              {isAdmin ? (
                <AdminDeleteButton
                  mode="button"
                  resource="project-types"
                  recordId={selectedType.id}
                  recordName={selectedType.name}
                  onDeleted={() => {
                    setSelectedType(null);
                    void loadData();
                  }}
                  onDeactivate={async () => {
                    await updateProjectType(selectedType.id, { is_active: false });
                    showSuccess('Project type deactivated.');
                    setSelectedType(null);
                    await loadData();
                  }}
                />
              ) : null}
            </DrawerQuickActions>
          ) : null
        }
      >
        {selectedType ? (
          <FormSection title="Overview" icon={CategoryOutlinedIcon}>
            <FormField label="Name" value={selectedType.name} slotProps={{ input: { readOnly: true } }} />
            <FormField
              label="Description"
              value={formatCellValue(selectedType.description) || '—'}
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
