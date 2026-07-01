import { Box, List, ListItemButton, ListItemText, Paper, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../common/EmptyState';
import type { DashboardMyTasks, DashboardTaskItem } from '../../types';
import { formatDate } from '../../utils/format';

function TaskList({
  title,
  items,
  emptyLabel,
}: {
  title: string;
  items: DashboardTaskItem[];
  emptyLabel: string;
}) {
  const navigate = useNavigate();

  return (
    <Paper variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
      <Box sx={{ px: 2, pt: 2, pb: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 650 }}>
          {title}
        </Typography>
      </Box>
      {items.length === 0 ? (
        <Box sx={{ px: 2, pb: 2 }}>
          <Typography variant="body2" color="text.secondary">
            {emptyLabel}
          </Typography>
        </Box>
      ) : (
        <List dense disablePadding sx={{ pb: 1 }}>
          {items.map((item) => (
            <ListItemButton
              key={`${item.task_type}-${item.id}`}
              onClick={() => {
                if (item.href) navigate(item.href);
              }}
              sx={{ px: 2, py: 0.75 }}
            >
              <ListItemText
                primary={item.title}
                secondary={
                  [item.subtitle, item.due_date ? `Due ${formatDate(item.due_date)}` : null]
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
      )}
    </Paper>
  );
}

interface MyTasksWidgetProps {
  tasks: DashboardMyTasks;
}

export function MyTasksWidget({ tasks }: MyTasksWidgetProps) {
  const hasAny =
    tasks.assigned_projects.length > 0 ||
    tasks.pending_approvals.length > 0 ||
    tasks.upcoming_milestones.length > 0;

  if (!hasAny) {
    return (
      <Paper variant="outlined" sx={{ borderRadius: 3, p: 2 }}>
        <EmptyState title="You're all caught up" description="No assigned projects or pending approvals." />
      </Paper>
    );
  }

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' },
        gap: 2,
      }}
    >
      <TaskList
        title="My Projects"
        items={tasks.assigned_projects}
        emptyLabel="No active project assignments"
      />
      <TaskList
        title="Pending Approvals"
        items={tasks.pending_approvals}
        emptyLabel="No timesheets awaiting approval"
      />
      <TaskList
        title="Upcoming Milestones"
        items={tasks.upcoming_milestones}
        emptyLabel="No milestones due in the next two weeks"
      />
    </Box>
  );
}
