import { Box, Card, CardContent, Typography } from '@mui/material';
import TrendingDownRoundedIcon from '@mui/icons-material/TrendingDownRounded';
import TrendingFlatRoundedIcon from '@mui/icons-material/TrendingFlatRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import { alpha, useTheme } from '@mui/material/styles';
import type { SvgIconComponent } from '@mui/icons-material';
import { designTokens } from '../../theme/designTokens';
import type { KpiAccent } from '../ui/design-system/KpiMetricCard';

export interface DashboardKpiTrend {
  value: string;
  direction?: 'up' | 'down' | 'flat';
}

export interface DashboardKpiCardProps {
  title: string;
  value: string;
  icon: SvgIconComponent;
  onClick?: () => void;
  accent?: KpiAccent;
  trend?: DashboardKpiTrend;
}

const accentKeys: KpiAccent[] = ['primary', 'warning', 'error', 'success', 'info'];

export function DashboardKpiCard({
  title,
  value,
  icon: Icon,
  onClick,
  accent = 'primary',
  trend,
}: DashboardKpiCardProps) {
  const theme = useTheme();
  const paletteKey = accentKeys.includes(accent) ? accent : 'primary';
  const accentColor = theme.palette[paletteKey].main;

  const TrendIcon =
    trend?.direction === 'up'
      ? TrendingUpRoundedIcon
      : trend?.direction === 'down'
        ? TrendingDownRoundedIcon
        : TrendingFlatRoundedIcon;

  const trendColor =
    trend?.direction === 'up'
      ? theme.palette.success.main
      : trend?.direction === 'down'
        ? theme.palette.error.main
        : theme.palette.text.secondary;

  return (
    <Card
      onClick={onClick}
      elevation={0}
      sx={{
        minHeight: 52,
        height: '100%',
        cursor: onClick ? 'pointer' : 'default',
        borderRadius: `${designTokens.radius.md}px`,
        border: '1px solid',
        borderColor: 'divider',
        borderLeft: `3px solid ${accentColor}`,
        bgcolor: designTokens.semantic.card,
        boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04)',
        transition: `box-shadow ${designTokens.motion.fast}, border-color ${designTokens.motion.fast}, background-color ${designTokens.motion.fast}`,
        '&:hover': onClick
          ? {
              boxShadow: designTokens.elevation.cardHover,
              bgcolor: alpha(accentColor, 0.03),
            }
          : undefined,
      }}
    >
      <CardContent sx={{ p: '6px 8px !important', '&:last-child': { pb: '6px !important' } }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 0.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4, minWidth: 0, flex: 1 }}>
            <Icon sx={{ fontSize: 13, color: accentColor, flexShrink: 0 }} />
            <Typography
              sx={{
                fontSize: 10,
                fontWeight: 700,
                color: 'text.secondary',
                lineHeight: 1.2,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {title}
            </Typography>
          </Box>
          {trend ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.15, flexShrink: 0 }}>
              <TrendIcon sx={{ fontSize: 11, color: trendColor }} />
              <Typography sx={{ fontSize: 9, fontWeight: 700, color: trendColor, lineHeight: 1 }}>
                {trend.value}
              </Typography>
            </Box>
          ) : (
            <Box sx={{ width: 28, flexShrink: 0 }} />
          )}
        </Box>
        <Typography
          sx={{
            fontSize: 17,
            fontWeight: 800,
            lineHeight: 1.15,
            letterSpacing: '-0.02em',
            mt: 0.25,
            fontVariantNumeric: 'tabular-nums',
          }}
          noWrap
        >
          {value}
        </Typography>
      </CardContent>
    </Card>
  );
}
