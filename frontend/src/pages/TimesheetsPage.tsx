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
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import { DataGrid, GridActionsCellItem, type GridColDef } from '@mui/x-data-grid';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import PageHeader from '../components/common/PageHeader';
import AlertBanner from '../components/common/AlertBanner';
import StatusChip from '../components/common/StatusChip';
import { useLookupMaps } from '../hooks/useLookupMaps';
import {
  projectsApi,
  timesheetEntriesApi,
  timesheetsApi,
  usersApi,
} from '../api/resources';
import type { Timesheet, TimesheetEntry, TimesheetStatus } from '../types';

export default function TimesheetsPage() {
  const { users, projects } = useLookupMaps();
  const [tab, setTab] = useState(0);
  const [timesheets, setTimesheets] = useState<Timesheet[]>([]);
  const [entries, setEntries] = useState<TimesheetEntry[]>([]);
  const [userOptions, setUserOptions] = useState<{ id: string; name: string }[]>([]);
  const [timesheetOptions, setTimesheetOptions] = useState<{ id: string; label: string }[]>([]);
  const [projectOptions, setProjectOptions] = useState<{ id: string; name: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [entryOpen, setEntryOpen] = useState(false);
  const [editingSheet, setEditingSheet] = useState<Timesheet | null>(null);
  const [editingEntry, setEditingEntry] = useState<TimesheetEntry | null>(null);
  const [sheetForm, setSheetForm] = useState({ user_id: '', week_start: '', status: 'draft' as TimesheetStatus });
  const [entryForm, setEntryForm] = useState({
    timesheet_id: '',
    project_id: '',
    entry_date: '',
    hours: 8,
    description: '',
  });

  const load = useCallback(() => {
    Promise.all([timesheetsApi.list(), timesheetEntriesApi.list()])
      .then(([sheets, entryRows]) => {
        setTimesheets(sheets);
        setEntries(entryRows);
        setTimesheetOptions(
          sheets.map((s) => ({
            id: s.id,
            label: `${users[s.user_id] ?? s.user_id} · week of ${s.week_start}`,
          })),
        );
      })
      .catch((err) => setError(err.message));
  }, [users]);

  useEffect(() => {
    load();
    Promise.all([usersApi.list(), projectsApi.list()]).then(([u, p]) => {
      setUserOptions(u.map((x) => ({ id: x.id, name: `${x.first_name} ${x.last_name}` })));
      setProjectOptions(p.map((x) => ({ id: x.id, name: `${x.code} — ${x.name}` })));
    });
  }, [load]);

  const saveSheet = async () => {
    try {
      if (editingSheet) await timesheetsApi.update(editingSheet.id, sheetForm);
      else await timesheetsApi.create(sheetForm);
      setSheetOpen(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    }
  };

  const saveEntry = async () => {
    try {
      const payload = { ...entryForm, description: entryForm.description || null };
      if (editingEntry) await timesheetEntriesApi.update(editingEntry.id, payload);
      else await timesheetEntriesApi.create(payload);
      setEntryOpen(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    }
  };

  const sheetColumns: GridColDef<Timesheet>[] = [
    {
      field: 'user_id',
      headerName: 'User',
      flex: 1,
      valueGetter: (_, row) => users[row.user_id] ?? row.user_id,
    },
    { field: 'week_start', headerName: 'Week Start', width: 120 },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => <StatusChip value={params.value} />,
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
            setEditingSheet(params.row);
            setSheetForm({
              user_id: params.row.user_id,
              week_start: params.row.week_start,
              status: params.row.status,
            });
            setSheetOpen(true);
          }}
        />,
        <GridActionsCellItem
          icon={<DeleteIcon />}
          label="Delete"
          onClick={() => timesheetsApi.remove(params.id as string).then(load)}
        />,
      ],
    },
  ];

  const entryColumns: GridColDef<TimesheetEntry>[] = [
    {
      field: 'project_id',
      headerName: 'Project',
      flex: 1,
      valueGetter: (_, row) => projects[row.project_id] ?? row.project_id,
    },
    { field: 'entry_date', headerName: 'Date', width: 120 },
    { field: 'hours', headerName: 'Hours', width: 90 },
    { field: 'description', headerName: 'Description', flex: 1 },
    {
      field: 'actions',
      type: 'actions',
      width: 90,
      getActions: (params) => [
        <GridActionsCellItem
          icon={<EditIcon />}
          label="Edit"
          onClick={() => {
            setEditingEntry(params.row);
            setEntryForm({
              timesheet_id: params.row.timesheet_id,
              project_id: params.row.project_id,
              entry_date: params.row.entry_date,
              hours: params.row.hours,
              description: params.row.description ?? '',
            });
            setEntryOpen(true);
          }}
        />,
        <GridActionsCellItem
          icon={<DeleteIcon />}
          label="Delete"
          onClick={() => timesheetEntriesApi.remove(params.id as string).then(load)}
        />,
      ],
    },
  ];

  return (
    <Box>
      <PageHeader title="Timesheets" subtitle="Weekly timesheets and time entries" />
      <AlertBanner message={error} onClose={() => setError(null)} />
      <Card sx={{ mb: 2 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)}>
          <Tab label="Timesheets" />
          <Tab label="Entries" />
        </Tabs>
      </Card>

      {tab === 0 && (
        <>
          <Box sx={{ mb: 2 }}>
            <Button
              variant="contained"
              onClick={() => {
                setEditingSheet(null);
                setSheetForm({ user_id: '', week_start: '', status: 'draft' });
                setSheetOpen(true);
              }}
            >
              New Timesheet
            </Button>
          </Box>
          <Card sx={{ p: 1 }}>
            <DataGrid rows={timesheets} columns={sheetColumns} autoHeight pageSizeOptions={[10, 25]} initialState={{ pagination: { paginationModel: { pageSize: 10 } } }} disableRowSelectionOnClick />
          </Card>
        </>
      )}

      {tab === 1 && (
        <>
          <Box sx={{ mb: 2 }}>
            <Button
              variant="contained"
              onClick={() => {
                setEditingEntry(null);
                setEntryForm({ timesheet_id: '', project_id: '', entry_date: '', hours: 8, description: '' });
                setEntryOpen(true);
              }}
            >
              New Entry
            </Button>
          </Box>
          <Card sx={{ p: 1 }}>
            <DataGrid rows={entries} columns={entryColumns} autoHeight pageSizeOptions={[10, 25]} initialState={{ pagination: { paginationModel: { pageSize: 10 } } }} disableRowSelectionOnClick />
          </Card>
        </>
      )}

      <Dialog open={sheetOpen} onClose={() => setSheetOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingSheet ? 'Edit Timesheet' : 'New Timesheet'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid size={{ xs: 12 }}>
              <FormControl fullWidth required>
                <InputLabel>User</InputLabel>
                <Select label="User" value={sheetForm.user_id} onChange={(e) => setSheetForm({ ...sheetForm, user_id: e.target.value })}>
                  {userOptions.map((u) => <MenuItem key={u.id} value={u.id}>{u.name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField label="Week Start" type="date" fullWidth slotProps={{ inputLabel: { shrink: true } }} value={sheetForm.week_start} onChange={(e) => setSheetForm({ ...sheetForm, week_start: e.target.value })} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControl fullWidth>
                <InputLabel>Status</InputLabel>
                <Select label="Status" value={sheetForm.status} onChange={(e) => setSheetForm({ ...sheetForm, status: e.target.value as TimesheetStatus })}>
                  {['draft', 'submitted', 'approved', 'rejected'].map((s) => <MenuItem key={s} value={s}>{s}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSheetOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={saveSheet}>Save</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={entryOpen} onClose={() => setEntryOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingEntry ? 'Edit Entry' : 'New Entry'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid size={{ xs: 12 }}>
              <FormControl fullWidth required>
                <InputLabel>Timesheet</InputLabel>
                <Select label="Timesheet" value={entryForm.timesheet_id} onChange={(e) => setEntryForm({ ...entryForm, timesheet_id: e.target.value })}>
                  {timesheetOptions.map((t) => <MenuItem key={t.id} value={t.id}>{t.label}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12 }}>
              <FormControl fullWidth required>
                <InputLabel>Project</InputLabel>
                <Select label="Project" value={entryForm.project_id} onChange={(e) => setEntryForm({ ...entryForm, project_id: e.target.value })}>
                  {projectOptions.map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField label="Date" type="date" fullWidth slotProps={{ inputLabel: { shrink: true } }} value={entryForm.entry_date} onChange={(e) => setEntryForm({ ...entryForm, entry_date: e.target.value })} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField label="Hours" type="number" fullWidth value={entryForm.hours} onChange={(e) => setEntryForm({ ...entryForm, hours: Number(e.target.value) })} />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <TextField label="Description" fullWidth multiline rows={2} value={entryForm.description} onChange={(e) => setEntryForm({ ...entryForm, description: e.target.value })} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEntryOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={saveEntry}>Save</Button>
        </DialogActions>
      </Dialog>

      {timesheets.length === 0 && tab === 0 && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Create a timesheet first, then add entries on the Entries tab.
        </Typography>
      )}
    </Box>
  );
}
