import { Box, Stack, Typography } from '@mui/material';
import FolderOutlinedIcon from '@mui/icons-material/FolderOutlined';
import FlagOutlinedIcon from '@mui/icons-material/FlagOutlined';
import ScheduleOutlinedIcon from '@mui/icons-material/ScheduleOutlined';
import PersonAddOutlinedIcon from '@mui/icons-material/PersonAddOutlined';
import CloudUploadOutlinedIcon from '@mui/icons-material/CloudUploadOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type { DashboardActivityItem } from '../../types';
import { designTokens } from '../../theme/designTokens';
import { formatDateTime } from '../../utils/format';

const ACTIVITY_META: Record<
  DashboardActivityItem['category'],
  { icon: typeof FolderOutlinedIcon; color: string }
> = {
  project: { icon: FolderOutlinedIcon, color: designTokens.semantic.primary },
  milestone: { icon: FlagOutlinedIcon, color: '#8b5cf6' },
  timesheet: { icon: ScheduleOutlinedIcon, color: '#0ea5e9' },
  user: { icon: PersonAddOutlinedIcon, color: designTokens.semantic.success },
  import: { icon: CloudUploadOutlinedIcon, color: designTokens.semantic.warning },
};

interface ActivityTimelineProps {
  activities: DashboardActivityItem[];
}

export function ActivityTimeline({ activities }: ActivityTimelineProps) {
  const navigate = useNavigate();
  const sorted = useMemo(
    () => [...activities].sort((a, b) => b.occurred_at.localeCompare(a.occurred_at)),
    [activities],
  );

  if (!sorted.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No recent activity.
      </Typography>
    );
  }

  return (
    <Stack spacing={0}>
      {sorted.map((activity, index) => {
        const meta = ACTIVITY_META[activity.category] ?? {
          icon: WarningAmberOutlinedIcon,
          color: designTokens.semantic.neutral,
        };
        const Icon = meta.icon;
        const isLast = index === sorted.length - 1;

        return (
          <Box
            key={activity.id}
            onClick={() => activity.href && navigate(activity.href)}
            sx={{
              display: 'flex',
              gap: 2,
              py: 1.5,
              cursor: activity.href ? 'pointer' : 'default',
              borderRadius: `${designTokens.radius.md}px`,
              px: 1,
              mx: -1,
              transition: `background-color ${designTokens.motion.fast}`,
              '&:hover': activity.href ? { bgcolor: designTokens.semantic.neutralSoft } : undefined,
            }}
          >
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 32 }}>
              <Box
                sx={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  bgcolor: `${meta.color}18`,
                  color: meta.color,
                  display: 'grid',
                  placeItems: 'center',
                  flexShrink: 0,
                }}
              >
                <Icon sx={{ fontSize: 16 }} />
              </Box>
              {!isLast ? (
                <Box
                  sx={{
                    width: 2,
                    flex: 1,
                    minHeight: 16,
                    bgcolor: 'divider',
                    mt: 0.5,
                  }}
                />
              ) : null}
            </Box>
            <Box sx={{ flex: 1, minWidth: 0, pb: isLast ? 0 : 0.5 }}>
              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                {activity.title}
              </Typography>
              {activity.detail ? (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
                  {activity.detail}
                </Typography>
              ) : null}
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                {[activity.actor_name, formatDateTime(activity.occurred_at)].filter(Boolean).join(' · ')}
              </Typography>
            </Box>
          </Box>
        );
      })}
    </Stack>
  );
}
