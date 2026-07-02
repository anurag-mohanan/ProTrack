import { Box, Card, CardContent, Typography } from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import type { SvgIconComponent } from '@mui/icons-material';

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
}: KpiMetricCardProps) {
  const theme = useTheme();
  const iconAccent = accent ?? 'primary';
  const paletteKey = accentKeys.includes(iconAccent) ? iconAccent : 'primary';
  const iconBackground = accent
    ? alpha(theme.palette[paletteKey].main, 0.12)
    : theme.palette.grey[100];
  const iconForeground = accent ? theme.palette[paletteKey].main : theme.palette.text.secondary;

  return (
    <Card
      onClick={onClick}
      elevation={0}
      sx={{
        height: compact ? 88 : 108,
        cursor: onClick ? 'pointer' : 'default',
        borderRadius: 2.5,
        boxShadow: (theme) =>
          selected ? theme.palette.prosohm.shadowCardHover : theme.palette.prosohm.shadowCard,
        border: '1px solid',
        borderColor: selected ? 'primary.main' : 'divider',
        bgcolor: selected ? (theme) => `${theme.palette.primary.main}08` : 'background.paper',
        transition: 'box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease',
        '&:hover': onClick
          ? {
              transform: 'translateY(-2px)',
              boxShadow: (theme) => theme.palette.prosohm.shadowCardHover,
            }
          : undefined,
      }}
    >
      <CardContent
        sx={{
          p: '14px 16px !important',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 1.5,
        }}
      >
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography
            sx={{
              fontSize: 14,
              fontWeight: 600,
              lineHeight: 1.2,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              color: 'text.primary',
            }}
          >
            {title}
          </Typography>
          <Typography
            sx={{
              fontSize: compact ? 30 : 32,
              fontWeight: 700,
              lineHeight: 1.1,
              letterSpacing: '-0.02em',
              my: 0.25,
              whiteSpace: 'nowrap',
            }}
          >
            {value}
          </Typography>
          {subtitle ? (
            <Typography
              sx={{
                fontSize: 12,
                lineHeight: 1.2,
                color: 'text.secondary',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {subtitle}
            </Typography>
          ) : null}
        </Box>
        <Box
          sx={{
            width: compact ? 40 : 44,
            height: compact ? 40 : 44,
            borderRadius: '50%',
            display: 'grid',
            placeItems: 'center',
            bgcolor: iconBackground,
            color: iconForeground,
            flexShrink: 0,
          }}
        >
          <Icon sx={{ fontSize: compact ? 20 : 22 }} />
        </Box>
      </CardContent>
    </Card>
  );
}
