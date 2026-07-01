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
import { streamsApi } from '../../api/resources';
import type { Stream } from '../../types';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';

interface StreamFormState {
  name: string;
  description: string;
  is_active: boolean;
}

const emptyForm: StreamFormState = {
  name: '',
  description: '',
  is_active: true,
};

export default function StreamsPage() {
  const { showSuccess, showError } = useToast();
  const [streams, setStreams] = useState<Stream[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [viewStream, setViewStream] = useState<Stream | null>(null);
  const [editingStream, setEditingStream] = useState<Stream | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Stream | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [form, setForm] = useState<StreamFormState>(emptyForm);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      setStreams(await streamsApi.list());
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredStreams = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return streams;
    return streams.filter((stream) => {
      const haystack = [stream.name, stream.description ?? ''].join(' ').toLowerCase();
      return haystack.includes(term);
    });
  }, [search, streams]);

  const openCreate = () => {
    setEditingStream(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  useOpenCreateFromQuery(openCreate);

  const openEdit = (stream: Stream) => {
    setEditingStream(stream);
    setForm({
      name: stream.name,
      description: stream.description ?? '',
      is_active: stream.is_active,
    });
    setFormOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        description: form.description || null,
        is_active: form.is_active,
      };
      if (editingStream) {
        await streamsApi.update(editingStream.id, payload);
        showSuccess('Stream updated successfully.');
      } else {
        await streamsApi.create(payload);
        showSuccess('Stream created successfully.');
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
      await streamsApi.remove(deleteTarget.id);
      showSuccess('Stream deleted successfully.');
      setDeleteTarget(null);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setActionLoading(false);
    }
  };

  const columns: GridColDef<Stream>[] = [
    { field: 'name', headerName: 'Name', flex: 1.2, minWidth: 140 },
    {
      field: 'description',
      headerName: 'Description',
      flex: 2,
      minWidth: 180,
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
            <IconButton size="small" onClick={() => setViewStream(params.row)}>
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

  if (loading) return <LoadingState message="Loading streams…" />;

  return (
    <Box>
      <PageHeader
        title="Streams"
        subtitle="Manage engineering streams"
        action={
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
            Create Stream
          </Button>
        }
      />

      <Card sx={{ p: 2, mb: 2 }}>
        <TextField
          label="Search by name or description"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, width: '100%', maxWidth: 480 }}
        />
      </Card>

      <Card sx={{ p: 1 }}>
        <DataGrid
          rows={filteredStreams}
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
        <DialogTitle>{editingStream ? 'Edit Stream' : 'Create Stream'}</DialogTitle>
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
            {editingStream ? 'Save' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(viewStream)}
        onClose={() => setViewStream(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Stream Details</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {viewStream && (
            <>
              <TextField label="Name" value={viewStream.name} slotProps={{ input: { readOnly: true } }} fullWidth />
              <TextField
                label="Description"
                value={viewStream.description ?? '—'}
                slotProps={{ input: { readOnly: true } }}
                multiline
                minRows={2}
                fullWidth
              />
              <TextField
                label="Status"
                value={viewStream.is_active ? 'Active' : 'Inactive'}
                slotProps={{ input: { readOnly: true } }}
                fullWidth
              />
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setViewStream(null)}>Close</Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete Stream"
        message={
          deleteTarget
            ? `Delete stream "${deleteTarget.name}"? This action cannot be undone.`
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
