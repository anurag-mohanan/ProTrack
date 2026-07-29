import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Alert, Box, Chip, FormControlLabel, Switch, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import StreamOutlinedIcon from '@mui/icons-material/StreamOutlined';
import type { GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { ClientPaginatedDataGrid } from '../../components/common/ClientPaginatedDataGrid';
import { LoadingState } from '../../components/common/LoadingState';
import { AdminDeleteButton } from '../../components/admin/AdminDeleteButton';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { streamsApi } from '../../api/resources';
import type { Stream } from '../../types';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import { ContentCard } from '../../components/ui/cards';
import {
  DrawerQuickActions,
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

interface StreamFormState {
  name: string;
  description: string;
  is_active: boolean;
  use_project_prefix: boolean;
  use_project_numbering: boolean;
  project_number_prefix: string;
  project_number_format: string;
  next_project_sequence: string;
}

const emptyForm: StreamFormState = {
  name: '',
  description: '',
  is_active: true,
  use_project_prefix: false,
  use_project_numbering: false,
  project_number_prefix: '',
  project_number_format: '',
  next_project_sequence: '1',
};

function numberingSummary(stream: Stream): string {
  const parts: string[] = [];
  if (stream.use_project_prefix && stream.project_number_prefix) {
    parts.push(`Prefix ${stream.project_number_prefix}`);
  } else if (stream.use_project_prefix) {
    parts.push('Prefix on');
  }
  if (stream.use_project_numbering) {
    const fmt = stream.project_number_format?.trim() || 'auto seq';
    parts.push(`Numbering (${fmt})`);
  }
  return parts.length ? parts.join(' · ') : 'Customer numbers';
}

function previewCode(form: StreamFormState): string | null {
  if (!form.use_project_prefix && !form.use_project_numbering) return null;
  const prefix = form.use_project_prefix ? form.project_number_prefix.trim() : '';
  const seq = form.next_project_sequence.trim() || '1';
  if (form.use_project_numbering) {
    const fmt =
      form.project_number_format.trim() || (prefix ? '{prefix}-{seq}' : '{seq}');
    return fmt
      .replaceAll('{prefix}', prefix)
      .replaceAll('{seq}', seq)
      .replaceAll('{tool_number}', 'TOOL-001')
      .replaceAll('{year}', String(new Date().getFullYear()))
      .replaceAll('--', '-')
      .replace(/^-+|-+$/g, '');
  }
  if (prefix) return `${prefix}-TOOL-001`;
  return null;
}

export default function StreamsPage() {
  const { user } = useAuth();
  const isAdmin = canDeleteRecords(user?.role_name ?? '');
  const { showSuccess, showError } = useToast();
  const [streams, setStreams] = useState<Stream[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [selectedStream, setSelectedStream] = useState<Stream | null>(null);
  const [editingStream, setEditingStream] = useState<Stream | null>(null);
  const [form, setForm] = useState<StreamFormState>(emptyForm);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      setStreams(await streamsApi.list({ limit: 500 }));
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
      const haystack = [
        stream.name,
        stream.description ?? '',
        stream.project_number_prefix ?? '',
        stream.project_number_format ?? '',
      ]
        .join(' ')
        .toLowerCase();
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
      use_project_prefix: Boolean(stream.use_project_prefix),
      use_project_numbering: Boolean(stream.use_project_numbering),
      project_number_prefix: stream.project_number_prefix ?? '',
      project_number_format: stream.project_number_format ?? '',
      next_project_sequence: String(stream.next_project_sequence ?? 1),
    });
    setFormOpen(true);
  };

  const handleSave = async (event?: FormEvent) => {
    event?.preventDefault();
    const validationError = validateRequiredFields(form, [{ key: 'name', label: 'Name' }]);
    if (validationError) {
      showError(validationError);
      return;
    }
    if (form.use_project_prefix && !form.project_number_prefix.trim()) {
      showError('Enter a project code prefix, or turn off the prefix option.');
      return;
    }
    const sequence = Number.parseInt(form.next_project_sequence, 10);
    if (form.use_project_numbering && (!Number.isFinite(sequence) || sequence < 1)) {
      showError('Next sequence must be a whole number of 1 or higher.');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        description: optionalString(form.description),
        is_active: form.is_active,
        use_project_prefix: form.use_project_prefix,
        use_project_numbering: form.use_project_numbering,
        project_number_prefix: form.use_project_prefix
          ? optionalString(form.project_number_prefix)
          : null,
        project_number_format: form.use_project_numbering
          ? optionalString(form.project_number_format)
          : null,
        next_project_sequence: form.use_project_numbering
          ? sequence
          : editingStream?.next_project_sequence ?? 1,
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

  const sampleCode = previewCode(form);

  const columns: GridColDef<Stream>[] = [
    { field: 'name', headerName: 'Name', flex: 1.2, minWidth: 140 },
    {
      field: 'description',
      headerName: 'Description',
      flex: 1.6,
      minWidth: 160,
      valueFormatter: (value) => formatCellValue(value as string | null),
    },
    {
      field: 'project_number_prefix',
      headerName: 'Project codes',
      flex: 1.2,
      minWidth: 160,
      valueGetter: (_value, row) => numberingSummary(row),
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
      headerName: '',
      width: isAdmin ? DATA_GRID_ACTIONS_COLUMN_WIDTH + 40 : DATA_GRID_ACTIONS_COLUMN_WIDTH,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <TableRowActions
          onEdit={() => openEdit(params.row)}
          deleteAction={
            isAdmin ? (
              <AdminDeleteButton
                resource="streams"
                recordId={params.row.id}
                recordName={params.row.name}
                onDeleted={() => void loadData()}
                onDeactivate={async () => {
                  await streamsApi.update(params.row.id, { is_active: false });
                  showSuccess('Stream deactivated.');
                  await loadData();
                }}
              />
            ) : undefined
          }
        />
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading streams…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Streams"
        subtitle="Manage engineering streams"
        action={
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
            Create Stream
          </ProsohmButton>
        }
      />

      <SearchToolbar>
        <FormField
          label="Search by name or description"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, flex: 1, maxWidth: 480 }}
        />
      </SearchToolbar>

      <ContentCard noPadding>
        <ClientPaginatedDataGrid
          rows={filteredStreams}
          columns={columns}
          autoHeight
          filterKey={search}
          onRowOpen={(rowId) => {
            const stream = filteredStreams.find((item) => item.id === rowId);
            if (stream) setSelectedStream(stream);
          }}
        />
      </ContentCard>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingStream ? 'Edit Stream' : 'Create Stream'}
        subtitle="Engineering stream configuration"
        icon={StreamOutlinedIcon}
        formId="stream-form"
        submitLabel={editingStream ? 'Save Changes' : 'Create Stream'}
        loading={saving}
      >
        <Box
          component="form"
          id="stream-form"
          onSubmit={(event) => void handleSave(event)}
          sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
        >
          <FormSection title="Stream Details" icon={StreamOutlinedIcon}>
            <FormField
              label="Name"
              required
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
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

          <FormSection title="Project numbering (optional)" icon={StreamOutlinedIcon}>
            <Alert severity="info" sx={{ mb: 1 }}>
              Leave these off when projects use customer-supplied project numbers. Turn them on only
              when this stream should assign ProTrack prefixes and/or automatic numbers.
            </Alert>
            <FormControlLabel
              control={
                <Switch
                  checked={form.use_project_prefix}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      use_project_prefix: event.target.checked,
                    }))
                  }
                />
              }
              label="Add a project code prefix for this stream?"
            />
            {form.use_project_prefix ? (
              <FormField
                label="Prefix"
                required
                value={form.project_number_prefix}
                helper="Example: MD, FIX, CAM"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    project_number_prefix: event.target.value,
                  }))
                }
              />
            ) : null}
            <FormControlLabel
              control={
                <Switch
                  checked={form.use_project_numbering}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      use_project_numbering: event.target.checked,
                    }))
                  }
                />
              }
              label="Add an automatic numbering system for this stream?"
            />
            {form.use_project_numbering ? (
              <>
                <FormField
                  label="Number format"
                  value={form.project_number_format}
                  helper="Use {prefix}, {seq}, {tool_number}, {year}. Leave blank for {prefix}-{seq} or {seq}."
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      project_number_format: event.target.value,
                    }))
                  }
                />
                <FormField
                  label="Next sequence number"
                  type="number"
                  value={form.next_project_sequence}
                  helper="Used for the next auto-numbered project on this stream."
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      next_project_sequence: event.target.value,
                    }))
                  }
                />
              </>
            ) : null}
            {sampleCode ? (
              <Typography variant="body2" color="text.secondary">
                Example next code: <strong>{sampleCode}</strong>
              </Typography>
            ) : null}
          </FormSection>
        </Box>
      </FormDrawer>

      <RecordDetailDrawer
        open={Boolean(selectedStream)}
        onClose={() => setSelectedStream(null)}
        title={selectedStream?.name ?? 'Stream'}
        subtitle="Engineering stream"
        icon={StreamOutlinedIcon}
        status={
          selectedStream ? (
            <Chip
              label={selectedStream.is_active ? 'Active' : 'Inactive'}
              size="small"
              color={selectedStream.is_active ? 'success' : 'default'}
            />
          ) : null
        }
        quickActions={
          selectedStream ? (
            <DrawerQuickActions>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => {
                  openEdit(selectedStream);
                  setSelectedStream(null);
                }}
              >
                Edit
              </ProsohmButton>
              {isAdmin ? (
                <AdminDeleteButton
                  mode="button"
                  resource="streams"
                  recordId={selectedStream.id}
                  recordName={selectedStream.name}
                  onDeleted={() => {
                    setSelectedStream(null);
                    void loadData();
                  }}
                  onDeactivate={async () => {
                    await streamsApi.update(selectedStream.id, { is_active: false });
                    showSuccess('Stream deactivated.');
                    setSelectedStream(null);
                    await loadData();
                  }}
                />
              ) : null}
            </DrawerQuickActions>
          ) : null
        }
      >
        {selectedStream ? (
          <FormSection title="Overview" icon={StreamOutlinedIcon}>
            <FormField label="Name" value={selectedStream.name} slotProps={{ input: { readOnly: true } }} />
            <FormField
              label="Description"
              value={formatCellValue(selectedStream.description) || '—'}
              multiline
              minRows={2}
              slotProps={{ input: { readOnly: true } }}
            />
            <FormField
              label="Project codes"
              value={numberingSummary(selectedStream)}
              slotProps={{ input: { readOnly: true } }}
            />
          </FormSection>
        ) : null}
      </RecordDetailDrawer>
    </PageContainer>
  );
}
