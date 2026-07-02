import { Box, Grid, Typography } from '@mui/material';
import type { TimesheetStatus } from '../../types/common';
import { TimesheetStatusChip } from '../common/StatusChip';
import type { TimesheetMonthSummary } from '../../utils/timesheetMonth';
import { formatNumber } from '../../utils/format';

interface TimesheetMonthSummaryBarProps {
  monthLabel: string;
  status: TimesheetStatus | 'draft';
  summary: TimesheetMonthSummary;
}

function Metric({ label, value, emphasize }: { label: string; value: string; emphasize?: boolean }) {
  return (
    <Box
      sx={{
        p: 1.5,
        borderRadius: 2,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        minWidth: 0,
      }}
    >
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {label}
      </Typography>
      <Typography
        variant={emphasize ? 'h6' : 'subtitle1'}
        sx={{ fontWeight: emphasize ? 700 : 600, whiteSpace: 'nowrap' }}
      >
        {value}
      </Typography>
    </Box>
  );
}

export function TimesheetMonthSummaryBar({
  monthLabel,
  status,
  summary,
}: TimesheetMonthSummaryBarProps) {
  return (
    <Box sx={{ mb: 2 }}>
      <Grid container spacing={1.5}>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <Box
            sx={{
              p: 1.5,
              borderRadius: 2,
              border: 1,
              borderColor: 'divider',
              bgcolor: 'background.paper',
              height: '100%',
            }}
          >
            <Typography variant="caption" color="text.secondary">
              Status
            </Typography>
            <Box sx={{ mt: 0.5 }}>
              <TimesheetStatusChip status={status} />
            </Box>
          </Box>
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <Metric label="Expected Hours" value={formatNumber(summary.expectedHours, 1)} emphasize />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <Metric label="Entered" value={formatNumber(summary.enteredHours, 1)} emphasize />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <Metric
            label="Remaining"
            value={formatNumber(summary.remainingHours, 1)}
            emphasize
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <Metric label="Billable" value={formatNumber(summary.billableHours, 1)} />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <Metric label="Non Productive" value={formatNumber(summary.nonProductiveHours, 1)} />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <Metric
            label="Efficiency"
            value={
              summary.efficiencyPercent === null ? '—' : `${summary.efficiencyPercent}%`
            }
          />
        </Grid>
      </Grid>
      <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
        Summary for {monthLabel}
      </Typography>
    </Box>
  );
}
