import { Box, Paper, Typography } from '@mui/material';
import NotificationsNoneIcon from '@mui/icons-material/NotificationsNone';
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import TodayOutlinedIcon from '@mui/icons-material/TodayOutlined';
import type { DashboardFuturePlaceholders } from '../../types';

const PLACEHOLDERS = [
  { key: 'notifications', label: 'Notifications', icon: NotificationsNoneIcon },
  { key: 'ai_recommendations', label: 'AI Recommendations', icon: AutoAwesomeOutlinedIcon },
  { key: 'todays_priorities', label: "Today's Priorities", icon: TodayOutlinedIcon },
] as const;

interface DashboardFutureStripProps {
  placeholders: DashboardFuturePlaceholders;
}

export function DashboardFutureStrip({ placeholders }: DashboardFutureStripProps) {
  const enabledMap = {
    notifications: placeholders.notifications_enabled,
    ai_recommendations: placeholders.ai_recommendations_enabled,
    todays_priorities: placeholders.todays_priorities_enabled,
  };

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' },
        gap: 2,
        mt: 1,
      }}
    >
      {PLACEHOLDERS.map(({ key, label, icon: Icon }) => {
        const enabled = enabledMap[key];
        return (
          <Paper
            key={key}
            variant="outlined"
            sx={{
              borderRadius: 3,
              p: 2,
              opacity: enabled ? 1 : 0.72,
              borderStyle: enabled ? 'solid' : 'dashed',
              bgcolor: 'grey.50',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, mb: 0.5 }}>
              <Icon sx={{ fontSize: 18, color: 'text.secondary' }} />
              <Typography variant="subtitle2" sx={{ fontWeight: 650 }}>
                {label}
              </Typography>
            </Box>
            <Typography variant="caption" color="text.secondary">
              {enabled ? 'Available soon' : 'Coming soon'}
            </Typography>
          </Paper>
        );
      })}
    </Box>
  );
}
