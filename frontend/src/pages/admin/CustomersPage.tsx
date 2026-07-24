import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  Chip,
  FormControlLabel,
  Grid,
  Link,
  Switch,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import BusinessOutlinedIcon from '@mui/icons-material/BusinessOutlined';
import NotesOutlinedIcon from '@mui/icons-material/NotesOutlined';
import BarChartOutlinedIcon from '@mui/icons-material/BarChartOutlined';
import type { GridColDef } from '@mui/x-data-grid';
import { useQueryClient } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { ServerPaginatedDataGrid } from '../../components/common/ServerPaginatedDataGrid';
import { LoadingState } from '../../components/common/LoadingState';
import { AdminDeleteButton } from '../../components/admin/AdminDeleteButton';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { contactsApi, customersApi } from '../../api/resources';
import { fetchTeams, fetchWorkingModels } from '../../api/lookups';
import { fetchProjectTemplates, fetchProjectTypes } from '../../api/projectTemplates';
import { ensureArray } from '../../types/pagination';
import type { Contact, Customer, WorkingModel } from '../../types';
import type { ProjectTemplate, ProjectType } from '../../types/ProjectTemplate';
import type { Team } from '../../types/Team';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  DrawerQuickActions,
  CollapsibleFormSection,
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
  RecordDetailDrawer,
  SearchToolbar,
  StickyRecordHeader,
  TableRowActions,
} from '../../components/ui/design-system';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import { formatCellValue, formatDateTime } from '../../utils/format';
import { optionalString, optionalUuid, validateRequiredFields } from '../../utils/formValues';
import { canDeleteRecords } from '../../utils/permissions';
import { useAuth } from '../../context/AuthContext';
import { DATA_GRID_ACTIONS_COLUMN_WIDTH } from '../../theme/componentStyles';

interface CustomerFormState {
  name: string;
  code: string;
  notes: string;
  is_active: boolean;
  default_project_template_id: string;
  default_team_id: string;
  default_project_type_id: string;
  default_working_model_id: string;
  default_folder_structure: string;
  due_date_calculation: string;
  project_number_format: string;
  project_number_prefix: string;
  default_currency_code: string;
}

const emptyForm: CustomerFormState = {
  name: '',
  code: '',
  notes: '',
  is_active: true,
  default_project_template_id: '',
  default_team_id: '',
  default_project_type_id: '',
  default_working_model_id: '',
  default_folder_structure: '',
  due_date_calculation: 'from_start',
  project_number_format: '',
  project_number_prefix: '',
  default_currency_code: 'INR',
};

const CUSTOMER_SECTION_STORAGE_KEY = 'protrack:sections:customer-form';

export default function CustomersPage() {
  const { user } = useAuth();
  const isAdmin = canDeleteRecords(user?.role_name ?? '');
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [projectTypes, setProjectTypes] = useState<ProjectType[]>([]);
  const [projectTemplates, setProjectTemplates] = useState<ProjectTemplate[]>([]);
  const [workingModels, setWorkingModels] = useState<WorkingModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search);
  const [formOpen, setFormOpen] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [form, setForm] = useState<CustomerFormState>(emptyForm);
  const baselineRef = useRef('');

  const serializeForm = (values: CustomerFormState) => JSON.stringify(values);

  const isFormDirty = useMemo(
    () => serializeForm(form) !== baselineRef.current,
    [form],
  );

  const handleDiscardForm = () => {
    setForm(JSON.parse(baselineRef.current) as CustomerFormState);
  };

  const contactCounts = useMemo(() => {
    const counts = new Map<string, number>();
    contacts.forEach((contact) => {
      counts.set(contact.customer_id, (counts.get(contact.customer_id) ?? 0) + 1);
    });
    return counts;
  }, [contacts]);

  const listFilters = useMemo(() => {
    const params: Record<string, string> = {};
    if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
    return params;
  }, [debouncedSearch]);

  const refreshCustomers = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['customers'] });
  }, [queryClient]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [contactsData, teamsData, typesData, templatesData, modelsData] =
        await Promise.all([
          contactsApi.list({ limit: 500 }),
          fetchTeams(),
          fetchProjectTypes(),
          fetchProjectTemplates(),
          fetchWorkingModels(),
        ]);
      const safeContacts = ensureArray<Contact>(contactsData);
      const safeTeams = ensureArray<Team>(teamsData);
      const safeTypes = ensureArray<ProjectType>(typesData);
      const safeTemplates = ensureArray<ProjectTemplate>(templatesData);
      setContacts(safeContacts);
      setTeams(safeTeams.filter((team) => team.is_active));
      setProjectTypes(safeTypes.filter((type) => type.is_active));
      setProjectTemplates(safeTemplates.filter((template) => template.is_active));
      setWorkingModels(modelsData.filter((model) => model.is_active && !model.is_archived));
      refreshCustomers();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [refreshCustomers, showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const openCreate = () => {
    setEditingCustomer(null);
    setForm(emptyForm);
    baselineRef.current = serializeForm(emptyForm);
    setFormOpen(true);
  };

  useOpenCreateFromQuery(openCreate);

  const openEdit = (customer: Customer) => {
    setEditingCustomer(customer);
    const nextForm = {
      name: customer.name,
      code: customer.code ?? '',
      notes: customer.notes ?? '',
      is_active: customer.is_active,
      default_project_template_id: customer.default_project_template_id ?? '',
      default_team_id: customer.default_team_id ?? '',
      default_project_type_id: customer.default_project_type_id ?? '',
      default_working_model_id: customer.default_working_model_id ?? '',
      default_folder_structure: customer.default_folder_structure ?? '',
      due_date_calculation: customer.due_date_calculation ?? 'from_start',
      project_number_format: customer.project_number_format ?? '',
      project_number_prefix: customer.project_number_prefix ?? '',
      default_currency_code: customer.default_currency_code ?? 'INR',
    };
    setForm(nextForm);
    baselineRef.current = serializeForm(nextForm);
    setFormOpen(true);
  };

  const handleSave = async () => {
    const validationError = validateRequiredFields(
      { name: form.name },
      [{ key: 'name', label: 'Name' }],
    );
    if (validationError) {
      showError(validationError);
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name: form.name,
        code: optionalString(form.code),
        notes: optionalString(form.notes),
        is_active: form.is_active,
        default_project_template_id: optionalUuid(form.default_project_template_id),
        default_team_id: optionalUuid(form.default_team_id),
        default_project_type_id: optionalUuid(form.default_project_type_id),
        default_working_model_id: optionalUuid(form.default_working_model_id),
        default_folder_structure: optionalString(form.default_folder_structure),
        due_date_calculation: form.due_date_calculation as Customer['due_date_calculation'],
        project_number_format: optionalString(form.project_number_format),
        project_number_prefix: optionalString(form.project_number_prefix),
        default_currency_code: form.default_currency_code || 'INR',
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
      valueFormatter: (value) => formatCellValue(value as string | null),
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
            onClick={(event) => event.stopPropagation()}
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
      valueFormatter: (value) => formatDateTime(value as string | undefined),
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
              <AdminDeleteButton
                resource="customers"
                recordId={params.row.id}
                recordName={params.row.name}
                onDeleted={() => void loadData()}
                showArchive
                showDeactivate={false}
                onArchive={async () => {
                  await customersApi.update(params.row.id, { is_active: false });
                  showSuccess('Customer archived.');
                  await loadData();
                }}
              />
            ) : undefined
          }
        />
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading customers…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Customers"
        subtitle="Manage customer records and relationships"
        action={
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
            Create Customer
          </ProsohmButton>
        }
      />

      <SearchToolbar sticky>
        <FormField
          label="Search by name or code"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, flex: 1, maxWidth: 480 }}
        />
      </SearchToolbar>

      <ContentCard noPadding>
        <ServerPaginatedDataGrid<Customer, Customer>
          queryKey={['customers']}
          fetcher={customersApi.listPaginated}
          filters={listFilters}
          enabled={!loading}
          columns={columns}
          pinLeftFields={['name']}
          autoHeight
          onRowOpen={(rowId) => {
            setSelectedCustomer((current) =>
              current?.id === rowId ? current : ({ id: rowId } as Customer),
            );
            void customersApi.get(String(rowId)).then(setSelectedCustomer).catch((error) => {
              showError(getErrorMessage(error));
            });
          }}
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
        dirty={isFormDirty}
        onDiscard={handleDiscardForm}
      >
        <Box
          component="form"
          id="customer-form"
          onSubmit={(event) => {
            event.preventDefault();
            void handleSave();
          }}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}
        >
          <StickyRecordHeader
            compact
            mode={editingCustomer ? 'full' : 'draft'}
            primaryLabel={form.name || 'New Customer'}
            secondaryLabel={form.code ? `Code ${form.code}` : 'Customer profile'}
            customerName={form.name || null}
            stickyTop={0}
          />

          <CollapsibleFormSection
            sectionId="general-information"
            storageKey={CUSTOMER_SECTION_STORAGE_KEY}
            title="General Information"
            icon={BusinessOutlinedIcon}
          >
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
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Default currency"
                value={form.default_currency_code}
                helper="Used as the default for quotes and multi-country customers. Changing this does not rewrite historical INR postings."
                options={[
                  { value: 'INR', label: 'INR — Indian Rupee' },
                  { value: 'USD', label: 'USD — US Dollar' },
                  { value: 'EUR', label: 'EUR — Euro' },
                  { value: 'GBP', label: 'GBP — British Pound' },
                  { value: 'AED', label: 'AED — UAE Dirham' },
                  { value: 'SGD', label: 'SGD — Singapore Dollar' },
                ]}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    default_currency_code: String(event.target.value),
                  }))
                }
              />
            </Grid>
          </CollapsibleFormSection>

          <CollapsibleFormSection
            sectionId="project-defaults"
            storageKey={CUSTOMER_SECTION_STORAGE_KEY}
            title="Project Defaults"
            icon={BarChartOutlinedIcon}
          >
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
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Default Working Model"
                value={form.default_working_model_id}
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
                    label: [
                      template.name,
                      template.project_type_name ? `· ${template.project_type_name}` : null,
                      template.customer_name ? `· ${template.customer_name}` : '· General',
                      `· ${template.milestone_count ?? 0} milestones`,
                    ]
                      .filter(Boolean)
                      .join(' '),
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
          </CollapsibleFormSection>

          <CollapsibleFormSection
            sectionId="project-numbering"
            storageKey={CUSTOMER_SECTION_STORAGE_KEY}
            title="Project Numbering"
            icon={BusinessOutlinedIcon}
          >
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
          </CollapsibleFormSection>

          <CollapsibleFormSection
            sectionId="notes"
            storageKey={CUSTOMER_SECTION_STORAGE_KEY}
            title="Notes"
            icon={NotesOutlinedIcon}
          >
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
          </CollapsibleFormSection>
        </Box>
      </FormDrawer>

      <RecordDetailDrawer
        open={Boolean(selectedCustomer)}
        onClose={() => setSelectedCustomer(null)}
        title={selectedCustomer?.name ?? 'Customer'}
        subtitle="Customer profile"
        icon={BusinessOutlinedIcon}
        width={560}
        status={
          selectedCustomer ? (
            <Chip
              label={selectedCustomer.is_active ? 'Active' : 'Inactive'}
              size="small"
              color={selectedCustomer.is_active ? 'success' : 'default'}
            />
          ) : null
        }
        quickActions={
          selectedCustomer ? (
            <DrawerQuickActions>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => {
                  openEdit(selectedCustomer);
                  setSelectedCustomer(null);
                }}
              >
                Edit
              </ProsohmButton>
              {isAdmin ? (
                <AdminDeleteButton
                  mode="button"
                  resource="customers"
                  recordId={selectedCustomer.id}
                  recordName={selectedCustomer.name}
                  showArchive
                  showDeactivate={false}
                  onDeleted={() => {
                    setSelectedCustomer(null);
                    void loadData();
                  }}
                  onArchive={async () => {
                    await customersApi.update(selectedCustomer.id, { is_active: false });
                    showSuccess('Customer archived.');
                    setSelectedCustomer(null);
                    await loadData();
                  }}
                />
              ) : null}
            </DrawerQuickActions>
          ) : null
        }
      >
        {selectedCustomer ? (
          <>
            <FormSection title="Overview" icon={BusinessOutlinedIcon}>
              <FormField label="Name" value={selectedCustomer.name} slotProps={{ input: { readOnly: true } }} />
              <FormField
                label="Code"
                value={formatCellValue(selectedCustomer.code) || '—'}
                slotProps={{ input: { readOnly: true } }}
              />
            </FormSection>

            <FormSection title="Contacts" icon={BusinessOutlinedIcon}>
              <Link
                component={RouterLink}
                to={`/admin/contacts?customer_id=${selectedCustomer.id}`}
                underline="hover"
              >
                View {contactCounts.get(selectedCustomer.id) ?? 0} contact(s)
              </Link>
            </FormSection>

            <FormSection title="Details" icon={BarChartOutlinedIcon}>
              <FormField
                label="Created Date"
                value={formatDateTime(selectedCustomer.created_at) || '—'}
                slotProps={{ input: { readOnly: true } }}
              />
              <FormField
                label="Notes"
                value={formatCellValue(selectedCustomer.notes) || '—'}
                multiline
                minRows={3}
                slotProps={{ input: { readOnly: true } }}
              />
            </FormSection>
          </>
        ) : null}
      </RecordDetailDrawer>
    </PageContainer>
  );
}
