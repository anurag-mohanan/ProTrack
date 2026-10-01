import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  checkinLicense,
  checkoutLicense,
  fetchLicenseSchedule,
  fetchLicenseSessions,
  itAllocationKeys,
} from '../../../api/itAllocation';
import { itOperationsKeys, updateSoftwareLicense } from '../../../api/itOperations';
import { getErrorMessage } from '../../../api/client';
import { useToast } from '../../../context/ToastContext';
import type { SoftwareLicensePool } from '../../../types/itOperations';
import { formatDate } from '../../../utils/format';
import { ProsohmButton } from '../../ui/ProsohmButton';
import { FormField, FormSelect } from '../../ui/design-system';
import { COMPLIANCE_COLORS, LICENSE_METRIC_OPTIONS, metricRule } from './licenseMetrics';
import { ScheduleTimeline } from './ScheduleTimeline';

type Props = {
  pool: SoftwareLicensePool | null;
  canManage: boolean;
  onClose: () => void;
};

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <Box sx={{ minWidth: 110 }}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="h6">{value}</Typography>
    </Box>
  );
}

export function LicenseDetailDialog({ pool, canManage, onClose }: Props) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [onDate, setOnDate] = useState('');
  const [metric, setMetric] = useState('');
  const [checkoutUser, setCheckoutUser] = useState('');

  const scheduleQuery = useQuery({
    queryKey: itAllocationKeys.licenseSchedule(pool?.id ?? '', onDate || undefined),
    queryFn: () => fetchLicenseSchedule(pool!.id, onDate || undefined),
    enabled: Boolean(pool),
  });
  const summary = scheduleQuery.data?.summary;
  const concurrent = summary?.metric === 'CONCURRENT';

  const sessionsQuery = useQuery({
    queryKey: itAllocationKeys.sessions(pool?.id ?? ''),
    queryFn: () => fetchLicenseSessions(pool!.id),
    enabled: Boolean(pool) && concurrent,
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: itAllocationKeys.all });
    void queryClient.invalidateQueries({ queryKey: itOperationsKeys.all });
  };

  const metricMutation = useMutation({
    mutationFn: () => updateSoftwareLicense(pool!.id, { assignment_model: metric }),
    onSuccess: () => {
      showSuccess('License metric updated.');
      setMetric('');
      refresh();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });
  const checkoutMutation = useMutation({
    mutationFn: () => checkoutLicense(pool!.id, { user_id: checkoutUser }),
    onSuccess: () => {
      showSuccess('License checked out.');
      setCheckoutUser('');
      refresh();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });
  const checkinMutation = useMutation({
    mutationFn: (sessionId: string) => checkinLicense(sessionId),
    onSuccess: () => {
      showSuccess('License released.');
      refresh();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const authorizedOptions = useMemo(() => {
    const data = scheduleQuery.data;
    if (!data) return [];
    const active = new Set((sessionsQuery.data ?? []).filter((s) => s.is_active).map((s) => s.user_id));
    const seen = new Map<string, string>();
    for (const row of [...data.scheduled, ...data.authorized_only]) {
      if (row.kind === 'assignment' && row.user_id && !active.has(row.user_id)) {
        seen.set(row.user_id, row.user_name || row.user_id);
      }
    }
    return [...seen].map(([value, label]) => ({ value, label }));
  }, [scheduleQuery.data, sessionsQuery.data]);

  const currentModel = pool?.assignment_model || pool?.license_type || '';

  return (
    <Dialog open={Boolean(pool)} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>
        {pool?.software_name || 'License'}
        {pool?.entitlement_code ? ` · ${pool.entitlement_code}` : ''}
      </DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {scheduleQuery.isError ? <Alert severity="error">{getErrorMessage(scheduleQuery.error)}</Alert> : null}
        {summary ? (
          <>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
              <Chip label={summary.metric_label} color="primary" variant="outlined" />
              <Chip
                label={summary.compliance_status.replace('_', ' ')}
                color={COMPLIANCE_COLORS[summary.compliance_status] ?? 'default'}
              />
              <Typography variant="body2" color="text.secondary">
                {summary.compliance_reason}
              </Typography>
            </Stack>
            <Typography variant="body2">{summary.metric_rule}</Typography>
            <Stack direction="row" spacing={3} sx={{ flexWrap: 'wrap' }}>
              <Stat label="Rights owned" value={summary.metric === 'SITE' ? 'Site' : summary.rights_owned} />
              <Stat label="Authorized users" value={summary.authorized_users} />
              <Stat
                label={concurrent ? 'Scheduled peak' : 'Allocated'}
                value={summary.rights_allocated}
              />
              {concurrent ? <Stat label="Active usage" value={summary.active_usage} /> : null}
              <Stat
                label="Available"
                value={summary.available_rights === null ? 'Unlimited' : summary.available_rights}
              />
            </Stack>
          </>
        ) : null}

        {canManage ? (
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ alignItems: 'flex-start' }}>
            <FormSelect
              label="License metric"
              value={metric || currentModel}
              onChange={(event) => setMetric(String(event.target.value))}
              options={LICENSE_METRIC_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
              helper={metricRule(metric || currentModel)}
              sx={{ minWidth: 260 }}
            />
            <ProsohmButton
              buttonVariant="outlined"
              disabled={!metric || metric === currentModel}
              loading={metricMutation.isPending}
              onClick={() => metricMutation.mutate()}
            >
              Change metric
            </ProsohmButton>
          </Stack>
        ) : null}

        <Divider />
        <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
          <Typography variant="subtitle1">Schedule</Typography>
          <FormField
            label="Date"
            type="date"
            value={onDate}
            onChange={(event) => setOnDate(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            sx={{ maxWidth: 180 }}
          />
        </Stack>
        {concurrent && scheduleQuery.data ? (
          <ScheduleTimeline blocks={scheduleQuery.data.blocks} capacityLabel="Rights free" />
        ) : null}
        {scheduleQuery.data ? (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Employee</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Window</TableCell>
                <TableCell>Dates</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {[...scheduleQuery.data.scheduled, ...scheduleQuery.data.authorized_only].map((row) => (
                <TableRow key={`${row.kind}-${row.id}`}>
                  <TableCell>{row.user_name || '—'}</TableCell>
                  <TableCell>
                    {row.kind === 'reservation'
                      ? 'Reservation'
                      : row.window === 'Unscheduled'
                        ? 'Authorized (no right consumed)'
                        : 'Allocated'}
                  </TableCell>
                  <TableCell>{row.window}</TableCell>
                  <TableCell>{row.dates}</TableCell>
                </TableRow>
              ))}
              {!scheduleQuery.data.scheduled.length && !scheduleQuery.data.authorized_only.length ? (
                <TableRow>
                  <TableCell colSpan={4}>No active assignments.</TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        ) : null}

        {concurrent ? (
          <>
            <Divider />
            <Typography variant="subtitle1">Active usage (check-out / release)</Typography>
            {canManage ? (
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ alignItems: 'flex-start' }}>
                <FormSelect
                  label="Authorized employee"
                  value={checkoutUser}
                  onChange={(event) => setCheckoutUser(String(event.target.value))}
                  options={authorizedOptions}
                  sx={{ minWidth: 260 }}
                />
                <ProsohmButton
                  buttonVariant="primary"
                  disabled={!checkoutUser}
                  loading={checkoutMutation.isPending}
                  onClick={() => checkoutMutation.mutate()}
                >
                  Check out
                </ProsohmButton>
              </Stack>
            ) : null}
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Employee</TableCell>
                  <TableCell>Checked out</TableCell>
                  <TableCell>Released</TableCell>
                  <TableCell>Source</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {(sessionsQuery.data ?? []).map((s) => (
                  <TableRow key={s.id}>
                    <TableCell>{s.user_name || '—'}</TableCell>
                    <TableCell>{formatDate(s.checked_out_at)} {s.checked_out_at.slice(11, 16)}</TableCell>
                    <TableCell>
                      {s.checked_in_at ? `${formatDate(s.checked_in_at)} ${s.checked_in_at.slice(11, 16)}` : 'In use'}
                    </TableCell>
                    <TableCell>{s.source}</TableCell>
                    <TableCell align="right">
                      {canManage && s.is_active ? (
                        <ProsohmButton
                          size="small"
                          buttonVariant="secondary"
                          loading={checkinMutation.isPending}
                          onClick={() => checkinMutation.mutate(s.id)}
                        >
                          Release
                        </ProsohmButton>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
                {!(sessionsQuery.data ?? []).length ? (
                  <TableRow>
                    <TableCell colSpan={5}>No usage sessions recorded.</TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </>
        ) : null}
      </DialogContent>
      <DialogActions>
        <ProsohmButton buttonVariant="outlined" onClick={onClose}>
          Close
        </ProsohmButton>
      </DialogActions>
    </Dialog>
  );
}
