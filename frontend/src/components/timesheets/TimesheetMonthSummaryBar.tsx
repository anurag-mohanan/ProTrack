import { Box, Divider, Typography } from '@mui/material';
import type { TimesheetStatus } from '../../types/common';
import { TimesheetStatusChip } from '../common/StatusChip';
import type { TimesheetMonthSummary } from '../../utils/timesheetMonth';
import { designTokens } from '../../theme/designTokens';
import { formatNumber } from '../../utils/format';

interface TimesheetMonthSummaryBarProps {
  status: TimesheetStatus | 'draft';
  summary: TimesheetMonthSummary;
  todayHours?: number;
  weeklyTotal?: number;
}

function MetricCard({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <Box
      sx={{
        px: 1.5,
        py: 1,
        borderRadius: `${designTokens.radius.md}px`,
        bgcolor: accent ? `${accent}14` : designTokens.semantic.neutralSoft,
        minWidth: 88,
      }}
    >
      <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, display: 'block' }}>
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 800, fontSize: '1.05rem', color: accent ?? 'text.primary' }}>
        {value}
      </Typography>
    </Box>
  );
}

export function TimesheetMonthSummaryBar({
  status,
  summary,
  todayHours = 0,
  weeklyTotal,
}: TimesheetMonthSummaryBarProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 1.5,
        px: 2,
        py: 1.5,
        mb: 2,
        borderRadius: `${designTokens.radius.lg}px`,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: designTokens.semantic.card,
        boxShadow: designTokens.elevation.card,
      }}
    >
      <TimesheetStatusChip status={status} />
      <Divider orientation="vertical" flexItem sx={{ display: { xs: 'none', md: 'block' } }} />
      <MetricCard label="Today" value={formatNumber(todayHours, 1)} accent={designTokens.semantic.primary} />
      <MetricCard label="Billable" value={formatNumber(summary.billableHours, 1)} accent={designTokens.semantic.success} />
      <MetricCard label="Non-Productive" value={formatNumber(summary.nonProductiveHours, 1)} accent={designTokens.semantic.warning} />
      <MetricCard label="Leave" value={formatNumber(summary.leaveDays, 0)} accent={designTokens.semantic.primary} />
      {weeklyTotal !== undefined ? (
        <MetricCard label="Weekly Total" value={formatNumber(weeklyTotal, 1)} />
      ) : null}
      <MetricCard label="Monthly Total" value={formatNumber(summary.enteredHours, 1)} />
      <MetricCard
        label="Remaining"
        value={formatNumber(summary.remainingHours, 1)}
        accent={summary.remainingHours < 0 ? designTokens.semantic.danger : undefined}
      />
      <MetricCard
        label="Efficiency"
        value={summary.efficiencyPercent === null ? '—' : `${summary.efficiencyPercent}%`}
      />
    </Box>
  );
}
