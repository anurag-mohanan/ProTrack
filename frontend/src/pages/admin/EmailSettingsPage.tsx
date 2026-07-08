import { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  FormControlLabel,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { LoadingState } from '../../components/common/LoadingState';
import { applyZohoDefaults, testEmailConnection } from '../../api/communication';
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
    provider_type: 'zoho',
    smtp_host: 'smtp.zoho.com',
    smtp_port: 465,
    smtp_username: '',
    smtp_password: '',
    use_tls: false,
    use_ssl: true,
    sender_name: '',
    sender_email: '',
    reply_to_email: '',
    company_signature: '',
  });
  const [testAddress, setTestAddress] = useState('');

  useEffect(() => {
    if (query.data) {
      setForm((current) => ({
        ...current,
        enabled: query.data.enabled,
        provider_type: query.data.provider_type ?? 'zoho',
        smtp_host: query.data.smtp_host ?? 'smtp.zoho.com',
        smtp_port: query.data.smtp_port,
        smtp_username: query.data.smtp_username ?? '',
        smtp_password: '',
        use_tls: query.data.use_tls,
        use_ssl: query.data.use_ssl,
        sender_name: query.data.sender_name ?? '',
        sender_email: query.data.sender_email ?? '',
        reply_to_email: query.data.reply_to_email ?? '',
        company_signature: query.data.company_signature ?? '',
      }));
    }
  }, [query.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      updateEmailSettings({
        enabled: form.enabled,
        provider_type: form.provider_type,
        smtp_host: form.smtp_host || null,
        smtp_port: form.smtp_port,
        smtp_username: form.smtp_username || null,
        smtp_password: form.smtp_password || undefined,
        use_tls: form.use_tls,
        use_ssl: form.use_ssl,
        sender_name: form.sender_name || null,
        sender_email: form.sender_email || null,
        reply_to_email: form.reply_to_email || null,
        company_signature: form.company_signature || null,
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

  const connectionMutation = useMutation({
    mutationFn: testEmailConnection,
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['settings', 'email'] });
      if (result.success) showSuccess('SMTP connection successful');
      else showError(result.message ?? 'SMTP connection failed');
    },
    onError: (error: Error) => showError(error.message),
  });

  const zohoMutation = useMutation({
    mutationFn: applyZohoDefaults,
    onSuccess: () => {
      showSuccess('Zoho Mail defaults applied');
      void queryClient.invalidateQueries({ queryKey: ['settings', 'email'] });
    },
    onError: (error: Error) => showError(error.message),
  });

  if (query.isLoading) return <LoadingState message="Loading email settings…" />;

  const connectionStatus = query.data?.connection_status;

  return (
    <Box>
      <PageHeader
        title="Email Settings"
        subtitle="Configure Zoho Mail SMTP for automatic and manual engineering communications"
      />
      {connectionStatus ? (
        <Alert
          severity={connectionStatus === 'connected' ? 'success' : 'warning'}
          sx={{ mb: 2 }}
        >
          Connection status: {connectionStatus}
          {query.data?.connection_message ? ` — ${query.data.connection_message}` : ''}
        </Alert>
      ) : null}
      <ContentCard title="SMTP configuration">
        <Stack spacing={2}>
          <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
            <Chip label="Provider: Zoho Mail" color="primary" variant="outlined" />
            <ProsohmButton
              buttonVariant="outlined"
              onClick={() => zohoMutation.mutate()}
              loading={zohoMutation.isPending}
            >
              Apply Zoho Defaults
            </ProsohmButton>
            <ProsohmButton
              buttonVariant="outlined"
              onClick={() => connectionMutation.mutate()}
              loading={connectionMutation.isPending}
            >
              Test Connection
            </ProsohmButton>
          </Stack>
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
            helperText="Zoho: smtp.zoho.com — port 465 (SSL) or 587 (TLS)"
          />
          <TextField
            label="Port"
            type="number"
            value={form.smtp_port}
            onChange={(event) =>
              setForm((current) => ({ ...current, smtp_port: Number(event.target.value) || 465 }))
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
            label="Use TLS (STARTTLS) — port 587"
          />
          <FormControlLabel
            control={
              <Switch
                checked={form.use_ssl}
                onChange={(event) => setForm((current) => ({ ...current, use_ssl: event.target.checked }))}
              />
            }
            label="Use SSL — port 465 (recommended for Zoho)"
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
          <TextField
            label="Reply-to email"
            value={form.reply_to_email}
            onChange={(event) => setForm((current) => ({ ...current, reply_to_email: event.target.value }))}
          />
          <TextField
            label="Company signature"
            value={form.company_signature}
            onChange={(event) =>
              setForm((current) => ({ ...current, company_signature: event.target.value }))
            }
            multiline
            minRows={3}
            helperText="Appended to all outbound emails"
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
          <Typography variant="caption" color="text.secondary">
            SMTP passwords are encrypted at rest and never returned by the API.
          </Typography>
        </Stack>
      </ContentCard>
    </Box>
  );
}
