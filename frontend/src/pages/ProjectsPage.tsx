import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Card,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from '@mui/material';
import { DataGrid, GridActionsCellItem, type GridColDef } from '@mui/x-data-grid';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import PageHeader from '../components/common/PageHeader';
import AlertBanner from '../components/common/AlertBanner';
import StatusChip from '../components/common/StatusChip';
import { useLookupMaps } from '../hooks/useLookupMaps';
import {
  contactsApi,
  customersApi,
  projectsApi,
  rolesApi,
  streamsApi,
  usersApi,
} from '../api/resources';
import type { Project, ProjectStatus, User } from '../types';

const PROJECT_STATUSES: ProjectStatus[] = [
  'not_started',
  'in_progress',
  'waiting_for_customer',
  'completed',
];

const emptyForm = {
  tool_number: '',
  part_description: '',
  customer_id: '',
  customer_contact_id: '',
  design_leader_id: '',
  designer_id: '',
  surfacer_id: '',
  stream_id: '',
  code: '',
  quoted_hours: '',
  due_date: '',
  status: 'not_started' as ProjectStatus,
  notes: '',
};

function userLabel(user: User) {
  return `${user.first_name} ${user.last_name}`;
}

export default function ProjectsPage() {
  const { customers, users } = useLookupMaps();
  const [rows, setRows] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Project | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [customerOptions, setCustomerOptions] = useState<{ id: string; name: string }[]>([]);
  const [streamOptions, setStreamOptions] = useState<{ id: string; name: string }[]>([]);
  const [contactOptions, setContactOptions] = useState<{ id: string; name: string }[]>([]);
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [roleNames, setRoleNames] = useState<Record<string, string>>({});

  const load = useCallback(() => {
    projectsApi
      .list()
      .then(setRows)
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    load();
    Promise.all([customersApi.list(), streamsApi.list(), usersApi.list(), rolesApi.list()])
      .then(([c, s, u, r]) => {
        setCustomerOptions(c.map((x) => ({ id: x.id, name: x.name })));
        setStreamOptions(s.map((x) => ({ id: x.id, name: x.name })));
        setAllUsers(u);
        setRoleNames(Object.fromEntries(r.map((role) => [role.id, role.name])));
      })
      .catch(() => undefined);
  }, [load]);

  useEffect(() => {
    if (!form.customer_id) {
      setContactOptions([]);
      return;
    }
    contactsApi
      .list({ customer_id: form.customer_id })
      .then((contacts) =>
        setContactOptions(
          contacts.map((c) => ({
            id: c.id,
            name: `${c.first_name} ${c.last_name}`,
          })),
        ),
      )
      .catch(() => setContactOptions([]));
  }, [form.customer_id]);

  const usersByRole = useMemo(() => {
    const filterRole = (roleName: string) =>
      allUsers
        .filter((u) => u.is_active && roleNames[u.role_id] === roleName)
        .map((u) => ({ id: u.id, name: userLabel(u) }));

    return {
      designLeader: filterRole('Design Leader'),
      designer: filterRole('Designer'),
      surfacer: filterRole('Surfacer'),
    };
  }, [allUsers, roleNames]);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
  };

  const openEdit = (row: Project) => {
    setEditing(row);
    setForm({
      tool_number: row.tool_number,
      part_description: row.part_description,
      customer_id: row.customer_id,
      customer_contact_id: row.customer_contact_id,
      design_leader_id: row.design_leader_id,
      designer_id: row.designer_id ?? '',
      surfacer_id: row.surfacer_id ?? '',
      stream_id: row.stream_id,
      code: row.code,
      quoted_hours: String(row.quoted_hours),
      due_date: row.due_date,
      status: row.status,
      notes: row.notes ?? '',
    });
    setOpen(true);
  };

  const save = async () => {
    try {
      const payload = {
        tool_number: form.tool_number,
        part_description: form.part_description,
        customer_id: form.customer_id,
        customer_contact_id: form.customer_contact_id,
        design_leader_id: form.design_leader_id,
        designer_id: form.designer_id || null,
        surfacer_id: form.surfacer_id || null,
        stream_id: form.stream_id,
        code: form.code,
        quoted_hours: Number(form.quoted_hours),
        due_date: form.due_date,
        status: form.status,
        notes: form.notes || null,
      };
      if (editing) {
        await projectsApi.update(editing.id, payload);
      } else {
        await projectsApi.create(payload);
      }
      setOpen(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    }
  };

  const remove = async (id: string) => {
    try {
      await projectsApi.remove(id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  const columns: GridColDef<Project>[] = [
    { field: 'code', headerName: 'Code', width: 110 },
    { field: 'tool_number', headerName: 'Tool #', width: 110 },
    { field: 'part_description', headerName: 'Part', flex: 1, minWidth: 160 },
    {
      field: 'customer_id',
      headerName: 'Customer',
      flex: 1,
      minWidth: 140,
      valueGetter: (_, row) => customers[row.customer_id] ?? row.customer_id,
    },
    {
      field: 'design_leader_id',
      headerName: 'Design Leader',
      flex: 1,
      minWidth: 140,
      valueGetter: (_, row) => users[row.design_leader_id] ?? row.design_leader_id,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 160,
      renderCell: (params) => <StatusChip value={params.value} />,
    },
    { field: 'due_date', headerName: 'Due Date', width: 120 },
    { field: 'quoted_hours', headerName: 'Quoted Hrs', width: 110 },
    {
      field: 'actions',
      type: 'actions',
      width: 90,
      getActions: (params) => [
        <GridActionsCellItem icon={<EditIcon />} label="Edit" onClick={() => openEdit(params.row)} />,
        <GridActionsCellItem icon={<DeleteIcon />} label="Delete" onClick={() => remove(params.id as string)} />,
      ],
    },
  ];

  return (
    <Box>
      <PageHeader
        title="Projects"
        subtitle="Track Mold Design and other business stream projects"
        actionLabel="New Project"
        onAction={openCreate}
      />
      <AlertBanner message={error} onClose={() => setError(null)} />
      <Card sx={{ p: 1 }}>
        <DataGrid
          rows={rows}
          columns={columns}
          autoHeight
          pageSizeOptions={[10, 25]}
          initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
          disableRowSelectionOnClick
        />
      </Card>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>{editing ? 'Edit Project' : 'New Project'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField label="Code" fullWidth required value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField label="Tool Number" fullWidth required value={form.tool_number} onChange={(e) => setForm({ ...form, tool_number: e.target.value })} />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <TextField label="Part Description" fullWidth required value={form.part_description} onChange={(e) => setForm({ ...form, part_description: e.target.value })} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControl fullWidth required>
                <InputLabel>Customer</InputLabel>
                <Select
                  label="Customer"
                  value={form.customer_id}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      customer_id: e.target.value,
                      customer_contact_id: '',
                    })
                  }
                >
                  {customerOptions.map((c) => <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControl fullWidth required disabled={!form.customer_id}>
                <InputLabel>Customer Contact</InputLabel>
                <Select
                  label="Customer Contact"
                  value={form.customer_contact_id}
                  onChange={(e) => setForm({ ...form, customer_contact_id: e.target.value })}
                >
                  {contactOptions.map((c) => <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <FormControl fullWidth required>
                <InputLabel>Stream</InputLabel>
                <Select label="Stream" value={form.stream_id} onChange={(e) => setForm({ ...form, stream_id: e.target.value })}>
                  {streamOptions.map((s) => <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <FormControl fullWidth required>
                <InputLabel>Design Leader</InputLabel>
                <Select label="Design Leader" value={form.design_leader_id} onChange={(e) => setForm({ ...form, design_leader_id: e.target.value })}>
                  {usersByRole.designLeader.map((u) => <MenuItem key={u.id} value={u.id}>{u.name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <FormControl fullWidth>
                <InputLabel>Designer</InputLabel>
                <Select label="Designer" value={form.designer_id} onChange={(e) => setForm({ ...form, designer_id: e.target.value })}>
                  <MenuItem value="">None</MenuItem>
                  {usersByRole.designer.map((u) => <MenuItem key={u.id} value={u.id}>{u.name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <FormControl fullWidth>
                <InputLabel>Surfacer</InputLabel>
                <Select label="Surfacer" value={form.surfacer_id} onChange={(e) => setForm({ ...form, surfacer_id: e.target.value })}>
                  <MenuItem value="">None</MenuItem>
                  {usersByRole.surfacer.map((u) => <MenuItem key={u.id} value={u.id}>{u.name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <TextField label="Quoted Hours" type="number" fullWidth required value={form.quoted_hours} onChange={(e) => setForm({ ...form, quoted_hours: e.target.value })} />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <TextField label="Due Date" type="date" fullWidth required slotProps={{ inputLabel: { shrink: true } }} value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControl fullWidth>
                <InputLabel>Status</InputLabel>
                <Select label="Status" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as ProjectStatus })}>
                  {PROJECT_STATUSES.map((s) => (
                    <MenuItem key={s} value={s}>{s.replace(/_/g, ' ')}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12 }}>
              <TextField label="Notes" fullWidth multiline rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={save}>Save</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
