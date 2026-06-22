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
import { milestonesApi, projectsApi } from '../api/resources';
import type { Milestone, MilestoneStatus } from '../types';
import { projectLabel } from '../types';

const MILESTONE_STATUSES: MilestoneStatus[] = [
  'not_started',
  'in_progress',
  'completed',
  'not_applicable',
];

const emptyForm = {
  project_id: '',
  name: '',
  description: '',
  status: 'not_started' as MilestoneStatus,
  due_date: '',
  sort_order: 0,
};

export default function MilestonesPage() {
  const { projects } = useLookupMaps();
  const [rows, setRows] = useState<Milestone[]>([]);
  const [projectFilter, setProjectFilter] = useState('');
  const [projectOptions, setProjectOptions] = useState<{ id: string; name: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Milestone | null>(null);
  const [form, setForm] = useState(emptyForm);

  const load = useCallback(() => {
    milestonesApi
      .list(projectFilter ? { project_id: projectFilter } : undefined)
      .then(setRows)
      .catch((err) => setError(err.message));
  }, [projectFilter]);

  useEffect(() => {
    load();
    projectsApi.list().then((p) =>
      setProjectOptions(p.map((x) => ({ id: x.id, name: projectLabel(x) }))),
    );
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm({ ...emptyForm, project_id: projectFilter });
    setOpen(true);
  };

  const openEdit = (row: Milestone) => {
    setEditing(row);
    setForm({
      project_id: row.project_id,
      name: row.name,
      description: row.description ?? '',
      status: row.status,
      due_date: row.due_date ?? '',
      sort_order: row.sort_order,
    });
    setOpen(true);
  };

  const save = async () => {
    try {
      const payload = {
        ...form,
        description: form.description || null,
        due_date: form.due_date || null,
      };
      if (editing) await milestonesApi.update(editing.id, payload);
      else await milestonesApi.create(payload);
      setOpen(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    }
  };

  const remove = async (id: string) => {
    try {
      await milestonesApi.remove(id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  const columns: GridColDef<Milestone>[] = [
    { field: 'name', headerName: 'Milestone', flex: 1, minWidth: 180 },
    {
      field: 'project_id',
      headerName: 'Project',
      flex: 1,
      minWidth: 160,
      valueGetter: (_, row) => projects[row.project_id] ?? row.project_id,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 150,
      renderCell: (params) => <StatusChip value={params.value} />,
    },
    { field: 'due_date', headerName: 'Due Date', width: 120 },
    { field: 'sort_order', headerName: 'Order', width: 80 },
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
      <PageHeader title="Milestones" subtitle="Manage project milestones and delivery dates" actionLabel="New Milestone" onAction={openCreate} />
      <AlertBanner message={error} onClose={() => setError(null)} />
      <Card sx={{ p: 2, mb: 2 }}>
        <FormControl sx={{ minWidth: 280 }}>
          <InputLabel>Filter by Project</InputLabel>
          <Select label="Filter by Project" value={projectFilter} onChange={(e) => setProjectFilter(e.target.value)}>
            <MenuItem value="">All projects</MenuItem>
            {projectOptions.map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
          </Select>
        </FormControl>
      </Card>
      <Card sx={{ p: 1 }}>
        <DataGrid rows={rows} columns={columns} autoHeight pageSizeOptions={[10, 25]} initialState={{ pagination: { paginationModel: { pageSize: 10 } } }} disableRowSelectionOnClick />
      </Card>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? 'Edit Milestone' : 'New Milestone'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid size={{ xs: 12 }}>
              <FormControl fullWidth required>
                <InputLabel>Project</InputLabel>
                <Select label="Project" value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })}>
                  {projectOptions.map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12 }}>
              <TextField label="Name" fullWidth required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControl fullWidth>
                <InputLabel>Status</InputLabel>
                <Select label="Status" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as MilestoneStatus })}>
                  {MILESTONE_STATUSES.map((s) => <MenuItem key={s} value={s}>{s.replace(/_/g, ' ')}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField label="Due Date" type="date" fullWidth slotProps={{ inputLabel: { shrink: true } }} value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
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
