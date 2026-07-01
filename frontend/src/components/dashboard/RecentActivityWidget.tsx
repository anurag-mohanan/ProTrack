import { Box, Paper, Typography } from '@mui/material';
import type { Activity } from '../../types';
import { formatDateTime } from '../../utils/format';

const ACTION_LABELS: Record<string, string> = {
  project_created: 'Project created',
  project_updated: 'Project updated',
  project_archived: 'Project archived',
  project_restored: 'Project restored',
  project_deleted: 'Project deleted',
  project_restored_from_deleted: 'Project restored from deleted',
  milestone_completed: 'Milestone completed',
  milestone_reopened: 'Milestone reopened',
  timesheet_submitted: 'Timesheet submitted',
  timesheet_approved: 'Timesheet approved',
  timesheet_rejected: 'Timesheet rejected',
  user_logged_in: 'User signed in',
  user_archived: 'User archived',
  user_restored: 'User restored',
  user_deleted: 'User deleted',
  user_restored_from_deleted: 'User restored from deleted',
};

function activityLabel(action: string): string {
  return ACTION_LABELS[action] ?? action.replaceAll('_', ' ');
}

interface RecentActivityWidgetProps {
  activities: Activity[];
}

export function RecentActivityWidget({ activities }: RecentActivityWidgetProps) {
  if (!activities.length) {
    return (
      <Paper variant="outlined" sx={{ borderRadius: 3, p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          No recent activity yet.
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper variant="outlined" sx={{ borderRadius: 3, overflow: 'hidden' }}>
      {activities.map((activity, index) => (
        <Box
          key={activity.id}
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 2,
            px: 2,
            py: 1.25,
            borderBottom: index < activities.length - 1 ? '1px solid' : 'none',
            borderColor: 'divider',
          }}
        >
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {activityLabel(activity.action)}
            </Typography>
            <Typography variant="caption" color="text.secondary" noWrap>
              {activity.new_value ?? activity.old_value ?? activity.user_name ?? 'System'}
            </Typography>
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>
            {formatDateTime(activity.created_at)}
          </Typography>
        </Box>
      ))}
    </Paper>
  );
}
