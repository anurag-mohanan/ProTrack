import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  Chip,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { apiClient, getErrorMessage } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { useToast } from '../../context/ToastContext';

type HistoryPack = {
  id: string;
  title: string;
  description: string;
  template: string | null;
  columns: string[];
  href?: string | null;
  note?: string | null;
};

type ImportResult = {
  pack: string;
  dry_run: boolean;
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
  warnings: string[];
};

export default function HistoryDataImportPage() {
  const { showSuccess, showError } = useToast();
  const navigate = useNavigate();
  const [packId, setPackId] = useState('employment');
  const [file, setFile] = useState<File | null>(null);
  const [lastResult, setLastResult] = useState<ImportResult | null>(null);

  const packsQuery = useQuery({
    queryKey: ['imports', 'history-packs'],
    queryFn: async () =>
      (await apiClient.get<HistoryPack[]>('/imports/history/packs')).data,
  });

  const csvPacks = useMemo(
    () => (packsQuery.data ?? []).filter((p) => Boolean(p.template)),
    [packsQuery.data],
  );
  const linkedPacks = useMemo(
    () => (packsQuery.data ?? []).filter((p) => !p.template),
    [packsQuery.data],
  );

  const selected = csvPacks.find((p) => p.id === packId) ?? csvPacks[0];

  const runImport = useMutation({
    mutationFn: async (dryRun: boolean) => {
      if (!file || !selected) throw new Error('Select a pack and CSV file');
      const form = new FormData();
      form.append('file', file);
      form.append('dry_run', dryRun ? 'true' : 'false');
      return (
        await apiClient.post<ImportResult>(
          `/imports/history/packs/${selected.id}/import`,
          form,
          { headers: { 'Content-Type': 'multipart/form-data' } },
        )
      ).data;
    },
    onSuccess: (data) => {
      setLastResult(data);
      if (data.dry_run) {
        showSuccess(
          `Dry run: ${data.created} create / ${data.updated} update / ${data.skipped} skipped`,
        );
      } else {
        showSuccess(
          `Imported: ${data.created} created, ${data.updated} updated (${data.errors.length} errors)`,
        );
      }
    },
    onError: (error) => showError(getErrorMessage(error) || 'Import failed'),
  });

  const downloadTemplate = async () => {
    if (!selected) return;
    try {
      const response = await apiClient.get(
        `/imports/history/packs/${selected.id}/template`,
        { responseType: 'blob' },
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selected.id}_history_template.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      showError(getErrorMessage(error) || 'Could not download template');
    }
  };

  if (packsQuery.isLoading) {
    return <LoadingState message="Loading history import packs…" />;
  }

  return (
    <Stack spacing={2}>
      <PageHeader
        title="History data import"
        subtitle="Bring employment, compensation, expenses, customers, and other past records into ProTrack before go-live."
      />

      <ContentCard>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
          Linked importers
        </Typography>
        <Stack spacing={1}>
          {linkedPacks.map((pack) => (
            <Stack
              key={pack.id}
              direction={{ xs: 'column', sm: 'row' }}
              spacing={1}
              sx={{ justifyContent: 'space-between', alignItems: { sm: 'center' } }}
            >
              <Stack>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {pack.title}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {pack.description}
                  {pack.note ? ` — ${pack.note}` : ''}
                </Typography>
              </Stack>
              {pack.href ? (
                <ProsohmButton
                  size="small"
                  buttonVariant="outlined"
                  onClick={() => navigate(pack.href!)}
                >
                  Open
                </ProsohmButton>
              ) : null}
            </Stack>
          ))}
        </Stack>
      </ContentCard>

      <ContentCard>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
          CSV history packs
        </Typography>
        <Stack spacing={1.5}>
          <TextField
            select
            size="small"
            label="Pack"
            value={selected?.id ?? ''}
            onChange={(e) => {
              setPackId(e.target.value);
              setLastResult(null);
              setFile(null);
            }}
          >
            {csvPacks.map((pack) => (
              <MenuItem key={pack.id} value={pack.id}>
                {pack.title}
              </MenuItem>
            ))}
          </TextField>
          {selected ? (
            <Typography variant="body2" color="text.secondary">
              {selected.description}
              <br />
              Columns: {selected.columns.join(', ')}
            </Typography>
          ) : null}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
            <ProsohmButton size="small" buttonVariant="outlined" onClick={() => void downloadTemplate()}>
              Download template
            </ProsohmButton>
            <ProsohmButton size="small" component="label" buttonVariant="outlined">
              Choose CSV
              <input
                hidden
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </ProsohmButton>
            {file ? <Chip label={file.name} /> : null}
          </Stack>
          <Stack direction="row" spacing={1}>
            <ProsohmButton
              size="small"
              buttonVariant="outlined"
              disabled={!file || runImport.isPending}
              onClick={() => runImport.mutate(true)}
            >
              Dry run
            </ProsohmButton>
            <ProsohmButton
              size="small"
              disabled={!file || runImport.isPending}
              onClick={() => runImport.mutate(false)}
            >
              Import
            </ProsohmButton>
          </Stack>
        </Stack>
      </ContentCard>

      {lastResult ? (
        <ContentCard>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
            Last result ({lastResult.dry_run ? 'dry run' : 'committed'})
          </Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>
            Created {lastResult.created} · Updated {lastResult.updated} · Skipped{' '}
            {lastResult.skipped}
          </Typography>
          {lastResult.warnings.length ? (
            <Typography variant="body2" color="warning.main" sx={{ mb: 1 }}>
              Warnings: {lastResult.warnings.slice(0, 8).join(' | ')}
            </Typography>
          ) : null}
          {lastResult.errors.length ? (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Errors</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {lastResult.errors.slice(0, 30).map((err) => (
                  <TableRow key={err}>
                    <TableCell>{err}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <Typography variant="body2" color="success.main">
              No row errors
            </Typography>
          )}
        </ContentCard>
      ) : null}
    </Stack>
  );
}
