import { List, ListItemButton, ListItemText, Paper, Typography } from '@mui/material';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type { DashboardMyTasks, DashboardTaskItem } from '../../types';
import { formatDate } from '../../utils/format';

const TASK_TYPE_LABELS: Record<string, string> = {
  milestone: 'Pending milestone',
  approval: 'Pending approval',
  review: 'Pending review',
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
      <Paper
        variant="outlined"
        sx={{
          borderRadius: 3,
          p: 2.5,
          boxShadow: (theme) => theme.palette.prosohm.shadowCard,
        }}
      >
        <Typography variant="body2" color="text.secondary">
          No data available
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
        {items.map((item) => (
          <ListItemButton
            key={`${item.task_type}-${item.id}`}
            onClick={() => {
              if (item.href) navigate(item.href);
            }}
            sx={{
              px: 2.5,
              py: 1.25,
              borderBottom: '1px solid',
              borderColor: 'divider',
            }}
          >
            <ListItemText
              primary={item.title}
              secondary={
                [
                  taskLabel(item),
                  item.subtitle,
                  item.due_date ? `Due ${formatDate(item.due_date)}` : null,
                ]
                  .filter(Boolean)
                  .join(' · ') || undefined
              }
              slotProps={{
                primary: { variant: 'body2', sx: { fontWeight: 600 } },
                secondary: { variant: 'caption' },
              }}
            />
          </ListItemButton>
        ))}
      </List>
    </Paper>
  );
}
