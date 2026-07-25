import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ScheduleIcon from '@mui/icons-material/Schedule';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import { Box, Stack, Typography } from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import type { SvgIconComponent } from '@mui/icons-material';
import { formatNumber } from '../../../utils/format';
import type { ProjectQuickFilter, ProjectPortfolioMetrics } from '../../../utils/projectCommandCenter';
import { ProjectHoursPerformanceCard } from './ProjectHoursPerformanceCard';

interface ProjectKpiBarProps {
  metrics?: ProjectPortfolioMetrics;
  loading?: boolean;
  activeFilter?: ProjectQuickFilter;
  onFilter: (filter: ProjectQuickFilter) => void;
}

function MiniStat({
  title,
  value,
  icon: Icon,
  selected,
  tone,
  onClick,
}: {
  title: string;
  value: string;
  icon: SvgIconComponent;
  selected: boolean;
  tone?: 'primary' | 'warning' | 'error' | 'success';
  onClick: () => void;
}) {
  const theme = useTheme();
  const color = tone ? theme.palette[tone].main : theme.palette.text.secondary;

  return (
    <Box
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onClick();
        }
      }}
      sx={{
        flex: '1 1 0',
        minWidth: 104,
        px: 1,
        py: 0.65,
        borderRadius: 1.25,
        border: '1px solid',
        borderColor: selected ? 'primary.main' : 'divider',
        bgcolor: selected ? alpha(theme.palette.primary.main, 0.08) : 'background.paper',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: 0.75,
        '&:hover': { bgcolor: selected ? alpha(theme.palette.primary.main, 0.12) : 'action.hover' },
      }}
    >
      <Box
        sx={{
          width: 26,
          height: 26,
          borderRadius: 1,
          display: 'grid',
          placeItems: 'center',
          bgcolor: alpha(color, 0.12),
          color,
          flexShrink: 0,
        }}
      >
        <Icon sx={{ fontSize: 16 }} />
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography
          sx={{
            fontSize: '0.62rem',
            fontWeight: 700,
            color: 'text.secondary',
            lineHeight: 1.1,
            textTransform: 'uppercase',
            letterSpacing: '0.03em',
          }}
          noWrap
        >
          {title}
        </Typography>
        <Typography sx={{ fontWeight: 800, fontSize: '1rem', lineHeight: 1.15 }} noWrap>
          {value}
        </Typography>
      </Box>
    </Box>
  );
}

export function ProjectKpiBar({
  metrics,
  loading,
  activeFilter = 'none',
  onFilter,
}: ProjectKpiBarProps) {
  const unavailable = loading || !metrics;

  return (
    <Stack
      direction="row"
      useFlexGap
      sx={{ flexWrap: 'wrap', gap: 0.5, mb: 0.5, alignItems: 'stretch' }}
    >
      <MiniStat
        title="Active"
        value={unavailable ? '—' : formatNumber(metrics!.liveCount, 0)}
        icon={FolderOpenIcon}
        selected={activeFilter === 'active'}
        tone={!unavailable && metrics!.liveCount > 0 ? 'primary' : undefined}
        onClick={() => onFilter('active')}
      />
      <MiniStat
        title="Due week"
        value={unavailable ? '—' : formatNumber(metrics!.dueThisWeekCount, 0)}
        icon={ScheduleIcon}
        selected={activeFilter === 'due_week'}
        tone={!unavailable && metrics!.dueThisWeekCount > 0 ? 'warning' : undefined}
        onClick={() => onFilter('due_week')}
      />
      <MiniStat
        title="Overdue"
        value={unavailable ? '—' : formatNumber(metrics!.overdueCount, 0)}
        icon={WarningAmberIcon}
        selected={activeFilter === 'overdue'}
        tone={!unavailable && metrics!.overdueCount > 0 ? 'error' : undefined}
        onClick={() => onFilter('overdue')}
      />
      <MiniStat
        title="Completed"
        value={unavailable ? '—' : formatNumber(metrics!.completedThisMonthCount, 0)}
        icon={TaskAltIcon}
        selected={activeFilter === 'completed_month'}
        tone={!unavailable && metrics!.completedThisMonthCount > 0 ? 'success' : undefined}
        onClick={() => onFilter('completed_month')}
      />
      <Box sx={{ flex: '1 1 180px', minWidth: 160, maxWidth: 240 }}>
        <ProjectHoursPerformanceCard
          quotedHours={metrics?.quotedHours}
          actualHours={metrics?.actualHours}
          loading={loading}
        />
      </Box>
    </Stack>
  );
}
