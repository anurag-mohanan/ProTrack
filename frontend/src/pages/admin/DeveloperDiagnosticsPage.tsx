import { useMemo } from 'react';
import {
  Alert,
  Box,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { useState } from 'react';
import {
  fetchDeveloperDiagnosticsSummary,
  operationsQueryKeys,
  runMaintenanceAction,
  runReleaseValidation,
  type HealthLevel,
} from '../../api/operations';
import { createBackup } from '../../api/system';
import { useToast } from '../../context/ToastContext';

function chipColor(status: string): 'success' | 'warning' | 'error' | 'default' {
  const value = status.toLowerCase();
  if (value === 'pass' || value === 'healthy' || value === 'running' || value === 'ready') return 'success';
  if (value === 'warning' || value === 'degraded') return 'warning';
  if (value === 'fail' || value === 'critical' || value === 'blocked') return 'error';
  return 'default';
}

function scoreColor(status: HealthLevel): 'success' | 'warning' | 'error' {
  if (status === 'healthy') return 'success';
  if (status === 'warning') return 'warning';
  return 'error';
}

export default function DeveloperDiagnosticsPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const summaryQuery = useQuery({
    queryKey: operationsQueryKeys.diagnosticsSummary,
    queryFn: fetchDeveloperDiagnosticsSummary,
    refetchInterval: 30_000,
  });

  const releaseMutation = useMutation({
    mutationFn: runReleaseValidation,
    onSuccess: () => {
      showSuccess('Release validation completed.');
      void queryClient.invalidateQueries({ queryKey: operationsQueryKeys.diagnosticsSummary });
    },
    onError: (error: Error) => showError(error.message),
  });

  const repairMutation = useMutation({
    mutationFn: runMaintenanceAction,
    onSuccess: (result) => {
      showSuccess(result.message);
      void queryClient.invalidateQueries({ queryKey: operationsQueryKeys.diagnosticsSummary });
    },
    onError: (error: Error) => showError(error.message),
  });

  const backupMutation = useMutation({
    mutationFn: createBackup,
    onSuccess: () => {
      showSuccess('Database backup created.');
      void queryClient.invalidateQueries({ queryKey: operationsQueryKeys.diagnosticsSummary });
    },
    onError: (error: Error) => showError(error.message),
  });

  const summary = summaryQuery.data;
  const releaseReport = summary?.release_validation;
  const [confirmAction, setConfirmAction] = useState<{
    type: 'repair' | 'release';
    action?: string;
    label: string;
  } | null>(null);

  const failingDefaults = useMemo(
    () => (summary?.default_data ?? []).filter((row) => row.status !== 'pass'),
    [summary?.default_data],
  );

  if (summaryQuery.isLoading) {
    return <LoadingState message="Loading developer diagnostics…" />;
  }

  if (summaryQuery.isError || !summary) {
    return (
      <Box>
        <PageHeader title="Diagnostics" subtitle="Hidden internal diagnostics center" />
        <Alert severity="error">Unable to load diagnostics summary.</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title="Developer Diagnostics & System Health"
        subtitle="Internal release verification, failure isolation, and safe recovery actions"
        action={
          <Stack direction="row" spacing={1}>
            <ProsohmButton
              startIcon={<PlayArrowIcon />}
              onClick={() => setConfirmAction({ type: 'release', label: 'Run Full Release Validation' })}
              loading={releaseMutation.isPending}
            >
              Run Full Release Validation
            </ProsohmButton>
            <ProsohmButton
              buttonVariant="outlined"
              onClick={() => void summaryQuery.refetch()}
              loading={summaryQuery.isFetching}
            >
              Refresh
            </ProsohmButton>
          </Stack>
        }
      />

      <Stack spacing={2}>
        <ContentCard title="System Health">
          <Stack spacing={1.5}>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
              <Chip label={summary.overall_status.toUpperCase()} color={chipColor(summary.overall_status)} />
              <Typography variant="body2" color="text.secondary">
                Last checked: {new Date(summary.last_checked).toLocaleString()}
              </Typography>
            </Stack>
            <Typography variant="h4" sx={{ fontWeight: 700 }}>
              {summary.overall_score}%
            </Typography>
            <LinearProgress
              variant="determinate"
              value={summary.overall_score}
              color={scoreColor(summary.overall_status)}
              sx={{ height: 10, borderRadius: 5 }}
            />
          </Stack>
        </ContentCard>

        <Grid container spacing={2}>
          {summary.summary_cards.map((card) => (
            <Grid key={card.name} size={{ xs: 12, sm: 6, md: 4, lg: 3 }}>
              <ContentCard title={card.name}>
                <Stack spacing={0.75}>
                  <Chip size="small" label={card.status_label} color={chipColor(card.status)} />
                  <Typography variant="caption" color="text.secondary">
                    {card.detail ?? `Checked ${new Date(card.last_checked).toLocaleTimeString()}`}
                  </Typography>
                </Stack>
              </ContentCard>
            </Grid>
          ))}
        </Grid>

        <ContentCard title="Database Diagnostics">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Table</TableCell>
                <TableCell>Records</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Missing FK</TableCell>
                <TableCell>Duplicate Keys</TableCell>
                <TableCell>Issues</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {summary.database_tables.map((row) => (
                <TableRow key={row.table}>
                  <TableCell>{row.table}</TableCell>
                  <TableCell>{row.records}</TableCell>
                  <TableCell>
                    <Chip size="small" label={row.status} color={chipColor(row.status)} />
                  </TableCell>
                  <TableCell>{row.missing_fk}</TableCell>
                  <TableCell>{row.duplicate_keys}</TableCell>
                  <TableCell>{row.issues}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </ContentCard>

        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 6 }}>
            <ContentCard title="Default Data Validation">
              <Stack spacing={1}>
                {summary.default_data.map((row) => (
                  <Stack key={row.name} direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="body2">{row.name}</Typography>
                    <Stack direction="row" spacing={1}>
                      <Chip size="small" label={row.status.toUpperCase()} color={chipColor(row.status)} />
                      {row.restore_action ? (
                        <ProsohmButton
                          size="small"
                          buttonVariant="outlined"
                            onClick={() =>
                              setConfirmAction({
                                type: 'repair',
                                action: row.restore_action ?? '',
                                label: `Restore Default: ${row.name}`,
                              })
                            }
                          loading={repairMutation.isPending}
                        >
                          Restore Default
                        </ProsohmButton>
                      ) : null}
                    </Stack>
                  </Stack>
                ))}
              </Stack>
            </ContentCard>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <ContentCard title="Customer Template Validation">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Customer</TableCell>
                    <TableCell>Template</TableCell>
                    <TableCell>Milestones</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {summary.customer_templates.map((row) => (
                    <TableRow key={`${row.customer}-${row.template_name}`}>
                      <TableCell>{row.customer}</TableCell>
                      <TableCell>{row.template_name}</TableCell>
                      <TableCell>
                        {row.actual_milestones}/{row.expected_milestones}
                      </TableCell>
                      <TableCell>
                        <Chip size="small" label={row.status.toUpperCase()} color={chipColor(row.status)} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </ContentCard>
          </Grid>
        </Grid>

        <ContentCard title="API Monitor">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Method</TableCell>
                <TableCell>Endpoint</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Response Time</TableCell>
                <TableCell>Last Error</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {summary.api_monitor.slice(0, 50).map((row) => (
                <TableRow key={`${row.method}-${row.endpoint}`}>
                  <TableCell>{row.method}</TableCell>
                  <TableCell>{row.endpoint}</TableCell>
                  <TableCell>
                    <Chip size="small" label={row.status.toUpperCase()} color={chipColor(row.status)} />
                  </TableCell>
                  <TableCell>{row.response_time_ms} ms</TableCell>
                  <TableCell>{row.last_error ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </ContentCard>

        <ContentCard title="Runtime Errors">
          {summary.runtime_errors.length === 0 ? (
            <Alert severity="success">No grouped runtime errors detected.</Alert>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Category</TableCell>
                  <TableCell>Count</TableCell>
                  <TableCell>Severity</TableCell>
                  <TableCell>Message</TableCell>
                  <TableCell>Last Seen</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {summary.runtime_errors.map((row) => (
                  <TableRow key={row.error_key}>
                    <TableCell>{row.category}</TableCell>
                    <TableCell>{row.count}</TableCell>
                    <TableCell>
                      <Chip size="small" label={row.severity.toUpperCase()} color={chipColor(row.severity)} />
                    </TableCell>
                    <TableCell>{row.sample_message ?? '—'}</TableCell>
                    <TableCell>{row.last_seen_at ? new Date(row.last_seen_at).toLocaleString() : '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </ContentCard>

        <ContentCard title="Release Validation Report">
          {releaseReport ? (
            <Grid container spacing={2}>
              {[
                ['Pages Tested', releaseReport.pages_tested],
                ['API Tested', releaseReport.api_tested],
                ['Database Checks', releaseReport.database_checks],
                ['Passed', releaseReport.passed],
                ['Warnings', releaseReport.warnings],
                ['Critical', releaseReport.critical],
              ].map(([label, value]) => (
                <Grid key={String(label)} size={{ xs: 6, sm: 4, md: 2 }}>
                  <Typography variant="caption" color="text.secondary">{label}</Typography>
                  <Typography variant="h6">{value}</Typography>
                </Grid>
              ))}
              <Grid size={{ xs: 12 }}>
                <Chip label={releaseReport.status_label} color={chipColor(releaseReport.status)} />
              </Grid>
            </Grid>
          ) : (
            <Alert severity="info">No release validation report yet. Run full validation to generate one.</Alert>
          )}
        </ContentCard>

        <ContentCard title="Self-Healing Tools">
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
            {[
              ['Rebuild Customer Templates', 'rebuild_customer_templates'],
              ['Restore Default Roles', 'restore_default_roles'],
              ['Restore Task Types', 'restore_task_types'],
              ['Repair Foreign Keys', 'repair_foreign_keys'],
              ['Rebuild Search Index', 'rebuild_search_index'],
              ['Clear Cache', 'clear_cache'],
              ['Restart Background Services', 'restart_scheduler'],
              ['Validate Database', 'test_database'],
            ].map(([label, action]) => (
              <ProsohmButton
                key={action}
                size="small"
                buttonVariant="outlined"
                onClick={() =>
                  setConfirmAction({
                    type: 'repair',
                    action: String(action),
                    label: String(label),
                  })
                }
                loading={repairMutation.isPending}
              >
                {label}
              </ProsohmButton>
            ))}
            <ProsohmButton
              size="small"
              buttonVariant="outlined"
              onClick={() =>
                setConfirmAction({
                  type: 'repair',
                  action: 'create_backup',
                  label: 'Backup Database',
                })
              }
              loading={backupMutation.isPending}
            >
              Backup Database
            </ProsohmButton>
          </Stack>
          {failingDefaults.length > 0 ? (
            <Alert severity="warning" sx={{ mt: 2 }}>
              {failingDefaults.length} default configuration checks need attention.
            </Alert>
          ) : null}
        </ContentCard>
      </Stack>

      <Dialog open={Boolean(confirmAction)} onClose={() => setConfirmAction(null)}>
        <DialogTitle>Confirm Action</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            Are you sure you want to run <strong>{confirmAction?.label}</strong>?
          </Typography>
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setConfirmAction(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            onClick={() => {
              if (!confirmAction) return;
              if (confirmAction.type === 'release') {
                releaseMutation.mutate();
              } else if (confirmAction.action === 'create_backup') {
                backupMutation.mutate();
              } else if (confirmAction.action) {
                repairMutation.mutate(confirmAction.action);
              }
              setConfirmAction(null);
            }}
          >
            Confirm
          </ProsohmButton>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
