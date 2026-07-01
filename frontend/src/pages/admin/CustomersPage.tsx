import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Chip,
  FormControlLabel,
  Grid,
  IconButton,
  Link,
  Switch,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import VisibilityIcon from '@mui/icons-material/Visibility';
import BusinessOutlinedIcon from '@mui/icons-material/BusinessOutlined';
import NotesOutlinedIcon from '@mui/icons-material/NotesOutlined';
import BarChartOutlinedIcon from '@mui/icons-material/BarChartOutlined';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { Link as RouterLink } from 'react-router-dom';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { contactsApi, customersApi } from '../../api/resources';
import { fetchTeams } from '../../api/lookups';
import { fetchProjectTemplates, fetchProjectTypes } from '../../api/projectTemplates';
import type { Contact, Customer } from '../../types';
import type { ProjectTemplate, ProjectType } from '../../types/ProjectTemplate';
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
} from '../../components/ui/design-system';
import { prosohmDataGridSx } from '../../theme/componentStyles';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';

interface CustomerFormState {
  name: string;
  code: string;
  notes: string;
  is_active: boolean;
  default_project_template_id: string;
  default_team_id: string;
  default_project_type_id: string;
  default_folder_structure: string;
  due_date_calculation: string;
  project_number_format: string;
  project_number_prefix: string;
}

const emptyForm: CustomerFormState = {
  name: '',
  code: '',
  notes: '',
  is_active: true,
  default_project_template_id: '',
  default_team_id: '',
  default_project_type_id: '',
  default_folder_structure: '',
  due_date_calculation: 'from_start',
  project_number_format: '',
  project_number_prefix: '',
};

function formatDate(value: string | undefined): string {
  if (!value) return '—';
  return new Date(value).toLocaleDateString();
}

export default function CustomersPage() {
  const theme = useTheme();
  const gridSx = useMemo(() => prosohmDataGridSx(theme), [theme]);
  const { showSuccess, showError } = useToast();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [projectTypes, setProjectTypes] = useState<ProjectType[]>([]);
  const [projectTemplates, setProjectTemplates] = useState<ProjectTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [viewCustomer, setViewCustomer] = useState<Customer | null>(null);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [form, setForm] = useState<CustomerFormState>(emptyForm);

  const contactCounts = useMemo(() => {
    const counts = new Map<string, number>();
    contacts.forEach((contact) => {
      counts.set(contact.customer_id, (counts.get(contact.customer_id) ?? 0) + 1);
    });
    return counts;
  }, [contacts]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [customersData, contactsData, teamsData, typesData, templatesData] =
        await Promise.all([
          customersApi.list({ limit: 500 }),
          contactsApi.list(),
          fetchTeams(),
          fetchProjectTypes(),
          fetchProjectTemplates(),
        ]);
      setCustomers(customersData);
      setContacts(contactsData);
      setTeams(teamsData.filter((team) => team.is_active));
      setProjectTypes(typesData.filter((type) => type.is_active));
      setProjectTemplates(templatesData.filter((template) => template.is_active));
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredCustomers = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return customers;
    return customers.filter((customer) => {
      const haystack = [customer.name, customer.code ?? ''].join(' ').toLowerCase();
      return haystack.includes(term);
    });
  }, [customers, search]);

  const openCreate = () => {
    setEditingCustomer(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  useOpenCreateFromQuery(openCreate);

  const openEdit = (customer: Customer) => {
    setEditingCustomer(customer);
    setForm({
      name: customer.name,
      code: customer.code ?? '',
      notes: customer.notes ?? '',
      is_active: customer.is_active,
      default_project_template_id: customer.default_project_template_id ?? '',
      default_team_id: customer.default_team_id ?? '',
      default_project_type_id: customer.default_project_type_id ?? '',
      default_folder_structure: customer.default_folder_structure ?? '',
      due_date_calculation: customer.due_date_calculation ?? 'from_start',
      project_number_format: customer.project_number_format ?? '',
      project_number_prefix: customer.project_number_prefix ?? '',
    });
    setFormOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        code: form.code || null,
        notes: form.notes || null,
        is_active: form.is_active,
        default_project_template_id: form.default_project_template_id || null,
        default_team_id: form.default_team_id || null,
        default_project_type_id: form.default_project_type_id || null,
        default_folder_structure: form.default_folder_structure || null,
        due_date_calculation: form.due_date_calculation as Customer['due_date_calculation'],
        project_number_format: form.project_number_format || null,
        project_number_prefix: form.project_number_prefix || null,
      };
      if (editingCustomer) {
        await customersApi.update(editingCustomer.id, payload);
        showSuccess('Customer updated successfully.');
      } else {
        await customersApi.create(payload);
        showSuccess('Customer created successfully.');
      }
      setFormOpen(false);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const columns: GridColDef<Customer>[] = [
    { field: 'name', headerName: 'Name', flex: 1.5, minWidth: 160 },
    { field: 'code', headerName: 'Code', flex: 1, minWidth: 100 },
    {
      field: 'notes',
      headerName: 'Notes',
      flex: 1.5,
      minWidth: 160,
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
      field: 'contacts',
      headerName: 'Contacts',
      width: 110,
      sortable: false,
      renderCell: (params) => {
        const count = contactCounts.get(params.row.id) ?? 0;
        return (
          <Link
            component={RouterLink}
            to={`/admin/contacts?customer_id=${params.row.id}`}
            underline="hover"
          >
            {count}
          </Link>
        );
      },
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
      width: 100,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="View">
            <IconButton size="small" onClick={() => setViewCustomer(params.row)}>
              <VisibilityIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openEdit(params.row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading customers…" />;

  return (
    <Box>
      <PageHeader
        title="Customers"
        subtitle="Manage customer records and relationships"
        action={
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
            Create Customer
          </ProsohmButton>
        }
      />

      <SearchToolbar>
        <FormField
          label="Search by name or code"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, flex: 1, maxWidth: 480 }}
        />
      </SearchToolbar>

      <ContentCard noPadding>
        <DataGrid
          rows={filteredCustomers}
          columns={columns}
          autoHeight
          disableRowSelectionOnClick
          pageSizeOptions={[10, 25, 50]}
          initialState={{
            pagination: { paginationModel: { pageSize: 10 } },
          }}
          sx={gridSx}
        />
      </ContentCard>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingCustomer ? 'Edit Customer' : 'Create Customer'}
        subtitle="Manage customer profile and account status."
        icon={BusinessOutlinedIcon}
        formId="customer-form"
        width={560}
        submitLabel={editingCustomer ? 'Save Changes' : 'Create Customer'}
        loading={saving}
      >
        <Box
          component="form"
          id="customer-form"
          onSubmit={(event) => {
            event.preventDefault();
            void handleSave();
          }}
          sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
        >
          <FormSection title="General Information" icon={BusinessOutlinedIcon}>
            <Grid size={{ xs: 12 }}>
              <FormField
                label="Name"
                required
                value={form.name}
                onChange={(event) =>
                  setForm((current) => ({ ...current, name: event.target.value }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Code"
                value={form.code}
                onChange={(event) =>
                  setForm((current) => ({ ...current, code: event.target.value }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={form.is_active}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        is_active: event.target.checked,
                      }))
                    }
                  />
                }
                label="Active customer"
              />
            </Grid>
          </FormSection>

          <FormSection title="Project Defaults" icon={BarChartOutlinedIcon}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Default Project Type"
                value={form.default_project_type_id}
                options={[
                  { value: '', label: 'None' },
                  ...projectTypes.map((type) => ({ value: type.id, label: type.name })),
                ]}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    default_project_type_id: String(event.target.value),
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Default Team"
                searchable
                value={form.default_team_id}
                options={[
                  { value: '', label: 'None' },
                  ...teams.map((team) => ({ value: team.id, label: team.name })),
                ]}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    default_team_id: String(event.target.value),
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <FormSelect
                label="Default Project Template"
                searchable
                value={form.default_project_template_id}
                options={[
                  { value: '', label: 'None' },
                  ...projectTemplates.map((template) => ({
                    value: template.id,
                    label: template.name,
                  })),
                ]}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    default_project_template_id: String(event.target.value),
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <FormField
                label="Default Folder Structure"
                value={form.default_folder_structure}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    default_folder_structure: event.target.value,
                  }))
                }
              />
            </Grid>
          </FormSection>

          <FormSection title="Project Numbering" icon={BusinessOutlinedIcon}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Number Prefix"
                value={form.project_number_prefix}
                helper="Example: SYBRIDGE, TI, ABC"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    project_number_prefix: event.target.value,
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Due Date Calculation"
                value={form.due_date_calculation}
                options={[
                  { value: 'from_start', label: 'From project start' },
                  { value: 'from_previous_milestone', label: 'From previous milestone' },
                  { value: 'business_days', label: 'Business days only' },
                ]}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    due_date_calculation: String(event.target.value),
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <FormField
                label="Project Number Format"
                value={form.project_number_format}
                helper="Use {tool_number}, {prefix}, {seq}, {customer_code}"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    project_number_format: event.target.value,
                  }))
                }
              />
            </Grid>
          </FormSection>

          <FormSection title="Notes" icon={NotesOutlinedIcon}>
            <Grid size={{ xs: 12 }}>
              <FormField
                label="Notes"
                multiline
                rows={4}
                maxLength={2000}
                value={form.notes}
                onChange={(event) =>
                  setForm((current) => ({ ...current, notes: event.target.value }))
                }
              />
            </Grid>
          </FormSection>
        </Box>
      </FormDrawer>

      <ModernDrawer
        open={Boolean(viewCustomer)}
        onClose={() => setViewCustomer(null)}
        title="Customer Profile"
        subtitle={viewCustomer?.name}
        icon={BusinessOutlinedIcon}
        width={560}
        footer={
          <ProsohmButton buttonVariant="outlined" onClick={() => setViewCustomer(null)}>
            Close
          </ProsohmButton>
        }
      >
        {viewCustomer ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <FormSection title="General Information" icon={BusinessOutlinedIcon}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormField label="Name" value={viewCustomer.name} slotProps={{ input: { readOnly: true } }} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormField
                  label="Code"
                  value={viewCustomer.code ?? '—'}
                  slotProps={{ input: { readOnly: true } }}
                />
              </Grid>
              <Grid size={{ xs: 12 }}>
                <FormField
                  label="Status"
                  value={viewCustomer.is_active ? 'Active' : 'Inactive'}
                  slotProps={{ input: { readOnly: true } }}
                />
              </Grid>
            </FormSection>

            <FormSection title="Contacts" icon={BusinessOutlinedIcon}>
              <Grid size={{ xs: 12 }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  Linked contacts for this customer
                </Typography>
                <Link
                  component={RouterLink}
                  to={`/admin/contacts?customer_id=${viewCustomer.id}`}
                  underline="hover"
                >
                  View {contactCounts.get(viewCustomer.id) ?? 0} contact(s)
                </Link>
              </Grid>
            </FormSection>

            <FormSection title="Statistics" icon={BarChartOutlinedIcon}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormField
                  label="Created Date"
                  value={formatDate(viewCustomer.created_at)}
                  slotProps={{ input: { readOnly: true } }}
                />
              </Grid>
              <Grid size={{ xs: 12 }}>
                <FormField
                  label="Notes"
                  value={viewCustomer.notes ?? '—'}
                  multiline
                  rows={3}
                  slotProps={{ input: { readOnly: true } }}
                />
              </Grid>
            </FormSection>
          </Box>
        ) : null}
      </ModernDrawer>
    </Box>
  );
}
