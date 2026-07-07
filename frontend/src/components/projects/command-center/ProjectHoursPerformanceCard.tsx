import TimerOutlinedIcon from '@mui/icons-material/TimerOutlined';
import { Box, Card, CardContent, LinearProgress, Typography } from '@mui/material';
import { alpha, useTheme, type Theme } from '@mui/material/styles';
import type { DashboardSummary } from '../../../types';
import { designTokens } from '../../../theme/designTokens';
import { formatNumber } from '../../../utils/format';
import {
  calculateEAC,
  forecastVariance,
  hoursPerformanceTone,
  hoursUtilizationPercent,
  type HoursPerformanceTone,
} from '../../../utils/projectHoursMetrics';

interface ProjectHoursPerformanceCardProps {
  summary: DashboardSummary | undefined;
  loading?: boolean;
}

const toneColor = (tone: HoursPerformanceTone, theme: Theme) => {
  if (tone === 'success') return theme.palette.success.main;
  if (tone === 'warning') return theme.palette.warning.main;
  return theme.palette.error.main;
};

export function ProjectHoursPerformanceCard({ summary, loading }: ProjectHoursPerformanceCardProps) {
  const theme = useTheme();
  const unavailable = loading || !summary;

  const quoted = Number(summary?.total_quoted_hours_active ?? 0);
  const actual = Number(summary?.total_actual_hours_productive ?? 0);
  const variance = Number(summary?.hours_variance ?? actual - quoted);
  const progress = Number(summary?.overall_progress_percent ?? 0);
  const utilization = hoursUtilizationPercent(actual, quoted);
  const tone = hoursPerformanceTone(actual, quoted);
  const barColor = toneColor(tone, theme);
  const eac = calculateEAC(actual, progress);
  const forecast = forecastVariance(actual, quoted, progress);

  const varianceLabel =
    unavailable ? '—' : `${variance > 0 ? '+' : ''}${formatNumber(variance, 0)} hrs`;

  return (
    <Card
      elevation={0}
      sx={{
        minHeight: 72,
        borderRadius: `${designTokens.radius.lg}px`,
        boxShadow: designTokens.elevation.card,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: designTokens.semantic.card,
        gridColumn: { xs: '1 / -1', md: 'span 2' },
      }}
    >
      <CardContent sx={{ p: '10px 12px !important', height: '100%' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.75 }}>
          <Box
            sx={{
              width: 24,
              height: 24,
              borderRadius: `${designTokens.radius.sm}px`,
              display: 'grid',
              placeItems: 'center',
              bgcolor: alpha(barColor, 0.12),
              color: barColor,
              flexShrink: 0,
            }}
          >
            <TimerOutlinedIcon sx={{ fontSize: 15 }} />
          </Box>
          <Typography sx={{ fontSize: 12, fontWeight: 700, color: 'text.secondary' }}>
            Project Hours
          </Typography>
        </Box>

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', sm: 'repeat(4, minmax(0, 1fr))' },
            gap: 1,
            mb: 0.75,
          }}
        >
          <MetricLine label="Quoted" value={unavailable ? '—' : `${formatNumber(quoted, 0)} hrs`} />
          <MetricLine label="Actual" value={unavailable ? '—' : `${formatNumber(actual, 0)} hrs`} />
          <MetricLine
            label="Variance"
            value={varianceLabel}
            valueColor={unavailable ? undefined : barColor}
          />
          {eac != null && !unavailable ? (
            <MetricLine
              label="Projected"
              value={`${formatNumber(eac, 0)} hrs`}
              hint={
                forecast != null
                  ? `${forecast > 0 ? '+' : ''}${formatNumber(forecast, 0)} forecast`
                  : undefined
              }
            />
          ) : (
            <MetricLine label="Progress" value={unavailable ? '—' : `${formatNumber(progress, 0)}%`} />
          )}
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <LinearProgress
            variant="determinate"
            value={unavailable ? 0 : utilization}
            sx={{
              flex: 1,
              height: 5,
              borderRadius: designTokens.radius.pill,
              bgcolor: designTokens.semantic.neutralSoft,
              '& .MuiLinearProgress-bar': {
                borderRadius: designTokens.radius.pill,
                bgcolor: barColor,
              },
            }}
          />
          <Typography sx={{ fontSize: 11, fontWeight: 700, color: 'text.secondary', minWidth: 36 }}>
            {unavailable ? '—' : `${formatNumber(utilization, 0)}%`}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
}

function MetricLine({
  label,
  value,
  valueColor,
  hint,
}: {
  label: string;
  value: string;
  valueColor?: string;
  hint?: string;
}) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography sx={{ fontSize: 10, fontWeight: 600, color: 'text.secondary', lineHeight: 1.2 }}>
        {label}
      </Typography>
      <Typography
        sx={{
          fontSize: 13,
          fontWeight: 800,
          lineHeight: 1.2,
          color: valueColor ?? 'text.primary',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {value}
      </Typography>
      {hint ? (
        <Typography sx={{ fontSize: 10, color: 'text.secondary', lineHeight: 1.2 }}>
          {hint}
        </Typography>
      ) : null}
    </Box>
  );
}
