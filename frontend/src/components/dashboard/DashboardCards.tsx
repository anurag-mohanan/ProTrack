import type { ReactNode } from 'react';
import { Box, Typography } from '@mui/material';
import type { SvgIconComponent } from '@mui/icons-material';
import { KpiMetricCard, type KpiAccent } from '../ui/design-system/KpiMetricCard';

interface ActionKpiCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: SvgIconComponent;
  onClick?: () => void;
  statusColor?: KpiAccent | 'info';
  trend?: { value: string; direction?: 'up' | 'down' | 'flat' };
}

interface DashboardSectionProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
}

export function ActionKpiCard({
  title,
  value,
  subtitle,
  icon,
  onClick,
  statusColor,
  trend,
}: ActionKpiCardProps) {
  return (
    <KpiMetricCard
      title={title}
      value={value}
      subtitle={subtitle}
      icon={icon}
      onClick={onClick}
      accent={statusColor === 'info' ? 'info' : statusColor}
      trend={trend}
    />
  );
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
          mb: 2,
        }}
      >
        <Box>
          <Typography variant="sectionTitle" sx={{ letterSpacing: '-0.01em' }}>
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
