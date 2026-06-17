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
  LinearProgress,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import { DataGrid, GridActionsCellItem, type GridColDef } from '@mui/x-data-grid';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import PageHeader from '../components/common/PageHeader';
import AlertBanner from '../components/common/AlertBanner';
import { useLookupMaps } from '../hooks/useLookupMaps';
import { projectMembersApi, projectsApi, usersApi } from '../api/resources';
import type { ProjectMember } from '../types';

const emptyForm = {
  project_id: '',
  user_id: '',
  role_on_project: 'member',
  allocation_percent: 100,
  start_date: '',
  end_date: '',
};

export default function ResourcePlanningPage() {
  const { projects, users } = useLookupMaps();
  const [rows, setRows] = useState<ProjectMember[]>([]);
  const [projectFilter, setProjectFilter] = useState('');
  const [projectOptions, setProjectOptions] = useState<{ id: string; name: string }[]>([]);
  const [userOptions, setUserOptions] = useState<{ id: string; name: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ProjectMember | null>(null);
  const [form, setForm] = useState(emptyForm);

  const load = useCallback(() => {
    projectMembersApi
      .list(projectFilter ? { project_id: projectFilter } : undefined)
      .then(setRows)
      .catch((err) => setError(err.message));
  }, [projectFilter]);

  useEffect(() => {
    load();
    Promise.all([projectsApi.list(), usersApi.list()]).then(([p, u]) => {
      setProjectOptions(p.map((x) => ({ id: x.id, name: `${x.code} — ${x.name}` })));
      setUserOptions(u.map((x) => ({ id: x.id, name: `${x.first_name} ${x.last_name}` })));
    });
  }, [load]);

  const save = async () => {
    try {
      const payload = {
        ...form,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
      };
      if (editing) await projectMembersApi.update(editing.id, payload);
      else await projectMembersApi.create(payload);
      setOpen(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    }
  };

  const columns: GridColDef<ProjectMember>[] = [
    {
      field: 'project_id',
      headerName: 'Project',
      flex: 1,
      minWidth: 180,
      valueGetter: (_, row) => projects[row.project_id] ?? row.project_id,
    },
    {
      field: 'user_id',
      headerName: 'Team Member',
      flex: 1,
      minWidth: 160,
      valueGetter: (_, row) => users[row.user_id] ?? row.user_id,
    },
    { field: 'role_on_project', headerName: 'Role', width: 120 },
    {
      field: 'allocation_percent',
      headerName: 'Allocation',
      width: 160,
      renderCell: (params) => (
        <Box sx={{ width: '100%', pr: 1 }}>
          <Typography variant="caption">{params.value}%</Typography>
          <LinearProgress variant="determinate" value={params.value as number} sx={{ mt: 0.5 }} />
        </Box>
      ),
    },
    { field: 'start_date', headerName: 'Start', width: 110 },
    { field: 'end_date', headerName: 'End', width: 110 },
    {
      field: 'actions',
      type: 'actions',
      width: 90,
      getActions: (params) => [
        <GridActionsCellItem
          icon={<EditIcon />}
          label="Edit"
          onClick={() => {
            setEditing(params.row);
            setForm({
              project_id: params.row.project_id,
              user_id: params.row.user_id,
              role_on_project: params.row.role_on_project,
              allocation_percent: params.row.allocation_percent,
              start_date: params.row.start_date ?? '',
              end_date: params.row.end_date ?? '',
            });
            setOpen(true);
          }}
        />,
        <GridActionsCellItem
          icon={<DeleteIcon />}
          label="Delete"
          onClick={() => projectMembersApi.remove(params.id as string).then(load)}
        />,
      ],
    },
  ];

  return (
    <Box>
      <PageHeader
        title="Resource Planning"
        subtitle="Assign team members to projects with allocation percentages"
        actionLabel="Add Assignment"
        onAction={() => {
          setEditing(null);
          setForm({ ...emptyForm, project_id: projectFilter });
          setOpen(true);
        }}
      />
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
        <DialogTitle>{editing ? 'Edit Assignment' : 'New Assignment'}</DialogTitle>
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
              <FormControl fullWidth required>
                <InputLabel>Team Member</InputLabel>
                <Select label="Team Member" value={form.user_id} onChange={(e) => setForm({ ...form, user_id: e.target.value })}>
                  {userOptions.map((u) => <MenuItem key={u.id} value={u.id}>{u.name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField label="Role on Project" fullWidth value={form.role_on_project} onChange={(e) => setForm({ ...form, role_on_project: e.target.value })} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField label="Allocation %" type="number" fullWidth value={form.allocation_percent} onChange={(e) => setForm({ ...form, allocation_percent: Number(e.target.value) })} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField label="Start Date" type="date" fullWidth slotProps={{ inputLabel: { shrink: true } }} value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField label="End Date" type="date" fullWidth slotProps={{ inputLabel: { shrink: true } }} value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
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
