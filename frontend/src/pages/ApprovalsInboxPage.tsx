import { useMemo } from 'react';
import {
  Box,
  Chip,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { dashboardQueryKeys, fetchDashboardMyTasks } from '../api/dashboard';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import type { DashboardTaskItem } from '../types';
import { formatDate } from '../utils/format';

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

export function ApprovalsInboxPage() {
  const navigate = useNavigate();
  const tasksQuery = useQuery({
    queryKey: dashboardQueryKeys.myTasks,
    queryFn: fetchDashboardMyTasks,
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  const items = useMemo(() => {
    const tasks = tasksQuery.data;
    if (!tasks) return [];
    return [
      ...tasks.pending_approvals,
      ...tasks.upcoming_milestones,
      ...(tasks.pending_reviews ?? []),
    ].sort((a, b) => {
      const aDate = a.due_date ?? '9999-12-31';
      const bDate = b.due_date ?? '9999-12-31';
      return aDate.localeCompare(bDate);
    });
  }, [tasksQuery.data]);

  if (tasksQuery.isLoading) {
    return (
      <PageContainer>
        <LoadingState message="Loading approvals…" />
      </PageContainer>
    );
  }

  if (tasksQuery.isError) {
    return (
      <PageContainer>
        <ErrorState
          error={tasksQuery.error}
          title="Unable to load approvals inbox"
          onRetry={() => void tasksQuery.refetch()}
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageHeader
        title="Approvals inbox"
        subtitle="Unified view of pending approvals, reviews, and upcoming milestones"
      />

      {!items.length ? (
        <EmptyState
          title="You are all caught up"
          description="No pending approvals, reviews, or assigned milestones right now."
          icon={<TaskAltIcon color="success" fontSize="large" />}
        />
      ) : (
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
                    sx={{ px: 2, py: 1.5 }}
                    primary={
                      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {item.title}
                        </Typography>
                        <Chip label={taskLabel(item)} size="small" variant="outlined" />
                      </Stack>
                    }
                    secondary={
                      [
                        item.subtitle ? `Tool ${item.subtitle}` : null,
                        item.due_date ? `Due ${formatDate(item.due_date)}` : null,
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
      )}
    </PageContainer>
  );
}
