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
import { customersApi, projectsApi, streamsApi, usersApi } from '../api/resources';
import type { Project, ProjectStatus } from '../types';

const emptyForm = {
  customer_id: '',
  stream_id: '',
  created_by: '',
  name: '',
  code: '',
  description: '',
  status: 'draft' as ProjectStatus,
  planned_start: '',
  planned_end: '',
};

export default function ProjectsPage() {
  const { customers, streams } = useLookupMaps();
  const [rows, setRows] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Project | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [customerOptions, setCustomerOptions] = useState<{ id: string; name: string }[]>([]);
  const [streamOptions, setStreamOptions] = useState<{ id: string; name: string }[]>([]);
  const [userOptions, setUserOptions] = useState<{ id: string; name: string }[]>([]);

  const load = useCallback(() => {
    projectsApi
      .list()
      .then(setRows)
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    load();
    Promise.all([customersApi.list(), streamsApi.list(), usersApi.list()])
      .then(([c, s, u]) => {
        setCustomerOptions(c.map((x) => ({ id: x.id, name: x.name })));
        setStreamOptions(s.map((x) => ({ id: x.id, name: x.name })));
        setUserOptions(u.map((x) => ({ id: x.id, name: `${x.first_name} ${x.last_name}` })));
      })
      .catch(() => undefined);
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
  };

  const openEdit = (row: Project) => {
    setEditing(row);
    setForm({
      customer_id: row.customer_id,
      stream_id: row.stream_id,
      created_by: row.created_by,
      name: row.name,
      code: row.code,
      description: row.description ?? '',
      status: row.status,
      planned_start: row.planned_start ?? '',
      planned_end: row.planned_end ?? '',
    });
    setOpen(true);
  };

  const save = async () => {
    try {
      const payload = {
        ...form,
        description: form.description || null,
        planned_start: form.planned_start || null,
        planned_end: form.planned_end || null,
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
    { field: 'name', headerName: 'Name', flex: 1, minWidth: 180 },
    {
      field: 'customer_id',
      headerName: 'Customer',
      flex: 1,
      minWidth: 140,
      valueGetter: (_, row) => customers[row.customer_id] ?? row.customer_id,
    },
    {
      field: 'stream_id',
      headerName: 'Stream',
      width: 160,
      valueGetter: (_, row) => streams[row.stream_id] ?? row.stream_id,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => <StatusChip value={params.value} />,
    },
    { field: 'planned_start', headerName: 'Start', width: 110 },
    { field: 'planned_end', headerName: 'End', width: 110 },
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
              <FormControl fullWidth>
                <InputLabel>Status</InputLabel>
                <Select label="Status" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as ProjectStatus })}>
                  {['draft', 'active', 'on_hold', 'completed', 'cancelled'].map((s) => (
                    <MenuItem key={s} value={s}>{s.replace(/_/g, ' ')}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12 }}>
              <TextField label="Name" fullWidth required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <FormControl fullWidth required>
                <InputLabel>Customer</InputLabel>
                <Select label="Customer" value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })}>
                  {customerOptions.map((c) => <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>)}
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
                <InputLabel>Created By</InputLabel>
                <Select label="Created By" value={form.created_by} onChange={(e) => setForm({ ...form, created_by: e.target.value })}>
                  {userOptions.map((u) => <MenuItem key={u.id} value={u.id}>{u.name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField label="Planned Start" type="date" fullWidth slotProps={{ inputLabel: { shrink: true } }} value={form.planned_start} onChange={(e) => setForm({ ...form, planned_start: e.target.value })} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField label="Planned End" type="date" fullWidth slotProps={{ inputLabel: { shrink: true } }} value={form.planned_end} onChange={(e) => setForm({ ...form, planned_end: e.target.value })} />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <TextField label="Description" fullWidth multiline rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
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
