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
import { streamsApi, taskTypesApi } from '../api/resources';
import type { Stream, TaskType } from '../types';

export default function StreamsPage() {
  const [tab, setTab] = useState(0);
  const [streams, setStreams] = useState<Stream[]>([]);
  const [taskTypes, setTaskTypes] = useState<TaskType[]>([]);
  const [streamFilter, setStreamFilter] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [streamOpen, setStreamOpen] = useState(false);
  const [taskOpen, setTaskOpen] = useState(false);
  const [editingStream, setEditingStream] = useState<Stream | null>(null);
  const [editingTask, setEditingTask] = useState<TaskType | null>(null);
  const [streamForm, setStreamForm] = useState({ name: '', description: '', is_active: true });
  const [taskForm, setTaskForm] = useState({
    stream_id: '',
    name: '',
    description: '',
    is_billable: true,
    is_active: true,
  });

  const load = useCallback(() => {
    Promise.all([
      streamsApi.list(),
      taskTypesApi.list(streamFilter ? { stream_id: streamFilter } : undefined),
    ])
      .then(([s, t]) => {
        setStreams(s);
        setTaskTypes(t);
      })
      .catch((err) => setError(err.message));
  }, [streamFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const streamColumns: GridColDef<Stream>[] = [
    { field: 'name', headerName: 'Stream', flex: 1, minWidth: 200 },
    { field: 'description', headerName: 'Description', flex: 1, minWidth: 240 },
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
            setEditingStream(params.row);
            setStreamForm({
              name: params.row.name,
              description: params.row.description ?? '',
              is_active: params.row.is_active,
            });
            setStreamOpen(true);
          }}
        />,
        <GridActionsCellItem icon={<DeleteIcon />} label="Delete" onClick={() => streamsApi.remove(params.id as string).then(load)} />,
      ],
    },
  ];

  const taskColumns: GridColDef<TaskType>[] = [
    {
      field: 'stream_id',
      headerName: 'Stream',
      flex: 1,
      valueGetter: (_, row) => streams.find((s) => s.id === row.stream_id)?.name ?? row.stream_id,
    },
    { field: 'name', headerName: 'Task Type', flex: 1, minWidth: 160 },
    { field: 'description', headerName: 'Description', flex: 1, minWidth: 200 },
    {
      field: 'is_billable',
      headerName: 'Billable',
      width: 90,
      valueGetter: (_, row) => (row.is_billable ? 'Yes' : 'No'),
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
            setEditingTask(params.row);
            setTaskForm({
              stream_id: params.row.stream_id,
              name: params.row.name,
              description: params.row.description ?? '',
              is_billable: params.row.is_billable,
              is_active: params.row.is_active,
            });
            setTaskOpen(true);
          }}
        />,
        <GridActionsCellItem icon={<DeleteIcon />} label="Delete" onClick={() => taskTypesApi.remove(params.id as string).then(load)} />,
      ],
    },
  ];

  const saveStream = async () => {
    try {
      const payload = { ...streamForm, description: streamForm.description || null };
      if (editingStream) await streamsApi.update(editingStream.id, payload);
      else await streamsApi.create(payload);
      setStreamOpen(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    }
  };

  const saveTask = async () => {
    try {
      const payload = { ...taskForm, description: taskForm.description || null };
      if (editingTask) await taskTypesApi.update(editingTask.id, payload);
      else await taskTypesApi.create(payload);
      setTaskOpen(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    }
  };

  return (
    <Box>
      <PageHeader title="Streams & Task Types" subtitle="Business streams and associated task types" />
      <AlertBanner message={error} onClose={() => setError(null)} />
      <Card sx={{ mb: 2 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)}>
          <Tab label="Business Streams" />
          <Tab label="Task Types" />
        </Tabs>
      </Card>

      {tab === 0 && (
        <>
          <Box sx={{ mb: 2 }}>
            <Button variant="contained" onClick={() => { setEditingStream(null); setStreamForm({ name: '', description: '', is_active: true }); setStreamOpen(true); }}>
              New Stream
            </Button>
          </Box>
          <Card sx={{ p: 1 }}>
            <DataGrid rows={streams} columns={streamColumns} autoHeight pageSizeOptions={[10, 25]} initialState={{ pagination: { paginationModel: { pageSize: 10 } } }} disableRowSelectionOnClick />
          </Card>
        </>
      )}

      {tab === 1 && (
        <>
          <Card sx={{ p: 2, mb: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
            <FormControl sx={{ minWidth: 260 }}>
              <InputLabel>Filter by Stream</InputLabel>
              <Select label="Filter by Stream" value={streamFilter} onChange={(e) => setStreamFilter(e.target.value)}>
                <MenuItem value="">All streams</MenuItem>
                {streams.map((s) => <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>)}
              </Select>
            </FormControl>
            <Button variant="contained" onClick={() => { setEditingTask(null); setTaskForm({ stream_id: streamFilter, name: '', description: '', is_billable: true, is_active: true }); setTaskOpen(true); }}>
              New Task Type
            </Button>
          </Card>
          <Card sx={{ p: 1 }}>
            <DataGrid rows={taskTypes} columns={taskColumns} autoHeight pageSizeOptions={[10, 25]} initialState={{ pagination: { paginationModel: { pageSize: 10 } } }} disableRowSelectionOnClick />
          </Card>
        </>
      )}

      <Dialog open={streamOpen} onClose={() => setStreamOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingStream ? 'Edit Stream' : 'New Stream'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid size={{ xs: 12 }}><TextField label="Name" fullWidth required value={streamForm.name} onChange={(e) => setStreamForm({ ...streamForm, name: e.target.value })} /></Grid>
            <Grid size={{ xs: 12 }}><TextField label="Description" fullWidth multiline rows={3} value={streamForm.description} onChange={(e) => setStreamForm({ ...streamForm, description: e.target.value })} /></Grid>
            <Grid size={{ xs: 12 }}><FormControlLabel control={<Switch checked={streamForm.is_active} onChange={(e) => setStreamForm({ ...streamForm, is_active: e.target.checked })} />} label="Active" /></Grid>
          </Grid>
        </DialogContent>
        <DialogActions><Button onClick={() => setStreamOpen(false)}>Cancel</Button><Button variant="contained" onClick={saveStream}>Save</Button></DialogActions>
      </Dialog>

      <Dialog open={taskOpen} onClose={() => setTaskOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingTask ? 'Edit Task Type' : 'New Task Type'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid size={{ xs: 12 }}>
              <FormControl fullWidth required>
                <InputLabel>Stream</InputLabel>
                <Select label="Stream" value={taskForm.stream_id} onChange={(e) => setTaskForm({ ...taskForm, stream_id: e.target.value })}>
                  {streams.map((s) => <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12 }}><TextField label="Name" fullWidth required value={taskForm.name} onChange={(e) => setTaskForm({ ...taskForm, name: e.target.value })} /></Grid>
            <Grid size={{ xs: 12 }}><TextField label="Description" fullWidth multiline rows={2} value={taskForm.description} onChange={(e) => setTaskForm({ ...taskForm, description: e.target.value })} /></Grid>
            <Grid size={{ xs: 12 }}><FormControlLabel control={<Switch checked={taskForm.is_billable} onChange={(e) => setTaskForm({ ...taskForm, is_billable: e.target.checked })} />} label="Billable" /></Grid>
            <Grid size={{ xs: 12 }}><FormControlLabel control={<Switch checked={taskForm.is_active} onChange={(e) => setTaskForm({ ...taskForm, is_active: e.target.checked })} />} label="Active" /></Grid>
          </Grid>
        </DialogContent>
        <DialogActions><Button onClick={() => setTaskOpen(false)}>Cancel</Button><Button variant="contained" onClick={saveTask}>Save</Button></DialogActions>
      </Dialog>
    </Box>
  );
}
