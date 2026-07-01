import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Chip,
  FormControlLabel,
  Grid,
  IconButton,
  Switch,
  Tooltip,
  useTheme,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import LockResetIcon from '@mui/icons-material/LockReset';
import PersonOffIcon from '@mui/icons-material/PersonOff';
import PersonIcon from '@mui/icons-material/Person';
import VisibilityIcon from '@mui/icons-material/Visibility';
import BadgeOutlinedIcon from '@mui/icons-material/BadgeOutlined';
import ContactMailOutlinedIcon from '@mui/icons-material/ContactMailOutlined';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { resetUserPassword, rolesApi, usersApi } from '../../api/resources';
import { fetchDepartments } from '../../api/settings';
import { fetchTeams } from '../../api/lookups';
import type { Role, User } from '../../types';
import type { Department } from '../../types/Settings';
import type { Team } from '../../types/Team';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
  ModernDrawer,
  SearchToolbar,
  EmptyState,
} from '../../components/ui/design-system';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import { prosohmDataGridSx } from '../../theme/componentStyles';

interface UserFormState {
  first_name: string;
  last_name: string;
  email: string;
  role_id: string;
  team_id: string;
  department_id: string;
  working_hours_per_day: number;
  working_days: string;
  employment_type: string;
  skill_level: string;
  joining_date: string;
  leaving_date: string;
  availability_status: string;
  max_allocation_percent: number;
  password: string;
  is_active: boolean;
}

const emptyForm: UserFormState = {
  first_name: '',
  last_name: '',
  email: '',
  role_id: '',
  team_id: '',
  department_id: '',
  working_hours_per_day: 8,
  working_days: 'Mon,Tue,Wed,Thu,Fri',
  employment_type: '',
  skill_level: '',
  joining_date: '',
  leaving_date: '',
  availability_status: 'available',
  max_allocation_percent: 100,
  password: '',
  is_active: true,
};

function formatDate(value: string | undefined): string {
  if (!value) return '—';
  return new Date(value).toLocaleDateString();
}

export default function UsersPage() {
  const theme = useTheme();
  const gridSx = useMemo(() => prosohmDataGridSx(theme), [theme]);
  const { showSuccess, showError } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
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

  const roleOptions = useMemo(
    () => roles.map((role) => ({ value: role.id, label: role.name })),
    [roles],
  );

  const activeFilterOptions = [
    { value: 'all', label: 'All' },
    { value: 'active', label: 'Active' },
    { value: 'inactive', label: 'Inactive' },
  ];

  const roleFilterOptions = useMemo(
    () => [{ value: 'all', label: 'All Roles' }, ...roleOptions],
    [roleOptions],
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | boolean> = {};
      if (roleFilter !== 'all') params.role_id = roleFilter;
      if (activeFilter === 'active') params.is_active = true;
      if (activeFilter === 'inactive') params.is_active = false;

      const [usersData, rolesData, teamsData, departmentsData] = await Promise.all([
        usersApi.list(params),
        rolesApi.list(),
        fetchTeams(),
        fetchDepartments(),
      ]);
      setUsers(usersData);
      setRoles(rolesData);
      setTeams(teamsData);
      setDepartments(departmentsData.filter((row) => row.is_active));
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

  const teamOptions = useMemo(
    () => [
      { value: '', label: 'No Team' },
      ...teams.map((team) => ({ value: team.id, label: team.name })),
    ],
    [teams],
  );

  const departmentOptions = useMemo(
    () => [
      { value: '', label: 'No Department' },
      ...departments.map((row) => ({ value: row.id, label: row.name })),
    ],
    [departments],
  );

  const openCreate = () => {
    setEditingUser(null);
    setForm({
      ...emptyForm,
      role_id: roles[0]?.id ?? '',
    });
    setFormOpen(true);
  };

  useOpenCreateFromQuery(openCreate);

  const openEdit = (user: User) => {
    setEditingUser(user);
    setForm({
      first_name: user.first_name,
      last_name: user.last_name,
      email: user.email,
      role_id: user.role_id,
      team_id: user.team_id ?? '',
      department_id: user.department_id ?? '',
      working_hours_per_day: user.working_hours_per_day ?? 8,
      working_days: user.working_days ?? 'Mon,Tue,Wed,Thu,Fri',
      employment_type: user.employment_type ?? '',
      skill_level: user.skill_level ?? '',
      joining_date: user.joining_date ?? '',
      leaving_date: user.leaving_date ?? '',
      availability_status: user.availability_status ?? 'available',
      max_allocation_percent: user.max_allocation_percent ?? 100,
      password: '',
      is_active: user.is_active,
    });
    setFormOpen(true);
  };

  const buildCapacityPayload = () => ({
    department_id: form.department_id || null,
    working_hours_per_day: form.working_hours_per_day,
    working_days: form.working_days,
    employment_type: (form.employment_type || null) as User['employment_type'],
    skill_level: (form.skill_level || null) as User['skill_level'],
    joining_date: form.joining_date || null,
    leaving_date: form.leaving_date || null,
    availability_status: form.availability_status as User['availability_status'],
    max_allocation_percent: form.max_allocation_percent,
  });

  const handleSave = async () => {
    setSaving(true);
    try {
      if (editingUser) {
        await usersApi.update(editingUser.id, {
          first_name: form.first_name,
          last_name: form.last_name,
          email: form.email,
          role_id: form.role_id,
          team_id: form.team_id || null,
          is_active: form.is_active,
          ...buildCapacityPayload(),
        });
        showSuccess('User updated successfully.');
      } else {
        await usersApi.create({
          first_name: form.first_name,
          last_name: form.last_name,
          email: form.email,
          role_id: form.role_id,
          team_id: form.team_id || null,
          password: form.password,
          is_active: form.is_active,
          ...buildCapacityPayload(),
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
      field: 'team_name',
      headerName: 'Team',
      flex: 1,
      minWidth: 130,
      valueGetter: (_value, row) => row.team_name ?? '—',
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
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
            Create User
          </ProsohmButton>
        }
      />

      <SearchToolbar>
        <FormField
          label="Search by name or email"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 260, flex: 1 }}
        />
        <FormSelect
          label="Role"
          value={roleFilter}
          options={roleFilterOptions}
          onChange={(event) => setRoleFilter(String(event.target.value))}
          sx={{ minWidth: 200 }}
        />
        <FormSelect
          label="Status"
          value={activeFilter}
          options={activeFilterOptions}
          onChange={(event) => setActiveFilter(String(event.target.value))}
          sx={{ minWidth: 160 }}
        />
      </SearchToolbar>

      <ContentCard noPadding>
        {filteredUsers.length === 0 ? (
          <EmptyState title="No users found" description="Try adjusting your search or filters." />
        ) : (
          <DataGrid
            rows={filteredUsers}
            columns={columns}
            autoHeight
            disableRowSelectionOnClick
            pageSizeOptions={[10, 25, 50]}
            initialState={{
              pagination: { paginationModel: { pageSize: 10 } },
            }}
            sx={gridSx}
          />
        )}
      </ContentCard>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingUser ? 'Edit User' : 'Create User'}
        subtitle="Manage profile, role, and account status."
        icon={PersonIcon}
        formId="user-form"
        width={560}
        submitLabel={editingUser ? 'Save Changes' : 'Create User'}
        loading={saving}
      >
        <Box
          component="form"
          id="user-form"
          onSubmit={(event) => {
            event.preventDefault();
            void handleSave();
          }}
          sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
        >
          <FormSection title="Contact Details" icon={ContactMailOutlinedIcon}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="First Name"
                required
                value={form.first_name}
                onChange={(event) =>
                  setForm((current) => ({ ...current, first_name: event.target.value }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Last Name"
                required
                value={form.last_name}
                onChange={(event) =>
                  setForm((current) => ({ ...current, last_name: event.target.value }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <FormField
                label="Email"
                type="email"
                required
                value={form.email}
                onChange={(event) =>
                  setForm((current) => ({ ...current, email: event.target.value }))
                }
              />
            </Grid>
          </FormSection>

          <FormSection title="Role & Access" icon={BadgeOutlinedIcon}>
            <Grid size={{ xs: 12 }}>
              <FormSelect
                label="Role"
                required
                value={form.role_id}
                options={roleOptions}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    role_id: String(event.target.value),
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <FormSelect
                label="Team"
                searchable
                value={form.team_id}
                options={teamOptions}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    team_id: String(event.target.value),
                  }))
                }
              />
            </Grid>
            {!editingUser ? (
              <Grid size={{ xs: 12 }}>
                <FormField
                  label="Temporary Password"
                  type="password"
                  required
                  value={form.password}
                  helper="Minimum 8 characters. User must change on first login."
                  onChange={(event) =>
                    setForm((current) => ({ ...current, password: event.target.value }))
                  }
                />
              </Grid>
            ) : null}
            <Grid size={{ xs: 12 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={form.is_active}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, is_active: event.target.checked }))
                    }
                  />
                }
                label="Active account"
              />
            </Grid>
          </FormSection>

          <FormSection title="Designer Capacity" icon={BadgeOutlinedIcon}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Department"
                searchable
                value={form.department_id}
                options={departmentOptions}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    department_id: String(event.target.value),
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Employment Type"
                value={form.employment_type}
                options={[
                  { value: '', label: 'Not set' },
                  { value: 'full_time', label: 'Full Time' },
                  { value: 'part_time', label: 'Part Time' },
                  { value: 'contract', label: 'Contract' },
                  { value: 'intern', label: 'Intern' },
                ]}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    employment_type: String(event.target.value),
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <FormField
                label="Working Hours / Day"
                type="number"
                value={form.working_hours_per_day}
                slotProps={{ htmlInput: { min: 1, max: 24, step: 0.5 } }}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    working_hours_per_day: Number(event.target.value),
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <FormField
                label="Working Days"
                value={form.working_days}
                helper="Comma-separated, e.g. Mon,Tue,Wed,Thu,Fri"
                onChange={(event) =>
                  setForm((current) => ({ ...current, working_days: event.target.value }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <FormField
                label="Max Allocation %"
                type="number"
                value={form.max_allocation_percent}
                slotProps={{ htmlInput: { min: 0, max: 100 } }}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    max_allocation_percent: Number(event.target.value),
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <FormSelect
                label="Skill Level"
                value={form.skill_level}
                options={[
                  { value: '', label: 'Not set' },
                  { value: 'beginner', label: 'Beginner' },
                  { value: 'intermediate', label: 'Intermediate' },
                  { value: 'advanced', label: 'Advanced' },
                  { value: 'expert', label: 'Expert' },
                ]}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    skill_level: String(event.target.value),
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <FormSelect
                label="Availability"
                value={form.availability_status}
                options={[
                  { value: 'available', label: 'Available' },
                  { value: 'allocated', label: 'Allocated' },
                  { value: 'on_leave', label: 'On Leave' },
                  { value: 'unavailable', label: 'Unavailable' },
                ]}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    availability_status: String(event.target.value),
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <FormField
                label="Joining Date"
                type="date"
                slotProps={{ inputLabel: { shrink: true } }}
                value={form.joining_date}
                onChange={(event) =>
                  setForm((current) => ({ ...current, joining_date: event.target.value }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <FormField
                label="Leaving Date"
                type="date"
                slotProps={{ inputLabel: { shrink: true } }}
                value={form.leaving_date}
                onChange={(event) =>
                  setForm((current) => ({ ...current, leaving_date: event.target.value }))
                }
              />
            </Grid>
          </FormSection>
        </Box>
      </FormDrawer>

      <ModernDrawer
        open={Boolean(viewUser)}
        onClose={() => setViewUser(null)}
        title="User Profile"
        subtitle={viewUser ? `${viewUser.first_name} ${viewUser.last_name}` : undefined}
        icon={PersonIcon}
        width={520}
        footer={
          <ProsohmButton buttonVariant="outlined" onClick={() => setViewUser(null)}>
            Close
          </ProsohmButton>
        }
      >
        {viewUser ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <FormSection title="Contact Details" icon={ContactMailOutlinedIcon}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormField label="First Name" value={viewUser.first_name} slotProps={{ input: { readOnly: true } }} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormField label="Last Name" value={viewUser.last_name} slotProps={{ input: { readOnly: true } }} />
              </Grid>
              <Grid size={{ xs: 12 }}>
                <FormField label="Email" value={viewUser.email} slotProps={{ input: { readOnly: true } }} />
              </Grid>
            </FormSection>
            <FormSection title="Employment" icon={BadgeOutlinedIcon}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormField
                  label="Role"
                  value={roleMap.get(viewUser.role_id) ?? '—'}
                  slotProps={{ input: { readOnly: true } }}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormField
                  label="Status"
                  value={viewUser.is_active ? 'Active' : 'Inactive'}
                  slotProps={{ input: { readOnly: true } }}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormField
                  label="Team"
                  value={viewUser.team_name ?? 'No Team'}
                  slotProps={{ input: { readOnly: true } }}
                />
              </Grid>
              <Grid size={{ xs: 12 }}>
                <FormField
                  label="Created Date"
                  value={formatDate(viewUser.created_at)}
                  slotProps={{ input: { readOnly: true } }}
                />
              </Grid>
            </FormSection>
          </Box>
        ) : null}
      </ModernDrawer>

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
