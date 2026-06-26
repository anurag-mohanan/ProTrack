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
  FormControlLabel,
  IconButton,
  Link,
  Switch,
  TextField,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { Link as RouterLink } from 'react-router-dom';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { contactsApi, customersApi } from '../../api/resources';
import type { Contact, Customer } from '../../types';

interface CustomerFormState {
  name: string;
  code: string;
  notes: string;
  is_active: boolean;
}

const emptyForm: CustomerFormState = {
  name: '',
  code: '',
  notes: '',
  is_active: true,
};

function formatDate(value: string | undefined): string {
  if (!value) return '—';
  return new Date(value).toLocaleDateString();
}

export default function CustomersPage() {
  const { showSuccess, showError } = useToast();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
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
      const [customersData, contactsData] = await Promise.all([
        customersApi.list(),
        contactsApi.list(),
      ]);
      setCustomers(customersData);
      setContacts(contactsData);
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

  const openEdit = (customer: Customer) => {
    setEditingCustomer(customer);
    setForm({
      name: customer.name,
      code: customer.code ?? '',
      notes: customer.notes ?? '',
      is_active: customer.is_active,
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
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
            Create Customer
          </Button>
        }
      />

      <Card sx={{ p: 2, mb: 2 }}>
        <TextField
          label="Search by name or code"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, width: '100%', maxWidth: 480 }}
        />
      </Card>

      <Card sx={{ p: 1 }}>
        <DataGrid
          rows={filteredCustomers}
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
        <DialogTitle>{editingCustomer ? 'Edit Customer' : 'Create Customer'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <TextField
            label="Name"
            value={form.name}
            onChange={(event) =>
              setForm((current) => ({ ...current, name: event.target.value }))
            }
            required
            fullWidth
          />
          <TextField
            label="Code"
            value={form.code}
            onChange={(event) =>
              setForm((current) => ({ ...current, code: event.target.value }))
            }
            fullWidth
          />
          <TextField
            label="Notes"
            value={form.notes}
            onChange={(event) =>
              setForm((current) => ({ ...current, notes: event.target.value }))
            }
            multiline
            minRows={3}
            fullWidth
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
            {editingCustomer ? 'Save' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(viewCustomer)}
        onClose={() => setViewCustomer(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Customer Details</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {viewCustomer && (
            <>
              <TextField label="Name" value={viewCustomer.name} slotProps={{ input: { readOnly: true } }} fullWidth />
              <TextField
                label="Code"
                value={viewCustomer.code ?? '—'}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
              <TextField
                label="Notes"
                value={viewCustomer.notes ?? '—'}
                slotProps={{ input: { readOnly: true } }}
                multiline
                minRows={2}
                fullWidth
              />
              <TextField
                label="Status"
                value={viewCustomer.is_active ? 'Active' : 'Inactive'}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
              <TextField
                label="Contacts"
                value={String(contactCounts.get(viewCustomer.id) ?? 0)}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
              <TextField
                label="Created Date"
                value={formatDate(viewCustomer.created_at)}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setViewCustomer(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
