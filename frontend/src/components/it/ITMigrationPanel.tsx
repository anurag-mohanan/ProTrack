import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Checkbox,
  FormControlLabel,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import CloudUploadRoundedIcon from '@mui/icons-material/CloudUploadRounded';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  analyzeItMigration,
  commitItMigration,
  fetchMigrationSourceTypes,
  type ITMigrationAnalyzeResult,
  type ITMigrationImportResult,
} from '../../api/itOperations';
import { getErrorMessage } from '../../api/client';
import { ContentCard } from '../ui/cards';
import { ProsohmButton } from '../ui/ProsohmButton';
import { FormSelect } from '../ui/design-system';
import { useToast } from '../../context/ToastContext';

export function ITMigrationPanel() {
  const { showSuccess, showError } = useToast();
  const [sourceType, setSourceType] = useState('hardware');
  const [file, setFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<ITMigrationAnalyzeResult | null>(null);
  const [importResult, setImportResult] = useState<ITMigrationImportResult | null>(null);
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [confirmed, setConfirmed] = useState(false);

  const sourcesQuery = useQuery({
    queryKey: ['it', 'migration', 'source-types'],
    queryFn: fetchMigrationSourceTypes,
  });

  const sourceOptions = useMemo(
    () =>
      (sourcesQuery.data ?? []).map((s) => ({
        value: s.id,
        label: s.label,
      })),
    [sourcesQuery.data],
  );

  const selectedMeta = sourcesQuery.data?.find((s) => s.id === sourceType);

  const analyzeMutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('Choose an Excel file first.');
      return analyzeItMigration(sourceType, file);
    },
    onSuccess: (data) => {
      setAnalysis(data);
      setImportResult(null);
      setConfirmed(false);
      showSuccess('Analysis complete — review before importing.');
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const importMutation = useMutation({
    mutationFn: async () => {
      if (!analysis?.session_id) throw new Error('Run Analyze first.');
      if (!confirmed) throw new Error('Confirm the import checkbox first.');
      return commitItMigration({
        session_id: analysis.session_id,
        confirm: true,
        skip_duplicates: skipDuplicates,
      });
    },
    onSuccess: (data) => {
      setImportResult(data);
      showSuccess(data.message || 'Import committed.');
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  return (
    <ContentCard title="Data Migration">
      <Stack spacing={2.5}>
        <Alert severity="warning">
          Spreadsheet passwords, TeamViewer credentials, and Windows license keys are never
          imported, previewed, logged, or stored. Account rows are marked Migration Required for
          secure reset later.
        </Alert>

        <FormSelect
          label="Source"
          value={sourceType}
          onChange={(event) => {
            setSourceType(String(event.target.value));
            setAnalysis(null);
            setImportResult(null);
          }}
          options={sourceOptions.length ? sourceOptions : [{ value: 'hardware', label: 'Hardware' }]}
          sx={{ maxWidth: 420 }}
        />
        {selectedMeta ? (
          <Typography variant="body2" color="text.secondary">
            {selectedMeta.description} Sheet hint: <strong>{selectedMeta.sheet_hint}</strong>
          </Typography>
        ) : null}

        <Box>
          <ProsohmButton
            component="label"
            buttonVariant="outlined"
            startIcon={<CloudUploadRoundedIcon />}
          >
            {file ? file.name : 'Choose .xlsx file'}
            <input
              hidden
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => {
                const next = event.target.files?.[0] ?? null;
                setFile(next);
                setAnalysis(null);
                setImportResult(null);
              }}
            />
          </ProsohmButton>
        </Box>

        <Stack direction="row" spacing={1.5}>
          <ProsohmButton
            buttonVariant="primary"
            loading={analyzeMutation.isPending}
            disabled={!file}
            onClick={() => analyzeMutation.mutate()}
          >
            Analyze
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="outlined"
            loading={importMutation.isPending}
            disabled={!analysis || !confirmed}
            onClick={() => importMutation.mutate()}
          >
            Confirm import
          </ProsohmButton>
        </Stack>

        {analysis ? (
          <Stack spacing={2}>
            <Alert severity="info">{analysis.message}</Alert>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ flexWrap: 'wrap' }}>
              <Stat label="Records found" value={analysis.records_found} />
              <Stat label="New" value={analysis.new_records} />
              <Stat label="Duplicates" value={analysis.potential_duplicates} />
              <Stat label="Needs review" value={analysis.requires_review} />
              <Stat
                label="Secret columns excluded"
                value={analysis.sensitive_data_excluded_count}
              />
            </Stack>

            {analysis.sensitive_columns_excluded.length > 0 ? (
              <Alert severity="success">
                Excluded sensitive columns: {analysis.sensitive_columns_excluded.join(', ')}
              </Alert>
            ) : null}

            <FormControlLabel
              control={
                <Checkbox
                  checked={skipDuplicates}
                  onChange={(e) => setSkipDuplicates(e.target.checked)}
                />
              }
              label="Skip strong duplicates (do not overwrite existing assets)"
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />
              }
              label="I reviewed the preview, exceptions, and duplicates — commit this import"
            />

            {analysis.exceptions.length > 0 ? (
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Exceptions (first {analysis.exceptions.length})
                </Typography>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>ID</TableCell>
                      <TableCell>Severity</TableCell>
                      <TableCell>Code</TableCell>
                      <TableCell>Detail</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {analysis.exceptions.slice(0, 25).map((row) => (
                      <TableRow key={String(row.id)}>
                        <TableCell>{String(row.id)}</TableCell>
                        <TableCell>{String(row.severity)}</TableCell>
                        <TableCell>{String(row.code)}</TableCell>
                        <TableCell>{String(row.detail)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            ) : null}

            {analysis.preview_rows.length > 0 ? (
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Preview (sanitized — no secrets)
                </Typography>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      {Object.keys(analysis.preview_rows[0])
                        .slice(0, 8)
                        .map((key) => (
                          <TableCell key={key}>{key}</TableCell>
                        ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {analysis.preview_rows.slice(0, 8).map((row, index) => (
                      <TableRow key={index}>
                        {Object.keys(analysis.preview_rows[0])
                          .slice(0, 8)
                          .map((key) => (
                            <TableCell key={key}>{row[key] || '—'}</TableCell>
                          ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            ) : null}
          </Stack>
        ) : null}

        {importResult ? (
          <Alert severity="success">
            Imported {importResult.imported}, skipped {importResult.skipped}, duplicated{' '}
            {importResult.duplicated}. Organization-owned {importResult.organization_owned},
            customer-owned {importResult.customer_owned}. Secrets excluded:{' '}
            {importResult.sensitive_data_excluded}.
            {importResult.errors.length
              ? ` Errors: ${importResult.errors.slice(0, 3).join('; ')}`
              : ''}
          </Alert>
        ) : null}
      </Stack>
    </ContentCard>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Box
      sx={{
        minWidth: 120,
        px: 1.5,
        py: 1,
        borderRadius: 1,
        bgcolor: 'action.hover',
      }}
    >
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="h6">{value}</Typography>
    </Box>
  );
}
