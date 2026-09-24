import { useMemo, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import DevicesRoundedIcon from '@mui/icons-material/DevicesRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import { useQuery } from '@tanstack/react-query';
import {
  fetchComputersByShift,
  fetchWorkstationCapacityForPlanning,
  resourcePlanningQueryKeys,
  type ComputersByShiftReport,
} from '../../api/resourcePlanning';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';
import { DashboardPanel, KpiMetricCard } from '../ui/design-system';
import { KpiStrip } from '../analytics/KpiStrip';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';

type Props = {
  teamId?: string;
};

function ComputerRows({
  rows,
}: {
  rows: ComputersByShiftReport['open_computers'];
}) {
  if (!rows.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        None
      </Typography>
    );
  }
  return (
    <Table size="small">
      <TableHead>
        <TableRow>
          <TableCell>Computer</TableCell>
          <TableCell>Asset</TableCell>
          <TableCell>Current user</TableCell>
          <TableCell>Shift</TableCell>
          <TableCell>Next / other</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.computer_id}>
            <TableCell>
              <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center' }}>
                <Typography sx={{ fontWeight: 600 }}>{row.computer_name}</Typography>
                {row.is_shared_candidate ? (
                  <Chip size="small" label="Shared" color="info" variant="outlined" />
                ) : null}
              </Stack>
            </TableCell>
            <TableCell>{row.asset_number || '—'}</TableCell>
            <TableCell>
              {row.assigned_to_name || 'Open'}
              {row.previous_user_name ? (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  Prev: {row.previous_user_name}
                </Typography>
              ) : null}
            </TableCell>
            <TableCell>{row.current_shift_display || row.current_shift_name || '—'}</TableCell>
            <TableCell>
              {row.other_shift_user_name ? (
                <>
                  <Typography variant="body2">{row.other_shift_user_name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {row.other_shift_display || row.other_shift_name || 'Other shift'}
                  </Typography>
                </>
              ) : row.next_shift_display || row.next_shift_name ? (
                <>
                  <Typography variant="body2">
                    {row.next_shift_display || row.next_shift_name}
                  </Typography>
                  {row.next_change_date ? (
                    <Typography variant="caption" color="text.secondary">
                      from {row.next_change_date}
                    </Typography>
                  ) : null}
                </>
              ) : (
                '—'
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function ResourcePlanningComputersByShiftPanel({ teamId }: Props) {
  const [onDate] = useState(() => new Date().toISOString().slice(0, 10));

  const query = useQuery({
    queryKey: resourcePlanningQueryKeys.computersByShift({ team_id: teamId, on_date: onDate }),
    queryFn: () => fetchComputersByShift({ team_id: teamId, on_date: onDate }),
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  const capacityQuery = useQuery({
    queryKey: resourcePlanningQueryKeys.workstationCapacity({ on_date: onDate }),
    queryFn: () => fetchWorkstationCapacityForPlanning({ on_date: onDate }),
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  const report = query.data;
  const shiftTotals = useMemo(
    () => (report?.shifts ?? []).map((s) => ({ code: s.shift_code, count: s.assigned_count })),
    [report],
  );

  if (query.isLoading) return <LoadingState message="Loading computers by shift…" />;
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  if (!report) return null;

  return (
    <Stack spacing={2}>
      <KpiStrip columns={4}>
        <KpiMetricCard
          compact
          title="Open (any shift)"
          value={String(report.summary.open)}
          icon={DevicesRoundedIcon}
          accent={report.summary.open > 0 ? 'success' : 'primary'}
        />
        <KpiMetricCard
          compact
          title="Assigned w/ shift"
          value={String(report.summary.assigned_with_shift)}
          icon={ScheduleRoundedIcon}
          accent="primary"
        />
        <KpiMetricCard
          compact
          title="Shared candidates"
          value={String(report.summary.shared_candidates)}
          icon={GroupsRoundedIcon}
          accent={report.summary.shared_candidates > 0 ? 'warning' : 'success'}
        />
        <KpiMetricCard
          compact
          title="No shift"
          value={String(report.summary.assigned_without_shift)}
          icon={DevicesRoundedIcon}
          accent={report.summary.assigned_without_shift > 0 ? 'warning' : 'success'}
        />
      </KpiStrip>

      {capacityQuery.data?.length ? (
        <DashboardPanel
          title="Workstation package capacity"
          subtitle="Physical packages available per shift — same inventory as IT"
        >
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Type</TableCell>
                <TableCell align="right">Total</TableCell>
                <TableCell>Shift availability</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {capacityQuery.data
                .filter((row) => row.total > 0)
                .map((row) => (
                  <TableRow key={row.computer_type}>
                    <TableCell>{row.label}</TableCell>
                    <TableCell align="right">{row.total}</TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 0.5 }}>
                        {row.shifts.map((s) => (
                          <Chip
                            key={s.shift_code}
                            size="small"
                            label={`${s.shift_name}: ${s.available} avail`}
                            color={s.available > 0 ? 'success' : 'default'}
                            variant="outlined"
                          />
                        ))}
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
            </TableBody>
          </Table>
        </DashboardPanel>
      ) : null}

      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
        {shiftTotals.map((row) => (
          <Chip
            key={row.code}
            label={`${row.code}: ${row.count}`}
            variant="outlined"
            size="small"
          />
        ))}
        <Chip size="small" label={`Open: ${report.summary.open}`} color="success" variant="outlined" />
      </Stack>

      {(report.shifts ?? []).map((section) => (
        <Accordion
          key={section.shift_code}
          defaultExpanded={section.assigned_count > 0}
          disableGutters
          elevation={0}
          sx={{ border: 1, borderColor: 'divider', borderRadius: 1, '&:before': { display: 'none' } }}
        >
          <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
            <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', width: '100%', pr: 1 }}>
              <Typography sx={{ fontWeight: 700, flex: 1 }}>
                {section.shift_display || section.shift_name}
              </Typography>
              <Chip size="small" label={`${section.assigned_count} assigned`} />
            </Stack>
          </AccordionSummary>
          <AccordionDetails>
            <ComputerRows rows={section.computers} />
          </AccordionDetails>
        </Accordion>
      ))}

      <DashboardPanel title="Open computers" subtitle="Available to any shift — shared pool">
        <ComputerRows rows={report.open_computers} />
      </DashboardPanel>

      {report.shared_computers.length > 0 ? (
        <DashboardPanel
          title="Shared-desk candidates"
          subtitle="Multiple historical users — other-shift peer shown when active today"
        >
          <ComputerRows rows={report.shared_computers} />
        </DashboardPanel>
      ) : null}

      {report.assigned_without_shift.length > 0 ? (
        <DashboardPanel title="Assigned without shift today" subtitle="Needs shift assignment review">
          <ComputerRows rows={report.assigned_without_shift} />
        </DashboardPanel>
      ) : null}
    </Stack>
  );
}
