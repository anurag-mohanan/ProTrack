import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ScheduleIcon from '@mui/icons-material/Schedule';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import TimerIcon from '@mui/icons-material/Timer';
import { Box, Card, CardContent, Typography } from '@mui/material';
import type { SvgIconComponent } from '@mui/icons-material';
import type { DashboardSummary } from '../../../types';
import { formatNumber } from '../../../utils/format';
import type { ProjectQuickFilter } from '../../../utils/projectCommandCenter';

interface ProjectKpiBarProps {
  summary: DashboardSummary | undefined;
  loading?: boolean;
  onFilter: (filter: ProjectQuickFilter) => void;
}

interface CompactKpiProps {
  title: string;
  value: string;
  subtitle: string;
  icon: SvgIconComponent;
  onClick?: () => void;
  accent?: 'primary' | 'warning' | 'error' | 'success';
}

function CompactKpiCard({ title, value, subtitle, icon: Icon, onClick, accent }: CompactKpiProps) {
  const iconColor =
    accent === 'error'
      ? 'error.main'
      : accent === 'warning'
        ? 'warning.main'
        : accent === 'success'
          ? 'success.main'
          : accent === 'primary'
            ? 'primary.main'
            : 'text.secondary';

  return (
    <Card
      onClick={onClick}
      sx={{
        height: 64,
        cursor: onClick ? 'pointer' : 'default',
        borderRadius: 2.5,
        boxShadow: (theme) => theme.palette.prosohm.shadowCard,
        border: '1px solid',
        borderColor: 'divider',
        transition: 'box-shadow 0.18s ease, transform 0.18s ease',
        '&:hover': onClick
          ? {
              transform: 'translateY(-1px)',
              boxShadow: (theme) => theme.palette.prosohm.shadowCardHover,
            }
          : undefined,
      }}
    >
      <CardContent
        sx={{
          p: '12px 14px !important',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 1,
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, display: 'block' }}>
            {title}
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 700, lineHeight: 1.1, my: 0.25 }}>
            {value}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap>
            {subtitle}
          </Typography>
        </Box>
        <Box
          sx={{
            width: 32,
            height: 32,
            borderRadius: 1.5,
            display: 'grid',
            placeItems: 'center',
            bgcolor: 'grey.50',
            color: iconColor,
            flexShrink: 0,
          }}
        >
          <Icon sx={{ fontSize: 17 }} />
        </Box>
      </CardContent>
    </Card>
  );
}

export function ProjectKpiBar({ summary, loading, onFilter }: ProjectKpiBarProps) {
  const unavailable = loading || !summary;

  const kpis: CompactKpiProps[] = [
    {
      title: 'Active Projects',
      value: unavailable ? '—' : formatNumber(summary!.active_projects ?? 0, 0),
      subtitle: 'Live portfolio',
      icon: FolderOpenIcon,
      accent: !unavailable && (summary!.active_projects ?? 0) > 0 ? 'primary' : undefined,
      onClick: () => onFilter('active'),
    },
    {
      title: 'Due This Week',
      value: unavailable ? '—' : formatNumber(summary!.projects_due_this_week ?? 0, 0),
      subtitle: 'Due Mon–Sun',
      icon: ScheduleIcon,
      accent: !unavailable && (summary!.projects_due_this_week ?? 0) > 0 ? 'warning' : undefined,
      onClick: () => onFilter('due_week'),
    },
    {
      title: 'Overdue',
      value: unavailable ? '—' : formatNumber(summary!.overdue_projects ?? 0, 0),
      subtitle: 'Past due',
      icon: WarningAmberIcon,
      accent: !unavailable && (summary!.overdue_projects ?? 0) > 0 ? 'error' : undefined,
      onClick: () => onFilter('overdue'),
    },
    {
      title: 'Completed This Month',
      value: unavailable ? '—' : formatNumber(summary!.completed_this_month ?? 0, 0),
      subtitle: 'Delivered',
      icon: TaskAltIcon,
      accent: !unavailable && (summary!.completed_this_month ?? 0) > 0 ? 'success' : undefined,
      onClick: () => onFilter('completed_month'),
    },
    {
      title: 'Quoted Hours',
      value: unavailable ? '—' : formatNumber(summary!.total_quoted_hours_active ?? 0, 1),
      subtitle: 'Active projects',
      icon: ScheduleIcon,
    },
    {
      title: 'Actual Hours',
      value: unavailable ? '—' : formatNumber(summary!.total_actual_hours_productive ?? 0, 1),
      subtitle: 'Approved hours',
      icon: TimerIcon,
    },
  ];

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)', lg: 'repeat(6, 1fr)' },
        gap: 1.25,
        mb: 2,
      }}
    >
      {kpis.map((kpi) => (
        <CompactKpiCard key={kpi.title} {...kpi} />
      ))}
    </Box>
  );
}
