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
import EditIcon from '@mui/icons-material/Edit';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { nonProductiveCodesApi } from '../../api/resources';
import type { NonProductiveCode } from '../../types';

interface NpCodeFormState {
  code: string;
  description: string;
  sort_order: string;
  is_active: boolean;
}

const emptyForm: NpCodeFormState = {
  code: '',
  description: '',
  sort_order: '0',
  is_active: true,
};

export default function NonProductiveCodesPage() {
  const { showSuccess, showError } = useToast();
  const [rows, setRows] = useState<NonProductiveCode[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<NonProductiveCode | null>(null);
  const [form, setForm] = useState<NpCodeFormState>(emptyForm);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await nonProductiveCodesApi.list({ limit: 500 });
      setRows(
        [...data].sort((a, b) => a.sort_order - b.sort_order || a.code.localeCompare(b.code)),
      );
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const columns = useMemo<GridColDef<NonProductiveCode>[]>(
    () => [
      { field: 'code', headerName: 'Code', flex: 1, minWidth: 120 },
      { field: 'description', headerName: 'Description', flex: 2, minWidth: 220 },
      { field: 'sort_order', headerName: 'Sort', width: 90 },
      {
        field: 'is_active',
        headerName: 'Active',
        width: 100,
        renderCell: (params) => (
          <Chip
            size="small"
            label={params.value ? 'Active' : 'Inactive'}
            color={params.value ? 'success' : 'default'}
          />
        ),
      },
      {
        field: 'actions',
        headerName: '',
        width: 70,
        sortable: false,
        filterable: false,
        renderCell: (params) => (
          <Tooltip title="Edit">
            <IconButton
              size="small"
              onClick={() => {
                setEditing(params.row);
                setForm({
                  code: params.row.code,
                  description: params.row.description,
                  sort_order: String(params.row.sort_order),
                  is_active: params.row.is_active,
                });
                setFormOpen(true);
              }}
            >
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ),
      },
    ],
    [],
  );

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        code: form.code.trim(),
        description: form.description.trim(),
        sort_order: Number(form.sort_order) || 0,
        is_active: form.is_active,
      };
      if (editing) {
        await nonProductiveCodesApi.update(editing.id, payload);
        showSuccess('NP code updated');
      } else {
        await nonProductiveCodesApi.create(payload);
        showSuccess('NP code created');
      }
      setFormOpen(false);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingState />;

  return (
    <Box>
      <PageHeader
        title="Non-Productive Codes"
        subtitle="Manage NP codes used for non-productive timesheet entries"
        action={
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
            Add Code
          </Button>
        }
      />

      <Card sx={{ p: 2 }}>
        <DataGrid
          rows={rows}
          columns={columns}
          autoHeight
          disableRowSelectionOnClick
          pageSizeOptions={[25, 50, 100]}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
        />
      </Card>

      <Dialog open={formOpen} onClose={() => setFormOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? 'Edit NP Code' : 'New NP Code'}</DialogTitle>
        <DialogContent>
          <TextField
            label="Code"
            fullWidth
            margin="normal"
            required
            value={form.code}
            onChange={(event) => setForm((prev) => ({ ...prev, code: event.target.value }))}
          />
          <TextField
            label="Description"
            fullWidth
            margin="normal"
            required
            value={form.description}
            onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
          />
          <TextField
            label="Sort Order"
            type="number"
            fullWidth
            margin="normal"
            value={form.sort_order}
            onChange={(event) => setForm((prev) => ({ ...prev, sort_order: event.target.value }))}
          />
          <FormControlLabel
            control={
              <Switch
                checked={form.is_active}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, is_active: event.target.checked }))
                }
              />
            }
            label="Active"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFormOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={saving || !form.code.trim() || !form.description.trim()}
            onClick={() => void handleSave()}
          >
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
