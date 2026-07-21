import { useMemo, useState, type FormEvent } from 'react';
import { Box, Chip, MenuItem, Stack, TextField, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ApartmentIcon from '@mui/icons-material/Apartment';
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
import { orgDepartmentsApi, usersApi } from '../../api/resources';
import type { OrgDepartment } from '../../types';

interface DeptFormState {
  id: string | null;
  code: string;
  name: string;
  description: string;
  colour: string;
  sort_order: string;
  head_user_id: string;
  is_active: boolean;
}

const emptyForm: DeptFormState = {
  id: null,
  code: '',
  name: '',
  description: '',
  colour: '#1976d2',
  sort_order: '100',
  head_user_id: '',
  is_active: true,
};

export default function OrgDepartmentsPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<DeptFormState>(emptyForm);

  const departmentsQuery = useQuery({
    queryKey: ['org-departments'],
    queryFn: () => orgDepartmentsApi.list(),
  });

  const usersQuery = useQuery({
    queryKey: ['users', 'active-lite'],
    queryFn: () => usersApi.list({ limit: 500 }),
  });

  const departments = departmentsQuery.data ?? [];
  const userOptions = useMemo(
    () =>
      (usersQuery.data ?? [])
        .map((user) => ({
          id: user.id,
          name: `${user.first_name} ${user.last_name}`.trim(),
        }))
        .sort((a, b) => a.name.localeCompare(b.name)),
    [usersQuery.data],
  );

  const totals = useMemo(() => {
    const people = departments.reduce((sum, dept) => sum + dept.member_count, 0);
    return { deptCount: departments.length, people };
  }, [departments]);

  const saveMutation = useMutation({
    mutationFn: async (state: DeptFormState) => {
      const payload = {
        code: state.code.trim(),
        name: state.name.trim(),
        description: state.description.trim() || null,
        colour: state.colour || '#1976d2',
        sort_order: Number.isFinite(Number(state.sort_order)) ? Number(state.sort_order) : 100,
        head_user_id: state.head_user_id || null,
        is_active: state.is_active,
      };
      if (state.id) {
        return orgDepartmentsApi.update(state.id, payload);
      }
      return orgDepartmentsApi.create(payload);
    },
    onSuccess: (_data, state) => {
      showSuccess(state.id ? 'Department updated.' : 'Department created.');
      setFormOpen(false);
      void queryClient.invalidateQueries({ queryKey: ['org-departments'] });
      void queryClient.invalidateQueries({ queryKey: ['teams', 'organization-chart'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const openCreate = () => {
    setForm({ ...emptyForm });
    setFormOpen(true);
  };

  const openEdit = (dept: OrgDepartment) => {
    setForm({
      id: dept.id,
      code: dept.code,
      name: dept.name,
      description: dept.description ?? '',
      colour: dept.colour || '#1976d2',
      sort_order: String(dept.sort_order ?? 100),
      head_user_id: dept.head_user_id ?? '',
      is_active: dept.is_active,
    });
    setFormOpen(true);
  };

  const handleSubmit = (event?: FormEvent) => {
    event?.preventDefault();
    if (!form.name.trim() || !form.code.trim()) {
      showError('Department code and name are required.');
      return;
    }
    saveMutation.mutate(form);
  };

  if (departmentsQuery.isLoading) return <LoadingState message="Loading departments…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Organization Departments"
        subtitle="Standardized org-chart units (Management, Engineering, Sales, Accounts, Human Resource, IT). The Managing Director heads the chart; people can be dragged between departments on the Organization Chart."
        action={
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
            Create Department
          </ProsohmButton>
        }
      />

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mb: 2 }}>
        <ContentCard>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
            <ApartmentIcon color="primary" />
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 800, lineHeight: 1 }}>
                {totals.deptCount}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Departments
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
                People assigned to departments
              </Typography>
            </Box>
          </Stack>
        </ContentCard>
      </Stack>

      <Stack spacing={1.5}>
        {departments.map((dept) => {
          const accent = dept.colour || '#607d8b';
          return (
            <ContentCard key={dept.id} noPadding>
              <Box
                sx={{
                  px: 2,
                  py: 1.5,
                  borderLeft: `4px solid ${accent}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 2,
                  flexWrap: 'wrap',
                }}
              >
                <Box sx={{ minWidth: 0 }}>
                  <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                    <Typography sx={{ fontWeight: 800 }}>{dept.name}</Typography>
                    <Chip label={dept.code} size="small" variant="outlined" />
                    {!dept.is_active ? (
                      <Chip label="Inactive" size="small" color="warning" variant="outlined" />
                    ) : null}
                    {dept.member_count > 0 ? (
                      <Chip
                        label={`${dept.member_count} ${dept.member_count === 1 ? 'person' : 'people'}`}
                        size="small"
                        color="success"
                        variant="outlined"
                      />
                    ) : null}
                  </Stack>
                  <Typography variant="caption" color="text.secondary">
                    {dept.head_name ? `Head · ${dept.head_name}` : 'No department head'}
                    {dept.description ? ` · ${dept.description}` : ''}
                  </Typography>
                </Box>
                <TableRowActions
                  onEdit={() => openEdit(dept)}
                  deleteAction={
                    <AdminDeleteButton
                      resource="org-departments"
                      recordId={dept.id}
                      recordName={dept.name}
                      onDeleted={() => {
                        void queryClient.invalidateQueries({ queryKey: ['org-departments'] });
                        void queryClient.invalidateQueries({
                          queryKey: ['teams', 'organization-chart'],
                        });
                      }}
                    />
                  }
                />
              </Box>
            </ContentCard>
          );
        })}
      </Stack>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={form.id ? 'Edit Department' : 'Create Department'}
        subtitle="Org-chart department unit"
        icon={ApartmentIcon}
        formId="org-department-form"
        submitLabel={form.id ? 'Save Changes' : 'Create Department'}
        loading={saveMutation.isPending}
      >
        <Box
          component="form"
          id="org-department-form"
          onSubmit={(event) => void handleSubmit(event)}
          sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
        >
          <FormSection title="Department Details" icon={ApartmentIcon}>
            <FormField
              label="Name"
              required
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
            />
            <FormField
              label="Code"
              required
              value={form.code}
              helperText="Stable identifier (e.g. engineering, hr_admin). Avoid changing on existing departments."
              onChange={(event) =>
                setForm((prev) => ({ ...prev, code: event.target.value.trim() }))
              }
            />
            <FormField
              label="Description"
              value={form.description}
              multiline
              minRows={2}
              onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
            />
          </FormSection>

          <FormSection title="Placement & Appearance" icon={PeopleAltOutlinedIcon}>
            <TextField
              select
              fullWidth
              size="small"
              label="Department head"
              value={form.head_user_id}
              onChange={(event) => setForm((prev) => ({ ...prev, head_user_id: event.target.value }))}
            >
              <MenuItem value="">— No head —</MenuItem>
              {userOptions.map((user) => (
                <MenuItem key={user.id} value={user.id}>
                  {user.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              type="color"
              fullWidth
              size="small"
              label="Colour"
              value={form.colour}
              onChange={(event) => setForm((prev) => ({ ...prev, colour: event.target.value }))}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <FormField
              label="Sort order (lower = earlier)"
              type="number"
              value={form.sort_order}
              onChange={(event) => setForm((prev) => ({ ...prev, sort_order: event.target.value }))}
              helperText="Controls the top-to-bottom order of departments on the chart."
            />
            <TextField
              select
              fullWidth
              size="small"
              label="Status"
              value={form.is_active ? 'active' : 'inactive'}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, is_active: event.target.value === 'active' }))
              }
            >
              <MenuItem value="active">Active</MenuItem>
              <MenuItem value="inactive">Inactive</MenuItem>
            </TextField>
          </FormSection>
        </Box>
      </FormDrawer>
    </PageContainer>
  );
}
