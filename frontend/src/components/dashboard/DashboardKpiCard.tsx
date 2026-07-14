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
        minHeight: 92,
        width: '100%',
        height: '100%',
        cursor: onClick ? 'pointer' : 'default',
        borderRadius: `${designTokens.radius.md}px`,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: designTokens.semantic.card,
        boxShadow: '0 1px 3px rgba(15, 23, 42, 0.06)',
        transition: `transform ${designTokens.motion.fast}, box-shadow ${designTokens.motion.fast}, border-color ${designTokens.motion.fast}`,
        '&:hover': onClick
          ? {
              transform: 'translateY(-2px)',
              boxShadow: designTokens.elevation.cardHover,
              borderColor: alpha(accentColor, 0.35),
              bgcolor: alpha(accentColor, 0.03),
            }
          : undefined,
      }}
    >
      <CardContent sx={{ p: '10px 12px !important', '&:last-child': { pb: '10px !important' } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 0.5 }}>
          <Box
            sx={{
              width: 28,
              height: 28,
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              bgcolor: alpha(accentColor, 0.1),
              flexShrink: 0,
            }}
          >
            <Icon sx={{ fontSize: 16, color: accentColor }} />
          </Box>
          {trend ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.15 }}>
              <TrendIcon sx={{ fontSize: 12, color: trendColor }} />
            </Box>
          ) : null}
        </Box>
        <Typography
          sx={{
            fontSize: 11,
            fontWeight: 700,
            color: 'text.secondary',
            lineHeight: 1.2,
            mt: 0.75,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {title}
        </Typography>
        <Typography
          sx={{
            fontSize: 20,
            fontWeight: 800,
            lineHeight: 1.15,
            letterSpacing: '-0.02em',
            mt: 0.35,
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
