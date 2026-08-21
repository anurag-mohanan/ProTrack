import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
  Chip,
} from '@mui/material';
import CloudUploadRoundedIcon from '@mui/icons-material/CloudUploadRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  analyzeItDataImport,
  commitItDataImport,
  executeItReset,
  fetchItDataImportBatches,
  fetchItDataImportTypes,
  fetchItResetPreview,
  rollbackItDataImport,
  type ITDataImportAnalyzeResult,
  type ITDataImportCommitResult,
  type ITDataImportTypeStatus,
} from '../../api/itOperations';
import { getErrorMessage } from '../../api/client';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingState } from '../../components/common/LoadingState';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { FormField, FormSelect } from '../../components/ui/design-system';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import {
  accessContextFromUser,
  canManageItDataImports,
  ROLES,
} from '../../utils/permissions';

function statusLabel(status: string): string {
  if (status === 'imported') return 'Imported';
  if (status === 'review_only') return 'Review Only';
  if (status.startsWith('waiting_for_')) {
    const dep = status.replace('waiting_for_', '').replace(/_/g, ' ');
    return `Waiting for ${dep}`;
  }
  return 'Not Imported';
}

function statusColor(status: string): 'success' | 'warning' | 'default' | 'info' {
  if (status === 'imported') return 'success';
  if (status.startsWith('waiting_for_')) return 'warning';
  if (status === 'review_only') return 'info';
  return 'default';
}

function nextRecommended(types: ITDataImportTypeStatus[]): ITDataImportTypeStatus | null {
  return (
    types.find((t) => !t.review_only && t.status !== 'imported') ??
    types.find((t) => t.review_only && t.status !== 'imported') ??
    null
  );
}

export function ITDataImportPage() {
  const { user } = useAuth();
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const ctx = accessContextFromUser(user);
  const allowed = canManageItDataImports(ctx);
  const isAdmin = ctx.role_name === ROLES.ADMIN;

  const [importType, setImportType] = useState('assets');
  const [file, setFile] = useState<File | null>(null);
  const [sheetOverride, setSheetOverride] = useState('');
  const [analysis, setAnalysis] = useState<ITDataImportAnalyzeResult | null>(null);
  const [commitResult, setCommitResult] = useState<ITDataImportCommitResult | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [depDialogOpen, setDepDialogOpen] = useState(false);
  const [pendingAnalyze, setPendingAnalyze] = useState(false);
  const [rollbackId, setRollbackId] = useState<string | null>(null);
  const [resetPhrase, setResetPhrase] = useState('');
  const [resetConfirm, setResetConfirm] = useState(false);

  const typesQuery = useQuery({
    queryKey: ['it', 'data-import', 'types'],
    queryFn: fetchItDataImportTypes,
    enabled: allowed,
  });

  const historyQuery = useQuery({
    queryKey: ['it', 'data-import', 'batches'],
    queryFn: () => fetchItDataImportBatches(),
    enabled: allowed,
  });

  const resetPreviewQuery = useQuery({
    queryKey: ['it', 'reset-preview'],
    queryFn: fetchItResetPreview,
    enabled: isAdmin,
  });

  const resetMutation = useMutation({
    mutationFn: () =>
      executeItReset({ confirmation_phrase: resetPhrase, confirm: resetConfirm }),
    onSuccess: (data) => {
      showSuccess(data.message || 'IT data reset complete.');
      setResetPhrase('');
      setResetConfirm(false);
      void queryClient.invalidateQueries({ queryKey: ['it'] });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const typeOptions = useMemo(
    () =>
      (typesQuery.data ?? []).map((t) => ({
        value: t.id,
        label: `${t.recommended_order}. ${t.label}`,
      })),
    [typesQuery.data],
  );

  const selectedMeta = typesQuery.data?.find((t) => t.id === importType);
  const nextType = nextRecommended(typesQuery.data ?? []);

  const runAnalyze = async () => {
    if (!file) throw new Error('Choose an Excel file first.');
    return analyzeItDataImport(importType, file, sheetOverride || null);
  };

  const analyzeMutation = useMutation({
    mutationFn: runAnalyze,
    onSuccess: (data) => {
      setAnalysis(data);
      setCommitResult(null);
      setConfirmed(false);
      if (data.other_sheets.length && !sheetOverride) {
        setSheetOverride('');
      }
      showSuccess('Workbook analyzed — review mapping and first 10 records before commit.');
      void queryClient.invalidateQueries({ queryKey: ['it', 'data-import'] });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const commitMutation = useMutation({
    mutationFn: async () => {
      if (!analysis?.batch_id) throw new Error('Analyze first.');
      if (!confirmed) throw new Error('Confirm the import checkbox first.');
      if (!analysis.commit_allowed || analysis.block_commit) {
        throw new Error('Commit is blocked until mapping/fidelity issues are fixed.');
      }
      return commitItDataImport({
        batch_id: analysis.batch_id,
        confirm: true,
        skip_duplicates: skipDuplicates,
      });
    },
    onSuccess: (data) => {
      setCommitResult(data);
      showSuccess(data.message || 'Import committed.');
      void queryClient.invalidateQueries({ queryKey: ['it', 'data-import'] });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const rollbackMutation = useMutation({
    mutationFn: async (batchId: string) =>
      rollbackItDataImport({ batch_id: batchId, confirm: true }),
    onSuccess: (data) => {
      setRollbackId(null);
      showSuccess(data.message || 'Batch rolled back.');
      void queryClient.invalidateQueries({ queryKey: ['it', 'data-import'] });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const onAnalyzeClick = () => {
    if (!file) {
      showError('Choose an Excel file first.');
      return;
    }
    const deps = selectedMeta?.depends_on ?? [];
    const missing = deps.filter((dep) => {
      const row = typesQuery.data?.find((t) => t.id === dep);
      return !row || row.status !== 'imported';
    });
    if (missing.length) {
      setPendingAnalyze(true);
      setDepDialogOpen(true);
      return;
    }
    analyzeMutation.mutate();
  };

  if (!allowed) {
    return (
      <PageContainer>
        <ErrorState error={new Error('Manage IT Data Imports permission is required.')} title="Access denied" />
      </PageContainer>
    );
  }

  if (typesQuery.isLoading) {
    return (
      <PageContainer>
        <LoadingState message="Loading IT Data Import…" />
      </PageContainer>
    );
  }

  const previewCols = analysis
    ? [
        'asset_number',
        'external_id',
        'name',
        'description',
        'asset_type',
        'ownership_type',
        'owner_customer',
        'customer_used_for',
        'assigned_to',
        'serial_number',
        'current_status',
        'computer_name',
        'ip_address',
        'item_name',
        'software_name',
        'employee_name',
        'supplier_name',
        'identifier',
        '_action',
      ].filter((key) => analysis.first_10_records.some((row) => row[key] != null && row[key] !== ''))
    : [];

  return (
    <PageContainer>
      <PageHeader subtitle="Import one split workbook at a time. Preview and confirm before every commit." />

      <Stack spacing={2.5}>
        {isAdmin && resetPreviewQuery.data && (
          <ContentCard title="IT operational data reset (Admin)">
            <Alert severity="error" sx={{ mb: 2 }}>
              Permanently removes all current IT operational records (assets, computers,
              inventory, IPs, software, IT accounts, import batches). Does NOT delete
              employees, users, teams, customers, projects, timesheets, roles, asset types,
              or IT settings.
            </Alert>
            <Typography variant="body2" sx={{ mb: 1 }}>
              Operational rows to delete:{' '}
              <strong>{resetPreviewQuery.data.total_operational_records}</strong> · Session
              files: {resetPreviewQuery.data.session_cache_files} · Employees preserved:{' '}
              {resetPreviewQuery.data.will_not_delete.employees_users}
            </Typography>
            <FormControlLabel
              control={
                <Checkbox
                  checked={resetConfirm}
                  onChange={(e) => setResetConfirm(e.target.checked)}
                />
              }
              label="I understand this permanently deletes IT operational data."
            />
            <FormField
              label={`Type ${resetPreviewQuery.data.confirm_phrase} to confirm`}
              value={resetPhrase}
              onChange={(e) => setResetPhrase(e.target.value)}
              sx={{ maxWidth: 360, my: 1 }}
            />
            <ProsohmButton
              buttonVariant="danger"
              disabled={
                !resetConfirm ||
                resetPhrase !== resetPreviewQuery.data.confirm_phrase ||
                resetMutation.isPending
              }
              onClick={() => resetMutation.mutate()}
            >
              {resetMutation.isPending ? 'Resetting…' : 'RESET IT DATA'}
            </ProsohmButton>
          </ContentCard>
        )}

        <Alert severity="info">
          Recommended order: Assets → Computers → IP Addresses → Inventory → Software → User
          Accounts → Suppliers. Migration Exceptions are review-only. Passwords are never
          imported.
        </Alert>

        <ContentCard title="Migration checklist">
          <Stack spacing={1}>
            {(typesQuery.data ?? []).map((t) => (
              <Stack
                key={t.id}
                direction="row"
                sx={{
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  py: 0.5,
                  borderBottom: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <Box>
                  <Typography sx={{ fontWeight: 600 }}>
                    {t.status === 'imported' ? '✓ ' : '○ '}
                    {t.label}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Expected file: {t.expected_filename} · Sheet: {t.canonical_sheet}
                  </Typography>
                </Box>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                  {t.status === 'imported' && (
                    <Typography variant="body2">{t.success_count} records</Typography>
                  )}
                  <Chip size="small" label={statusLabel(t.status)} color={statusColor(t.status)} />
                </Stack>
              </Stack>
            ))}
          </Stack>
          {nextType && (
            <Alert severity="success" sx={{ mt: 2 }}>
              Next recommended import: <strong>{nextType.label}</strong> (
              {nextType.expected_filename})
            </Alert>
          )}
        </ContentCard>

        <ContentCard title="Import one file">
          <Stack spacing={2}>
            <FormSelect
              label="Import type"
              value={importType}
              onChange={(event) => {
                setImportType(String(event.target.value));
                setAnalysis(null);
                setCommitResult(null);
                setConfirmed(false);
                setSheetOverride('');
                setFile(null);
              }}
              options={typeOptions}
            />

            {selectedMeta && (
              <Typography variant="body2" color="text.secondary">
                Expected file: <strong>{selectedMeta.expected_filename}</strong>
                {selectedMeta.review_only ? ' · Review only (not asset data)' : null}
              </Typography>
            )}

            <ProsohmButton component="label" buttonVariant="outlined" startIcon={<CloudUploadRoundedIcon />}>
              {file ? file.name : 'Select Excel file'}
              <input
                hidden
                type="file"
                accept=".xlsx,.xlsm"
                onChange={(event) => {
                  const next = event.target.files?.[0] ?? null;
                  setFile(next);
                  setAnalysis(null);
                  setCommitResult(null);
                  setConfirmed(false);
                }}
              />
            </ProsohmButton>

            {analysis && analysis.other_sheets.length > 0 && (
              <FormSelect
                label="Data sheet (canonical recommended)"
                value={sheetOverride || analysis.sheet_name}
                onChange={(event) => setSheetOverride(String(event.target.value))}
                options={[
                  { value: analysis.canonical_sheet || analysis.sheet_name, label: `${analysis.canonical_sheet || analysis.sheet_name} (recommended)` },
                  ...analysis.other_sheets
                    .filter((s) => s !== analysis.sheet_name && s !== 'README')
                    .map((s) => ({ value: s, label: s })),
                ]}
                helper="Re-run Analyze after changing the sheet. Compat sheets are never selected by default."
              />
            )}

            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <ProsohmButton
                onClick={onAnalyzeClick}
                disabled={!file || analyzeMutation.isPending}
              >
                {analyzeMutation.isPending ? 'Analyzing…' : 'Inspect & Preview'}
              </ProsohmButton>
              {sheetOverride && sheetOverride !== analysis?.sheet_name && (
                <ProsohmButton
                  buttonVariant="outlined"
                  onClick={() => analyzeMutation.mutate()}
                  disabled={!file || analyzeMutation.isPending}
                >
                  Re-analyze selected sheet
                </ProsohmButton>
              )}
            </Stack>
          </Stack>
        </ContentCard>

        {analysis && (
          <ContentCard title={`${selectedMeta?.label ?? 'Import'} preview`}>
            <Stack spacing={2}>
              {analysis.dependency_warnings.map((w) => (
                <Alert key={w} severity="warning">
                  {w}
                </Alert>
              ))}
              {analysis.fidelity_note && (
                <Alert severity={analysis.block_commit ? 'error' : 'info'}>
                  {analysis.fidelity_note}
                </Alert>
              )}
              <Typography>
                File: <strong>{analysis.filename}</strong> · Sheet:{' '}
                <strong>{analysis.sheet_name}</strong> · Batch:{' '}
                <strong>{analysis.batch_code}</strong>
              </Typography>
              <Typography variant="body2">
                Records: {analysis.stats.records_found ?? 0} · Importable:{' '}
                {analysis.stats.importable ?? 0} · Duplicates: {analysis.stats.duplicates ?? 0} ·
                Errors: {analysis.stats.errors ?? 0} · Warnings: {analysis.stats.warnings ?? 0} ·
                Review: {analysis.stats.reviews ?? 0}
              </Typography>

              <Typography sx={{ fontWeight: 600 }}>Column mapping</Typography>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>ProTrack field</TableCell>
                    <TableCell>Source column</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {Object.entries(analysis.column_bindings).map(([field, source]) => (
                    <TableRow key={field}>
                      <TableCell>{field}</TableCell>
                      <TableCell>{source || '— unmapped —'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {analysis.unmapped_columns.length > 0 && (
                <Alert severity="info">
                  Unmapped columns (preserved in session metadata where applicable):{' '}
                  {analysis.unmapped_columns.join(', ')}
                </Alert>
              )}

              <Typography sx={{ fontWeight: 600 }}>First 10 records (critical fidelity check)</Typography>
              <Box sx={{ overflowX: 'auto' }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      {previewCols.map((c) => (
                        <TableCell key={c}>{c}</TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {analysis.first_10_records.map((row, idx) => (
                      <TableRow key={idx}>
                        {previewCols.map((c) => (
                          <TableCell key={c}>{String(row[c] ?? '')}</TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>

              {!analysis.review_only && (
                <>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={skipDuplicates}
                        onChange={(e) => setSkipDuplicates(e.target.checked)}
                      />
                    }
                    label="Skip strong duplicates (default)"
                  />
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={confirmed}
                        onChange={(e) => setConfirmed(e.target.checked)}
                      />
                    }
                    label="I reviewed the mapping and first 10 records. Commit this import batch only."
                  />
                  <ProsohmButton
                    onClick={() => commitMutation.mutate()}
                    disabled={
                      !confirmed ||
                      !analysis.commit_allowed ||
                      analysis.block_commit ||
                      commitMutation.isPending
                    }
                  >
                    {commitMutation.isPending ? 'Committing…' : 'Confirm & Commit Import'}
                  </ProsohmButton>
                  <Typography variant="caption" color="text.secondary">
                    Commit does not start the next file automatically.
                  </Typography>
                </>
              )}
              {analysis.review_only && (
                <Alert severity="warning">
                  Migration Exceptions are review data. Commit stores review records only — never
                  as assets.
                </Alert>
              )}
              {analysis.review_only && (
                <>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={confirmed}
                        onChange={(e) => setConfirmed(e.target.checked)}
                      />
                    }
                    label="Load these exceptions into the review queue (not assets)."
                  />
                  <ProsohmButton
                    onClick={() => commitMutation.mutate()}
                    disabled={!confirmed || commitMutation.isPending}
                  >
                    {commitMutation.isPending ? 'Saving…' : 'Save Exceptions for Review'}
                  </ProsohmButton>
                </>
              )}
            </Stack>
          </ContentCard>
        )}

        {commitResult && (
          <ContentCard title="Import complete">
            <Stack spacing={1}>
              <Typography>
                Batch <strong>{commitResult.batch_code}</strong> · Status:{' '}
                {commitResult.status}
              </Typography>
              <Typography>
                Imported: {commitResult.imported} · Skipped: {commitResult.skipped} · Duplicates:{' '}
                {commitResult.duplicated}
              </Typography>
              {commitResult.errors?.length > 0 && (
                <Alert severity="warning">{commitResult.errors.slice(0, 10).join(' · ')}</Alert>
              )}
              {nextRecommended(typesQuery.data ?? []) && (
                <Alert severity="success">
                  {selectedMeta?.label} import completed. Next recommended:{' '}
                  <strong>{nextRecommended(typesQuery.data ?? [])?.label}</strong>
                  <Box sx={{ mt: 1 }}>
                    <ProsohmButton
                      size="small"
                      onClick={() => {
                        const next = nextRecommended(typesQuery.data ?? []);
                        if (!next) return;
                        setImportType(next.id);
                        setAnalysis(null);
                        setCommitResult(null);
                        setFile(null);
                        setConfirmed(false);
                      }}
                    >
                      Import {nextRecommended(typesQuery.data ?? [])?.label}
                    </ProsohmButton>
                  </Box>
                </Alert>
              )}
            </Stack>
          </ContentCard>
        )}

        <ContentCard title="Import history">
          {(historyQuery.data ?? []).length === 0 ? (
            <Typography color="text.secondary">No import batches yet.</Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Batch</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>File</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Records</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(historyQuery.data ?? []).map((b) => (
                  <TableRow key={b.id}>
                    <TableCell>{b.created_at?.slice(0, 19)?.replace('T', ' ')}</TableCell>
                    <TableCell>{b.batch_code}</TableCell>
                    <TableCell>{b.import_type}</TableCell>
                    <TableCell>{b.filename}</TableCell>
                    <TableCell>{b.status}</TableCell>
                    <TableCell>
                      {b.success_count}/{b.record_count}
                    </TableCell>
                    <TableCell>
                      {b.status === 'committed' && (
                        <ProsohmButton
                          size="small"
                          buttonVariant="outlined"
                          onClick={() => setRollbackId(b.id)}
                        >
                          Roll back batch
                        </ProsohmButton>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </ContentCard>
      </Stack>

      <Dialog open={depDialogOpen} onClose={() => setDepDialogOpen(false)}>
        <DialogTitle>Dependency warning</DialogTitle>
        <DialogContent>
          <Typography>
            Recommended prerequisites for this import are not fully committed yet. Records may not
            link correctly. Continue with analyze anyway?
          </Typography>
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setDepDialogOpen(false)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            onClick={() => {
              setDepDialogOpen(false);
              if (pendingAnalyze) analyzeMutation.mutate();
              setPendingAnalyze(false);
            }}
          >
            Continue
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(rollbackId)} onClose={() => setRollbackId(null)}>
        <DialogTitle>Roll back import batch?</DialogTitle>
        <DialogContent>
          <Typography>
            This permanently removes only records tagged with this import batch. Employees,
            customers, projects, timesheets, and IT configuration are not deleted.
          </Typography>
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setRollbackId(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="outlined"
            disabled={rollbackMutation.isPending}
            onClick={() => rollbackId && rollbackMutation.mutate(rollbackId)}
          >
            Confirm rollback
          </ProsohmButton>
        </DialogActions>
      </Dialog>
    </PageContainer>
  );
}
