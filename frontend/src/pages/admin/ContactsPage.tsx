import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Box, Chip, FormControlLabel, Switch } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ContactPageOutlinedIcon from '@mui/icons-material/ContactPageOutlined';
import type { GridColDef } from '@mui/x-data-grid';
import { useSearchParams } from 'react-router-dom';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { AdminDeleteButton } from '../../components/admin/AdminDeleteButton';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { contactsApi, customersApi } from '../../api/resources';
import { fetchContactTypes } from '../../api/settings';
import type { Contact, Customer } from '../../types';
import type { ContactType } from '../../types/Settings';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  DrawerQuickActions,
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
  ProsohmDataGrid,
  RecordDetailDrawer,
  FilterDrawer,
  FilterToolbar,
  compactFilterFieldSx,
  TableRowActions,
} from '../../components/ui/design-system';
import { formatCellValue, formatDateTime } from '../../utils/format';
import { optionalString, optionalUuid, validateRequiredFields } from '../../utils/formValues';
import { canDeleteRecords } from '../../utils/permissions';
import { useAuth } from '../../context/AuthContext';
import { DATA_GRID_ACTIONS_COLUMN_WIDTH } from '../../theme/componentStyles';

interface ContactFormState {
  customer_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  job_title: string;
  contact_type_id: string;
  is_primary: boolean;
  is_active: boolean;
}

const emptyForm: ContactFormState = {
  customer_id: '',
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  job_title: '',
  contact_type_id: '',
  is_primary: false,
  is_active: true,
};

export default function ContactsPage() {
  const { user } = useAuth();
  const isAdmin = canDeleteRecords(user?.role_name ?? '');
  const { showSuccess, showError } = useToast();
  const [searchParams] = useSearchParams();
  const customerFilterParam = searchParams.get('customer_id') ?? 'all';

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [contactTypes, setContactTypes] = useState<ContactType[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [appliedCustomerFilter, setAppliedCustomerFilter] = useState(customerFilterParam);
  const [draftCustomerFilter, setDraftCustomerFilter] = useState(customerFilterParam);
  const [formOpen, setFormOpen] = useState(false);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [editingContact, setEditingContact] = useState<Contact | null>(null);
  const [form, setForm] = useState<ContactFormState>(emptyForm);

  const customerMap = useMemo(
    () => new Map(customers.map((customer) => [customer.id, customer.name])),
    [customers],
  );

  useEffect(() => {
    setAppliedCustomerFilter(customerFilterParam);
    setDraftCustomerFilter(customerFilterParam);
  }, [customerFilterParam]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const contactParams =
        appliedCustomerFilter !== 'all' ? { customer_id: appliedCustomerFilter } : undefined;
      const [contactsData, customersData, contactTypesData] = await Promise.all([
        contactsApi.list(contactParams),
        customersApi.list(),
        fetchContactTypes(),
      ]);
      setContacts(contactsData);
      setCustomers(customersData);
      setContactTypes(contactTypesData);
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [appliedCustomerFilter, showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredContacts = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return contacts;
    return contacts.filter((contact) => {
      const haystack = [
        contact.first_name,
        contact.last_name,
        contact.email ?? '',
        contact.phone ?? '',
        contact.job_title ?? '',
      ]
        .join(' ')
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [contacts, search]);

  const openCreate = () => {
    setEditingContact(null);
    setForm({
      ...emptyForm,
      customer_id:
        appliedCustomerFilter !== 'all'
          ? appliedCustomerFilter
          : (customers[0]?.id ?? ''),
    });
    setFormOpen(true);
  };

  useOpenCreateFromQuery(openCreate);

  const openEdit = (contact: Contact) => {
    setEditingContact(contact);
    setForm({
      customer_id: contact.customer_id,
      first_name: contact.first_name,
      last_name: contact.last_name,
      email: contact.email ?? '',
      phone: contact.phone ?? '',
      job_title: contact.job_title ?? '',
      contact_type_id: contact.contact_type_id ?? '',
      is_primary: contact.is_primary,
      is_active: contact.is_active,
    });
    setFormOpen(true);
  };

  const handleSave = async (event?: FormEvent) => {
    event?.preventDefault();
    const validationError = validateRequiredFields(
      {
        customer_id: form.customer_id,
        first_name: form.first_name,
        last_name: form.last_name,
      },
      [
        { key: 'customer_id', label: 'Customer' },
        { key: 'first_name', label: 'First name' },
        { key: 'last_name', label: 'Last name' },
      ],
    );
    if (validationError) {
      showError(validationError);
      return;
    }

    setSaving(true);
    try {
      const payload = {
        customer_id: form.customer_id,
        first_name: form.first_name,
        last_name: form.last_name,
        email: optionalString(form.email),
        phone: optionalString(form.phone),
        job_title: optionalString(form.job_title),
        contact_type_id: optionalUuid(form.contact_type_id),
        is_primary: form.is_primary,
        is_active: form.is_active,
      };
      if (editingContact) {
        await contactsApi.update(editingContact.id, payload);
        showSuccess('Contact updated successfully.');
      } else {
        await contactsApi.create(payload);
        showSuccess('Contact created successfully.');
      }
      setFormOpen(false);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const contactDisplayName = (contact: Contact) =>
    `${contact.first_name} ${contact.last_name}`;

  const columns: GridColDef<Contact>[] = [
    {
      field: 'customer_id',
      headerName: 'Customer',
      flex: 1.2,
      minWidth: 140,
      valueFormatter: (value) => formatCellValue(customerMap.get(value as string)),
    },
    { field: 'first_name', headerName: 'First Name', flex: 1, minWidth: 120 },
    { field: 'last_name', headerName: 'Last Name', flex: 1, minWidth: 120 },
    {
      field: 'email',
      headerName: 'Email',
      flex: 1.2,
      minWidth: 160,
      valueFormatter: (value) => formatCellValue(value as string | null),
    },
    {
      field: 'phone',
      headerName: 'Phone',
      flex: 1,
      minWidth: 120,
      valueFormatter: (value) => formatCellValue(value as string | null),
    },
    {
      field: 'job_title',
      headerName: 'Title',
      flex: 1,
      minWidth: 120,
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
                resource="contacts"
                recordId={params.row.id}
                recordName={contactDisplayName(params.row)}
                onDeleted={() => void loadData()}
                onDeactivate={async () => {
                  await contactsApi.update(params.row.id, { is_active: false });
                  showSuccess('Contact deactivated.');
                  await loadData();
                }}
              />
            ) : undefined
          }
        />
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading contacts…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Contacts"
        subtitle="Manage customer contacts"
        action={
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
            Create Contact
          </ProsohmButton>
        }
      />

      <FilterToolbar
        filterButton={{
          activeCount: appliedCustomerFilter !== 'all' ? 1 : 0,
          onClick: () => setFiltersOpen(true),
        }}
        chips={
          appliedCustomerFilter !== 'all'
            ? [
                {
                  key: 'customer',
                  label: `Customer: ${customerMap.get(appliedCustomerFilter) ?? 'Unknown'}`,
                  onRemove: () => {
                    setAppliedCustomerFilter('all');
                    setDraftCustomerFilter('all');
                  },
                },
              ]
            : []
        }
        onClearAll={() => {
          setAppliedCustomerFilter('all');
          setDraftCustomerFilter('all');
        }}
      >
        <FormField
          label="Search contacts"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 260, flex: 1, maxWidth: 420 }}
        />
      </FilterToolbar>

      <ContentCard noPadding>
        <ProsohmDataGrid
          rows={filteredContacts}
          columns={columns}
          autoHeight
          pageSizeOptions={[25, 50, 100]}
          initialState={{
            pagination: { paginationModel: { pageSize: 25 } },
          }}
          onRowOpen={(rowId) => {
            const contact = filteredContacts.find((item) => item.id === rowId);
            if (contact) setSelectedContact(contact);
          }}
        />
      </ContentCard>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingContact ? 'Edit Contact' : 'Create Contact'}
        subtitle="Customer contact details"
        icon={ContactPageOutlinedIcon}
        formId="contact-form"
        submitLabel={editingContact ? 'Save Changes' : 'Create Contact'}
        loading={saving}
      >
        <Box
          component="form"
          id="contact-form"
          onSubmit={(event) => void handleSave(event)}
          sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
        >
          <FormSection title="Contact Details" icon={ContactPageOutlinedIcon}>
            <FormSelect
              label="Customer"
              required
              value={form.customer_id}
              options={customers.map((customer) => ({ value: customer.id, label: customer.name }))}
              onChange={(event) =>
                setForm((current) => ({ ...current, customer_id: String(event.target.value) }))
              }
            />
            <FormField
              label="First Name"
              required
              value={form.first_name}
              onChange={(event) =>
                setForm((current) => ({ ...current, first_name: event.target.value }))
              }
            />
            <FormField
              label="Last Name"
              required
              value={form.last_name}
              onChange={(event) =>
                setForm((current) => ({ ...current, last_name: event.target.value }))
              }
            />
            <FormField
              label="Email"
              type="email"
              value={form.email}
              onChange={(event) =>
                setForm((current) => ({ ...current, email: event.target.value }))
              }
            />
            <FormField
              label="Phone"
              value={form.phone}
              onChange={(event) =>
                setForm((current) => ({ ...current, phone: event.target.value }))
              }
            />
            <FormField
              label="Title"
              value={form.job_title}
              onChange={(event) =>
                setForm((current) => ({ ...current, job_title: event.target.value }))
              }
            />
            <FormSelect
              label="Contact Type"
              value={form.contact_type_id}
              options={[
                { value: '', label: 'Not set' },
                ...contactTypes.map((type) => ({ value: type.id, label: type.name })),
              ]}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  contact_type_id: String(event.target.value),
                }))
              }
            />
            <FormControlLabel
              control={
                <Switch
                  checked={form.is_primary}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, is_primary: event.target.checked }))
                  }
                />
              }
              label="Primary contact"
            />
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
          </FormSection>
        </Box>
      </FormDrawer>

      <RecordDetailDrawer
        open={Boolean(selectedContact)}
        onClose={() => setSelectedContact(null)}
        title={selectedContact ? contactDisplayName(selectedContact) : 'Contact'}
        subtitle="Customer contact"
        icon={ContactPageOutlinedIcon}
        status={
          selectedContact ? (
            <Chip
              label={selectedContact.is_active ? 'Active' : 'Inactive'}
              size="small"
              color={selectedContact.is_active ? 'success' : 'default'}
            />
          ) : null
        }
        quickActions={
          selectedContact ? (
            <DrawerQuickActions>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => {
                  openEdit(selectedContact);
                  setSelectedContact(null);
                }}
              >
                Edit
              </ProsohmButton>
              {isAdmin ? (
                <AdminDeleteButton
                  mode="button"
                  resource="contacts"
                  recordId={selectedContact.id}
                  recordName={contactDisplayName(selectedContact)}
                  onDeleted={() => {
                    setSelectedContact(null);
                    void loadData();
                  }}
                  onDeactivate={async () => {
                    await contactsApi.update(selectedContact.id, { is_active: false });
                    showSuccess('Contact deactivated.');
                    setSelectedContact(null);
                    await loadData();
                  }}
                />
              ) : null}
            </DrawerQuickActions>
          ) : null
        }
      >
        {selectedContact ? (
          <FormSection title="Overview" icon={ContactPageOutlinedIcon}>
            <FormField
              label="Customer"
              value={formatCellValue(customerMap.get(selectedContact.customer_id)) || '—'}
              slotProps={{ input: { readOnly: true } }}
            />
            <FormField label="First Name" value={selectedContact.first_name} slotProps={{ input: { readOnly: true } }} />
            <FormField label="Last Name" value={selectedContact.last_name} slotProps={{ input: { readOnly: true } }} />
            <FormField
              label="Email"
              value={formatCellValue(selectedContact.email) || '—'}
              slotProps={{ input: { readOnly: true } }}
            />
            <FormField
              label="Phone"
              value={formatCellValue(selectedContact.phone) || '—'}
              slotProps={{ input: { readOnly: true } }}
            />
            <FormField
              label="Title"
              value={formatCellValue(selectedContact.job_title) || '—'}
              slotProps={{ input: { readOnly: true } }}
            />
            <FormField
              label="Created Date"
              value={formatDateTime(selectedContact.created_at) || '—'}
              slotProps={{ input: { readOnly: true } }}
            />
          </FormSection>
        ) : null}
      </RecordDetailDrawer>

      <FilterDrawer
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        title="Contact filters"
        onApply={() => setAppliedCustomerFilter(draftCustomerFilter)}
        onReset={() => setDraftCustomerFilter('all')}
      >
        <Box sx={compactFilterFieldSx}>
          <FormSelect
            label="Customer"
            size="small"
            value={draftCustomerFilter}
            options={[
              { value: 'all', label: 'All Customers' },
              ...customers.map((customer) => ({ value: customer.id, label: customer.name })),
            ]}
            onChange={(event) => setDraftCustomerFilter(String(event.target.value))}
          />
        </Box>
      </FilterDrawer>
    </PageContainer>
  );
}
