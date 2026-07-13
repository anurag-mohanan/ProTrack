import { useCallback, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
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
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import BadgeOutlinedIcon from '@mui/icons-material/BadgeOutlined';
import WorkHistoryOutlinedIcon from '@mui/icons-material/WorkHistoryOutlined';
import ContactMailOutlinedIcon from '@mui/icons-material/ContactMailOutlined';
import type { GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { UserDetailsDrawer } from '../../components/admin/UserDetailsDrawer';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { resetUserPassword, rolesApi, usersApi, forceUserPasswordChange, archiveUser, softDeleteUser, setUserTemporaryPassword, setUserMustChangePassword, unlockUser } from '../../api/resources';
import { fetchDepartments } from '../../api/settings';
import { fetchOperationalRoles, fetchTeams, fetchUsers, fetchWorkingModels } from '../../api/lookups';
import { PaginatedDataGrid } from '../../components/common/PaginatedDataGrid';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { usePaginatedQuery } from '../../hooks/usePaginatedQuery';
import { UserKpiConfiguration } from '../../components/admin/UserKpiConfiguration';
import { useAuth } from '../../context/AuthContext';
import { UserTeamAssignments, type UserTeamAssignmentFormValue } from '../../components/admin/UserTeamAssignments';
import { UserAccessControlSection } from '../../components/admin/UserAccessControlSection';
import type { ModuleKey, SpecialPermissionKey } from '../../config/accessControl';
import { ROLES, defaultModulesForRole, defaultSpecialPermissionsForRole } from '../../utils/permissions';
import type { Role, User, WorkingModel } from '../../types';
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
  FilterDrawer,
  FilterGroup,
  FilterToolbar,
  compactFilterFieldSx,
  EmptyState,
  TableRowActions,
} from '../../components/ui/design-system';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import { DATA_GRID_ACTIONS_COLUMN_WIDTH } from '../../theme/componentStyles';
import { formatCellValue, formatDisplayValue, formatEmploymentType, userDisplayName, userInitials } from '../../utils/format';
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
  team_assignments: UserTeamAssignmentFormValue[];
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
  module_access: ModuleKey[];
  special_permissions: SpecialPermissionKey[];
  operational_role_type_id: string;
  kpi_engineering_productivity: boolean;
  kpi_capacity_planning: boolean;
  kpi_utilization: boolean;
  kpi_workload_planning: boolean;
  kpi_dashboard_productivity: boolean;
  reset_kpi_defaults: boolean;
  default_working_model_id: string;
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
  team_assignments: [],
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
  module_access: [],
  special_permissions: [],
  operational_role_type_id: '',
  kpi_engineering_productivity: true,
  kpi_capacity_planning: true,
  kpi_utilization: true,
  kpi_workload_planning: true,
  kpi_dashboard_productivity: true,
  reset_kpi_defaults: true,
  default_working_model_id: '',
};

export default function UsersPage() {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const { user: currentUser, impersonateUser } = useAuth();
  const isAdmin = currentUser?.role_name === ROLES.ADMIN;
  const [lookupUsers, setLookupUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [operationalRoles, setOperationalRoles] = useState<Array<{ id: string; name: string; code: string; dashboard_profile: string }>>([]);
  const [workingModels, setWorkingModels] = useState<WorkingModel[]>([]);
  const [metadataLoading, setMetadataLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [appliedRoleFilter, setAppliedRoleFilter] = useState<string>('all');
  const [draftRoleFilter, setDraftRoleFilter] = useState<string>('all');
  const [appliedTeamFilter, setAppliedTeamFilter] = useState<string>('all');
  const [draftTeamFilter, setDraftTeamFilter] = useState<string>('all');
  const [appliedEmploymentFilter, setAppliedEmploymentFilter] = useState<string>('all');
  const [draftEmploymentFilter, setDraftEmploymentFilter] = useState<string>('all');
  const [appliedActiveFilter, setAppliedActiveFilter] = useState<string>('all');
  const [draftActiveFilter, setDraftActiveFilter] = useState<string>('all');
  const [formOpen, setFormOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [form, setForm] = useState<UserFormState>(emptyForm);
  const [resetTarget, setResetTarget] = useState<User | null>(null);
  const [tempPasswordTarget, setTempPasswordTarget] = useState<User | null>(null);
  const [unlockTarget, setUnlockTarget] = useState<User | null>(null);
  const [forceChangeTarget, setForceChangeTarget] = useState<User | null>(null);
  const [mustChangeTarget, setMustChangeTarget] = useState<User | null>(null);
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

  const debouncedSearch = useDebouncedValue(search);

  const listFilters = useMemo(() => {
    const params: Record<string, string | boolean> = {};
    if (appliedRoleFilter !== 'all') params.role_id = appliedRoleFilter;
    if (appliedActiveFilter === 'active') params.is_active = true;
    if (appliedActiveFilter === 'inactive') params.is_active = false;
    if (appliedTeamFilter !== 'all') params.team_id = appliedTeamFilter;
    if (appliedEmploymentFilter !== 'all') params.employment_type = appliedEmploymentFilter;
    if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
    return params;
  }, [
    appliedActiveFilter,
    appliedEmploymentFilter,
    appliedRoleFilter,
    appliedTeamFilter,
    debouncedSearch,
  ]);

  const { pagination, query: usersQuery, items: users } = usePaginatedQuery<User>({
    queryKey: ['users'],
    fetcher: usersApi.listPaginated,
    filters: listFilters,
    enabled: !metadataLoading,
  });

  const refreshUsers = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['users'] });
  }, [queryClient]);

  const loadMetadata = useCallback(async () => {
    setMetadataLoading(true);
    try {
      const [rolesData, teamsData, departmentsData, operationalRolesData, lookupUsersData, workingModelsData] =
        await Promise.all([
          rolesApi.list(),
          fetchTeams(),
          fetchDepartments(),
          fetchOperationalRoles(),
          fetchUsers(),
          fetchWorkingModels(),
        ]);
      setRoles(rolesData);
      setTeams(teamsData);
      setDepartments(departmentsData.filter((row) => row.is_active));
      setOperationalRoles(operationalRolesData);
      setLookupUsers(lookupUsersData);
      setWorkingModels(workingModelsData.filter((model) => model.is_active && !model.is_archived));
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setMetadataLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    void loadMetadata();
  }, [loadMetadata]);

  const managerOptions = useMemo(
    () => [
      { value: '', label: 'No Manager' },
      ...lookupUsers
        .filter((row) => row.id !== editingUser?.id)
        .map((row) => ({
          value: row.id,
          label: `${row.first_name} ${row.last_name}`,
        })),
    ],
    [lookupUsers, editingUser?.id],
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
    const defaultRoleId = roles[0]?.id ?? '';
    const defaultRoleName = roles[0]?.name ?? ROLES.DESIGNER;
    setEditingUser(null);
    setForm({
      ...emptyForm,
      role_id: defaultRoleId,
      module_access: defaultModulesForRole(defaultRoleName),
      special_permissions: defaultSpecialPermissionsForRole(defaultRoleName),
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
      team_assignments:
        user.team_assignments?.map((row) => ({
          team_id: row.team_id,
          team_name: row.team_name ?? teams.find((team) => team.id === row.team_id)?.name ?? '',
          relationship_type: row.relationship_type,
          is_primary: row.is_primary,
        })) ??
        (user.team_id
          ? [
              {
                team_id: user.team_id,
                team_name: user.team_name ?? '',
                relationship_type: 'member' as const,
                is_primary: true,
              },
            ]
          : []),
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
      module_access: (user.resolved_modules ?? user.module_access ?? defaultModulesForRole(roleMap.get(user.role_id) ?? '')) as ModuleKey[],
      special_permissions: (user.resolved_special_permissions ?? user.special_permissions ?? defaultSpecialPermissionsForRole(roleMap.get(user.role_id) ?? '')) as SpecialPermissionKey[],
      operational_role_type_id: user.kpi_configuration?.operational_role_type_id ?? user.operational_role_type_id ?? '',
      kpi_engineering_productivity: user.kpi_configuration?.kpi_engineering_productivity ?? user.kpi_engineering_productivity ?? true,
      kpi_capacity_planning: user.kpi_configuration?.kpi_capacity_planning ?? user.kpi_capacity_planning ?? true,
      kpi_utilization: user.kpi_configuration?.kpi_utilization ?? user.kpi_utilization ?? true,
      kpi_workload_planning: user.kpi_configuration?.kpi_workload_planning ?? user.kpi_workload_planning ?? true,
      kpi_dashboard_productivity: user.kpi_configuration?.kpi_dashboard_productivity ?? user.kpi_dashboard_productivity ?? true,
      reset_kpi_defaults: false,
      default_working_model_id: user.default_working_model_id ?? '',
    });
    setFormOpen(true);
  };

  const buildKpiPayload = () => ({
    operational_role_type_id: optionalUuid(form.operational_role_type_id),
    kpi_engineering_productivity: form.kpi_engineering_productivity,
    kpi_capacity_planning: form.kpi_capacity_planning,
    kpi_utilization: form.kpi_utilization,
    kpi_workload_planning: form.kpi_workload_planning,
    kpi_dashboard_productivity: form.kpi_dashboard_productivity,
    reset_kpi_defaults: form.reset_kpi_defaults,
  });

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
      requiredFields.push({ key: 'employment_type', label: 'Employment type' });
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

    if (!editingUser && form.team_assignments.length === 0) {
      showError('Select at least one team for the user.');
      return;
    }
    // Primary team is optional (EM / Design Leaders often oversee multiple teams).

    setSaving(true);
    try {
      const teamAssignmentsPayload = form.team_assignments.map((row) => ({
        team_id: row.team_id,
        relationship_type: row.relationship_type,
        is_primary: row.is_primary,
      }));
      const primaryTeamId =
        form.team_assignments.find((row) => row.is_primary)?.team_id ?? optionalUuid(form.team_id);
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
          team_id: primaryTeamId,
          team_assignments: teamAssignmentsPayload,
          is_active: form.is_active,
          ...identityPayload,
          ...buildCapacityPayload(),
          ...buildKpiPayload(),
          default_working_model_id: optionalUuid(form.default_working_model_id),
          module_access: form.module_access,
          special_permissions: form.special_permissions,
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
          team_id: primaryTeamId,
          team_assignments: teamAssignmentsPayload,
          password,
          must_change_password: form.generate_temporary_password,
          is_active: form.is_active,
          ...identityPayload,
          ...buildCapacityPayload(),
          ...buildKpiPayload(),
          default_working_model_id: optionalUuid(form.default_working_model_id),
          module_access: form.module_access,
          special_permissions: form.special_permissions,
        } as Partial<User> & { password: string; must_change_password?: boolean });
        showSuccess(
          form.generate_temporary_password
            ? `User created. Temporary password: ${password}`
            : 'User created successfully.',
        );
      }
      setFormOpen(false);
      await refreshUsers();
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

  const handleSetTemporaryPassword = async () => {
    if (!tempPasswordTarget) return;
    setActionLoading(true);
    try {
      const result = await setUserTemporaryPassword(tempPasswordTarget.id);
      showSuccess(
        result.temporary_password
          ? `${result.message} Temporary password: ${result.temporary_password}`
          : result.message,
      );
      setTempPasswordTarget(null);
      await refreshUsers();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setActionLoading(false);
    }
  };

  const handleUnlockUser = async () => {
    if (!unlockTarget) return;
    setActionLoading(true);
    try {
      await unlockUser(unlockTarget.id);
      showSuccess(`${unlockTarget.email} has been unlocked.`);
      setUnlockTarget(null);
      await refreshUsers();
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
      await refreshUsers();
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
      await refreshUsers();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setActionLoading(false);
    }
  };

  const handleToggleMustChangePassword = async () => {
    if (!mustChangeTarget) return;
    setActionLoading(true);
    try {
      const required = !mustChangeTarget.must_change_password;
      await setUserMustChangePassword(mustChangeTarget.id, required);
      showSuccess(
        required
          ? `${mustChangeTarget.email} will be required to change password when production mode is enabled.`
          : `${mustChangeTarget.email} no longer requires a password change.`,
      );
      setMustChangeTarget(null);
      await refreshUsers();
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
      await refreshUsers();
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
      await refreshUsers();
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
      headerName: 'Teams',
      flex: 1.2,
      minWidth: 160,
      valueGetter: (_value, row) =>
        row.team_names?.length
          ? row.team_names.join(', ')
          : formatDisplayValue(row.team_name),
    },
    {
      field: 'employment_type',
      headerName: 'Employment',
      width: 140,
      valueGetter: (_value, row) => formatEmploymentType(row.employment_type) || '—',
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

  if (metadataLoading && users.length === 0) return <LoadingState message="Loading users…" />;

  const activeFilterCount =
    (appliedRoleFilter !== 'all' ? 1 : 0) +
    (appliedTeamFilter !== 'all' ? 1 : 0) +
    (appliedEmploymentFilter !== 'all' ? 1 : 0) +
    (appliedActiveFilter !== 'all' ? 1 : 0);

  const filterChips = [
    appliedRoleFilter !== 'all'
      ? {
          key: 'role',
          label: `Role: ${roleMap.get(appliedRoleFilter) ?? 'Unknown'}`,
          onRemove: () => {
            setAppliedRoleFilter('all');
            setDraftRoleFilter('all');
          },
        }
      : null,
    appliedTeamFilter !== 'all'
      ? {
          key: 'team',
          label: `Team: ${teams.find((team) => team.id === appliedTeamFilter)?.name ?? 'Unknown'}`,
          onRemove: () => {
            setAppliedTeamFilter('all');
            setDraftTeamFilter('all');
          },
        }
      : null,
    appliedEmploymentFilter !== 'all'
      ? {
          key: 'employment',
          label: `Employment: ${formatEmploymentType(appliedEmploymentFilter)}`,
          onRemove: () => {
            setAppliedEmploymentFilter('all');
            setDraftEmploymentFilter('all');
          },
        }
      : null,
    appliedActiveFilter !== 'all'
      ? {
          key: 'active',
          label: `Status: ${appliedActiveFilter === 'active' ? 'Active' : 'Inactive'}`,
          onRemove: () => {
            setAppliedActiveFilter('all');
            setDraftActiveFilter('all');
          },
        }
      : null,
  ].filter((chip): chip is NonNullable<typeof chip> => chip !== null);

  const applyFilters = () => {
    setAppliedRoleFilter(draftRoleFilter);
    setAppliedTeamFilter(draftTeamFilter);
    setAppliedEmploymentFilter(draftEmploymentFilter);
    setAppliedActiveFilter(draftActiveFilter);
  };

  const resetFilters = () => {
    setDraftRoleFilter('all');
    setDraftTeamFilter('all');
    setDraftEmploymentFilter('all');
    setDraftActiveFilter('all');
  };

  const clearFilters = () => {
    setAppliedRoleFilter('all');
    setDraftRoleFilter('all');
    setAppliedTeamFilter('all');
    setDraftTeamFilter('all');
    setAppliedEmploymentFilter('all');
    setDraftEmploymentFilter('all');
    setAppliedActiveFilter('all');
    setDraftActiveFilter('all');
  };

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

      <FilterToolbar
        sticky
        filterButton={{ activeCount: activeFilterCount, onClick: () => setFiltersOpen(true) }}
        chips={filterChips}
        onClearAll={clearFilters}
      >
        <FormField
          label="Search users"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 260, flex: 1, maxWidth: 420 }}
        />
      </FilterToolbar>

      <ContentCard noPadding>
        {users.length === 0 && !usersQuery.isFetching ? (
          <EmptyState title="No users found" description="Try adjusting your search or filters." />
        ) : (
          <PaginatedDataGrid
            rows={users}
            columns={columns}
            pagination={pagination}
            loading={usersQuery.isFetching}
            pinLeftFields={['full_name']}
            autoHeight
            onRowOpen={(rowId) => {
              const user = users.find((item) => item.id === rowId);
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
                onChange={(event) => {
                  const nextRoleId = String(event.target.value);
                  const nextRoleName = roleMap.get(nextRoleId) ?? ROLES.DESIGNER;
                  setForm((current) => ({
                    ...current,
                    role_id: nextRoleId,
                    module_access: defaultModulesForRole(nextRoleName),
                    special_permissions: defaultSpecialPermissionsForRole(nextRoleName),
                  }));
                }}
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <UserTeamAssignments
                teams={teams.map((team) => ({ id: team.id, name: team.name }))}
                value={form.team_assignments}
                onChange={(team_assignments) =>
                  setForm((current) => ({
                    ...current,
                    team_assignments,
                    team_id:
                      team_assignments.find((row) => row.is_primary)?.team_id ?? '',
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

          <UserKpiConfiguration
            operationalRoles={operationalRoles}
            value={{
              operational_role_type_id: form.operational_role_type_id,
              kpi_engineering_productivity: form.kpi_engineering_productivity,
              kpi_capacity_planning: form.kpi_capacity_planning,
              kpi_utilization: form.kpi_utilization,
              kpi_workload_planning: form.kpi_workload_planning,
              kpi_dashboard_productivity: form.kpi_dashboard_productivity,
              reset_kpi_defaults: form.reset_kpi_defaults,
            }}
            onChange={(next) =>
              setForm((current) => ({
                ...current,
                ...next,
              }))
            }
          />

          <FormSection title="Working Model Default" icon={WorkHistoryOutlinedIcon}>
            <FormSelect
              label="Default Working Model"
              value={form.default_working_model_id}
              helper="Used when no project-level working model is set. Choose Overheads for Engineering Managers, HR, Office Admin, and other non-designer resources. Project working model always takes precedence."
              options={[
                { value: '', label: 'None' },
                ...workingModels.map((model) => ({ value: model.id, label: model.name })),
              ]}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  default_working_model_id: String(event.target.value),
                }))
              }
            />
          </FormSection>

          <UserAccessControlSection
            roleName={roleMap.get(form.role_id) ?? ROLES.DESIGNER}
            moduleAccess={form.module_access}
            specialPermissions={form.special_permissions}
            onModuleAccessChange={(module_access) => setForm((current) => ({ ...current, module_access }))}
            onSpecialPermissionsChange={(special_permissions) =>
              setForm((current) => ({ ...current, special_permissions }))
            }
          />

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
        onSetTemporaryPassword={setTempPasswordTarget}
        onForcePasswordChange={setForceChangeTarget}
        onToggleMustChangePassword={setMustChangeTarget}
        onUnlockUser={setUnlockTarget}
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
        open={Boolean(tempPasswordTarget)}
        title="Set Temporary Password"
        message={
          tempPasswordTarget
            ? `Set the standard soft-launch temporary password for ${tempPasswordTarget.first_name} ${tempPasswordTarget.last_name}? They will be required to change it on next login.`
            : ''
        }
        confirmLabel="Set Temporary Password"
        onConfirm={() => void handleSetTemporaryPassword()}
        onClose={() => setTempPasswordTarget(null)}
        loading={actionLoading}
      />

      <ConfirmDialog
        open={Boolean(unlockTarget)}
        title="Unlock User"
        message={
          unlockTarget
            ? `Unlock ${unlockTarget.first_name} ${unlockTarget.last_name} and reset failed login attempts?`
            : ''
        }
        confirmLabel="Unlock User"
        onConfirm={() => void handleUnlockUser()}
        onClose={() => setUnlockTarget(null)}
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
        open={Boolean(mustChangeTarget)}
        title={
          mustChangeTarget?.must_change_password
            ? 'Disable Must Change Password'
            : 'Enable Must Change Password'
        }
        message={
          mustChangeTarget
            ? mustChangeTarget.must_change_password
              ? `Clear the must-change-password flag for ${mustChangeTarget.first_name} ${mustChangeTarget.last_name}?`
              : `Require ${mustChangeTarget.first_name} ${mustChangeTarget.last_name} to change password when production mode is enabled?`
            : ''
        }
        confirmLabel={
          mustChangeTarget?.must_change_password ? 'Disable Requirement' : 'Enable Requirement'
        }
        onConfirm={() => void handleToggleMustChangePassword()}
        onClose={() => setMustChangeTarget(null)}
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
        recordName={
          deleteTarget ? `${deleteTarget.first_name} ${deleteTarget.last_name}`.trim() : undefined
        }
        message="This user will be removed from active lists. You can restore them from Deleted Users."
        confirmLabel="Delete"
        danger
        onConfirm={() => void handleDeleteUser()}
        onClose={() => setDeleteTarget(null)}
        loading={actionLoading}
      />

      <FilterDrawer
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        title="User filters"
        onApply={applyFilters}
        onReset={resetFilters}
      >
        <Box sx={{ pb: 1 }}>
          <Box sx={{ ...compactFilterFieldSx, display: 'flex', flexDirection: 'column', gap: 1 }}>
            <FormSelect
              label="Role"
              size="small"
              value={draftRoleFilter}
              options={roleFilterOptions}
              onChange={(event) => setDraftRoleFilter(String(event.target.value))}
            />
            <FormSelect
              label="Team"
              size="small"
              value={draftTeamFilter}
              options={teamFilterOptions}
              onChange={(event) => setDraftTeamFilter(String(event.target.value))}
            />
          </Box>
        </Box>
        <FilterGroup title="Advanced filters" icon={<GroupsOutlinedIcon sx={{ fontSize: 14 }} />}>
          <Box sx={{ ...compactFilterFieldSx, display: 'flex', flexDirection: 'column', gap: 1 }}>
            <FormSelect
              label="Employment status"
              size="small"
              value={draftEmploymentFilter}
              options={employmentFilterOptions}
              onChange={(event) => setDraftEmploymentFilter(String(event.target.value))}
            />
            <FormSelect
              label="Active / inactive"
              size="small"
              value={draftActiveFilter}
              options={activeFilterOptions}
              onChange={(event) => setDraftActiveFilter(String(event.target.value))}
            />
          </Box>
        </FilterGroup>
      </FilterDrawer>
    </PageContainer>
  );
}
