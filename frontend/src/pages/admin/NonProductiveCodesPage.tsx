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
  Stack,
  Switch,
  TextField,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ArchiveIcon from '@mui/icons-material/Archive';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import EditIcon from '@mui/icons-material/Edit';
import UnarchiveIcon from '@mui/icons-material/Unarchive';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminDeleteButton } from '../../components/admin/AdminDeleteButton';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { nonProductiveCodesApi } from '../../api/resources';
import type { NonProductiveCode } from '../../types';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import { formatCellValue } from '../../utils/format';
import { optionalString, validateRequiredFields } from '../../utils/formValues';

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
  const [showArchived, setShowArchived] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await nonProductiveCodesApi.list({ limit: 500, include_archived: showArchived });
      setRows(
        [...data]
          .filter((row) => showArchived || !row.is_archived)
          .sort((a, b) => a.sort_order - b.sort_order || a.code.localeCompare(b.code)),
      );
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [showArchived, showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const updateRow = async (
    row: NonProductiveCode,
    patch: Partial<NonProductiveCode>,
    successMessage: string,
  ) => {
    try {
      await nonProductiveCodesApi.update(row.id, patch);
      showSuccess(successMessage);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    }
  };

  const moveRow = async (row: NonProductiveCode, direction: 'up' | 'down') => {
    const sorted = [...rows].sort(
      (a, b) => a.sort_order - b.sort_order || a.code.localeCompare(b.code),
    );
    const index = sorted.findIndex((item) => item.id === row.id);
    const swapIndex = direction === 'up' ? index - 1 : index + 1;
    const neighbor = sorted[swapIndex];
    if (neighbor == null) return;

    setSaving(true);
    try {
      await nonProductiveCodesApi.update(row.id, { sort_order: neighbor.sort_order });
      await nonProductiveCodesApi.update(neighbor.id, { sort_order: row.sort_order });
      showSuccess('Sort order updated');
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const columns = useMemo<GridColDef<NonProductiveCode>[]>(
    () => [
      { field: 'code', headerName: 'Code', flex: 1, minWidth: 120 },
      {
        field: 'description',
        headerName: 'Description',
        flex: 2,
        minWidth: 220,
        valueFormatter: (value) => formatCellValue(value as string | null),
      },
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
        field: 'is_archived',
        headerName: 'Archived',
        width: 110,
        renderCell: (params) => (
          <Chip
            size="small"
            label={params.value ? 'Archived' : 'Current'}
            color={params.value ? 'warning' : 'default'}
          />
        ),
      },
      {
        field: 'actions',
        headerName: '',
        width: 220,
        sortable: false,
        filterable: false,
        renderCell: (params) => (
          <Stack direction="row" spacing={0.5}>
            <Tooltip title="Move up">
              <span>
                <IconButton size="small" disabled={saving} onClick={() => void moveRow(params.row, 'up')}>
                  <ArrowUpwardIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Move down">
              <span>
                <IconButton size="small" disabled={saving} onClick={() => void moveRow(params.row, 'down')}>
                  <ArrowDownwardIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Edit">
              <IconButton
                size="small"
                onClick={() => {
                  setEditing(params.row);
                  setForm({
                    code: params.row.code,
                    description: params.row.description ?? '',
                    sort_order: String(params.row.sort_order),
                    is_active: params.row.is_active,
                  });
                  setFormOpen(true);
                }}
              >
                <EditIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            {params.row.is_archived ? (
              <Tooltip title="Restore">
                <IconButton
                  size="small"
                  onClick={() =>
                    void updateRow(params.row, { is_archived: false }, 'NP code restored')
                  }
                >
                  <UnarchiveIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            ) : (
              <Tooltip title="Archive">
                <IconButton
                  size="small"
                  onClick={() =>
                    void updateRow(params.row, { is_archived: true }, 'NP code archived')
                  }
                >
                  <ArchiveIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
            <AdminDeleteButton
              resource="non-productive-codes"
              recordId={params.row.id}
              recordName={params.row.code}
              onDeleted={() => void loadData()}
              showArchive
              onArchive={async () => {
                await nonProductiveCodesApi.update(params.row.id, { is_archived: true });
                showSuccess('NP code archived.');
                await loadData();
              }}
              onDeactivate={async () => {
                await nonProductiveCodesApi.update(params.row.id, { is_active: false });
                showSuccess('NP code deactivated.');
                await loadData();
              }}
            />
          </Stack>
        ),
      },
    ],
    [loadData, saving, showSuccess],
  );

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  useOpenCreateFromQuery(openCreate);

  const handleSave = async () => {
    const validationError = validateRequiredFields(form, [{ key: 'code', label: 'Code' }]);
    if (validationError) {
      showError(validationError);
      return;
    }
    setSaving(true);
    try {
      const payload = {
        code: form.code.trim(),
        description: optionalString(form.description),
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

      <Box sx={{ mb: 2 }}>
        <FormControlLabel
          control={
            <Switch
              checked={showArchived}
              onChange={(event) => setShowArchived(event.target.checked)}
            />
          }
          label="Show archived codes"
        />
      </Box>

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
            disabled={saving || !form.code.trim()}
            onClick={() => void handleSave()}
          >
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
