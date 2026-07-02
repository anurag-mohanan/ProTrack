import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import {
  Box,
  Chip,
  FormControlLabel,
  IconButton,
  Stack,
  Switch,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ArchiveIcon from '@mui/icons-material/Archive';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import TimerOffOutlinedIcon from '@mui/icons-material/TimerOffOutlined';
import UnarchiveIcon from '@mui/icons-material/Unarchive';
import type { GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { AdminDeleteButton } from '../../components/admin/AdminDeleteButton';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { nonProductiveCodesApi } from '../../api/resources';
import type { NonProductiveCode } from '../../types';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  DrawerQuickActions,
  FormDrawer,
  FormField,
  FormSection,
  ProsohmDataGrid,
  RecordDetailDrawer,
  TableRowActions,
} from '../../components/ui/design-system';
import { formatCellValue } from '../../utils/format';
import { optionalString, validateRequiredFields } from '../../utils/formValues';
import { canDeleteRecords } from '../../utils/permissions';
import { useAuth } from '../../context/AuthContext';
import { DATA_GRID_ACTIONS_COLUMN_WIDTH } from '../../theme/componentStyles';

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
  const { user } = useAuth();
  const isAdmin = canDeleteRecords(user?.role_name ?? '');
  const { showSuccess, showError } = useToast();
  const [rows, setRows] = useState<NonProductiveCode[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [selectedCode, setSelectedCode] = useState<NonProductiveCode | null>(null);
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

  const openEdit = (row: NonProductiveCode) => {
    setEditing(row);
    setForm({
      code: row.code,
      description: row.description ?? '',
      sort_order: String(row.sort_order),
      is_active: row.is_active,
    });
    setFormOpen(true);
  };

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  useOpenCreateFromQuery(openCreate);

  const handleSave = async (event?: FormEvent) => {
    event?.preventDefault();
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

  const actionsColumnWidth = isAdmin
    ? DATA_GRID_ACTIONS_COLUMN_WIDTH + 160
    : DATA_GRID_ACTIONS_COLUMN_WIDTH + 120;

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
        width: actionsColumnWidth,
        sortable: false,
        filterable: false,
        renderCell: (params) => (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
            <Tooltip title="Move up">
              <span>
                <IconButton
                  size="small"
                  disabled={saving}
                  onClick={(event) => {
                    event.stopPropagation();
                    void moveRow(params.row, 'up');
                  }}
                >
                  <ArrowUpwardIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Move down">
              <span>
                <IconButton
                  size="small"
                  disabled={saving}
                  onClick={(event) => {
                    event.stopPropagation();
                    void moveRow(params.row, 'down');
                  }}
                >
                  <ArrowDownwardIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
            {params.row.is_archived ? (
              <Tooltip title="Restore">
                <IconButton
                  size="small"
                  onClick={(event) => {
                    event.stopPropagation();
                    void updateRow(params.row, { is_archived: false }, 'NP code restored');
                  }}
                >
                  <UnarchiveIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            ) : (
              <Tooltip title="Archive">
                <IconButton
                  size="small"
                  onClick={(event) => {
                    event.stopPropagation();
                    void updateRow(params.row, { is_archived: true }, 'NP code archived');
                  }}
                >
                  <ArchiveIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
            <TableRowActions
              onEdit={() => openEdit(params.row)}
              deleteAction={
                isAdmin ? (
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
                ) : undefined
              }
            />
          </Box>
        ),
      },
    ],
    [actionsColumnWidth, isAdmin, loadData, saving, showSuccess],
  );

  if (loading) return <LoadingState />;

  return (
    <PageContainer>
      <PageHeader
        title="Non-Productive Codes"
        subtitle="Manage NP codes used for non-productive timesheet entries"
        action={
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
            Add Code
          </ProsohmButton>
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

      <ContentCard noPadding>
        <ProsohmDataGrid
          rows={rows}
          columns={columns}
          autoHeight
          pageSizeOptions={[25, 50, 100]}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          onRowOpen={(rowId) => {
            const code = rows.find((item) => item.id === rowId);
            if (code) setSelectedCode(code);
          }}
        />
      </ContentCard>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? 'Edit NP Code' : 'New NP Code'}
        subtitle="Non-productive timesheet code"
        icon={TimerOffOutlinedIcon}
        formId="np-code-form"
        submitLabel={editing ? 'Save Changes' : 'Save'}
        loading={saving}
      >
        <Box
          component="form"
          id="np-code-form"
          onSubmit={(event) => void handleSave(event)}
          sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
        >
          <FormSection title="Code Details" icon={TimerOffOutlinedIcon}>
            <FormField
              label="Code"
              required
              value={form.code}
              onChange={(event) => setForm((prev) => ({ ...prev, code: event.target.value }))}
            />
            <FormField
              label="Description"
              value={form.description}
              onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
            />
            <FormField
              label="Sort Order"
              type="number"
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
          </FormSection>
        </Box>
      </FormDrawer>

      <RecordDetailDrawer
        open={Boolean(selectedCode)}
        onClose={() => setSelectedCode(null)}
        title={selectedCode?.code ?? 'NP Code'}
        subtitle="Non-productive code"
        icon={TimerOffOutlinedIcon}
        status={
          selectedCode ? (
            <Stack direction="row" spacing={1}>
              <Chip
                label={selectedCode.is_active ? 'Active' : 'Inactive'}
                size="small"
                color={selectedCode.is_active ? 'success' : 'default'}
              />
              {selectedCode.is_archived ? (
                <Chip label="Archived" size="small" color="warning" />
              ) : null}
            </Stack>
          ) : null
        }
        quickActions={
          selectedCode ? (
            <DrawerQuickActions>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => {
                  openEdit(selectedCode);
                  setSelectedCode(null);
                }}
              >
                Edit
              </ProsohmButton>
              {isAdmin ? (
                <AdminDeleteButton
                  mode="button"
                  resource="non-productive-codes"
                  recordId={selectedCode.id}
                  recordName={selectedCode.code}
                  showArchive
                  onDeleted={() => {
                    setSelectedCode(null);
                    void loadData();
                  }}
                  onArchive={async () => {
                    await nonProductiveCodesApi.update(selectedCode.id, { is_archived: true });
                    showSuccess('NP code archived.');
                    setSelectedCode(null);
                    await loadData();
                  }}
                  onDeactivate={async () => {
                    await nonProductiveCodesApi.update(selectedCode.id, { is_active: false });
                    showSuccess('NP code deactivated.');
                    setSelectedCode(null);
                    await loadData();
                  }}
                />
              ) : null}
            </DrawerQuickActions>
          ) : null
        }
      >
        {selectedCode ? (
          <FormSection title="Overview" icon={TimerOffOutlinedIcon}>
            <FormField label="Code" value={selectedCode.code} slotProps={{ input: { readOnly: true } }} />
            <FormField
              label="Description"
              value={formatCellValue(selectedCode.description) || '—'}
              multiline
              minRows={2}
              slotProps={{ input: { readOnly: true } }}
            />
            <FormField
              label="Sort Order"
              value={String(selectedCode.sort_order)}
              slotProps={{ input: { readOnly: true } }}
            />
          </FormSection>
        ) : null}
      </RecordDetailDrawer>
    </PageContainer>
  );
}
