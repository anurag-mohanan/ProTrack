import { Box, Divider, Typography } from '@mui/material';
import type { TimesheetStatus } from '../../types/common';
import { TimesheetStatusChip } from '../common/StatusChip';
import type { TimesheetMonthSummary } from '../../utils/timesheetMonth';
import { formatNumber } from '../../utils/format';

interface TimesheetMonthSummaryBarProps {
  status: TimesheetStatus | 'draft';
  summary: TimesheetMonthSummary;
}

function InlineMetric({ label, value }: { label: string; value: string }) {
  return (
    <Typography variant="body2" component="span" sx={{ whiteSpace: 'nowrap' }}>
      <Typography component="span" variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>
        {label}
      </Typography>
      <Typography component="span" sx={{ fontWeight: 700 }}>
        {value}
      </Typography>
    </Typography>
  );
}

export function TimesheetMonthSummaryBar({ status, summary }: TimesheetMonthSummaryBarProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 1.5,
        px: 1.5,
        py: 1,
        mb: 2,
        borderRadius: 2,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
      }}
    >
      <TimesheetStatusChip status={status} />
      <Divider orientation="vertical" flexItem sx={{ display: { xs: 'none', md: 'block' } }} />
      <InlineMetric label="Expected" value={formatNumber(summary.expectedHours, 0)} />
      <InlineMetric label="Entered" value={formatNumber(summary.enteredHours, 0)} />
      <InlineMetric label="Remaining" value={formatNumber(summary.remainingHours, 0)} />
      <InlineMetric label="Billable" value={formatNumber(summary.billableHours, 0)} />
      <InlineMetric label="NP" value={formatNumber(summary.nonProductiveHours, 0)} />
      <InlineMetric
        label="Efficiency"
        value={summary.efficiencyPercent === null ? '—' : `${summary.efficiencyPercent}%`}
      />
    </Box>
  );
}
