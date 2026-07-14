import { Box, Divider, LinearProgress, Tooltip, Typography } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import type { TimesheetStatus } from '../../types/common';
import { TimesheetStatusChip } from '../common/StatusChip';
import type { TimesheetMonthSummary } from '../../utils/timesheetMonth';
import { designTokens } from '../../theme/designTokens';
import { formatNumber } from '../../utils/format';

interface TimesheetMonthSummaryBarProps {
  status: TimesheetStatus | 'draft';
  summary: TimesheetMonthSummary;
  todayHours?: number;
  todayExpected?: number;
  weeklyHours?: number;
  weeklyExpected?: number;
  scopeLabel?: string;
  sx?: SxProps<Theme>;
}

function toPercent(value: number, target: number): number | null {
  if (target <= 0) return null;
  return Math.round((value / target) * 100);
}

function progressColor(percent: number | null): string {
  if (percent === null) return designTokens.semantic.primary;
  if (percent >= 100) return designTokens.semantic.success;
  if (percent >= 60) return designTokens.semantic.primary;
  return designTokens.semantic.warning;
}

function ProgressStat({
  label,
  value,
  target,
  unit = 'hrs',
  tooltip,
}: {
  label: string;
  value: number;
  target?: number;
  unit?: string;
  tooltip?: string;
}) {
  const hasTarget = target !== undefined && target > 0;
  const percent = hasTarget ? toPercent(value, target!) : null;
  const barValue = percent === null ? 0 : Math.min(100, percent);
  const accent = progressColor(percent);

  const content = (
    <Box
      sx={{
        px: 1.5,
        py: 1,
        borderRadius: `${designTokens.radius.md}px`,
        bgcolor: designTokens.semantic.neutralSoft,
        minWidth: 128,
        flex: '1 1 128px',
      }}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 1 }}>
        <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
          {label}
        </Typography>
        {percent !== null ? (
          <Typography sx={{ fontWeight: 800, fontSize: '0.72rem', color: accent }}>
            {percent}%
          </Typography>
        ) : null}
      </Box>
      <Typography sx={{ fontWeight: 800, fontSize: '1.05rem', lineHeight: 1.2 }}>
        {formatNumber(value, 1)}
        {hasTarget ? (
          <Typography component="span" sx={{ fontWeight: 600, fontSize: '0.8rem', color: 'text.secondary' }}>
            {' '}
            / {formatNumber(target!, 0)} {unit}
          </Typography>
        ) : (
          <Typography component="span" sx={{ fontWeight: 600, fontSize: '0.8rem', color: 'text.secondary' }}>
            {' '}
            {unit}
          </Typography>
        )}
      </Typography>
      {hasTarget ? (
        <LinearProgress
          variant="determinate"
          value={barValue}
          sx={{
            mt: 0.5,
            height: 4,
            borderRadius: designTokens.radius.pill,
            bgcolor: designTokens.semantic.neutralSoft,
            '& .MuiLinearProgress-bar': {
              borderRadius: designTokens.radius.pill,
              bgcolor: accent,
            },
          }}
        />
      ) : null}
    </Box>
  );

  return tooltip ? <Tooltip title={tooltip}>{content}</Tooltip> : content;
}

function MetricCard({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <Box
      sx={{
        px: 1.5,
        py: 1,
        borderRadius: `${designTokens.radius.md}px`,
        bgcolor: accent ? `${accent}14` : designTokens.semantic.neutralSoft,
        minWidth: 92,
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
  todayExpected,
  weeklyHours = 0,
  weeklyExpected,
  scopeLabel,
  sx,
}: TimesheetMonthSummaryBarProps) {
  const remainingHours = Math.max(0, summary.remainingHours);
  const leaveLabel =
    summary.leaveDays > 0
      ? `${formatNumber(summary.leaveDays, summary.leaveDays % 1 === 0 ? 0 : 1)} ${summary.leaveDays === 1 ? 'Day' : 'Days'}`
      : '0 Days';

  return (
    <Box
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'stretch',
        gap: 1.5,
        px: 2,
        py: 1.5,
        mb: 2,
        borderRadius: `${designTokens.radius.lg}px`,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: designTokens.semantic.card,
        boxShadow: designTokens.elevation.card,
        ...sx,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <TimesheetStatusChip status={status} />
        {scopeLabel ? (
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
            {scopeLabel}
          </Typography>
        ) : null}
      </Box>
      <Divider orientation="vertical" flexItem sx={{ display: { xs: 'none', md: 'block' } }} />

      <ProgressStat
        label="Today"
        value={todayHours}
        target={todayExpected}
        tooltip="Hours logged today vs your expected working hours."
      />
      <ProgressStat
        label="Weekly"
        value={weeklyHours}
        target={weeklyExpected}
        tooltip="Hours logged this week vs expected working hours."
      />
      <ProgressStat
        label="Monthly"
        value={summary.enteredHours}
        target={summary.expectedHours}
        tooltip="Worked hours this month (excludes leave) vs expected."
      />
      <ProgressStat
        label="Remaining"
        value={remainingHours}
        target={summary.expectedHours}
        tooltip="Expected working hours still to be logged this month."
      />

      <Divider orientation="vertical" flexItem sx={{ display: { xs: 'none', lg: 'block' } }} />

      <MetricCard label="Billable" value={formatNumber(summary.billableHours, 1)} accent={designTokens.semantic.success} />
      <MetricCard label="Non-Productive" value={formatNumber(summary.nonProductiveHours, 1)} accent={designTokens.semantic.warning} />
      <MetricCard label="Leave" value={leaveLabel} accent={designTokens.semantic.primary} />
      <MetricCard
        label="Efficiency"
        value={summary.efficiencyPercent === null ? '—' : `${summary.efficiencyPercent}%`}
      />
    </Box>
  );
}
