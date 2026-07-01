import type { ReactNode } from 'react';
import { Box, Card, CardContent, Typography } from '@mui/material';
import type { SvgIconComponent } from '@mui/icons-material';

interface ActionKpiCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: SvgIconComponent;
  onClick?: () => void;
  statusColor?: 'success' | 'warning' | 'error' | 'info' | 'primary';
}

export function ActionKpiCard({
  title,
  value,
  subtitle,
  icon: Icon,
  onClick,
  statusColor,
}: ActionKpiCardProps) {
  const iconColor =
    statusColor === 'success'
      ? 'success.main'
      : statusColor === 'warning'
        ? 'warning.main'
        : statusColor === 'error'
          ? 'error.main'
          : statusColor === 'info'
            ? 'info.main'
            : 'text.secondary';

  return (
    <Card
      onClick={onClick}
      sx={{
        height: '100%',
        cursor: onClick ? 'pointer' : 'default',
        borderRadius: 3,
        boxShadow: (theme) => theme.palette.prosohm.shadowCard,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.paper',
        transition: 'transform 0.18s ease, box-shadow 0.18s ease',
        '&:hover': onClick
          ? {
              transform: 'translateY(-2px)',
              boxShadow: (theme) => theme.palette.prosohm.shadowCardHover,
            }
          : undefined,
      }}
    >
      <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 1.5 }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 0.75, fontWeight: 500 }}>
              {title}
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 700, lineHeight: 1.1, letterSpacing: '-0.02em' }}>
              {value}
            </Typography>
            {subtitle ? (
              <Typography variant="caption" color="text.secondary" sx={{ mt: 0.75, display: 'block' }}>
                {subtitle}
              </Typography>
            ) : null}
          </Box>
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: 2,
              display: 'grid',
              placeItems: 'center',
              bgcolor: 'grey.50',
              color: iconColor,
              flexShrink: 0,
            }}
          >
            <Icon sx={{ fontSize: 18 }} />
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

interface DashboardSectionProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
}

export function DashboardSection({ title, subtitle, action, children }: DashboardSectionProps) {
  return (
    <Box sx={{ mb: 3 }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          gap: 2,
          mb: 1.5,
        }}
      >
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 650, letterSpacing: '-0.01em' }}>
            {title}
          </Typography>
          {subtitle ? (
            <Typography variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          ) : null}
        </Box>
        {action}
      </Box>
      {children}
    </Box>
  );
}
