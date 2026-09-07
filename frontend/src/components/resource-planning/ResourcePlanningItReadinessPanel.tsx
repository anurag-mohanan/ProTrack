import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import {
  fetchResourceItGaps,
  fetchResourceItMatrix,
  resourcePlanningQueryKeys,
} from '../../api/resourcePlanning';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';
import { DashboardPanel, KpiMetricCard } from '../ui/design-system';
import { KpiStrip } from '../analytics/KpiStrip';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';
import DevicesRoundedIcon from '@mui/icons-material/DevicesRounded';
import VerifiedUserRoundedIcon from '@mui/icons-material/VerifiedUserRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import Inventory2RoundedIcon from '@mui/icons-material/Inventory2Rounded';

type DatePreset = 'today' | 'week' | 'month';

type Props = {
  teamId?: string;
};

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function addDaysIso(base: string, days: number): string {
  const d = new Date(`${base}T12:00:00`);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function rangeForPreset(preset: DatePreset): { from: string; to: string; on: string } {
  const on = todayIso();
  if (preset === 'today') return { from: on, to: on, on };
  if (preset === 'week') return { from: on, to: addDaysIso(on, 6), on };
  return { from: on, to: addDaysIso(on, 29), on };
}

export function ResourcePlanningItReadinessPanel({ teamId }: Props) {
  const [preset, setPreset] = useState<DatePreset>('today');
  const range = useMemo(() => rangeForPreset(preset), [preset]);

  const gapsQuery = useQuery({
    queryKey: resourcePlanningQueryKeys.itGaps({ team_id: teamId, on_date: range.on }),
    queryFn: () => fetchResourceItGaps({ team_id: teamId, on_date: range.on }),
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  const matrixQuery = useQuery({
    queryKey: resourcePlanningQueryKeys.itMatrix({
      team_id: teamId,
      from_date: range.from,
      to_date: range.to,
    }),
    queryFn: () =>
      fetchResourceItMatrix({
        team_id: teamId,
        from_date: range.from,
        to_date: range.to,
      }),
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  if (gapsQuery.isLoading || matrixQuery.isLoading) {
    return <LoadingState message="Loading IT readiness…" />;
  }
  if (gapsQuery.error) return <ErrorState error={gapsQuery.error} />;
  if (matrixQuery.error) return <ErrorState error={matrixQuery.error} />;

  const gaps = gapsQuery.data;
  const matrix = matrixQuery.data;
  if (!gaps || !matrix) return null;

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
        {(
          [
            ['today', 'Today'],
            ['week', 'Next 7 days'],
            ['month', 'Next 30 days'],
          ] as const
        ).map(([key, label]) => (
          <Chip
            key={key}
            label={label}
            color={preset === key ? 'primary' : 'default'}
            variant={preset === key ? 'filled' : 'outlined'}
            onClick={() => setPreset(key)}
          />
        ))}
      </Stack>

      <KpiStrip columns={4}>
        <KpiMetricCard
          compact
          title="IT ready"
          value={`${matrix.ready_count}/${matrix.headcount}`}
          icon={VerifiedUserRoundedIcon}
          accent="success"
        />
        <KpiMetricCard
          compact
          title="Not ready"
          value={String(matrix.not_ready_count)}
          icon={WarningAmberRoundedIcon}
          accent={matrix.not_ready_count > 0 ? 'warning' : 'success'}
        />
        <KpiMetricCard
          compact
          title="No computer"
          value={String(gaps.users_without_computer.length)}
          icon={DevicesRoundedIcon}
          accent={gaps.users_without_computer.length > 0 ? 'error' : 'success'}
        />
        <KpiMetricCard
          compact
          title="Spare computers"
          value={`${gaps.spare_computers}/${gaps.total_computers}`}
          icon={Inventory2RoundedIcon}
          accent="info"
        />
      </KpiStrip>

      <DashboardPanel title="Insights" subtitle="Read-only signals from IT Operations">
        <Stack spacing={1}>
          {(gaps.alerts ?? []).length === 0 ? (
            <Alert severity="success">No IT readiness alerts for this scope.</Alert>
          ) : (
            gaps.alerts.map((alert) => (
              <Alert
                key={`${alert.code}-${alert.message}`}
                severity={
                  alert.severity === 'error'
                    ? 'error'
                    : alert.severity === 'warning'
                      ? 'warning'
                      : alert.severity === 'success'
                        ? 'success'
                        : 'info'
                }
              >
                {alert.message}
                {alert.count > 0 ? ` (${alert.count})` : ''}
              </Alert>
            ))
          )}
        </Stack>
      </DashboardPanel>

      <DashboardPanel
        title="People × IT readiness"
        subtitle={`${range.from} → ${range.to}`}
      >
        <Box sx={{ overflowX: 'auto' }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Person</TableCell>
                <TableCell>Team</TableCell>
                <TableCell>Computer</TableCell>
                <TableCell>Licenses</TableCell>
                <TableCell>Missing</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {matrix.rows.map((row) => (
                <TableRow key={row.user_id}>
                  <TableCell>
                    <Typography variant="body2">{row.full_name}</Typography>
                    {row.email ? (
                      <Typography variant="caption" color="text.secondary">
                        {row.email}
                      </Typography>
                    ) : null}
                  </TableCell>
                  <TableCell>{row.team_name ?? '—'}</TableCell>
                  <TableCell>
                    {row.has_computer
                      ? row.computer_name || row.asset_number || 'Assigned'
                      : 'None'}
                  </TableCell>
                  <TableCell>
                    {row.licensed_software_count}/{row.required_software_count}
                  </TableCell>
                  <TableCell>
                    {row.missing_software.length
                      ? row.missing_software.slice(0, 3).join(', ')
                      : '—'}
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={row.is_ready ? 'Ready' : 'Gap'}
                      color={row.is_ready ? 'success' : 'warning'}
                      variant="outlined"
                    />
                  </TableCell>
                </TableRow>
              ))}
              {matrix.rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6}>
                    <Typography variant="body2" color="text.secondary">
                      No people in this team scope.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Box>
      </DashboardPanel>

      {(gaps.oversubscribed_software.length > 0 ||
        gaps.expiring_pools.length > 0 ||
        gaps.software_without_pool.length > 0) && (
        <DashboardPanel title="License pressure" subtitle="Seat demand vs pools">
          <Stack spacing={1.5}>
            {gaps.oversubscribed_software.map((row) => (
              <Alert key={`over-${row.software_id}`} severity="warning">
                {row.software_name ?? row.software_id}: shortfall {row.seat_shortfall} seat(s)
                (need {row.required_headcount}, available {row.available_seats})
              </Alert>
            ))}
            {gaps.software_without_pool.map((row) => (
              <Alert key={`pool-${row.software_id}`} severity="info">
                {row.software_name ?? row.software_id}: required by {row.required_headcount}{' '}
                people but no license pool exists.
              </Alert>
            ))}
            {gaps.expiring_pools.map((row) => (
              <Alert key={`exp-${row.pool_id}`} severity="warning">
                {row.software_name ?? row.software_id} pool expires {row.expiry_date}
              </Alert>
            ))}
          </Stack>
        </DashboardPanel>
      )}
    </Stack>
  );
}
