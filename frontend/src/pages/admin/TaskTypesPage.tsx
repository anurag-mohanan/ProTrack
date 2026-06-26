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
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { streamsApi, taskTypesApi } from '../../api/resources';
import type { Stream, TaskType } from '../../types';

interface TaskTypeFormState {
  name: string;
  stream_id: string;
  description: string;
  is_billable: boolean;
  is_active: boolean;
}

const emptyForm: TaskTypeFormState = {
  name: '',
  stream_id: '',
  description: '',
  is_billable: true,
  is_active: true,
};

export default function TaskTypesPage() {
  const { showSuccess, showError } = useToast();
  const [taskTypes, setTaskTypes] = useState<TaskType[]>([]);
  const [streams, setStreams] = useState<Stream[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [viewTaskType, setViewTaskType] = useState<TaskType | null>(null);
  const [editingTaskType, setEditingTaskType] = useState<TaskType | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TaskType | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [form, setForm] = useState<TaskTypeFormState>(emptyForm);

  const streamMap = useMemo(
    () => new Map(streams.map((stream) => [stream.id, stream.name])),
    [streams],
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [taskTypesData, streamsData] = await Promise.all([
        taskTypesApi.list(),
        streamsApi.list(),
      ]);
      setTaskTypes(taskTypesData);
      setStreams(streamsData);
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredTaskTypes = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return taskTypes;
    return taskTypes.filter((taskType) => {
      const streamName = streamMap.get(taskType.stream_id) ?? '';
      const haystack = [taskType.name, taskType.description ?? '', streamName]
        .join(' ')
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [search, streamMap, taskTypes]);

  const openCreate = () => {
    setEditingTaskType(null);
    setForm({
      ...emptyForm,
      stream_id: streams[0]?.id ?? '',
    });
    setFormOpen(true);
  };

  const openEdit = (taskType: TaskType) => {
    setEditingTaskType(taskType);
    setForm({
      name: taskType.name,
      stream_id: taskType.stream_id,
      description: taskType.description ?? '',
      is_billable: taskType.is_billable,
      is_active: taskType.is_active,
    });
    setFormOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        stream_id: form.stream_id,
        description: form.description || null,
        is_billable: form.is_billable,
        is_active: form.is_active,
      };
      if (editingTaskType) {
        await taskTypesApi.update(editingTaskType.id, payload);
        showSuccess('Task type updated successfully.');
      } else {
        await taskTypesApi.create(payload);
        showSuccess('Task type created successfully.');
      }
      setFormOpen(false);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setActionLoading(true);
    try {
      await taskTypesApi.remove(deleteTarget.id);
      showSuccess('Task type deleted successfully.');
      setDeleteTarget(null);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setActionLoading(false);
    }
  };

  const columns: GridColDef<TaskType>[] = [
    { field: 'name', headerName: 'Name', flex: 1.2, minWidth: 140 },
    {
      field: 'stream_id',
      headerName: 'Stream',
      flex: 1,
      minWidth: 120,
      renderCell: (params) => (
        <Chip
          label={streamMap.get(params.value as string) ?? '—'}
          size="small"
          variant="outlined"
        />
      ),
    },
    {
      field: 'is_billable',
      headerName: 'Billable',
      width: 100,
      renderCell: (params) => (
        <Chip
          label={params.value ? 'Yes' : 'No'}
          size="small"
          color={params.value ? 'primary' : 'default'}
        />
      ),
    },
    {
      field: 'description',
      headerName: 'Description',
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
      field: 'actions',
      headerName: 'Actions',
      width: 130,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="View">
            <IconButton size="small" onClick={() => setViewTaskType(params.row)}>
              <VisibilityIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openEdit(params.row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton size="small" onClick={() => setDeleteTarget(params.row)}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading task types…" />;

  return (
    <Box>
      <PageHeader
        title="Task Types"
        subtitle="Manage billable task types by stream"
        action={
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
            Create Task Type
          </Button>
        }
      />

      <Card sx={{ p: 2, mb: 2 }}>
        <TextField
          label="Search by name, stream, or description"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, width: '100%', maxWidth: 480 }}
        />
      </Card>

      <Card sx={{ p: 1 }}>
        <DataGrid
          rows={filteredTaskTypes}
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
        <DialogTitle>{editingTaskType ? 'Edit Task Type' : 'Create Task Type'}</DialogTitle>
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
          <FormControl fullWidth required>
            <InputLabel>Stream</InputLabel>
            <Select
              label="Stream"
              value={form.stream_id}
              onChange={(event) =>
                setForm((current) => ({ ...current, stream_id: event.target.value }))
              }
            >
              {streams.map((stream) => (
                <MenuItem key={stream.id} value={stream.id}>
                  {stream.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Description"
            value={form.description}
            onChange={(event) =>
              setForm((current) => ({ ...current, description: event.target.value }))
            }
            multiline
            minRows={3}
            fullWidth
          />
          <FormControlLabel
            control={
              <Switch
                checked={form.is_billable}
                onChange={(event) =>
                  setForm((current) => ({ ...current, is_billable: event.target.checked }))
                }
              />
            }
            label="Billable"
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
            {editingTaskType ? 'Save' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(viewTaskType)}
        onClose={() => setViewTaskType(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Task Type Details</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {viewTaskType && (
            <>
              <TextField label="Name" value={viewTaskType.name} slotProps={{ input: { readOnly: true } }} fullWidth />
              <TextField
                label="Stream"
                value={streamMap.get(viewTaskType.stream_id) ?? '—'}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
              <TextField
                label="Billable"
                value={viewTaskType.is_billable ? 'Yes' : 'No'}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
              <TextField
                label="Description"
                value={viewTaskType.description ?? '—'}
                slotProps={{ input: { readOnly: true } }}
                multiline
                minRows={2}
                fullWidth
              />
              <TextField
                label="Status"
                value={viewTaskType.is_active ? 'Active' : 'Inactive'}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setViewTaskType(null)}>Close</Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete Task Type"
        message={
          deleteTarget
            ? `Delete task type "${deleteTarget.name}"? This action cannot be undone.`
            : ''
        }
        confirmLabel="Delete"
        onConfirm={() => void handleDelete()}
        onClose={() => setDeleteTarget(null)}
        loading={actionLoading}
      />
    </Box>
  );
}
