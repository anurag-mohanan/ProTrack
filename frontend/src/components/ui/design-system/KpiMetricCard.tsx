import { Box, Card, CardContent, Typography } from '@mui/material';
import TrendingDownRoundedIcon from '@mui/icons-material/TrendingDownRounded';
import TrendingFlatRoundedIcon from '@mui/icons-material/TrendingFlatRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import { alpha, useTheme } from '@mui/material/styles';
import type { SvgIconComponent } from '@mui/icons-material';
import { designTokens } from '../../../theme/designTokens';

export type KpiAccent = 'primary' | 'warning' | 'error' | 'success' | 'info';

interface KpiMetricCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: SvgIconComponent;
  onClick?: () => void;
  selected?: boolean;
  accent?: KpiAccent;
  compact?: boolean;
  trend?: { value: string; direction?: 'up' | 'down' | 'flat' };
}

const accentKeys: KpiAccent[] = ['primary', 'warning', 'error', 'success', 'info'];

export function KpiMetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  onClick,
  selected = false,
  accent,
  compact = false,
  trend,
}: KpiMetricCardProps) {
  const theme = useTheme();
  const iconAccent = accent ?? 'primary';
  const paletteKey = accentKeys.includes(iconAccent) ? iconAccent : 'primary';
  const iconBackground = accent
    ? alpha(theme.palette[paletteKey].main, 0.1)
    : designTokens.semantic.neutralSoft;
  const iconForeground = accent ? theme.palette[paletteKey].main : theme.palette.text.secondary;

  const TrendIcon =
    trend?.direction === 'up'
      ? TrendingUpRoundedIcon
      : trend?.direction === 'down'
        ? TrendingDownRoundedIcon
        : TrendingFlatRoundedIcon;

  return (
    <Card
      onClick={onClick}
      elevation={0}
      sx={{
        minHeight: compact ? 108 : 124,
        cursor: onClick ? 'pointer' : 'default',
        borderRadius: `${designTokens.radius.lg}px`,
        boxShadow: selected ? designTokens.elevation.cardHover : designTokens.elevation.card,
        border: '1px solid',
        borderColor: selected ? 'primary.main' : 'divider',
        bgcolor: selected ? alpha(theme.palette.primary.main, 0.04) : designTokens.semantic.card,
        transition: `box-shadow ${designTokens.motion.normal}, transform ${designTokens.motion.normal}, border-color ${designTokens.motion.fast}`,
        '&:hover': onClick
          ? {
              transform: 'translateY(-3px)',
              boxShadow: designTokens.elevation.cardHover,
            }
          : undefined,
      }}
    >
      <CardContent sx={{ p: '20px !important', height: '100%' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2 }}>
          <Box
            sx={{
              width: 44,
              height: 44,
              borderRadius: `${designTokens.radius.md}px`,
              display: 'grid',
              placeItems: 'center',
              bgcolor: iconBackground,
              color: iconForeground,
              flexShrink: 0,
            }}
          >
            <Icon sx={{ fontSize: 22 }} />
          </Box>
          {trend ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
              <TrendIcon sx={{ fontSize: 16 }} />
              <Typography variant="caption" sx={{ fontWeight: 700 }}>
                {trend.value}
              </Typography>
            </Box>
          ) : null}
        </Box>
        <Typography
          sx={{
            fontSize: 13,
            fontWeight: 600,
            color: 'text.secondary',
            mt: 1.5,
            letterSpacing: '0.01em',
          }}
        >
          {title}
        </Typography>
        <Typography
          sx={{
            fontSize: compact ? 30 : 34,
            fontWeight: 800,
            lineHeight: 1.05,
            letterSpacing: '-0.03em',
            my: 0.5,
          }}
        >
          {value}
        </Typography>
        {subtitle ? (
          <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.3 }}>
            {subtitle}
          </Typography>
        ) : null}
      </CardContent>
    </Card>
  );
}
