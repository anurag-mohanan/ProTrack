import { Box, List, ListItemButton, ListItemText, Paper, Typography } from '@mui/material';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type { DashboardActivityItem } from '../../types';
import { formatDateTime } from '../../utils/format';

const CATEGORY_LABELS: Record<DashboardActivityItem['category'], string> = {
  project: 'Project',
  milestone: 'Milestone',
  timesheet: 'Timesheet',
  user: 'User',
  import: 'Import',
};

const CATEGORY_COLORS: Record<DashboardActivityItem['category'], string> = {
  project: 'primary.main',
  milestone: 'secondary.main',
  timesheet: 'info.main',
  user: 'success.main',
  import: 'warning.main',
};

interface RecentActivityWidgetProps {
  activities: DashboardActivityItem[];
}

export function RecentActivityWidget({ activities }: RecentActivityWidgetProps) {
  const navigate = useNavigate();
  const sorted = useMemo(
    () => [...activities].sort((a, b) => b.occurred_at.localeCompare(a.occurred_at)),
    [activities],
  );

  if (!sorted.length) {
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
        {sorted.map((activity) => (
          <ListItemButton
            key={activity.id}
            disabled={!activity.href}
            onClick={() => {
              if (activity.href) navigate(activity.href);
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
                bgcolor: CATEGORY_COLORS[activity.category],
                flexShrink: 0,
              }}
            />
            <ListItemText
              sx={{ px: 2, py: 1.25 }}
              primary={activity.title}
              secondary={
                [
                  CATEGORY_LABELS[activity.category],
                  activity.detail,
                  activity.actor_name,
                  formatDateTime(activity.occurred_at),
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
