import { useEffect, useState, type FormEvent } from 'react';
import {
  Alert,
  Box,
  Chip,
  Divider,
  Grid,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import {
  fetchActiveSessions,
  fetchSecurityOverview,
  fetchSecurityPolicySettings,
  terminateUserSessions,
  updateSecurityPolicySettings,
  type SecurityPolicySettings,
} from '../../api/system';

const POLICY_FIELDS: { key: keyof SecurityPolicySettings; label: string; helper: string }[] = [
  { key: 'password_min_length', label: 'Minimum password length', helper: 'Characters' },
  { key: 'password_expiry_days', label: 'Password expiry', helper: 'Days (0 = never)' },
  { key: 'password_history_count', label: 'Password history', helper: 'Block reuse of last N' },
  { key: 'lockout_max_failed_attempts', label: 'Lockout threshold', helper: 'Failed attempts (0 = off)' },
  { key: 'lockout_duration_minutes', label: 'Lockout duration', helper: 'Minutes' },
  { key: 'session_idle_timeout_minutes', label: 'Session idle timeout', helper: 'Minutes (0 = off)' },
  { key: 'audit_retention_days', label: 'Audit retention', helper: 'Days' },
];

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 80 ? 'success' : score >= 60 ? 'warning' : 'error';
  return (
    <Box>
      <Stack direction="row" sx={{ alignItems: 'baseline' }} spacing={1}>
        <Typography variant="h3" sx={{ fontWeight: 700 }}>
          {score}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          / 100
        </Typography>
      </Stack>
      <LinearProgress
        variant="determinate"
        value={score}
        color={color}
        sx={{ mt: 1, height: 8, borderRadius: 4 }}
      />
    </Box>
  );
}

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <ContentCard>
      <Typography variant="h5" sx={{ fontWeight: 700 }}>
        {value}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
    </ContentCard>
  );
}

function StatusChip({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Chip
      icon={ok ? <CheckCircleIcon /> : <WarningAmberIcon />}
      color={ok ? 'success' : 'warning'}
      label={label}
      size="small"
      variant="outlined"
    />
  );
}

export default function SecurityCenterPage() {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();

  const overview = useQuery({ queryKey: ['security', 'overview'], queryFn: fetchSecurityOverview });
  const policy = useQuery({ queryKey: ['security', 'policy'], queryFn: fetchSecurityPolicySettings });
  const sessions = useQuery({ queryKey: ['security', 'sessions'], queryFn: fetchActiveSessions });

  const [form, setForm] = useState<SecurityPolicySettings | null>(null);
  useEffect(() => {
    if (policy.data) setForm(policy.data);
  }, [policy.data]);

  const savePolicy = useMutation({
    mutationFn: (payload: SecurityPolicySettings) => updateSecurityPolicySettings(payload),
    onSuccess: () => {
      showSuccess('Security policy updated.');
      queryClient.invalidateQueries({ queryKey: ['security', 'policy'] });
      queryClient.invalidateQueries({ queryKey: ['security', 'overview'] });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const terminate = useMutation({
    mutationFn: (userId: string) => terminateUserSessions(userId),
    onSuccess: () => {
      showSuccess('Sessions terminated.');
      queryClient.invalidateQueries({ queryKey: ['security', 'sessions'] });
      queryClient.invalidateQueries({ queryKey: ['security', 'overview'] });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  if (overview.isLoading) return <LoadingState message="Loading Security Center…" />;

  const data = overview.data;

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (form) savePolicy.mutate(form);
  };

  return (
    <PageContainer>
      <PageHeader
        title="Security Center"
        subtitle="Security posture, active sessions, and governance policy"
      />

      <Stack spacing={2}>
        {data && data.config_warnings.length > 0 && (
          <Alert severity="warning">
            <Typography sx={{ fontWeight: 600 }}>Configuration warnings</Typography>
            <ul style={{ margin: '4px 0 0 18px' }}>
              {data.config_warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </Alert>
        )}

        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 4 }}>
            <ContentCard title="Security score">
              <ScoreBadge score={data?.security_score ?? 0} />
              <Stack direction="row" spacing={1} sx={{ mt: 2, flexWrap: 'wrap', gap: 1 }}>
                <StatusChip ok={!!data?.secret_ok} label="Signing key" />
                <StatusChip ok={!!data?.encryption_ok} label="Encryption key" />
                <StatusChip ok={!!data?.hsts_enabled} label="HSTS" />
                <StatusChip ok={!!data?.rate_limiting_enabled} label="Rate limiting" />
              </Stack>
            </ContentCard>
          </Grid>
          <Grid size={{ xs: 6, md: 2 }}>
            <StatCard label="Failed logins (24h)" value={data?.failed_logins_24h ?? 0} />
          </Grid>
          <Grid size={{ xs: 6, md: 2 }}>
            <StatCard label="Locked accounts" value={data?.locked_accounts ?? 0} />
          </Grid>
          <Grid size={{ xs: 6, md: 2 }}>
            <StatCard label="Active sessions" value={data?.active_sessions ?? 0} />
          </Grid>
          <Grid size={{ xs: 6, md: 2 }}>
            <StatCard label="Exports (7d)" value={data?.export_events_7d ?? 0} />
          </Grid>
        </Grid>

        <ContentCard title="Security policy">
          <Box component="form" onSubmit={handleSubmit}>
            <Grid container spacing={2}>
              {POLICY_FIELDS.map((field) => (
                <Grid size={{ xs: 12, sm: 6, md: 3 }} key={field.key}>
                  <TextField
                    fullWidth
                    type="number"
                    label={field.label}
                    helperText={field.helper}
                    value={form ? form[field.key] : ''}
                    onChange={(event) =>
                      setForm((current) =>
                        current
                          ? { ...current, [field.key]: Number(event.target.value) }
                          : current,
                      )
                    }
                    slotProps={{ htmlInput: { min: 0 } }}
                  />
                </Grid>
              ))}
            </Grid>
            <Stack direction="row" sx={{ justifyContent: 'flex-end', mt: 2 }}>
              <ProsohmButton type="submit" disabled={savePolicy.isPending || !form}>
                Save policy
              </ProsohmButton>
            </Stack>
          </Box>
        </ContentCard>

        <ContentCard title="Active sessions">
          {sessions.isLoading ? (
            <LinearProgress />
          ) : (sessions.data?.length ?? 0) === 0 ? (
            <Typography color="text.secondary">No active sessions.</Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>User</TableCell>
                  <TableCell>IP address</TableCell>
                  <TableCell>Device</TableCell>
                  <TableCell>Started</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {sessions.data?.map((session) => (
                  <TableRow key={session.id}>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {session.user_name || '—'}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {session.user_email}
                      </Typography>
                    </TableCell>
                    <TableCell>{session.ip_address || '—'}</TableCell>
                    <TableCell>
                      <Typography variant="caption" sx={{ wordBreak: 'break-word' }}>
                        {session.user_agent || '—'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {session.created_at
                        ? new Date(session.created_at).toLocaleString()
                        : '—'}
                    </TableCell>
                    <TableCell align="right">
                      <ProsohmButton
                        buttonVariant="danger"
                        onClick={() => terminate.mutate(session.user_id)}
                        disabled={terminate.isPending}
                      >
                        Terminate
                      </ProsohmButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </ContentCard>

        <ContentCard title="Recent security events">
          {(data?.recent_events.length ?? 0) === 0 ? (
            <Typography color="text.secondary">No recent security events.</Typography>
          ) : (
            <Stack divider={<Divider flexItem />} spacing={1}>
              {data?.recent_events.map((event, index) => (
                <Stack
                  key={index}
                  direction="row"
                  spacing={2}
                  sx={{ alignItems: 'center', justifyContent: 'space-between' }}
                >
                  <Box>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {event.action}
                      {event.module ? ` · ${event.module}` : ''}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {event.ip_address || 'no IP'} ·{' '}
                      {event.created_at ? new Date(event.created_at).toLocaleString() : ''}
                    </Typography>
                  </Box>
                  <Chip
                    label={event.outcome || 'info'}
                    size="small"
                    color={event.outcome === 'failure' ? 'error' : 'success'}
                    variant="outlined"
                  />
                </Stack>
              ))}
            </Stack>
          )}
        </ContentCard>
      </Stack>
    </PageContainer>
  );
}
