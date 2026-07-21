import { useMemo, useState, type FormEvent } from 'react';
import { Box, Chip, MenuItem, Stack, TextField, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import BadgeOutlinedIcon from '@mui/icons-material/BadgeOutlined';
import PeopleAltOutlinedIcon from '@mui/icons-material/PeopleAltOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  FormDrawer,
  FormField,
  FormSection,
  TableRowActions,
} from '../../components/ui/design-system';
import { AdminDeleteButton } from '../../components/admin/AdminDeleteButton';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { rolesApi } from '../../api/resources';
import type { RoleHierarchyDepartment, RoleHierarchyNode } from '../../types';

interface RoleFormState {
  id: string | null;
  name: string;
  description: string;
  org_department_id: string;
  rank: string;
  parent_role_id: string;
  isSystem: boolean;
}

const emptyForm: RoleFormState = {
  id: null,
  name: '',
  description: '',
  org_department_id: '',
  rank: '100',
  parent_role_id: '',
  isSystem: false,
};

/** Depth of a role within its department (staying inside the department). */
function computeDepth(node: RoleHierarchyNode, byId: Map<string, RoleHierarchyNode>): number {
  let depth = 0;
  let current = node;
  const seen = new Set<string>([node.id]);
  while (current.parent_role_id && byId.has(current.parent_role_id)) {
    const parent = byId.get(current.parent_role_id)!;
    if (seen.has(parent.id)) break;
    seen.add(parent.id);
    depth += 1;
    current = parent;
  }
  return depth;
}

export default function RoleHierarchyPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<RoleFormState>(emptyForm);

  const hierarchyQuery = useQuery({
    queryKey: ['roles', 'hierarchy'],
    queryFn: rolesApi.hierarchy,
  });

  const departments = hierarchyQuery.data?.departments ?? [];

  const departmentOptions = useMemo(
    () =>
      departments
        .filter((dept) => dept.department_id)
        .map((dept) => ({ id: dept.department_id as string, name: dept.department_name })),
    [departments],
  );

  const allRoles = useMemo(
    () => departments.flatMap((dept) => dept.roles),
    [departments],
  );

  const totals = useMemo(() => {
    const roleCount = allRoles.length;
    const people = allRoles.reduce((sum, role) => sum + role.user_count, 0);
    return { roleCount, people, deptCount: departmentOptions.length };
  }, [allRoles, departmentOptions]);

  const saveMutation = useMutation({
    mutationFn: async (state: RoleFormState) => {
      const payload = {
        name: state.name.trim(),
        description: state.description.trim() || null,
        org_department_id: state.org_department_id || null,
        rank: Number.isFinite(Number(state.rank)) ? Number(state.rank) : 100,
        parent_role_id: state.parent_role_id || null,
      };
      if (state.id) {
        return rolesApi.update(state.id, payload);
      }
      return rolesApi.create(payload);
    },
    onSuccess: (_data, state) => {
      showSuccess(state.id ? 'Role updated.' : 'Role created.');
      setFormOpen(false);
      void queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const openCreate = (departmentId?: string | null) => {
    setForm({ ...emptyForm, org_department_id: departmentId ?? '' });
    setFormOpen(true);
  };

  const openEdit = (node: RoleHierarchyNode, departmentId: string | null) => {
    setForm({
      id: node.id,
      name: node.name,
      description: node.description ?? '',
      org_department_id: departmentId ?? '',
      rank: String(node.rank ?? 100),
      parent_role_id: node.parent_role_id ?? '',
      isSystem: node.is_system,
    });
    setFormOpen(true);
  };

  const handleSubmit = (event?: FormEvent) => {
    event?.preventDefault();
    if (!form.name.trim()) {
      showError('Role name is required.');
      return;
    }
    saveMutation.mutate(form);
  };

  if (hierarchyQuery.isLoading) return <LoadingState message="Loading role hierarchy…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Role Hierarchy"
        subtitle="Standardized roles grouped by department and placed top → bottom by seniority. New roles slot into the hierarchy without affecting existing access control."
        action={
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={() => openCreate()}>
            Create Role
          </ProsohmButton>
        }
      />

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mb: 2 }}>
        <ContentCard>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
            <AccountTreeIcon color="primary" />
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 800, lineHeight: 1 }}>
                {totals.roleCount}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Roles across {totals.deptCount} departments
              </Typography>
            </Box>
          </Stack>
        </ContentCard>
        <ContentCard>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
            <PeopleAltOutlinedIcon color="success" />
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 800, lineHeight: 1 }}>
                {totals.people}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                People assigned to roles
              </Typography>
            </Box>
          </Stack>
        </ContentCard>
      </Stack>

      <Stack spacing={2}>
        {departments.map((dept) => (
          <DepartmentCard
            key={dept.department_id ?? dept.department_name}
            dept={dept}
            onAdd={() => openCreate(dept.department_id)}
            onEdit={(node) => openEdit(node, dept.department_id)}
            onDeleted={() => void queryClient.invalidateQueries({ queryKey: ['roles'] })}
          />
        ))}
      </Stack>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={form.id ? 'Edit Role' : 'Create Role'}
        subtitle="Place the role in the org hierarchy"
        icon={BadgeOutlinedIcon}
        formId="role-hierarchy-form"
        submitLabel={form.id ? 'Save Changes' : 'Create Role'}
        loading={saveMutation.isPending}
      >
        <Box
          component="form"
          id="role-hierarchy-form"
          onSubmit={(event) => void handleSubmit(event)}
          sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
        >
          <FormSection title="Role Details" icon={BadgeOutlinedIcon}>
            <FormField
              label="Name"
              required
              value={form.name}
              disabled={form.isSystem}
              helperText={form.isSystem ? 'System role names cannot be changed.' : undefined}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
            />
            <FormField
              label="Description"
              value={form.description}
              multiline
              minRows={2}
              onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
            />
          </FormSection>

          <FormSection title="Hierarchy Placement" icon={AccountTreeIcon}>
            <TextField
              select
              fullWidth
              size="small"
              label="Department"
              value={form.org_department_id}
              onChange={(event) => setForm((prev) => ({ ...prev, org_department_id: event.target.value }))}
            >
              <MenuItem value="">— No department (system) —</MenuItem>
              {departmentOptions.map((dept) => (
                <MenuItem key={dept.id} value={dept.id}>
                  {dept.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              fullWidth
              size="small"
              label="Reports to (parent role)"
              value={form.parent_role_id}
              onChange={(event) => setForm((prev) => ({ ...prev, parent_role_id: event.target.value }))}
            >
              <MenuItem value="">— Top of hierarchy —</MenuItem>
              {allRoles
                .filter((role) => role.id !== form.id)
                .map((role) => (
                  <MenuItem key={role.id} value={role.id}>
                    {role.name}
                  </MenuItem>
                ))}
            </TextField>
            <FormField
              label="Rank (lower = more senior)"
              type="number"
              value={form.rank}
              onChange={(event) => setForm((prev) => ({ ...prev, rank: event.target.value }))}
              helperText="Controls top-to-bottom ordering within the department."
            />
          </FormSection>
        </Box>
      </FormDrawer>
    </PageContainer>
  );
}

function DepartmentCard({
  dept,
  onAdd,
  onEdit,
  onDeleted,
}: {
  dept: RoleHierarchyDepartment;
  onAdd: () => void;
  onEdit: (node: RoleHierarchyNode) => void;
  onDeleted: () => void;
}) {
  const accent = dept.colour ?? '#607d8b';
  const byId = useMemo(() => {
    const map = new Map<string, RoleHierarchyNode>();
    dept.roles.forEach((role) => map.set(role.id, role));
    return map;
  }, [dept.roles]);

  return (
    <ContentCard noPadding>
      <Box
        sx={{
          px: 2,
          py: 1.5,
          borderLeft: `4px solid ${accent}`,
          borderTopLeftRadius: 8,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 2,
          flexWrap: 'wrap',
        }}
      >
        <Box>
          <Typography sx={{ fontWeight: 800 }}>{dept.department_name}</Typography>
          <Typography variant="caption" color="text.secondary">
            {dept.roles.length} roles
          </Typography>
        </Box>
        {dept.department_id ? (
          <ProsohmButton buttonVariant="outlined" size="small" startIcon={<AddIcon />} onClick={onAdd}>
            Add role
          </ProsohmButton>
        ) : null}
      </Box>

      <Stack sx={{ p: 1.5 }} spacing={0.75}>
        {dept.roles.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ px: 1, py: 0.5 }}>
            No roles in this department yet.
          </Typography>
        ) : (
          dept.roles.map((node) => {
            const depth = computeDepth(node, byId);
            return (
              <Box
                key={node.id}
                sx={{
                  ml: `${depth * 24}px`,
                  px: 1.5,
                  py: 1,
                  borderRadius: 1.5,
                  border: '1px solid',
                  borderColor: 'divider',
                  bgcolor: 'background.paper',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 1.5,
                  borderLeft: depth > 0 ? `3px solid ${accent}55` : `1px solid`,
                }}
              >
                <Box sx={{ minWidth: 0 }}>
                  <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                    <Typography sx={{ fontWeight: 700 }}>{node.name}</Typography>
                    {node.is_system ? (
                      <Chip label="System" size="small" color="info" variant="outlined" />
                    ) : null}
                    <Chip label={`rank ${node.rank}`} size="small" variant="outlined" />
                    {node.user_count > 0 ? (
                      <Chip
                        label={`${node.user_count} ${node.user_count === 1 ? 'person' : 'people'}`}
                        size="small"
                        color="success"
                        variant="outlined"
                      />
                    ) : null}
                    {!node.is_active ? (
                      <Chip label="Inactive" size="small" color="warning" variant="outlined" />
                    ) : null}
                  </Stack>
                  {node.parent_role_name ? (
                    <Typography variant="caption" color="text.secondary">
                      Reports to {node.parent_role_name}
                    </Typography>
                  ) : node.description ? (
                    <Typography variant="caption" color="text.secondary">
                      {node.description}
                    </Typography>
                  ) : null}
                </Box>
                <TableRowActions
                  onEdit={() => onEdit(node)}
                  deleteAction={
                    node.is_system ? undefined : (
                      <AdminDeleteButton
                        resource="roles"
                        recordId={node.id}
                        recordName={node.name}
                        onDeleted={onDeleted}
                      />
                    )
                  }
                />
              </Box>
            );
          })
        )}
      </Stack>
    </ContentCard>
  );
}
