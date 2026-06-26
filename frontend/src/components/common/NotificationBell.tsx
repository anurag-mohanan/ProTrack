import NotificationsIcon from '@mui/icons-material/Notifications';
import {
  Badge,
  Box,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Menu,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
  getNotificationSummary,
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  notificationQueryKeys,
} from '../../services/notificationService';
import { formatDateTime } from '../../utils/format';
import type { Notification } from '../../types';

export function NotificationBell() {
  const queryClient = useQueryClient();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const summaryQuery = useQuery({
    queryKey: notificationQueryKeys.summary,
    queryFn: getNotificationSummary,
    refetchInterval: 30000,
  });

  const notificationsQuery = useQuery({
    queryKey: notificationQueryKeys.all,
    queryFn: () => getNotifications(false),
    enabled: Boolean(anchorEl),
  });

  const readMutation = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: notificationQueryKeys.all });
      void queryClient.invalidateQueries({ queryKey: notificationQueryKeys.summary });
    },
  });

  const readAllMutation = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: notificationQueryKeys.all });
      void queryClient.invalidateQueries({ queryKey: notificationQueryKeys.summary });
    },
  });

  return (
    <>
      <IconButton color="inherit" onClick={(event) => setAnchorEl(event.currentTarget)}>
        <Badge badgeContent={summaryQuery.data?.unread_count ?? 0} color="error">
          <NotificationsIcon />
        </Badge>
      </IconButton>
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
        slotProps={{ paper: { sx: { width: 360, maxHeight: 420 } } }}
      >
        <Box sx={{ px: 2, py: 1, display: 'flex', justifyContent: 'space-between' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Notifications
          </Typography>
          <Typography
            variant="caption"
            sx={{ cursor: 'pointer', color: 'primary.main' }}
            onClick={() => readAllMutation.mutate()}
          >
            Mark all read
          </Typography>
        </Box>
        <List dense>
          {(notificationsQuery.data ?? []).slice(0, 10).map((notification: Notification) => (
            <ListItem
              key={notification.id}
              sx={{
                bgcolor: notification.is_read ? 'transparent' : 'action.hover',
                cursor: 'pointer',
              }}
              onClick={() => {
                if (!notification.is_read) {
                  readMutation.mutate(notification.id);
                }
              }}
            >
              <ListItemText
                primary={notification.title}
                secondary={
                  <>
                    {notification.message}
                    <Typography component="span" variant="caption" sx={{ display: 'block' }}>
                      {formatDateTime(notification.created_at)}
                    </Typography>
                  </>
                }
              />
            </ListItem>
          ))}
        </List>
      </Menu>
    </>
  );
}
