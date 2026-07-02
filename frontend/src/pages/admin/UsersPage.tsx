import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Avatar,
  Box,
  Chip,
  FormControlLabel,
  Grid,
  IconButton,
  Switch,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import PersonIcon from '@mui/icons-material/Person';
import BadgeOutlinedIcon from '@mui/icons-material/BadgeOutlined';
import ContactMailOutlinedIcon from '@mui/icons-material/ContactMailOutlined';
import type { GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { UserDetailsDrawer } from '../../components/admin/UserDetailsDrawer';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { resetUserPassword, rolesApi, usersApi, forceUserPasswordChange, archiveUser, softDeleteUser } from '../../api/resources';
import { fetchDepartments } from '../../api/settings';
import { fetchTeams } from '../../api/lookups';
import { useAuth } from '../../context/AuthContext';
import { ROLES } from '../../utils/permissions';
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
  PasswordField,
  ProsohmDataGrid,
  SearchToolbar,
  EmptyState,
  TableRowActions,
} from '../../components/ui/design-system';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import { DATA_GRID_ACTIONS_COLUMN_WIDTH } from '../../theme/componentStyles';
import { formatCellValue, formatEmploymentType, formatUserWorkload, userDisplayName, userInitials } from '../../utils/format';
import { optionalString, optionalUuid, validateRequiredFields } from '../../utils/formValues';

interface UserFormState {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  designation: string;
  manager_id: string;
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
  confirm_password: string;
  generate_temporary_password: boolean;
  is_active: boolean;
}

const emptyForm: UserFormState = {
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  designation: '',
  manager_id: '',
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
  confirm_password: '',
  generate_temporary_password: false,
  is_active: true,
};

export default function UsersPage() {
  const { showSuccess, showError } = useToast();
  const { user: currentUser, impersonateUser } = useAuth();
  const isAdmin = currentUser?.role_name === ROLES.ADMIN;
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [teamFilter, setTeamFilter] = useState<string>('all');
  const [employmentFilter, setEmploymentFilter] = useState<string>('all');
  const [activeFilter, setActiveFilter] = useState<string>('all');
  const [formOpen, setFormOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [form, setForm] = useState<UserFormState>(emptyForm);
  const [resetTarget, setResetTarget] = useState<User | null>(null);
  const [forceChangeTarget, setForceChangeTarget] = useState<User | null>(null);
  const [impersonateTarget, setImpersonateTarget] = useState<User | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<User | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);
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

  const teamFilterOptions = useMemo(
    () => [
      { value: 'all', label: 'All Teams' },
      ...teams.map((team) => ({ value: team.id, label: team.name })),
    ],
    [teams],
  );

  const employmentFilterOptions = [
    { value: 'all', label: 'All Employment Types' },
    { value: 'full_time', label: 'Full Time' },
    { value: 'part_time', label: 'Part Time' },
    { value: 'contract', label: 'Contract' },
    { value: 'intern', label: 'Intern' },
  ];

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
        usersApi.list({ ...params, limit: 500 }),
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
    return users.filter((user) => {
      if (term) {
        const haystack = [user.first_name, user.last_name, user.email, userDisplayName(user)]
          .join(' ')
          .toLowerCase();
        if (!haystack.includes(term)) return false;
      }
      if (teamFilter !== 'all' && user.team_id !== teamFilter) return false;
      if (employmentFilter !== 'all' && user.employment_type !== employmentFilter) return false;
      return true;
    });
  }, [employmentFilter, search, teamFilter, users]);

  const teamOptions = useMemo(
    () => [
      { value: '', label: 'No Team' },
      ...teams.map((team) => ({ value: team.id, label: team.name })),
    ],
    [teams],
  );

  const managerOptions = useMemo(
    () => [
      { value: '', label: 'No Manager' },
      ...users
        .filter((row) => row.id !== editingUser?.id)
        .map((row) => ({
          value: row.id,
          label: `${row.first_name} ${row.last_name}`,
        })),
    ],
    [users, editingUser?.id],
  );

  const generateTempPassword = () => {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$';
    return Array.from({ length: 12 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
  };

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
      phone: user.phone ?? '',
      designation: user.designation ?? '',
      manager_id: user.manager_id ?? '',
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
      confirm_password: '',
      generate_temporary_password: false,
      is_active: user.is_active,
    });
    setFormOpen(true);
  };

  const buildCapacityPayload = () => ({
    department_id: optionalUuid(form.department_id),
    working_hours_per_day: form.working_hours_per_day,
    working_days: form.working_days,
    employment_type: (optionalString(form.employment_type) || null) as User['employment_type'],
    skill_level: (optionalString(form.skill_level) || null) as User['skill_level'],
    joining_date: optionalString(form.joining_date),
    leaving_date: optionalString(form.leaving_date),
    availability_status: form.availability_status as User['availability_status'],
    max_allocation_percent: form.max_allocation_percent,
  });

  const handleSave = async () => {
    const requiredFields = [
      { key: 'first_name', label: 'First name' },
      { key: 'last_name', label: 'Last name' },
      { key: 'email', label: 'Email' },
      { key: 'role_id', label: 'Role' },
    ];
    if (!editingUser) {
      requiredFields.push(
        { key: 'team_id', label: 'Team' },
        { key: 'employment_type', label: 'Employment type' },
      );
    }
    const validationError = validateRequiredFields(form, requiredFields);
    if (validationError) {
      showError(validationError);
      return;
    }

    if (!editingUser) {
      if (form.password !== form.confirm_password) {
        showError('Password and confirmation do not match.');
        return;
      }
      if (!form.generate_temporary_password && form.password.length < 8) {
        showError('Password must be at least 8 characters.');
        return;
      }
    }

    setSaving(true);
    try {
      const identityPayload = {
        phone: optionalString(form.phone),
        designation: optionalString(form.designation),
        manager_id: optionalUuid(form.manager_id),
      };
      if (editingUser) {
        await usersApi.update(editingUser.id, {
          first_name: form.first_name,
          last_name: form.last_name,
          email: form.email,
          role_id: form.role_id,
          team_id: optionalUuid(form.team_id),
          is_active: form.is_active,
          ...identityPayload,
          ...buildCapacityPayload(),
        });
        showSuccess('User updated successfully.');
      } else {
        const password = form.generate_temporary_password
          ? generateTempPassword()
          : form.password;
        await usersApi.create({
          first_name: form.first_name,
          last_name: form.last_name,
          email: form.email,
          role_id: form.role_id,
          team_id: optionalUuid(form.team_id),
          password,
          must_change_password: form.generate_temporary_password,
          is_active: form.is_active,
          ...identityPayload,
          ...buildCapacityPayload(),
        } as Partial<User> & { password: string; must_change_password?: boolean });
        showSuccess(
          form.generate_temporary_password
            ? `User created. Temporary password: ${password}`
            : 'User created successfully.',
        );
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

  const handleForcePasswordChange = async () => {
    if (!forceChangeTarget) return;
    setActionLoading(true);
    try {
      await forceUserPasswordChange(forceChangeTarget.id);
      showSuccess(`${forceChangeTarget.email} must change password on next login.`);
      setForceChangeTarget(null);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setActionLoading(false);
    }
  };

  const handleImpersonate = async () => {
    if (!impersonateTarget) return;
    setActionLoading(true);
    try {
      await impersonateUser(impersonateTarget.id);
      showSuccess(`Now impersonating ${impersonateTarget.email}.`);
      setImpersonateTarget(null);
      window.location.href = '/dashboard';
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setActionLoading(false);
    }
  };

  const handleArchiveUser = async () => {
    if (!archiveTarget) return;
    setActionLoading(true);
    try {
      await archiveUser(archiveTarget.id);
      showSuccess(`${archiveTarget.email} archived.`);
      setArchiveTarget(null);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteUser = async () => {
    if (!deleteTarget) return;
    setActionLoading(true);
    try {
      await softDeleteUser(deleteTarget.id);
      showSuccess(`${deleteTarget.email} deleted.`);
      setDeleteTarget(null);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setActionLoading(false);
    }
  };

  const columns: GridColDef<User>[] = [
    {
      field: 'avatar',
      headerName: '',
      width: 56,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Avatar sx={{ width: 36, height: 36, bgcolor: 'primary.main', fontSize: '0.875rem' }}>
          {userInitials(params.row)}
        </Avatar>
      ),
    },
    {
      field: 'full_name',
      headerName: 'Full Name',
      flex: 1.2,
      minWidth: 160,
      valueGetter: (_value, row) => userDisplayName(row),
    },
    { field: 'email', headerName: 'Email', flex: 1.5, minWidth: 200 },
    {
      field: 'role_id',
      headerName: 'Role',
      flex: 1,
      minWidth: 130,
      renderCell: (params) => (
        <Chip
          label={formatCellValue(roleMap.get(params.value as string)) || '—'}
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
      minWidth: 120,
      valueGetter: (_value, row) => formatCellValue(row.team_name),
    },
    {
      field: 'employment_type',
      headerName: 'Employment Status',
      width: 150,
      valueGetter: (_value, row) => formatEmploymentType(row.employment_type) || '—',
    },
    {
      field: 'active_projects_count',
      headerName: 'Current Workload',
      width: 140,
      valueGetter: (_value, row) => formatUserWorkload(row.active_projects_count),
    },
    {
      field: 'is_active',
      headerName: 'Status',
      width: 110,
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
              <Tooltip title="Delete">
                <IconButton
                  size="small"
                  color="error"
                  onClick={(event) => {
                    event.stopPropagation();
                    setDeleteTarget(params.row);
                  }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            ) : undefined
          }
        />
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading users…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Users"
        subtitle="Identify team members quickly and manage accounts from the details panel."
        action={
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
            Create User
          </ProsohmButton>
        }
      />

      <SearchToolbar>
        <FormField
          label="Search users"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 260, flex: 1 }}
        />
        <FormSelect
          label="Role"
          value={roleFilter}
          options={roleFilterOptions}
          onChange={(event) => setRoleFilter(String(event.target.value))}
          sx={{ minWidth: 180 }}
        />
        <FormSelect
          label="Team"
          value={teamFilter}
          options={teamFilterOptions}
          onChange={(event) => setTeamFilter(String(event.target.value))}
          sx={{ minWidth: 180 }}
        />
        <FormSelect
          label="Employment Status"
          value={employmentFilter}
          options={employmentFilterOptions}
          onChange={(event) => setEmploymentFilter(String(event.target.value))}
          sx={{ minWidth: 200 }}
        />
        <FormSelect
          label="Active / Inactive"
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
          <ProsohmDataGrid
            rows={filteredUsers}
            columns={columns}
            autoHeight
            pageSizeOptions={[10, 25, 50]}
            initialState={{
              pagination: { paginationModel: { pageSize: 10 } },
            }}
            onRowOpen={(rowId) => {
              const user = filteredUsers.find((item) => item.id === rowId);
              if (user) setSelectedUser(user);
            }}
          />
        )}
      </ContentCard>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingUser ? 'Edit User' : 'Create User'}
        subtitle={
          editingUser
            ? 'Update profile, role, and account settings.'
            : 'Add a team member with the essential details.'
        }
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
          <FormSection title="Basic Information" icon={ContactMailOutlinedIcon}>
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
            <Grid size={{ xs: 12, sm: 6 }}>
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
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Team"
                required={!editingUser}
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
              <FormField
                label="Phone"
                value={form.phone}
                onChange={(event) =>
                  setForm((current) => ({ ...current, phone: event.target.value }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Employment Type"
                required={!editingUser}
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
            {!editingUser ? (
              <>
                <Grid size={{ xs: 12 }}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={form.generate_temporary_password}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            generate_temporary_password: event.target.checked,
                            password: event.target.checked ? generateTempPassword() : '',
                            confirm_password: event.target.checked ? current.password : '',
                          }))
                        }
                      />
                    }
                    label="Generate temporary password"
                  />
                </Grid>
                {!form.generate_temporary_password ? (
                  <>
                    <Grid size={{ xs: 12, sm: 6 }}>
                      <PasswordField
                        label="Temporary Password"
                        required
                        value={form.password}
                        helper="Minimum 8 characters."
                        onChange={(event) =>
                          setForm((current) => ({ ...current, password: event.target.value }))
                        }
                      />
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>
                      <PasswordField
                        label="Confirm Password"
                        required
                        value={form.confirm_password}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            confirm_password: event.target.value,
                          }))
                        }
                      />
                    </Grid>
                  </>
                ) : null}
              </>
            ) : null}
          </FormSection>

          {editingUser ? (
            <>
              <FormSection title="Additional Details" icon={BadgeOutlinedIcon}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormField
                    label="Designation"
                    value={form.designation}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, designation: event.target.value }))
                    }
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormSelect
                    label="Manager"
                    searchable
                    value={form.manager_id}
                    options={managerOptions}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        manager_id: String(event.target.value),
                      }))
                    }
                  />
                </Grid>
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

              <FormSection title="Capacity & Scheduling" icon={BadgeOutlinedIcon}>
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
            </>
          ) : null}
        </Box>
      </FormDrawer>

      <UserDetailsDrawer
        user={selectedUser}
        open={Boolean(selectedUser)}
        onClose={() => setSelectedUser(null)}
        roleLabel={selectedUser ? formatCellValue(roleMap.get(selectedUser.role_id)) || '—' : '—'}
        isAdmin={isAdmin}
        canImpersonate={isAdmin && selectedUser?.id !== currentUser?.id}
        onEdit={(user) => {
          openEdit(user);
          setSelectedUser(null);
        }}
        onDelete={setDeleteTarget}
        onResetPassword={setResetTarget}
        onForcePasswordChange={setForceChangeTarget}
        onToggleActive={setToggleTarget}
        onArchive={setArchiveTarget}
        onImpersonate={setImpersonateTarget}
      />

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

      <ConfirmDialog
        open={Boolean(forceChangeTarget)}
        title="Force Password Change"
        message={
          forceChangeTarget
            ? `Require ${forceChangeTarget.first_name} ${forceChangeTarget.last_name} to change password on next login?`
            : ''
        }
        confirmLabel="Force Change"
        onConfirm={() => void handleForcePasswordChange()}
        onClose={() => setForceChangeTarget(null)}
        loading={actionLoading}
      />

      <ConfirmDialog
        open={Boolean(impersonateTarget)}
        title="Login As User"
        message={
          impersonateTarget
            ? `Sign in as ${impersonateTarget.first_name} ${impersonateTarget.last_name}?`
            : ''
        }
        confirmLabel="Login As User"
        onConfirm={() => void handleImpersonate()}
        onClose={() => setImpersonateTarget(null)}
        loading={actionLoading}
      />

      <ConfirmDialog
        open={Boolean(archiveTarget)}
        title="Archive User"
        message={
          archiveTarget
            ? `Archive ${archiveTarget.first_name} ${archiveTarget.last_name}?`
            : ''
        }
        confirmLabel="Archive"
        onConfirm={() => void handleArchiveUser()}
        onClose={() => setArchiveTarget(null)}
        loading={actionLoading}
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete User"
        message={
          deleteTarget
            ? `Delete ${deleteTarget.first_name} ${deleteTarget.last_name}?`
            : ''
        }
        confirmLabel="Delete"
        onConfirm={() => void handleDeleteUser()}
        onClose={() => setDeleteTarget(null)}
        loading={actionLoading}
      />
    </PageContainer>
  );
}
