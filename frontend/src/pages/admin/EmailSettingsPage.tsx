import { useEffect, useState } from 'react';
import { Box, FormControlLabel, Stack, Switch, TextField } from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { LoadingState } from '../../components/common/LoadingState';
import {
  fetchEmailSettings,
  sendEmailTest,
  updateEmailSettings,
} from '../../api/settings';
import { useToast } from '../../context/ToastContext';

export default function EmailSettingsPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ['settings', 'email'], queryFn: fetchEmailSettings });
  const [form, setForm] = useState({
    enabled: false,
    smtp_host: '',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: '',
    use_tls: true,
    use_ssl: false,
    sender_name: '',
    sender_email: '',
  });
  const [testAddress, setTestAddress] = useState('');

  useEffect(() => {
    if (query.data) {
      setForm((current) => ({
        ...current,
        enabled: query.data.enabled,
        smtp_host: query.data.smtp_host ?? '',
        smtp_port: query.data.smtp_port,
        smtp_username: query.data.smtp_username ?? '',
        smtp_password: '',
        use_tls: query.data.use_tls,
        use_ssl: query.data.use_ssl,
        sender_name: query.data.sender_name ?? '',
        sender_email: query.data.sender_email ?? '',
      }));
    }
  }, [query.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      updateEmailSettings({
        enabled: form.enabled,
        smtp_host: form.smtp_host || null,
        smtp_port: form.smtp_port,
        smtp_username: form.smtp_username || null,
        smtp_password: form.smtp_password || undefined,
        use_tls: form.use_tls,
        use_ssl: form.use_ssl,
        sender_name: form.sender_name || null,
        sender_email: form.sender_email || null,
      }),
    onSuccess: () => {
      showSuccess('Email settings saved');
      void queryClient.invalidateQueries({ queryKey: ['settings', 'email'] });
    },
    onError: (error: Error) => showError(error.message),
  });

  const testMutation = useMutation({
    mutationFn: () => sendEmailTest(testAddress),
    onSuccess: () => showSuccess('Test email sent'),
    onError: (error: Error) => showError(error.message),
  });

  if (query.isLoading) return <LoadingState message="Loading email settings…" />;

  return (
    <Box>
      <PageHeader
        title="Email Settings"
        subtitle="Configure SMTP for automatic and manual engineering notifications"
      />
      <ContentCard title="SMTP configuration">
        <Stack spacing={2}>
          <FormControlLabel
            control={
              <Switch
                checked={form.enabled}
                onChange={(event) => setForm((current) => ({ ...current, enabled: event.target.checked }))}
              />
            }
            label="Enable outbound email"
          />
          <TextField
            label="SMTP server"
            value={form.smtp_host}
            onChange={(event) => setForm((current) => ({ ...current, smtp_host: event.target.value }))}
          />
          <TextField
            label="Port"
            type="number"
            value={form.smtp_port}
            onChange={(event) =>
              setForm((current) => ({ ...current, smtp_port: Number(event.target.value) || 587 }))
            }
          />
          <TextField
            label="Username"
            value={form.smtp_username}
            onChange={(event) => setForm((current) => ({ ...current, smtp_username: event.target.value }))}
          />
          <TextField
            label={query.data?.has_password ? 'Password (leave blank to keep current)' : 'Password'}
            type="password"
            value={form.smtp_password}
            onChange={(event) => setForm((current) => ({ ...current, smtp_password: event.target.value }))}
          />
          <FormControlLabel
            control={
              <Switch
                checked={form.use_tls}
                onChange={(event) => setForm((current) => ({ ...current, use_tls: event.target.checked }))}
              />
            }
            label="Use TLS (STARTTLS)"
          />
          <FormControlLabel
            control={
              <Switch
                checked={form.use_ssl}
                onChange={(event) => setForm((current) => ({ ...current, use_ssl: event.target.checked }))}
              />
            }
            label="Use SSL"
          />
          <TextField
            label="Sender name"
            value={form.sender_name}
            onChange={(event) => setForm((current) => ({ ...current, sender_name: event.target.value }))}
          />
          <TextField
            label="Sender email"
            value={form.sender_email}
            onChange={(event) => setForm((current) => ({ ...current, sender_email: event.target.value }))}
          />
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
            <ProsohmButton onClick={() => saveMutation.mutate()} loading={saveMutation.isPending}>
              Save Email Settings
            </ProsohmButton>
            <TextField
              size="small"
              label="Test recipient"
              value={testAddress}
              onChange={(event) => setTestAddress(event.target.value)}
              sx={{ minWidth: 260 }}
            />
            <ProsohmButton
              buttonVariant="outlined"
              onClick={() => testMutation.mutate()}
              loading={testMutation.isPending}
              disabled={!testAddress.trim()}
            >
              Send Test Email
            </ProsohmButton>
          </Stack>
        </Stack>
      </ContentCard>
    </Box>
  );
}
