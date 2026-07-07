import TimerOutlinedIcon from '@mui/icons-material/TimerOutlined';
import { Box, Card, CardContent, Typography } from '@mui/material';
import { alpha, useTheme, type Theme } from '@mui/material/styles';
import type { DashboardSummary } from '../../../types';
import { designTokens } from '../../../theme/designTokens';
import { formatNumber } from '../../../utils/format';
import {
  formatHoursOverPercent,
  hoursBurnPercent,
  hoursUtilizationTone,
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
  const burnPct = hoursBurnPercent(actual, quoted);
  const tone = hoursUtilizationTone(actual, quoted);
  const accent = toneColor(tone, theme);
  const overLabel = formatHoursOverPercent(actual, quoted);
  const barValue = actual <= quoted ? Math.min(100, burnPct) : 100;

  return (
    <Card
      elevation={0}
      sx={{
        minHeight: 58,
        maxWidth: 220,
        borderRadius: `${designTokens.radius.lg}px`,
        boxShadow: designTokens.elevation.card,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: designTokens.semantic.card,
      }}
    >
      <CardContent sx={{ p: '8px 10px !important', height: '100%' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
          <Box
            sx={{
              width: 18,
              height: 18,
              borderRadius: `${designTokens.radius.sm}px`,
              display: 'grid',
              placeItems: 'center',
              bgcolor: alpha(accent, 0.12),
              color: accent,
              flexShrink: 0,
            }}
          >
            <TimerOutlinedIcon sx={{ fontSize: 12 }} />
          </Box>
          <Typography sx={{ fontSize: 11, fontWeight: 700, color: 'text.secondary' }}>
            Hours
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', gap: 1.5, mb: 0.5 }}>
          <Box>
            <Typography sx={{ fontSize: 9, fontWeight: 600, color: 'text.secondary', lineHeight: 1.1 }}>
              Quoted
            </Typography>
            <Typography sx={{ fontSize: 12, fontWeight: 800, lineHeight: 1.2, fontVariantNumeric: 'tabular-nums' }}>
              {unavailable ? '—' : formatNumber(quoted, 0)}
            </Typography>
          </Box>
          <Box>
            <Typography sx={{ fontSize: 9, fontWeight: 600, color: 'text.secondary', lineHeight: 1.1 }}>
              Actual
            </Typography>
            <Typography sx={{ fontSize: 12, fontWeight: 800, lineHeight: 1.2, fontVariantNumeric: 'tabular-nums' }}>
              {unavailable ? '—' : formatNumber(actual, 0)}
            </Typography>
          </Box>
          <Box sx={{ ml: 'auto', textAlign: 'right' }}>
            <Typography
              sx={{
                fontSize: 16,
                fontWeight: 800,
                lineHeight: 1.1,
                color: accent,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {unavailable ? '—' : `${formatNumber(Math.round(burnPct), 0)}%`}
            </Typography>
            {overLabel ? (
              <Typography sx={{ fontSize: 9, fontWeight: 700, color: accent, lineHeight: 1.1 }}>
                {overLabel}
              </Typography>
            ) : null}
          </Box>
        </Box>

        <Box
          sx={{
            height: 4,
            borderRadius: designTokens.radius.pill,
            bgcolor: designTokens.semantic.neutralSoft,
            overflow: 'hidden',
          }}
        >
          <Box
            sx={{
              width: `${barValue}%`,
              height: '100%',
              bgcolor: accent,
              borderRadius: designTokens.radius.pill,
              transition: `width ${designTokens.motion.normal}`,
            }}
          />
        </Box>
      </CardContent>
    </Card>
  );
}
