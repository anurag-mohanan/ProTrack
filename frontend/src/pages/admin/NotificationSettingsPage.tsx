import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Box, FormControlLabel, Switch } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { LoadingState } from '../../components/common/LoadingState';
import { fetchNotificationSettings, updateNotificationSettings } from '../../api/settings';
import { useEffect, useState } from 'react';
import { useToast } from '../../context/ToastContext';

export default function NotificationSettingsPage() {
  const { showSuccess } = useToast();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ['settings', 'notifications'],
    queryFn: fetchNotificationSettings,
  });
  const [form, setForm] = useState({
    projects_due_enabled: true,
    overdue_enabled: true,
    pending_approvals_enabled: true,
    new_assignments_enabled: true,
    imports_completed_enabled: true,
    email_notifications_enabled: true,
  });

  useEffect(() => {
    if (query.data) setForm({ ...form, ...query.data });
  }, [query.data]);

  const saveMutation = useMutation({
    mutationFn: () => updateNotificationSettings(form),
    onSuccess: () => {
      showSuccess('Notification settings saved');
      void queryClient.invalidateQueries({ queryKey: ['settings', 'notifications'] });
    },
  });

  if (query.isLoading) return <LoadingState message="Loading notification settings…" />;

  return (
    <Box>
      <PageHeader title="Notification Settings" subtitle="Control system notification categories" />
      <ContentCard title="Notification rules">
        {(
          [
            ['projects_due_enabled', 'Projects due'],
            ['overdue_enabled', 'Overdue projects'],
            ['pending_approvals_enabled', 'Pending approvals'],
            ['new_assignments_enabled', 'New assignments'],
            ['imports_completed_enabled', 'Imports completed'],
            ['email_notifications_enabled', 'Email notifications'],
          ] as const
        ).map(([key, label]) => (
          <FormControlLabel
            key={key}
            control={
              <Switch
                checked={form[key]}
                onChange={(event) =>
                  setForm((current) => ({ ...current, [key]: event.target.checked }))
                }
              />
            }
            label={label}
          />
        ))}
        <Box sx={{ mt: 2 }}>
          <ProsohmButton onClick={() => saveMutation.mutate()} loading={saveMutation.isPending}>
            Save Notification Settings
          </ProsohmButton>
        </Box>
      </ContentCard>
    </Box>
  );
}
