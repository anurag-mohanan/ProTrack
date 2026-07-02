import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Card,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  TextField,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { useSearchParams } from 'react-router-dom';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminDeleteButton } from '../../components/admin/AdminDeleteButton';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { contactsApi, customersApi } from '../../api/resources';
import { fetchContactTypes } from '../../api/settings';
import type { Contact, Customer } from '../../types';
import type { ContactType } from '../../types/Settings';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';

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

function formatDate(value: string | undefined): string {
  if (!value) return '—';
  return new Date(value).toLocaleDateString();
}

export default function ContactsPage() {
  const { showSuccess, showError } = useToast();
  const [searchParams] = useSearchParams();
  const customerFilterParam = searchParams.get('customer_id') ?? 'all';

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [contactTypes, setContactTypes] = useState<ContactType[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [customerFilter, setCustomerFilter] = useState(customerFilterParam);
  const [formOpen, setFormOpen] = useState(false);
  const [viewContact, setViewContact] = useState<Contact | null>(null);
  const [editingContact, setEditingContact] = useState<Contact | null>(null);
  const [form, setForm] = useState<ContactFormState>(emptyForm);

  const customerMap = useMemo(
    () => new Map(customers.map((customer) => [customer.id, customer.name])),
    [customers],
  );

  useEffect(() => {
    setCustomerFilter(customerFilterParam);
  }, [customerFilterParam]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const contactParams =
        customerFilter !== 'all' ? { customer_id: customerFilter } : undefined;
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
  }, [customerFilter, showError]);

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
        customerFilter !== 'all'
          ? customerFilter
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

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        customer_id: form.customer_id,
        first_name: form.first_name,
        last_name: form.last_name,
        email: form.email || null,
        phone: form.phone || null,
        job_title: form.job_title || null,
        contact_type_id: form.contact_type_id || null,
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

  const columns: GridColDef<Contact>[] = [
    {
      field: 'customer_id',
      headerName: 'Customer',
      flex: 1.2,
      minWidth: 140,
      valueFormatter: (value) => customerMap.get(value as string) ?? '—',
    },
    { field: 'first_name', headerName: 'First Name', flex: 1, minWidth: 120 },
    { field: 'last_name', headerName: 'Last Name', flex: 1, minWidth: 120 },
    {
      field: 'email',
      headerName: 'Email',
      flex: 1.2,
      minWidth: 160,
      valueFormatter: (value) => (value as string | null) || '—',
    },
    {
      field: 'phone',
      headerName: 'Phone',
      flex: 1,
      minWidth: 120,
      valueFormatter: (value) => (value as string | null) || '—',
    },
    {
      field: 'job_title',
      headerName: 'Title',
      flex: 1,
      minWidth: 120,
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
      field: 'created_at',
      headerName: 'Created Date',
      width: 130,
      valueFormatter: (value) => formatDate(value as string | undefined),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 130,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="View">
            <IconButton size="small" onClick={() => setViewContact(params.row)}>
              <VisibilityIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openEdit(params.row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <AdminDeleteButton
            resource="contacts"
            recordId={params.row.id}
            recordName={`${params.row.first_name} ${params.row.last_name}`}
            onDeleted={() => void loadData()}
            onDeactivate={async () => {
              await contactsApi.update(params.row.id, { is_active: false });
              showSuccess('Contact deactivated.');
              await loadData();
            }}
          />
        </Box>
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading contacts…" />;

  return (
    <Box>
      <PageHeader
        title="Contacts"
        subtitle="Manage customer contacts"
        action={
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
            Create Contact
          </Button>
        }
      />

      <Card sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <TextField
            label="Search contacts"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            sx={{ minWidth: 260, flex: 1 }}
          />
          <FormControl sx={{ minWidth: 220 }}>
            <InputLabel>Customer</InputLabel>
            <Select
              label="Customer"
              value={customerFilter}
              onChange={(event) => setCustomerFilter(event.target.value)}
            >
              <MenuItem value="all">All Customers</MenuItem>
              {customers.map((customer) => (
                <MenuItem key={customer.id} value={customer.id}>
                  {customer.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
      </Card>

      <Card sx={{ p: 1 }}>
        <DataGrid
          rows={filteredContacts}
          columns={columns}
          autoHeight
          disableRowSelectionOnClick
          pageSizeOptions={[10, 25, 50]}
          initialState={{
            pagination: { paginationModel: { pageSize: 10 } },
          }}
          sx={{ border: 0 }}
        />
      </Card>

      <Dialog
        open={formOpen}
        onClose={() => setFormOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{editingContact ? 'Edit Contact' : 'Create Contact'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <FormControl fullWidth required>
            <InputLabel>Customer</InputLabel>
            <Select
              label="Customer"
              value={form.customer_id}
              onChange={(event) =>
                setForm((current) => ({ ...current, customer_id: event.target.value }))
              }
            >
              {customers.map((customer) => (
                <MenuItem key={customer.id} value={customer.id}>
                  {customer.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="First Name"
            value={form.first_name}
            onChange={(event) =>
              setForm((current) => ({ ...current, first_name: event.target.value }))
            }
            required
            fullWidth
          />
          <TextField
            label="Last Name"
            value={form.last_name}
            onChange={(event) =>
              setForm((current) => ({ ...current, last_name: event.target.value }))
            }
            required
            fullWidth
          />
          <TextField
            label="Email"
            type="email"
            value={form.email}
            onChange={(event) =>
              setForm((current) => ({ ...current, email: event.target.value }))
            }
            fullWidth
          />
          <TextField
            label="Phone"
            value={form.phone}
            onChange={(event) =>
              setForm((current) => ({ ...current, phone: event.target.value }))
            }
            fullWidth
          />
          <TextField
            label="Title"
            value={form.job_title}
            onChange={(event) =>
              setForm((current) => ({ ...current, job_title: event.target.value }))
            }
            fullWidth
          />
          <FormControl fullWidth>
            <InputLabel>Contact Type</InputLabel>
            <Select
              label="Contact Type"
              value={form.contact_type_id}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  contact_type_id: String(event.target.value),
                }))
              }
            >
              <MenuItem value="">Not set</MenuItem>
              {contactTypes.map((type) => (
                <MenuItem key={type.id} value={type.id}>
                  {type.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
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
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFormOpen(false)} disabled={saving}>
            Cancel
          </Button>
          <Button variant="contained" onClick={() => void handleSave()} disabled={saving}>
            {editingContact ? 'Save' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(viewContact)}
        onClose={() => setViewContact(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Contact Details</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {viewContact && (
            <>
              <TextField
                label="Customer"
                value={customerMap.get(viewContact.customer_id) ?? '—'}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
              <TextField label="First Name" value={viewContact.first_name} slotProps={{ input: { readOnly: true } }} fullWidth />
              <TextField label="Last Name" value={viewContact.last_name} slotProps={{ input: { readOnly: true } }} fullWidth />
              <TextField label="Email" value={viewContact.email ?? '—'} slotProps={{ input: { readOnly: true } }} fullWidth />
              <TextField label="Phone" value={viewContact.phone ?? '—'} slotProps={{ input: { readOnly: true } }} fullWidth />
              <TextField label="Title" value={viewContact.job_title ?? '—'} slotProps={{ input: { readOnly: true } }} fullWidth />
              <TextField
                label="Status"
                value={viewContact.is_active ? 'Active' : 'Inactive'}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
              <TextField
                label="Created Date"
                value={formatDate(viewContact.created_at)}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setViewContact(null)}>Close</Button>
        </DialogActions>
      </Dialog>

    </Box>
  );
}
