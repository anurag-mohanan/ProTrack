import { Box, Chip, List, ListItemButton, ListItemText, Paper, Typography } from '@mui/material';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type { DashboardMyTasks, DashboardTaskItem } from '../../types';
import { formatDate } from '../../utils/format';

const TASK_TYPE_LABELS: Record<string, string> = {
  milestone: 'Milestone',
  approval: 'Approval',
  review: 'Review',
};

const PRIORITY_COLORS: Record<string, string> = {
  high: 'error.main',
  medium: 'warning.main',
  low: 'success.main',
};

function taskLabel(item: DashboardTaskItem): string {
  return TASK_TYPE_LABELS[item.task_type] ?? item.title;
}

interface MyTasksWidgetProps {
  tasks: DashboardMyTasks;
}

export function MyTasksWidget({ tasks }: MyTasksWidgetProps) {
  const navigate = useNavigate();

  const items = useMemo(() => {
    const merged = [
      ...tasks.pending_approvals,
      ...tasks.upcoming_milestones,
      ...(tasks.pending_reviews ?? []),
    ];
    return merged.sort((a, b) => {
      const aDate = a.due_date ?? '9999-12-31';
      const bDate = b.due_date ?? '9999-12-31';
      return aDate.localeCompare(bDate);
    });
  }, [tasks]);

  if (!items.length) {
    return (
      <Paper variant="outlined" sx={{ borderRadius: 3, p: 2.5 }}>
        <Typography variant="body2" color="text.secondary">
          No data available.
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        borderRadius: 3,
        overflow: 'hidden',
        boxShadow: (theme) => theme.palette.prosohm.shadowCard,
      }}
    >
      <List dense disablePadding>
        {items.map((item) => {
          const priority = item.priority ?? 'low';
          return (
            <ListItemButton
              key={`${item.task_type}-${item.id}`}
              onClick={() => {
                if (item.href) navigate(item.href);
              }}
              sx={{
                px: 0,
                py: 0,
                alignItems: 'stretch',
                borderBottom: '1px solid',
                borderColor: 'divider',
                '&:last-child': { borderBottom: 'none' },
              }}
            >
              <Box
                sx={{
                  width: 4,
                  bgcolor: PRIORITY_COLORS[priority] ?? PRIORITY_COLORS.low,
                  flexShrink: 0,
                }}
              />
              <ListItemText
                sx={{ px: 2, py: 1.25 }}
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {item.title}
                    </Typography>
                    <Chip label={taskLabel(item)} size="small" variant="outlined" />
                  </Box>
                }
                secondary={
                  [
                    item.subtitle ? `Tool ${item.subtitle}` : null,
                    item.due_date ? `Due ${formatDate(item.due_date)}` : null,
                    priority !== 'low' ? `${priority} priority` : null,
                  ]
                    .filter(Boolean)
                    .join(' · ') || undefined
                }
                slotProps={{
                  secondary: { variant: 'caption' },
                }}
              />
            </ListItemButton>
          );
        })}
      </List>
    </Paper>
  );
}
