import { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Card,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  Tab,
  Tabs,
  TextField,
} from '@mui/material';
import { DataGrid, GridActionsCellItem, type GridColDef } from '@mui/x-data-grid';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import PageHeader from '../components/common/PageHeader';
import AlertBanner from '../components/common/AlertBanner';
import { rolesApi, usersApi } from '../api/resources';
import type { Role, User } from '../types';

export default function UsersPage() {
  const [tab, setTab] = useState(0);
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [userOpen, setUserOpen] = useState(false);
  const [roleOpen, setRoleOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [userForm, setUserForm] = useState({
    role_id: '',
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    is_active: true,
  });
  const [roleForm, setRoleForm] = useState({ name: '', description: '' });

  const load = useCallback(() => {
    Promise.all([usersApi.list(), rolesApi.list()])
      .then(([u, r]) => {
        setUsers(u);
        setRoles(r);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const userColumns: GridColDef<User>[] = [
    { field: 'first_name', headerName: 'First Name', width: 130 },
    { field: 'last_name', headerName: 'Last Name', width: 130 },
    { field: 'email', headerName: 'Email', flex: 1, minWidth: 200 },
    {
      field: 'role_id',
      headerName: 'Role',
      width: 140,
      valueGetter: (_, row) => roles.find((r) => r.id === row.role_id)?.name ?? row.role_id,
    },
    {
      field: 'is_active',
      headerName: 'Active',
      width: 90,
      valueGetter: (_, row) => (row.is_active ? 'Yes' : 'No'),
    },
    {
      field: 'actions',
      type: 'actions',
      width: 90,
      getActions: (params) => [
        <GridActionsCellItem
          icon={<EditIcon />}
          label="Edit"
          onClick={() => {
            setEditingUser(params.row);
            setUserForm({
              role_id: params.row.role_id,
              email: params.row.email,
              password: '',
              first_name: params.row.first_name,
              last_name: params.row.last_name,
              is_active: params.row.is_active,
            });
            setUserOpen(true);
          }}
        />,
        <GridActionsCellItem icon={<DeleteIcon />} label="Delete" onClick={() => usersApi.remove(params.id as string).then(load)} />,
      ],
    },
  ];

  const roleColumns: GridColDef<Role>[] = [
    { field: 'name', headerName: 'Role', flex: 1, minWidth: 140 },
    { field: 'description', headerName: 'Description', flex: 1, minWidth: 240 },
    {
      field: 'actions',
      type: 'actions',
      width: 90,
      getActions: (params) => [
        <GridActionsCellItem
          icon={<EditIcon />}
          label="Edit"
          onClick={() => {
            setEditingRole(params.row);
            setRoleForm({ name: params.row.name, description: params.row.description ?? '' });
            setRoleOpen(true);
          }}
        />,
        <GridActionsCellItem icon={<DeleteIcon />} label="Delete" onClick={() => rolesApi.remove(params.id as string).then(load)} />,
      ],
    },
  ];

  const saveUser = async () => {
    try {
      if (editingUser) {
        const payload: Record<string, unknown> = {
          role_id: userForm.role_id,
          email: userForm.email,
          first_name: userForm.first_name,
          last_name: userForm.last_name,
          is_active: userForm.is_active,
        };
        if (userForm.password) payload.password = userForm.password;
        await usersApi.update(editingUser.id, payload);
      } else {
        await usersApi.create(userForm);
      }
      setUserOpen(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    }
  };

  const saveRole = async () => {
    try {
      const payload = { ...roleForm, description: roleForm.description || null };
      if (editingRole) await rolesApi.update(editingRole.id, payload);
      else await rolesApi.create(payload);
      setRoleOpen(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    }
  };

  return (
    <Box>
      <PageHeader title="Users & Roles" subtitle="User management and role-based access" />
      <AlertBanner message={error} onClose={() => setError(null)} />
      <Card sx={{ mb: 2 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)}>
          <Tab label="Users" />
          <Tab label="Roles" />
        </Tabs>
      </Card>

      {tab === 0 && (
        <>
          <Box sx={{ mb: 2 }}>
            <Button variant="contained" onClick={() => { setEditingUser(null); setUserForm({ role_id: '', email: '', password: '', first_name: '', last_name: '', is_active: true }); setUserOpen(true); }}>
              New User
            </Button>
          </Box>
          <Card sx={{ p: 1 }}>
            <DataGrid rows={users} columns={userColumns} autoHeight pageSizeOptions={[10, 25]} initialState={{ pagination: { paginationModel: { pageSize: 10 } } }} disableRowSelectionOnClick />
          </Card>
        </>
      )}

      {tab === 1 && (
        <>
          <Box sx={{ mb: 2 }}>
            <Button variant="contained" onClick={() => { setEditingRole(null); setRoleForm({ name: '', description: '' }); setRoleOpen(true); }}>
              New Role
            </Button>
          </Box>
          <Card sx={{ p: 1 }}>
            <DataGrid rows={roles} columns={roleColumns} autoHeight pageSizeOptions={[10, 25]} initialState={{ pagination: { paginationModel: { pageSize: 10 } } }} disableRowSelectionOnClick />
          </Card>
        </>
      )}

      <Dialog open={userOpen} onClose={() => setUserOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingUser ? 'Edit User' : 'New User'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid size={{ xs: 12, sm: 6 }}><TextField label="First Name" fullWidth required value={userForm.first_name} onChange={(e) => setUserForm({ ...userForm, first_name: e.target.value })} /></Grid>
            <Grid size={{ xs: 12, sm: 6 }}><TextField label="Last Name" fullWidth required value={userForm.last_name} onChange={(e) => setUserForm({ ...userForm, last_name: e.target.value })} /></Grid>
            <Grid size={{ xs: 12 }}><TextField label="Email" type="email" fullWidth required value={userForm.email} onChange={(e) => setUserForm({ ...userForm, email: e.target.value })} /></Grid>
            <Grid size={{ xs: 12 }}>
              <FormControl fullWidth required>
                <InputLabel>Role</InputLabel>
                <Select label="Role" value={userForm.role_id} onChange={(e) => setUserForm({ ...userForm, role_id: e.target.value })}>
                  {roles.map((r) => <MenuItem key={r.id} value={r.id}>{r.name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12 }}>
              <TextField
                label={editingUser ? 'New Password (optional)' : 'Password'}
                type="password"
                fullWidth
                required={!editingUser}
                value={userForm.password}
                onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
              />
            </Grid>
            <Grid size={{ xs: 12 }}><FormControlLabel control={<Switch checked={userForm.is_active} onChange={(e) => setUserForm({ ...userForm, is_active: e.target.checked })} />} label="Active" /></Grid>
          </Grid>
        </DialogContent>
        <DialogActions><Button onClick={() => setUserOpen(false)}>Cancel</Button><Button variant="contained" onClick={saveUser}>Save</Button></DialogActions>
      </Dialog>

      <Dialog open={roleOpen} onClose={() => setRoleOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingRole ? 'Edit Role' : 'New Role'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid size={{ xs: 12 }}><TextField label="Name" fullWidth required value={roleForm.name} onChange={(e) => setRoleForm({ ...roleForm, name: e.target.value })} /></Grid>
            <Grid size={{ xs: 12 }}><TextField label="Description" fullWidth multiline rows={3} value={roleForm.description} onChange={(e) => setRoleForm({ ...roleForm, description: e.target.value })} /></Grid>
          </Grid>
        </DialogContent>
        <DialogActions><Button onClick={() => setRoleOpen(false)}>Cancel</Button><Button variant="contained" onClick={saveRole}>Save</Button></DialogActions>
      </Dialog>
    </Box>
  );
}
