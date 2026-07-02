import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Box, Chip } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import BadgeOutlinedIcon from '@mui/icons-material/BadgeOutlined';
import type { GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { AdminDeleteButton } from '../../components/admin/AdminDeleteButton';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { rolesApi } from '../../api/resources';
import type { Role } from '../../types';
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
import { formatCellValue, formatDateTime } from '../../utils/format';
import { optionalString, validateRequiredFields } from '../../utils/formValues';
import { canDeleteRecords } from '../../utils/permissions';
import { useAuth } from '../../context/AuthContext';
import { DATA_GRID_ACTIONS_COLUMN_WIDTH } from '../../theme/componentStyles';

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

function isSystemRole(role: Role): boolean {
  return SYSTEM_ROLE_NAMES.has(role.name);
}

export default function RolesPage() {
  const { user } = useAuth();
  const isAdmin = canDeleteRecords(user?.role_name ?? '');
  const { showSuccess, showError } = useToast();
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
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

  const handleSave = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!editingRole) {
      const validationError = validateRequiredFields(form, [{ key: 'name', label: 'Name' }]);
      if (validationError) {
        showError(validationError);
        return;
      }
    }
    setSaving(true);
    try {
      const payload = {
        description: optionalString(form.description),
        ...(editingRole && !isSystemRole(editingRole) ? { name: form.name } : {}),
        ...(!editingRole ? { name: form.name.trim(), description: optionalString(form.description) } : {}),
      };

      if (editingRole) {
        await rolesApi.update(editingRole.id, payload);
        showSuccess('Role updated successfully.');
      } else {
        await rolesApi.create({
          name: form.name.trim(),
          description: optionalString(form.description),
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
      valueFormatter: (value) => formatCellValue(value as string | null),
    },
    {
      field: 'created_at',
      headerName: 'Created Date',
      width: 130,
      valueFormatter: (value) => formatDateTime(value as string | undefined),
    },
    {
      field: 'actions',
      headerName: '',
      width: isAdmin && filteredRoles.some((role) => !isSystemRole(role))
        ? DATA_GRID_ACTIONS_COLUMN_WIDTH + 40
        : DATA_GRID_ACTIONS_COLUMN_WIDTH,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <TableRowActions
          onEdit={() => openEdit(params.row)}
          deleteAction={
            isAdmin && !isSystemRole(params.row) ? (
              <AdminDeleteButton
                resource="roles"
                recordId={params.row.id}
                recordName={params.row.name}
                onDeleted={() => void loadData()}
              />
            ) : undefined
          }
        />
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading roles…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Roles"
        subtitle="Manage user roles and permissions"
        action={
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
            Create Role
          </ProsohmButton>
        }
      />

      <Box sx={{ mb: 2 }}>
        <ContentCard title="System Roles">
          <Box sx={{ mb: 1.5, color: 'text.secondary', typography: 'body2' }}>
            These roles are built into ProTrack. You can edit their descriptions but not their names or delete them.
          </Box>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {systemRoles.map((role) => (
              <Chip key={role.id} label={role.name} color="info" variant="outlined" />
            ))}
          </Box>
        </ContentCard>
      </Box>

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
          rows={filteredRoles}
          columns={columns}
          autoHeight
          pageSizeOptions={[10, 25, 50]}
          initialState={{
            pagination: { paginationModel: { pageSize: 10 } },
          }}
          onRowOpen={(rowId) => {
            const role = filteredRoles.find((item) => item.id === rowId);
            if (role) setSelectedRole(role);
          }}
        />
      </ContentCard>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingRole ? 'Edit Role' : 'Create Role'}
        subtitle="User role configuration"
        icon={BadgeOutlinedIcon}
        formId="role-form"
        submitLabel={editingRole ? 'Save Changes' : 'Create Role'}
        loading={saving}
      >
        <Box
          component="form"
          id="role-form"
          onSubmit={(event) => void handleSave(event)}
          sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
        >
          <FormSection title="Role Details" icon={BadgeOutlinedIcon}>
            <FormField
              label="Name"
              required
              value={form.name}
              onChange={(event) =>
                setForm((current) => ({ ...current, name: event.target.value }))
              }
              disabled={Boolean(editingRole && isSystemRole(editingRole))}
              helperText={
                editingRole && isSystemRole(editingRole)
                  ? 'System role names cannot be changed.'
                  : undefined
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
          </FormSection>
        </Box>
      </FormDrawer>

      <RecordDetailDrawer
        open={Boolean(selectedRole)}
        onClose={() => setSelectedRole(null)}
        title={selectedRole?.name ?? 'Role'}
        subtitle="User role"
        icon={BadgeOutlinedIcon}
        status={
          selectedRole ? (
            <Chip
              label={isSystemRole(selectedRole) ? 'System Role' : 'Custom Role'}
              size="small"
              color={isSystemRole(selectedRole) ? 'info' : 'default'}
              variant={isSystemRole(selectedRole) ? 'outlined' : 'filled'}
            />
          ) : null
        }
        quickActions={
          selectedRole ? (
            <DrawerQuickActions>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => {
                  openEdit(selectedRole);
                  setSelectedRole(null);
                }}
              >
                Edit
              </ProsohmButton>
              {isAdmin && !isSystemRole(selectedRole) ? (
                <AdminDeleteButton
                  mode="button"
                  resource="roles"
                  recordId={selectedRole.id}
                  recordName={selectedRole.name}
                  onDeleted={() => {
                    setSelectedRole(null);
                    void loadData();
                  }}
                />
              ) : null}
            </DrawerQuickActions>
          ) : null
        }
      >
        {selectedRole ? (
          <FormSection title="Overview" icon={BadgeOutlinedIcon}>
            <FormField label="Name" value={selectedRole.name} slotProps={{ input: { readOnly: true } }} />
            <FormField
              label="Description"
              value={formatCellValue(selectedRole.description) || '—'}
              multiline
              minRows={2}
              slotProps={{ input: { readOnly: true } }}
            />
            <FormField
              label="Created Date"
              value={formatDateTime(selectedRole.created_at) || '—'}
              slotProps={{ input: { readOnly: true } }}
            />
          </FormSection>
        ) : null}
      </RecordDetailDrawer>
    </PageContainer>
  );
}
