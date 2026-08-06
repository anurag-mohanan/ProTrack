import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Alert, Box, Chip, FormControlLabel, Switch, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import type { GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { ClientPaginatedDataGrid } from '../../components/common/ClientPaginatedDataGrid';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { workstreamsApi } from '../../api/resources';
import type { Workstream } from '../../types';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import { ContentCard } from '../../components/ui/cards';
import {
  FormDrawer,
  FormField,
  FormSection,
  RecordDetailDrawer,
  SearchToolbar,
  TableRowActions,
} from '../../components/ui/design-system';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { formatCellValue } from '../../utils/format';
import { optionalString, validateRequiredFields } from '../../utils/formValues';
import { canDeleteRecords } from '../../utils/permissions';
import { useAuth } from '../../context/AuthContext';
import { DATA_GRID_ACTIONS_COLUMN_WIDTH } from '../../theme/componentStyles';

interface WorkstreamFormState {
  name: string;
  code: string;
  description: string;
  icon: string;
  color: string;
  display_order: string;
  is_active: boolean;
}

const emptyForm: WorkstreamFormState = {
  name: '',
  code: '',
  description: '',
  icon: '',
  color: '',
  display_order: '0',
  is_active: true,
};

export default function WorkstreamsPage() {
  const { user } = useAuth();
  const isAdmin = canDeleteRecords(user?.role_name ?? '');
  const { showSuccess, showError } = useToast();
  const [rows, setRows] = useState<Workstream[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [selected, setSelected] = useState<Workstream | null>(null);
  const [editing, setEditing] = useState<Workstream | null>(null);
  const [form, setForm] = useState<WorkstreamFormState>(emptyForm);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await workstreamsApi.list({ limit: 500 }));
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const openCreate = useCallback(() => {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }, []);

  useOpenCreateFromQuery(openCreate);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return rows;
    return rows.filter((row) => {
      return (
        row.name.toLowerCase().includes(term) ||
        (row.code ?? '').toLowerCase().includes(term) ||
        (row.description ?? '').toLowerCase().includes(term)
      );
    });
  }, [rows, search]);

  const openEdit = (row: Workstream) => {
    setEditing(row);
    setForm({
      name: row.name,
      code: row.code ?? '',
      description: row.description ?? '',
      icon: row.icon ?? '',
      color: row.color ?? '',
      display_order: String(row.display_order ?? 0),
      is_active: row.is_active,
    });
    setFormOpen(true);
  };

  const handleSave = async (event: FormEvent) => {
    event.preventDefault();
    const missing = validateRequiredFields(form, [{ key: 'name', label: 'Name' }]);
    if (missing) {
      showError(missing);
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        code: optionalString(form.code),
        description: optionalString(form.description),
        icon: optionalString(form.icon),
        color: optionalString(form.color),
        display_order: Number(form.display_order) || 0,
        is_active: form.is_active,
      };
      if (editing) {
        await workstreamsApi.update(editing.id, payload);
        showSuccess('Workstream updated');
      } else {
        await workstreamsApi.create(payload);
        showSuccess('Workstream created');
      }
      setFormOpen(false);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const columns: GridColDef[] = [
    { field: 'name', headerName: 'Name', flex: 1, minWidth: 160 },
    { field: 'code', headerName: 'Code', width: 110 },
    {
      field: 'color',
      headerName: 'Color',
      width: 90,
      renderCell: (params) =>
        params.value ? (
          <Box
            sx={{
              width: 18,
              height: 18,
              borderRadius: '4px',
              bgcolor: String(params.value),
              border: '1px solid',
              borderColor: 'divider',
            }}
          />
        ) : (
          '—'
        ),
    },
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
    { field: 'display_order', headerName: 'Order', width: 90 },
    {
      field: 'actions',
      headerName: '',
      width: DATA_GRID_ACTIONS_COLUMN_WIDTH,
      sortable: false,
      renderCell: (params) => {
        const row = filtered.find((item) => item.id === params.id);
        if (!row) return null;
        return (
          <TableRowActions
            onEdit={() => openEdit(row)}
            deleteAction={
              isAdmin && row.is_active ? (
                <ProsohmButton
                  buttonVariant="secondary"
                  size="small"
                  onClick={async (event) => {
                    event.stopPropagation();
                    try {
                      await workstreamsApi.update(row.id, { is_active: false });
                      showSuccess('Workstream deactivated');
                      await loadData();
                    } catch (error) {
                      showError(getErrorMessage(error));
                    }
                  }}
                >
                  Deactivate
                </ProsohmButton>
              ) : undefined
            }
          />
        );
      },
    },
  ];

  if (loading) return <LoadingState message="Loading workstreams…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Workstreams"
        subtitle="Configure section order, visibility, icons, and colors for the Projects Command Center."
        action={
          isAdmin ? (
            <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
              Add workstream
            </ProsohmButton>
          ) : undefined
        }
      />

      <SearchToolbar>
        <FormField
          label="Search workstreams"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, flex: 1, maxWidth: 480 }}
        />
      </SearchToolbar>

      <ContentCard noPadding>
        <ClientPaginatedDataGrid
          rows={filtered}
          columns={columns}
          autoHeight
          filterKey={search}
          onRowOpen={(rowId) => {
            const row = filtered.find((item) => item.id === rowId);
            if (row) setSelected(row);
          }}
        />
      </ContentCard>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? 'Edit workstream' : 'New workstream'}
        subtitle="Configurable delivery taxonomy"
        icon={AccountTreeOutlinedIcon}
        formId="workstream-form"
        submitLabel={editing ? 'Save Changes' : 'Create Workstream'}
        loading={saving}
      >
        <Box
          component="form"
          id="workstream-form"
          onSubmit={(event) => void handleSave(event)}
          sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
        >
          <FormSection title="Details" icon={AccountTreeOutlinedIcon}>
            <FormField
              label="Name"
              required
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
            <FormField
              label="Code"
              value={form.code}
              onChange={(event) => setForm((current) => ({ ...current, code: event.target.value }))}
            />
            <FormField
              label="Description"
              value={form.description}
              onChange={(event) =>
                setForm((current) => ({ ...current, description: event.target.value }))
              }
              multiline
              minRows={3}
            />
            <FormField
              label="Icon key"
              value={form.icon}
              helper="Optional: mold, fixture, cad, change, product, concept, validation"
              onChange={(event) => setForm((current) => ({ ...current, icon: event.target.value }))}
            />
            <FormField
              label="Accent color"
              value={form.color}
              helper="Hex color for section chrome, e.g. #0d9488"
              onChange={(event) => setForm((current) => ({ ...current, color: event.target.value }))}
            />
            <FormField
              label="Display order"
              type="number"
              value={form.display_order}
              helper="Lower numbers appear first on the Projects Command Center"
              onChange={(event) =>
                setForm((current) => ({ ...current, display_order: event.target.value }))
              }
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
          </FormSection>
        </Box>
      </FormDrawer>

      <RecordDetailDrawer
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected?.name ?? 'Workstream'}
        subtitle="Workstream"
      >
        {selected ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            <Typography variant="body2">Code: {formatCellValue(selected.code)}</Typography>
            <Typography variant="body2">{formatCellValue(selected.description)}</Typography>
            {!selected.is_active ? (
              <Alert severity="info">Inactive workstreams are hidden from Projects sections.</Alert>
            ) : null}
            {isAdmin ? (
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
                <ProsohmButton
                  buttonVariant="secondary"
                  onClick={() => {
                    openEdit(selected);
                    setSelected(null);
                  }}
                >
                  Edit
                </ProsohmButton>
                {selected.is_active ? (
                  <ProsohmButton
                    buttonVariant="secondary"
                    onClick={async () => {
                      try {
                        await workstreamsApi.update(selected.id, { is_active: false });
                        showSuccess('Workstream deactivated');
                        setSelected(null);
                        await loadData();
                      } catch (error) {
                        showError(getErrorMessage(error));
                      }
                    }}
                  >
                    Deactivate
                  </ProsohmButton>
                ) : (
                  <ProsohmButton
                    buttonVariant="primary"
                    onClick={async () => {
                      try {
                        await workstreamsApi.update(selected.id, { is_active: true });
                        showSuccess('Workstream activated');
                        setSelected(null);
                        await loadData();
                      } catch (error) {
                        showError(getErrorMessage(error));
                      }
                    }}
                  >
                    Activate
                  </ProsohmButton>
                )}
              </Box>
            ) : null}
          </Box>
        ) : null}
      </RecordDetailDrawer>
    </PageContainer>
  );
}
