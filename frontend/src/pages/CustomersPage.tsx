import { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Card,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  Tab,
  Tabs,
  TextField,
} from '@mui/material';
import { DataGrid, GridActionsCellItem, type GridColDef } from '@mui/x-data-grid';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import PageHeader from '../components/common/PageHeader';
import AlertBanner from '../components/common/AlertBanner';
import { contactsApi, customersApi } from '../api/resources';
import type { Contact, Customer } from '../types';

export default function CustomersPage() {
  const [tab, setTab] = useState(0);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [customerFilter, setCustomerFilter] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [customerOpen, setCustomerOpen] = useState(false);
  const [contactOpen, setContactOpen] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [editingContact, setEditingContact] = useState<Contact | null>(null);
  const [customerForm, setCustomerForm] = useState({ name: '', code: '', address: '', is_active: true });
  const [contactForm, setContactForm] = useState({
    customer_id: '',
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    job_title: '',
    is_primary: false,
  });

  const load = useCallback(() => {
    Promise.all([
      customersApi.list(),
      contactsApi.list(customerFilter ? { customer_id: customerFilter } : undefined),
    ])
      .then(([c, ct]) => {
        setCustomers(c);
        setContacts(ct);
      })
      .catch((err) => setError(err.message));
  }, [customerFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const customerColumns: GridColDef<Customer>[] = [
    { field: 'name', headerName: 'Name', flex: 1, minWidth: 180 },
    { field: 'code', headerName: 'Code', width: 100 },
    { field: 'address', headerName: 'Address', flex: 1, minWidth: 200 },
    {
      field: 'is_active',
      headerName: 'Active',
      width: 90,
      valueGetter: (_, row) => (row.is_active ? 'Yes' : 'No'),
    },
    {
      field: 'actions',
      type: 'actions',
      width: 90,
      getActions: (params) => [
        <GridActionsCellItem
          icon={<EditIcon />}
          label="Edit"
          onClick={() => {
            setEditingCustomer(params.row);
            setCustomerForm({
              name: params.row.name,
              code: params.row.code ?? '',
              address: params.row.address ?? '',
              is_active: params.row.is_active,
            });
            setCustomerOpen(true);
          }}
        />,
        <GridActionsCellItem icon={<DeleteIcon />} label="Delete" onClick={() => customersApi.remove(params.id as string).then(load)} />,
      ],
    },
  ];

  const contactColumns: GridColDef<Contact>[] = [
    {
      field: 'customer_id',
      headerName: 'Customer',
      flex: 1,
      valueGetter: (_, row) => customers.find((c) => c.id === row.customer_id)?.name ?? row.customer_id,
    },
    { field: 'first_name', headerName: 'First Name', width: 120 },
    { field: 'last_name', headerName: 'Last Name', width: 120 },
    { field: 'email', headerName: 'Email', flex: 1, minWidth: 180 },
    { field: 'phone', headerName: 'Phone', width: 130 },
    { field: 'job_title', headerName: 'Title', width: 140 },
    {
      field: 'actions',
      type: 'actions',
      width: 90,
      getActions: (params) => [
        <GridActionsCellItem
          icon={<EditIcon />}
          label="Edit"
          onClick={() => {
            setEditingContact(params.row);
            setContactForm({
              customer_id: params.row.customer_id,
              first_name: params.row.first_name,
              last_name: params.row.last_name,
              email: params.row.email ?? '',
              phone: params.row.phone ?? '',
              job_title: params.row.job_title ?? '',
              is_primary: params.row.is_primary,
            });
            setContactOpen(true);
          }}
        />,
        <GridActionsCellItem icon={<DeleteIcon />} label="Delete" onClick={() => contactsApi.remove(params.id as string).then(load)} />,
      ],
    },
  ];

  const saveCustomer = async () => {
    try {
      const payload = {
        ...customerForm,
        code: customerForm.code || null,
        address: customerForm.address || null,
      };
      if (editingCustomer) await customersApi.update(editingCustomer.id, payload);
      else await customersApi.create(payload);
      setCustomerOpen(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    }
  };

  const saveContact = async () => {
    try {
      const payload = {
        ...contactForm,
        email: contactForm.email || null,
        phone: contactForm.phone || null,
        job_title: contactForm.job_title || null,
      };
      if (editingContact) await contactsApi.update(editingContact.id, payload);
      else await contactsApi.create(payload);
      setContactOpen(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    }
  };

  return (
    <Box>
      <PageHeader title="Customers" subtitle="Manage customers and their contacts" />
      <AlertBanner message={error} onClose={() => setError(null)} />
      <Card sx={{ mb: 2 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)}>
          <Tab label="Customers" />
          <Tab label="Contacts" />
        </Tabs>
      </Card>

      {tab === 0 && (
        <>
          <Box sx={{ mb: 2 }}>
            <Button variant="contained" onClick={() => { setEditingCustomer(null); setCustomerForm({ name: '', code: '', address: '', is_active: true }); setCustomerOpen(true); }}>
              New Customer
            </Button>
          </Box>
          <Card sx={{ p: 1 }}>
            <DataGrid rows={customers} columns={customerColumns} autoHeight pageSizeOptions={[10, 25]} initialState={{ pagination: { paginationModel: { pageSize: 10 } } }} disableRowSelectionOnClick />
          </Card>
        </>
      )}

      {tab === 1 && (
        <>
          <Card sx={{ p: 2, mb: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
            <FormControl sx={{ minWidth: 260 }}>
              <InputLabel>Filter by Customer</InputLabel>
              <Select label="Filter by Customer" value={customerFilter} onChange={(e) => setCustomerFilter(e.target.value)}>
                <MenuItem value="">All customers</MenuItem>
                {customers.map((c) => <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>)}
              </Select>
            </FormControl>
            <Button variant="contained" onClick={() => { setEditingContact(null); setContactForm({ customer_id: customerFilter, first_name: '', last_name: '', email: '', phone: '', job_title: '', is_primary: false }); setContactOpen(true); }}>
              New Contact
            </Button>
          </Card>
          <Card sx={{ p: 1 }}>
            <DataGrid rows={contacts} columns={contactColumns} autoHeight pageSizeOptions={[10, 25]} initialState={{ pagination: { paginationModel: { pageSize: 10 } } }} disableRowSelectionOnClick />
          </Card>
        </>
      )}

      <Dialog open={customerOpen} onClose={() => setCustomerOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingCustomer ? 'Edit Customer' : 'New Customer'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid size={{ xs: 12, sm: 8 }}><TextField label="Name" fullWidth required value={customerForm.name} onChange={(e) => setCustomerForm({ ...customerForm, name: e.target.value })} /></Grid>
            <Grid size={{ xs: 12, sm: 4 }}><TextField label="Code" fullWidth value={customerForm.code} onChange={(e) => setCustomerForm({ ...customerForm, code: e.target.value })} /></Grid>
            <Grid size={{ xs: 12 }}><TextField label="Address" fullWidth multiline rows={2} value={customerForm.address} onChange={(e) => setCustomerForm({ ...customerForm, address: e.target.value })} /></Grid>
            <Grid size={{ xs: 12 }}><FormControlLabel control={<Switch checked={customerForm.is_active} onChange={(e) => setCustomerForm({ ...customerForm, is_active: e.target.checked })} />} label="Active" /></Grid>
          </Grid>
        </DialogContent>
        <DialogActions><Button onClick={() => setCustomerOpen(false)}>Cancel</Button><Button variant="contained" onClick={saveCustomer}>Save</Button></DialogActions>
      </Dialog>

      <Dialog open={contactOpen} onClose={() => setContactOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingContact ? 'Edit Contact' : 'New Contact'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid size={{ xs: 12 }}>
              <FormControl fullWidth required>
                <InputLabel>Customer</InputLabel>
                <Select label="Customer" value={contactForm.customer_id} onChange={(e) => setContactForm({ ...contactForm, customer_id: e.target.value })}>
                  {customers.map((c) => <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}><TextField label="First Name" fullWidth required value={contactForm.first_name} onChange={(e) => setContactForm({ ...contactForm, first_name: e.target.value })} /></Grid>
            <Grid size={{ xs: 12, sm: 6 }}><TextField label="Last Name" fullWidth required value={contactForm.last_name} onChange={(e) => setContactForm({ ...contactForm, last_name: e.target.value })} /></Grid>
            <Grid size={{ xs: 12, sm: 6 }}><TextField label="Email" fullWidth value={contactForm.email} onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })} /></Grid>
            <Grid size={{ xs: 12, sm: 6 }}><TextField label="Phone" fullWidth value={contactForm.phone} onChange={(e) => setContactForm({ ...contactForm, phone: e.target.value })} /></Grid>
            <Grid size={{ xs: 12 }}><TextField label="Job Title" fullWidth value={contactForm.job_title} onChange={(e) => setContactForm({ ...contactForm, job_title: e.target.value })} /></Grid>
            <Grid size={{ xs: 12 }}><FormControlLabel control={<Switch checked={contactForm.is_primary} onChange={(e) => setContactForm({ ...contactForm, is_primary: e.target.checked })} />} label="Primary Contact" /></Grid>
          </Grid>
        </DialogContent>
        <DialogActions><Button onClick={() => setContactOpen(false)}>Cancel</Button><Button variant="contained" onClick={saveContact}>Save</Button></DialogActions>
      </Dialog>
    </Box>
  );
}
