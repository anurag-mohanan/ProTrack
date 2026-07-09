import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import PauseIcon from '@mui/icons-material/Pause';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { useMemo, useState } from 'react';
import { LineChart } from '@mui/x-charts/LineChart';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  fetchOperationsCenter,
  fetchOperationsHistory,
  fetchOperationsLogs,
  optimizeDatabase,
  operationsQueryKeys,
  runIntegrityCheck,
  runMaintenanceAction,
  runOperationsDiagnostics,
  type HealthLevel,
  type OperationsCenterSnapshot,
  type ServiceStatus,
} from '../../api/operations';
import { createBackup } from '../../api/system';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { ROLES } from '../../utils/permissions';
import { formatDisplayValue } from '../../utils/format';
import { PRODUCT_NAME, VERSION_DISPLAY } from '../../config/appMeta';

const REFRESH_MS = 30_000;

function alertSeverity(level: HealthLevel | ServiceStatus | string): 'success' | 'warning' | 'error' | 'info' {
  const v = level.toLowerCase();
  if (v === 'healthy' || v === 'running' || v === 'pass' || v === 'success') return 'success';
  if (v === 'warning' || v === 'degraded' || v === 'waiting') return 'warning';
  if (v === 'critical' || v === 'stopped' || v === 'fail' || v === 'failed' || v === 'error') return 'error';
  return 'info';
}

function statusColor(level: HealthLevel | ServiceStatus | string): 'success' | 'warning' | 'error' | 'info' | 'default' {
  const severity = alertSeverity(level);
  return severity === 'info' ? 'default' : severity;
}

function OverallBanner({ snapshot }: { snapshot: OperationsCenterSnapshot }) {
  const emoji = snapshot.overall_status === 'healthy' ? '🟢' : snapshot.overall_status === 'warning' ? '🟡' : '🔴';
  return (
    <ContentCard title="Overall System Status">
      <Stack direction="row" spacing={2} sx={{ alignItems: { sm: 'center' } }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          {emoji} {snapshot.overall_label}
        </Typography>
        <Chip label={`${PRODUCT_NAME} ${VERSION_DISPLAY}`} size="small" variant="outlined" />
        <Chip
          label={`API v${snapshot.application_version} ${snapshot.release_candidate}`}
          size="small"
          color="info"
          variant="outlined"
        />
      </Stack>
    </ContentCard>
  );
}

function ServiceGrid({ services }: { services: OperationsCenterSnapshot['services'] }) {
  return (
    <Grid container spacing={2}>
      {services.map((service) => (
        <Grid key={service.name} size={{ xs: 12, sm: 6, md: 4, lg: 3 }}>
          <ContentCard title={service.name}>
            <Stack spacing={1}>
              <Chip label={service.status_label} size="small" color={statusColor(service.status)} />
              {service.uptime_label ? (
                <Typography variant="body2" color="text.secondary">
                  Uptime: {service.uptime_label}
                </Typography>
              ) : null}
              {service.response_time_ms != null ? (
                <Typography variant="body2" color="text.secondary">
                  Response: {service.response_time_ms} ms
                </Typography>
              ) : null}
              {service.version ? (
                <Typography variant="body2" color="text.secondary">
                  Version: {service.version}
                </Typography>
              ) : null}
              {service.detail ? (
                <Typography variant="caption" color="text.secondary">
                  {service.detail}
                </Typography>
              ) : null}
            </Stack>
          </ContentCard>
        </Grid>
      ))}
    </Grid>
  );
}

function DiskPanel({ items }: { items: OperationsCenterSnapshot['disk_usage'] }) {
  return (
    <ContentCard title="Disk Usage">
      <Stack spacing={2}>
        {items.map((disk) => (
          <Box key={disk.name}>
            <Stack direction="row" sx={{ justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {disk.name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {disk.used_label} / {disk.total_label} ({disk.percent_used.toFixed(1)}%)
              </Typography>
            </Stack>
            <LinearProgress
              variant="determinate"
              value={Math.min(disk.percent_used, 100)}
              color={disk.critical ? 'error' : disk.warning ? 'warning' : 'primary'}
              sx={{ height: 8, borderRadius: 4 }}
            />
          </Box>
        ))}
      </Stack>
    </ContentCard>
  );
}

function AlertsPanel({ alerts }: { alerts: OperationsCenterSnapshot['alerts'] }) {
  return (
    <ContentCard title="Live Alerts">
      <Stack spacing={1}>
        {alerts.map((alert) => (
          <Alert key={alert.id} severity={alertSeverity(alert.severity)}>
            {alert.title}
            {alert.detail ? ` — ${alert.detail}` : ''}
          </Alert>
        ))}
      </Stack>
    </ContentCard>
  );
}

export default function AdminSystemPage() {
  const { user } = useAuth();
  const isAdmin = user?.role_name === ROLES.ADMIN;
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [tab, setTab] = useState(0);
  const [logCategory, setLogCategory] = useState('application');
  const [confirmAction, setConfirmAction] = useState<string | null>(null);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);
  const [diagnosticsReport, setDiagnosticsReport] = useState<Awaited<ReturnType<typeof runOperationsDiagnostics>> | null>(null);

  const snapshotQuery = useQuery({
    queryKey: operationsQueryKeys.snapshot,
    queryFn: fetchOperationsCenter,
    refetchInterval: autoRefresh ? REFRESH_MS : false,
  });

  const historyQuery = useQuery({
    queryKey: operationsQueryKeys.history('24h'),
    queryFn: () => fetchOperationsHistory('24h'),
    enabled: tab === 8,
  });

  const logsQuery = useQuery({
    queryKey: operationsQueryKeys.logs(logCategory),
    queryFn: () => fetchOperationsLogs(logCategory),
    enabled: tab === 7,
  });

  const maintenanceMutation = useMutation({
    mutationFn: runMaintenanceAction,
    onSuccess: (result) => {
      showSuccess(result.message);
      void queryClient.invalidateQueries({ queryKey: operationsQueryKeys.all });
    },
    onError: (error: Error) => showError(error.message),
  });

  const backupMutation = useMutation({
    mutationFn: createBackup,
    onSuccess: () => {
      showSuccess('Backup created');
      void queryClient.invalidateQueries({ queryKey: operationsQueryKeys.all });
    },
    onError: (error: Error) => showError(error.message),
  });

  const integrityMutation = useMutation({
    mutationFn: runIntegrityCheck,
    onSuccess: (result) => showSuccess(`Integrity: ${result.result}`),
    onError: (error: Error) => showError(error.message),
  });

  const optimizeMutation = useMutation({
    mutationFn: optimizeDatabase,
    onSuccess: (result) => showSuccess(result.message),
    onError: (error: Error) => showError(error.message),
  });

  const diagnosticsMutation = useMutation({
    mutationFn: runOperationsDiagnostics,
    onSuccess: (report) => {
      setDiagnosticsReport(report);
      setDiagnosticsOpen(true);
    },
    onError: (error: Error) => showError(error.message),
  });

  const lastUpdated = useMemo(
    () => (snapshotQuery.data?.generated_at ? new Date(snapshotQuery.data.generated_at).toLocaleString() : '—'),
    [snapshotQuery.data?.generated_at],
  );

  if (snapshotQuery.isLoading) {
    return <LoadingState message="Loading System Health & Operations Center…" />;
  }

  if (snapshotQuery.isError || !snapshotQuery.data) {
    return (
      <Box>
        <PageHeader title="System Health" subtitle="Platform monitoring and maintenance" />
        <Alert severity="error">Unable to load operations center data.</Alert>
      </Box>
    );
  }

  const snapshot = snapshotQuery.data;
  const db = snapshot.database;

  const maintenanceActions = [
    { id: 'run_diagnostics', label: 'Run Diagnostics' },
    { id: 'test_database', label: 'Test Database' },
    { id: 'test_email', label: 'Test Email' },
    { id: 'process_email_queue', label: 'Process Email Queue' },
    { id: 'clear_cache', label: 'Clear Cache' },
    { id: 'refresh_dashboard_cache', label: 'Refresh Dashboard Cache' },
    { id: 'reload_configuration', label: 'Reload Configuration' },
    { id: 'restart_backend', label: 'Restart Backend' },
    { id: 'restart_iis', label: 'Restart IIS' },
    { id: 'restart_scheduler', label: 'Restart Scheduler' },
  ];

  const handleMaintenance = (action: string) => {
    if (!isAdmin) return;
    if (action.startsWith('restart') || action === 'run_diagnostics') {
      setConfirmAction(action);
      return;
    }
    maintenanceMutation.mutate(action);
  };

  const confirmMaintenance = () => {
    if (!confirmAction) return;
    if (confirmAction === 'run_diagnostics') {
      diagnosticsMutation.mutate();
    } else {
      maintenanceMutation.mutate(confirmAction);
    }
    setConfirmAction(null);
  };

  return (
    <Box>
      <PageHeader
        title="System Health & Operations Center"
        subtitle="Real-time platform monitoring, diagnostics, and maintenance"
        action={
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
            <Typography variant="caption" color="text.secondary">
              Last updated: {lastUpdated}
            </Typography>
            <ProsohmButton
              size="small"
              buttonVariant="outlined"
              startIcon={autoRefresh ? <PauseIcon /> : <PlayArrowIcon />}
              onClick={() => setAutoRefresh((v) => !v)}
            >
              {autoRefresh ? 'Pause' : 'Resume'}
            </ProsohmButton>
            <ProsohmButton
              size="small"
              startIcon={<RefreshIcon />}
              onClick={() => void snapshotQuery.refetch()}
              loading={snapshotQuery.isFetching}
            >
              Refresh Now
            </ProsohmButton>
          </Stack>
        }
      />

      <Stack spacing={2.5}>
        <OverallBanner snapshot={snapshot} />
        <AlertsPanel alerts={snapshot.alerts} />

        <ContentCard title="Service Status">
          <ServiceGrid services={snapshot.services} />
        </ContentCard>

        <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto">
          <Tab label="Database" />
          <Tab label="IIS / Host" />
          <Tab label="Jobs" />
          <Tab label="Performance" />
          <Tab label="Errors" />
          <Tab label="Email & AI" />
          <Tab label="Backup" />
          <Tab label="Logs" />
          <Tab label="History" />
          <Tab label="Statistics" />
          <Tab label="API Monitor" />
          <Tab label="Timeline" />
          {isAdmin ? <Tab label="Maintenance" /> : null}
        </Tabs>

        {tab === 0 ? (
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 8 }}>
              <ContentCard title="Database Health">
                <Grid container spacing={2}>
                  {[
                    ['Connected', db.connected ? 'Yes' : 'No'],
                    ['Database', db.database_name ?? '—'],
                    ['Size', db.database_size_label],
                    ['SQLite', db.sqlite_version ?? '—'],
                    ['Tables', db.table_count],
                    ['Projects', db.total_projects],
                    ['Timesheets', db.total_timesheets],
                    ['Users', db.total_users],
                    ['Customers', db.total_customers],
                    ['Entries', db.total_entries],
                    ['Last Backup', db.last_backup_label ?? '—'],
                  ].map(([label, value]) => (
                    <Grid key={label} size={{ xs: 6, sm: 4 }}>
                      <Typography variant="caption" color="text.secondary">
                        {label}
                      </Typography>
                      <Typography variant="body1">{formatDisplayValue(value)}</Typography>
                    </Grid>
                  ))}
                </Grid>
              </ContentCard>
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <DiskPanel items={snapshot.disk_usage} />
              {isAdmin ? (
                <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                  <ProsohmButton size="small" onClick={() => integrityMutation.mutate()} loading={integrityMutation.isPending}>
                    Integrity Check
                  </ProsohmButton>
                  <ProsohmButton size="small" buttonVariant="outlined" onClick={() => optimizeMutation.mutate()} loading={optimizeMutation.isPending}>
                    Optimize
                  </ProsohmButton>
                </Stack>
              ) : null}
            </Grid>
          </Grid>
        ) : null}

        {tab === 1 ? (
          <ContentCard title="IIS / Host Health">
            <Grid container spacing={2}>
              {[
                ['Website Running', snapshot.iis.website_running ? 'Yes' : 'No'],
                ['App Pool', snapshot.iis.app_pool_status ?? '—'],
                ['Site Name', snapshot.iis.site_name ?? '—'],
                ['HTTPS', snapshot.iis.https_enabled == null ? '—' : snapshot.iis.https_enabled ? 'Enabled' : 'Disabled'],
                ['Platform', snapshot.iis.host_platform ?? '—'],
                ['Current Users', snapshot.iis.current_users],
              ].map(([label, value]) => (
                <Grid key={label} size={{ xs: 6, sm: 4 }}>
                  <Typography variant="caption" color="text.secondary">{label}</Typography>
                  <Typography variant="body1">{formatDisplayValue(value)}</Typography>
                </Grid>
              ))}
            </Grid>
            {snapshot.iis.note ? (
              <Alert severity="info" sx={{ mt: 2 }}>{snapshot.iis.note}</Alert>
            ) : null}
          </ContentCard>
        ) : null}

        {tab === 2 ? (
          <ContentCard title="Background Jobs">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Last Run</TableCell>
                  <TableCell>Message</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {snapshot.background_jobs.map((job) => (
                  <TableRow key={job.job_id}>
                    <TableCell>{job.name}</TableCell>
                    <TableCell>
                      <Chip label={job.status} size="small" color={statusColor(job.status)} />
                    </TableCell>
                    <TableCell>{job.last_run ? new Date(job.last_run).toLocaleString() : '—'}</TableCell>
                    <TableCell>{job.message ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ContentCard>
        ) : null}

        {tab === 3 ? (
          <Grid container spacing={2}>
            {[
              ['Avg API Response', `${snapshot.performance.average_api_response_ms} ms`],
              ['Requests / Min', snapshot.performance.requests_per_minute],
              ['Memory', snapshot.performance.memory_usage_mb != null ? `${snapshot.performance.memory_usage_mb} MB` : '—'],
              ['CPU', snapshot.performance.cpu_usage_percent != null ? `${snapshot.performance.cpu_usage_percent}%` : '—'],
              ['Failed Logins (24h)', snapshot.user_activity.failed_logins_24h],
              ['Active Users', snapshot.user_activity.users_logged_in],
            ].map(([label, value]) => (
              <Grid key={label} size={{ xs: 12, sm: 6, md: 4 }}>
                <ContentCard title={String(label)}>
                  <Typography variant="h5">{formatDisplayValue(String(value))}</Typography>
                </ContentCard>
              </Grid>
            ))}
          </Grid>
        ) : null}

        {tab === 4 ? (
          <ContentCard title="Error Monitor">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Time</TableCell>
                  <TableCell>Severity</TableCell>
                  <TableCell>Module</TableCell>
                  <TableCell>Message</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {snapshot.errors.length ? snapshot.errors.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{new Date(row.occurred_at).toLocaleString()}</TableCell>
                    <TableCell><Chip label={row.severity} size="small" color={statusColor(row.severity)} /></TableCell>
                    <TableCell>{row.module}</TableCell>
                    <TableCell>{row.message}</TableCell>
                  </TableRow>
                )) : (
                  <TableRow>
                    <TableCell colSpan={4}>
                      <Typography variant="body2" color="text.secondary">No recent errors.</Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </ContentCard>
        ) : null}

        {tab === 5 ? (
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 6 }}>
              <ContentCard title="Email Status">
                <Stack spacing={1}>
                  <Typography variant="body2">SMTP: {snapshot.email.smtp_connected ? 'Connected' : snapshot.email.smtp_connected === false ? 'Not configured' : 'Unknown'}</Typography>
                  <Typography variant="body2">Host: {snapshot.email.smtp_host ?? '—'}</Typography>
                  <Typography variant="body2">Queued: {snapshot.email.queued_emails}</Typography>
                  <Typography variant="body2">Failed: {snapshot.email.failed_emails}</Typography>
                  <Typography variant="body2">Retry Queue: {snapshot.email.retry_queue}</Typography>
                </Stack>
              </ContentCard>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <ContentCard title="AI Status">
                <Stack spacing={1}>
                  <Chip label={snapshot.ai.available ? 'Available' : 'Unavailable'} color={snapshot.ai.available ? 'success' : 'warning'} size="small" />
                  <Typography variant="body2">{snapshot.ai.detail ?? '—'}</Typography>
                  <Typography variant="body2">Recommendations today: {snapshot.ai.recommendations_today}</Typography>
                </Stack>
              </ContentCard>
            </Grid>
          </Grid>
        ) : null}

        {tab === 6 ? (
          <ContentCard title="Backup Center">
            <Stack spacing={1.5}>
              <Typography variant="body2">Last backup: {snapshot.backup.last_backup_filename ?? 'None'}</Typography>
              <Typography variant="body2">Size: {snapshot.backup.backup_size_label}</Typography>
              <Typography variant="body2">Location: {snapshot.backup.backup_location}</Typography>
              <Typography variant="body2">Backups on file: {snapshot.backup.backup_count}</Typography>
              {isAdmin ? (
                <ProsohmButton onClick={() => backupMutation.mutate()} loading={backupMutation.isPending}>
                  Backup Now
                </ProsohmButton>
              ) : null}
            </Stack>
          </ContentCard>
        ) : null}

        {tab === 7 ? (
          <ContentCard title="System Logs">
            <Tabs value={logCategory} onChange={(_, v) => setLogCategory(v)} sx={{ mb: 2 }}>
              {['application', 'api', 'database', 'imports', 'emails', 'authentication', 'scheduler'].map((cat) => (
                <Tab key={cat} label={cat} value={cat} />
              ))}
            </Tabs>
            <Box sx={{ maxHeight: 360, overflow: 'auto', fontFamily: 'monospace', fontSize: 12 }}>
              {(logsQuery.data ?? []).length ? (logsQuery.data ?? []).map((line, i) => (
                <Typography key={`${line.source}-${i}`} variant="caption" sx={{ display: 'block' }}>
                  {line.message}
                </Typography>
              )) : (
                <Typography variant="body2" color="text.secondary">No log files found for this category.</Typography>
              )}
            </Box>
          </ContentCard>
        ) : null}

        {tab === 8 ? (
          <ContentCard title="Health History (24h)">
            {historyQuery.data && historyQuery.data.length > 1 ? (
              <LineChart
                height={280}
                series={[
                  { data: historyQuery.data.map((p) => p.response_time_ms), label: 'Response ms' },
                  { data: historyQuery.data.map((p) => p.error_count), label: 'Errors' },
                ]}
                xAxis={[{
                  data: historyQuery.data.map((p) => new Date(p.recorded_at)),
                  scaleType: 'time',
                }]}
              />
            ) : (
              <Typography variant="body2" color="text.secondary">
                Collecting health snapshots — chart will appear after a few refresh cycles.
              </Typography>
            )}
          </ContentCard>
        ) : null}

        {tab === 9 ? (
          <Grid container spacing={2}>
            {Object.entries(snapshot.statistics).map(([key, value]) => (
              <Grid key={key} size={{ xs: 6, sm: 4, md: 3 }}>
                <ContentCard title={key.replace(/_/g, ' ')}>
                  <Typography variant="h5">{value}</Typography>
                </ContentCard>
              </Grid>
            ))}
          </Grid>
        ) : null}

        {tab === 10 ? (
          <ContentCard title="API Monitor">
            <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Method</TableCell>
                    <TableCell>Endpoint</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {snapshot.api_monitor.map((row) => (
                    <TableRow key={`${row.method}-${row.endpoint}`}>
                      <TableCell>{row.method}</TableCell>
                      <TableCell>{row.endpoint}</TableCell>
                      <TableCell>{row.last_status}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          </ContentCard>
        ) : null}

        {tab === 11 ? (
          <ContentCard title="System Timeline">
            <Stack spacing={1}>
              {snapshot.timeline.map((event, index) => (
                <Box key={`${event.occurred_at}-${index}`} sx={{ borderLeft: 3, borderColor: 'divider', pl: 2 }}>
                  <Typography variant="caption" color="text.secondary">
                    {new Date(event.occurred_at).toLocaleString()}
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{event.title}</Typography>
                  {event.detail ? <Typography variant="caption">{event.detail}</Typography> : null}
                </Box>
              ))}
            </Stack>
          </ContentCard>
        ) : null}

        {tab === 12 && isAdmin ? (
          <ContentCard title="Maintenance Actions">
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Destructive or host-level actions require confirmation.
            </Typography>
            <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
              {maintenanceActions.map((action) => (
                <ProsohmButton
                  key={action.id}
                  size="small"
                  buttonVariant={action.id.startsWith('restart') ? 'outlined' : 'primary'}
                  onClick={() => handleMaintenance(action.id)}
                  loading={maintenanceMutation.isPending || diagnosticsMutation.isPending}
                >
                  {action.label}
                </ProsohmButton>
              ))}
            </Stack>
          </ContentCard>
        ) : null}
      </Stack>

      <Dialog open={Boolean(confirmAction)} onClose={() => setConfirmAction(null)}>
        <DialogTitle>Confirm Maintenance Action</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            Are you sure you want to run: <strong>{confirmAction}</strong>?
          </Typography>
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setConfirmAction(null)}>Cancel</ProsohmButton>
          <ProsohmButton onClick={confirmMaintenance}>Confirm</ProsohmButton>
        </DialogActions>
      </Dialog>

      <Dialog open={diagnosticsOpen} onClose={() => setDiagnosticsOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Diagnostics Report</DialogTitle>
        <DialogContent>
          {diagnosticsReport ? (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Check</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Message</TableCell>
                  <TableCell>ms</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {diagnosticsReport.results.map((row) => (
                  <TableRow key={row.name}>
                    <TableCell>{row.name}</TableCell>
                    <TableCell><Chip label={row.status} size="small" color={statusColor(row.status)} /></TableCell>
                    <TableCell>{row.message}</TableCell>
                    <TableCell>{row.duration_ms}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
        </DialogContent>
        <DialogActions>
          <ProsohmButton onClick={() => setDiagnosticsOpen(false)}>Close</ProsohmButton>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
