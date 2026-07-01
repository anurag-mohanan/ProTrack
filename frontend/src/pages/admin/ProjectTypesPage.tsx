import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Card,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  Switch,
  TextField,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import {
  createProjectType,
  deleteProjectType,
  fetchAdminProjectTypes,
  updateProjectType,
} from '../../api/projectTemplates';
import type { ProjectType } from '../../types/ProjectTemplate';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';

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
  const { showSuccess, showError } = useToast();
  const [projectTypes, setProjectTypes] = useState<ProjectType[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editingType, setEditingType] = useState<ProjectType | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProjectType | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
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

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        description: form.description || null,
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

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setActionLoading(true);
    try {
      await deleteProjectType(deleteTarget.id);
      showSuccess('Project type deleted successfully.');
      setDeleteTarget(null);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setActionLoading(false);
    }
  };

  const columns: GridColDef<ProjectType>[] = [
    { field: 'name', headerName: 'Name', flex: 1.2, minWidth: 160 },
    {
      field: 'description',
      headerName: 'Description',
      flex: 2,
      minWidth: 180,
      valueFormatter: (value) => (value as string | null) || '—',
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
      headerName: 'Actions',
      width: 100,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openEdit(params.row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton size="small" onClick={() => setDeleteTarget(params.row)}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading project types…" />;

  return (
    <Box>
      <PageHeader
        title="Project Types"
        subtitle="Manage project classification types used by templates"
        action={
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
            Create Project Type
          </Button>
        }
      />

      <Card sx={{ p: 2, mb: 2 }}>
        <TextField
          label="Search by name or description"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, width: '100%', maxWidth: 480 }}
        />
      </Card>

      <Card sx={{ p: 1 }}>
        <DataGrid
          rows={filteredTypes}
          columns={columns}
          autoHeight
          disableRowSelectionOnClick
          pageSizeOptions={[10, 25, 50]}
          initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
          sx={{ border: 0 }}
        />
      </Card>

      <Dialog open={formOpen} onClose={() => setFormOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingType ? 'Edit Project Type' : 'Create Project Type'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <TextField
            label="Name"
            value={form.name}
            onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            required
            fullWidth
          />
          <TextField
            label="Description"
            value={form.description}
            onChange={(event) =>
              setForm((current) => ({ ...current, description: event.target.value }))
            }
            multiline
            minRows={3}
            fullWidth
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
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFormOpen(false)} disabled={saving}>
            Cancel
          </Button>
          <Button variant="contained" onClick={() => void handleSave()} disabled={saving}>
            {editingType ? 'Save' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete Project Type"
        message={
          deleteTarget
            ? `Delete project type "${deleteTarget.name}"? This action cannot be undone.`
            : ''
        }
        confirmLabel="Delete"
        onConfirm={() => void handleDelete()}
        onClose={() => setDeleteTarget(null)}
        loading={actionLoading}
      />
    </Box>
  );
}
