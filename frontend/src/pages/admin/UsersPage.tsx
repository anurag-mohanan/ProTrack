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
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  TextField,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import LockResetIcon from '@mui/icons-material/LockReset';
import PersonOffIcon from '@mui/icons-material/PersonOff';
import PersonIcon from '@mui/icons-material/Person';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { resetUserPassword, rolesApi, usersApi } from '../../api/resources';
import type { Role, User } from '../../types';

interface UserFormState {
  first_name: string;
  last_name: string;
  email: string;
  role_id: string;
  password: string;
  is_active: boolean;
}

const emptyForm: UserFormState = {
  first_name: '',
  last_name: '',
  email: '',
  role_id: '',
  password: '',
  is_active: true,
};

function formatDate(value: string | undefined): string {
  if (!value) return '—';
  return new Date(value).toLocaleDateString();
}

export default function UsersPage() {
  const { showSuccess, showError } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [activeFilter, setActiveFilter] = useState<string>('all');
  const [formOpen, setFormOpen] = useState(false);
  const [viewUser, setViewUser] = useState<User | null>(null);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [form, setForm] = useState<UserFormState>(emptyForm);
  const [resetTarget, setResetTarget] = useState<User | null>(null);
  const [toggleTarget, setToggleTarget] = useState<User | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const roleMap = useMemo(
    () => new Map(roles.map((role) => [role.id, role.name])),
    [roles],
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | boolean> = {};
      if (roleFilter !== 'all') params.role_id = roleFilter;
      if (activeFilter === 'active') params.is_active = true;
      if (activeFilter === 'inactive') params.is_active = false;

      const [usersData, rolesData] = await Promise.all([
        usersApi.list(params),
        rolesApi.list(),
      ]);
      setUsers(usersData);
      setRoles(rolesData);
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [activeFilter, roleFilter, showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredUsers = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return users;
    return users.filter((user) => {
      const haystack = [user.first_name, user.last_name, user.email]
        .join(' ')
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [search, users]);

  const openCreate = () => {
    setEditingUser(null);
    setForm({
      ...emptyForm,
      role_id: roles[0]?.id ?? '',
    });
    setFormOpen(true);
  };

  const openEdit = (user: User) => {
    setEditingUser(user);
    setForm({
      first_name: user.first_name,
      last_name: user.last_name,
      email: user.email,
      role_id: user.role_id,
      password: '',
      is_active: user.is_active,
    });
    setFormOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      if (editingUser) {
        await usersApi.update(editingUser.id, {
          first_name: form.first_name,
          last_name: form.last_name,
          email: form.email,
          role_id: form.role_id,
          is_active: form.is_active,
        });
        showSuccess('User updated successfully.');
      } else {
        await usersApi.create({
          first_name: form.first_name,
          last_name: form.last_name,
          email: form.email,
          role_id: form.role_id,
          password: form.password,
          is_active: form.is_active,
        } as Partial<User> & { password: string });
        showSuccess('User created successfully.');
      }
      setFormOpen(false);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const handleResetPassword = async () => {
    if (!resetTarget) return;
    setActionLoading(true);
    try {
      const result = await resetUserPassword(resetTarget.id, {
        generate_temporary: true,
      });
      const message = result.temporary_password
        ? `${result.message} Temporary password: ${result.temporary_password}`
        : result.message;
      showSuccess(message);
      setResetTarget(null);
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setActionLoading(false);
    }
  };

  const handleToggleActive = async () => {
    if (!toggleTarget) return;
    setActionLoading(true);
    try {
      await usersApi.update(toggleTarget.id, {
        is_active: !toggleTarget.is_active,
      });
      showSuccess(
        toggleTarget.is_active
          ? 'User deactivated successfully.'
          : 'User activated successfully.',
      );
      setToggleTarget(null);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setActionLoading(false);
    }
  };

  const columns: GridColDef<User>[] = [
    { field: 'first_name', headerName: 'First Name', flex: 1, minWidth: 120 },
    { field: 'last_name', headerName: 'Last Name', flex: 1, minWidth: 120 },
    { field: 'email', headerName: 'Email', flex: 1.5, minWidth: 180 },
    {
      field: 'role_id',
      headerName: 'Role',
      flex: 1,
      minWidth: 140,
      renderCell: (params) => (
        <Chip
          label={roleMap.get(params.value as string) ?? '—'}
          size="small"
          color="primary"
          variant="outlined"
        />
      ),
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
      field: 'created_at',
      headerName: 'Created Date',
      width: 130,
      valueFormatter: (value) => formatDate(value as string | undefined),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 180,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="View">
            <IconButton size="small" onClick={() => setViewUser(params.row)}>
              <VisibilityIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openEdit(params.row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Reset Password">
            <IconButton
              size="small"
              onClick={() => setResetTarget(params.row)}
            >
              <LockResetIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={params.row.is_active ? 'Deactivate' : 'Activate'}>
            <IconButton
              size="small"
              onClick={() => setToggleTarget(params.row)}
            >
              {params.row.is_active ? (
                <PersonOffIcon fontSize="small" />
              ) : (
                <PersonIcon fontSize="small" />
              )}
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading users…" />;

  return (
    <Box>
      <PageHeader
        title="Users"
        subtitle="Manage user accounts, roles, and access"
        action={
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
            Create User
          </Button>
        }
      />

      <Card sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <TextField
            label="Search by name or email"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            sx={{ minWidth: 260, flex: 1 }}
          />
          <FormControl sx={{ minWidth: 200 }}>
            <InputLabel>Role</InputLabel>
            <Select
              label="Role"
              value={roleFilter}
              onChange={(event) => setRoleFilter(event.target.value)}
            >
              <MenuItem value="all">All Roles</MenuItem>
              {roles.map((role) => (
                <MenuItem key={role.id} value={role.id}>
                  {role.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl sx={{ minWidth: 160 }}>
            <InputLabel>Status</InputLabel>
            <Select
              label="Status"
              value={activeFilter}
              onChange={(event) => setActiveFilter(event.target.value)}
            >
              <MenuItem value="all">All</MenuItem>
              <MenuItem value="active">Active</MenuItem>
              <MenuItem value="inactive">Inactive</MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Card>

      <Card sx={{ p: 1 }}>
        <DataGrid
          rows={filteredUsers}
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
        <DialogTitle>{editingUser ? 'Edit User' : 'Create User'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <TextField
            label="First Name"
            value={form.first_name}
            onChange={(event) =>
              setForm((current) => ({ ...current, first_name: event.target.value }))
            }
            required
            fullWidth
          />
          <TextField
            label="Last Name"
            value={form.last_name}
            onChange={(event) =>
              setForm((current) => ({ ...current, last_name: event.target.value }))
            }
            required
            fullWidth
          />
          <TextField
            label="Email"
            type="email"
            value={form.email}
            onChange={(event) =>
              setForm((current) => ({ ...current, email: event.target.value }))
            }
            required
            fullWidth
          />
          <FormControl fullWidth required>
            <InputLabel>Role</InputLabel>
            <Select
              label="Role"
              value={form.role_id}
              onChange={(event) =>
                setForm((current) => ({ ...current, role_id: event.target.value }))
              }
            >
              {roles.map((role) => (
                <MenuItem key={role.id} value={role.id}>
                  {role.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {!editingUser && (
            <TextField
              label="Temporary Password"
              type="password"
              value={form.password}
              onChange={(event) =>
                setForm((current) => ({ ...current, password: event.target.value }))
              }
              required
              fullWidth
              helperText="Minimum 8 characters. User must change on first login."
            />
          )}
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
            {editingUser ? 'Save' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(viewUser)}
        onClose={() => setViewUser(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>User Details</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {viewUser && (
            <>
              <TextField label="First Name" value={viewUser.first_name} slotProps={{ input: { readOnly: true } }} fullWidth />
              <TextField label="Last Name" value={viewUser.last_name} slotProps={{ input: { readOnly: true } }} fullWidth />
              <TextField label="Email" value={viewUser.email} slotProps={{ input: { readOnly: true } }} fullWidth />
              <TextField
                label="Role"
                value={roleMap.get(viewUser.role_id) ?? '—'}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
              <TextField
                label="Status"
                value={viewUser.is_active ? 'Active' : 'Inactive'}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
              <TextField
                label="Created Date"
                value={formatDate(viewUser.created_at)}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setViewUser(null)}>Close</Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={Boolean(resetTarget)}
        title="Reset Password"
        message={
          resetTarget
            ? `Generate a temporary password for ${resetTarget.first_name} ${resetTarget.last_name}? They will be required to change it on next login.`
            : ''
        }
        confirmLabel="Reset Password"
        onConfirm={() => void handleResetPassword()}
        onClose={() => setResetTarget(null)}
        loading={actionLoading}
      />

      <ConfirmDialog
        open={Boolean(toggleTarget)}
        title={toggleTarget?.is_active ? 'Deactivate User' : 'Activate User'}
        message={
          toggleTarget
            ? toggleTarget.is_active
              ? `Deactivate ${toggleTarget.first_name} ${toggleTarget.last_name}? They will no longer be able to sign in.`
              : `Activate ${toggleTarget.first_name} ${toggleTarget.last_name}?`
            : ''
        }
        confirmLabel={toggleTarget?.is_active ? 'Deactivate' : 'Activate'}
        onConfirm={() => void handleToggleActive()}
        onClose={() => setToggleTarget(null)}
        loading={actionLoading}
      />
    </Box>
  );
}
