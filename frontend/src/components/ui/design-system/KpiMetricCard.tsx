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
  /** Ultra-compact horizontal layout for command-center KPI strips. */
  dense?: boolean;
  trend?: { value: string; direction?: 'up' | 'down' | 'flat' };
}

const accentKeys: KpiAccent[] = ['primary', 'warning', 'error', 'success', 'info'];

function displayValue(value: string): string {
  const trimmed = value?.trim?.() ?? '';
  return trimmed.length ? trimmed : '0';
}

export function KpiMetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  onClick,
  selected = false,
  accent,
  compact = false,
  dense = false,
  trend,
}: KpiMetricCardProps) {
  const theme = useTheme();
  const iconAccent = accent ?? 'primary';
  const paletteKey = accentKeys.includes(iconAccent) ? iconAccent : 'primary';
  const iconBackground = accent
    ? alpha(theme.palette[paletteKey].main, 0.1)
    : designTokens.semantic.neutralSoft;
  const iconForeground = accent ? theme.palette[paletteKey].main : theme.palette.text.secondary;
  const shown = displayValue(value);

  const TrendIcon =
    trend?.direction === 'up'
      ? TrendingUpRoundedIcon
      : trend?.direction === 'down'
        ? TrendingDownRoundedIcon
        : TrendingFlatRoundedIcon;

  if (dense) {
    return (
      <Card
        onClick={onClick}
        elevation={0}
        sx={{
          position: 'relative',
          width: '100%',
          minHeight: 56,
          height: '100%',
          cursor: onClick ? 'pointer' : 'default',
          borderRadius: `${designTokens.radius.lg}px`,
          boxShadow: selected ? designTokens.elevation.cardHover : designTokens.elevation.card,
          border: '1.5px solid',
          borderColor: selected ? 'primary.main' : 'divider',
          bgcolor: selected ? alpha(theme.palette.primary.main, 0.08) : designTokens.semantic.card,
          transition: `box-shadow ${designTokens.motion.normal}, border-color ${designTokens.motion.normal}, background-color ${designTokens.motion.normal}`,
          overflow: 'hidden',
          '&:hover': onClick
            ? {
                boxShadow: designTokens.elevation.cardHover,
                borderColor: selected ? 'primary.main' : alpha(theme.palette.primary.main, 0.35),
              }
            : undefined,
          '&::after': selected
            ? {
                content: '""',
                position: 'absolute',
                left: 0,
                right: 0,
                bottom: 0,
                height: 3,
                bgcolor: 'primary.main',
                transition: `opacity ${designTokens.motion.fast}`,
              }
            : undefined,
        }}
      >
        <CardContent sx={{ p: '8px 10px !important', height: '100%' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 0 }}>
            <Box
              sx={{
                width: 18,
                height: 18,
                borderRadius: `${designTokens.radius.sm}px`,
                display: 'grid',
                placeItems: 'center',
                bgcolor: iconBackground,
                color: iconForeground,
                flexShrink: 0,
              }}
            >
              <Icon sx={{ fontSize: 12 }} />
            </Box>
            <Typography
              sx={{
                fontSize: 11,
                fontWeight: 600,
                color: selected ? 'primary.main' : 'text.secondary',
                letterSpacing: '0.01em',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                transition: `color ${designTokens.motion.fast}`,
              }}
            >
              {title}
            </Typography>
            {trend ? (
              <Box
                sx={{
                  ml: 'auto',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.25,
                  color: 'text.secondary',
                  flexShrink: 0,
                }}
              >
                <TrendIcon sx={{ fontSize: 12 }} />
                <Typography variant="caption" sx={{ fontWeight: 700, fontSize: 10 }}>
                  {trend.value}
                </Typography>
              </Box>
            ) : null}
          </Box>
          <Typography
            sx={{
              fontSize: 20,
              fontWeight: 800,
              lineHeight: 1.1,
              letterSpacing: '-0.03em',
              mt: 0.25,
              color: selected ? 'primary.dark' : 'text.primary',
              fontVariantNumeric: 'tabular-nums',
              transition: `color ${designTokens.motion.fast}`,
            }}
            noWrap
            title={shown}
          >
            {shown}
          </Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      onClick={onClick}
      elevation={0}
      sx={{
        width: '100%',
        minHeight: compact ? 96 : 112,
        height: '100%',
        cursor: onClick ? 'pointer' : 'default',
        borderRadius: `${designTokens.radius.lg}px`,
        boxShadow: selected ? designTokens.elevation.cardHover : designTokens.elevation.card,
        border: '1px solid',
        borderColor: selected ? 'primary.main' : 'divider',
        bgcolor: selected ? alpha(theme.palette.primary.main, 0.04) : designTokens.semantic.card,
        transition: `box-shadow ${designTokens.motion.normal}, transform ${designTokens.motion.normal}, border-color ${designTokens.motion.fast}`,
        overflow: 'hidden',
        '&:hover': onClick
          ? {
              transform: 'translateY(-2px)',
              boxShadow: designTokens.elevation.cardHover,
            }
          : undefined,
      }}
    >
      <CardContent
        sx={{
          p: compact ? '14px 16px !important' : '16px 18px !important',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          '&:last-child': { pb: compact ? '14px !important' : '16px !important' },
        }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 1.5 }}>
          <Box
            sx={{
              width: compact ? 36 : 40,
              height: compact ? 36 : 40,
              borderRadius: `${designTokens.radius.md}px`,
              display: 'grid',
              placeItems: 'center',
              bgcolor: iconBackground,
              color: iconForeground,
              flexShrink: 0,
            }}
          >
            <Icon sx={{ fontSize: compact ? 18 : 20 }} />
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
            fontSize: 12,
            fontWeight: 600,
            color: 'text.secondary',
            mt: 1.25,
            letterSpacing: '0.01em',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={title}
        >
          {title}
        </Typography>
        <Typography
          sx={{
            fontSize: compact ? 24 : 28,
            fontWeight: 800,
            lineHeight: 1.15,
            letterSpacing: '-0.03em',
            mt: 0.35,
            fontVariantNumeric: 'tabular-nums',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={shown}
        >
          {shown}
        </Typography>
        {subtitle ? (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              lineHeight: 1.3,
              mt: 0.25,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={subtitle}
          >
            {subtitle}
          </Typography>
        ) : null}
      </CardContent>
    </Card>
  );
}
