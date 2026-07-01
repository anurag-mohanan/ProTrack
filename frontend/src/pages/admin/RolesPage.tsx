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
  IconButton,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { rolesApi } from '../../api/resources';
import type { Role } from '../../types';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';

const SYSTEM_ROLE_NAMES = new Set([
  'Admin',
  'Engineering Manager',
  'Project Manager',
  'Design Leader',
  'Senior Designer',
  'Designer',
  'Junior Designer',
  'Surfacer',
  'Read Only',
]);

interface RoleFormState {
  name: string;
  description: string;
}

const emptyForm: RoleFormState = {
  name: '',
  description: '',
};

function formatDate(value: string | undefined): string {
  if (!value) return '—';
  return new Date(value).toLocaleDateString();
}

function isSystemRole(role: Role): boolean {
  return SYSTEM_ROLE_NAMES.has(role.name);
}

export default function RolesPage() {
  const { showSuccess, showError } = useToast();
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [viewRole, setViewRole] = useState<Role | null>(null);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Role | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [form, setForm] = useState<RoleFormState>(emptyForm);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      setRoles(await rolesApi.list());
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const systemRoles = useMemo(
    () => roles.filter((role) => isSystemRole(role)),
    [roles],
  );

  const filteredRoles = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return roles;
    return roles.filter((role) => {
      const haystack = [role.name, role.description ?? ''].join(' ').toLowerCase();
      return haystack.includes(term);
    });
  }, [roles, search]);

  const openCreate = () => {
    setEditingRole(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  useOpenCreateFromQuery(openCreate);

  const openEdit = (role: Role) => {
    setEditingRole(role);
    setForm({
      name: role.name,
      description: role.description ?? '',
    });
    setFormOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        description: form.description || null,
        ...(editingRole && !isSystemRole(editingRole) ? { name: form.name } : {}),
        ...(!editingRole ? { name: form.name, description: form.description || null } : {}),
      };

      if (editingRole) {
        await rolesApi.update(editingRole.id, payload);
        showSuccess('Role updated successfully.');
      } else {
        await rolesApi.create({
          name: form.name,
          description: form.description || null,
        });
        showSuccess('Role created successfully.');
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
      await rolesApi.remove(deleteTarget.id);
      showSuccess('Role deleted successfully.');
      setDeleteTarget(null);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setActionLoading(false);
    }
  };

  const columns: GridColDef<Role>[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      minWidth: 160,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <span>{params.value as string}</span>
          {isSystemRole(params.row) && (
            <Chip label="System" size="small" color="info" variant="outlined" />
          )}
        </Box>
      ),
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 2,
      minWidth: 200,
      valueFormatter: (value) => (value as string | null) || '—',
    },
    {
      field: 'created_at',
      headerName: 'Created Date',
      width: 130,
      valueFormatter: (value) => formatDate(value as string | undefined),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 130,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="View">
            <IconButton size="small" onClick={() => setViewRole(params.row)}>
              <VisibilityIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openEdit(params.row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={isSystemRole(params.row) ? 'System roles cannot be deleted' : 'Delete'}>
            <span>
              <IconButton
                size="small"
                disabled={isSystemRole(params.row)}
                onClick={() => setDeleteTarget(params.row)}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading roles…" />;

  return (
    <Box>
      <PageHeader
        title="Roles"
        subtitle="Manage user roles and permissions"
        action={
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
            Create Role
          </Button>
        }
      />

      <Card sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          System Roles
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          These roles are built into ProTrack. You can edit their descriptions but not their names or delete them.
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {systemRoles.map((role) => (
            <Chip key={role.id} label={role.name} color="info" variant="outlined" />
          ))}
        </Box>
      </Card>

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
          rows={filteredRoles}
          columns={columns}
          autoHeight
          disableRowSelectionOnClick
          pageSizeOptions={[10, 25, 50]}
          initialState={{
            pagination: { paginationModel: { pageSize: 10 } },
          }}
          sx={{ border: 0 }}
        />
      </Card>

      <Dialog
        open={formOpen}
        onClose={() => setFormOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{editingRole ? 'Edit Role' : 'Create Role'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <TextField
            label="Name"
            value={form.name}
            onChange={(event) =>
              setForm((current) => ({ ...current, name: event.target.value }))
            }
            required
            fullWidth
            disabled={Boolean(editingRole && isSystemRole(editingRole))}
            helperText={
              editingRole && isSystemRole(editingRole)
                ? 'System role names cannot be changed.'
                : undefined
            }
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
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFormOpen(false)} disabled={saving}>
            Cancel
          </Button>
          <Button variant="contained" onClick={() => void handleSave()} disabled={saving}>
            {editingRole ? 'Save' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(viewRole)}
        onClose={() => setViewRole(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Role Details</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {viewRole && (
            <>
              <TextField label="Name" value={viewRole.name} slotProps={{ input: { readOnly: true } }} fullWidth />
              <TextField
                label="Description"
                value={viewRole.description ?? '—'}
                slotProps={{ input: { readOnly: true } }}
                multiline
                minRows={2}
                fullWidth
              />
              <TextField
                label="Type"
                value={isSystemRole(viewRole) ? 'System Role' : 'Custom Role'}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
              <TextField
                label="Created Date"
                value={formatDate(viewRole.created_at)}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setViewRole(null)}>Close</Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete Role"
        message={
          deleteTarget
            ? `Delete role "${deleteTarget.name}"? This action cannot be undone.`
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
