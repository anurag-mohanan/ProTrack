import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Chip,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { apiClient, getErrorMessage } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { useToast } from '../../context/ToastContext';

type Tenant = {
  id: string;
  slug: string;
  name: string;
  edition: string;
  is_active: boolean;
  terminology: Record<string, string>;
  numbering_policy: Record<string, unknown>;
};

type TenantPack = {
  tenant_id: string;
  slug: string;
  name: string;
  edition: string;
  terminology: Record<string, string>;
  terminology_catalog: Record<string, string>;
  numbering_policy: Record<string, unknown>;
  numbering_catalog: Record<string, unknown>;
  branding: Record<string, unknown>;
  branding_defaults: Record<string, unknown>;
  company: {
    company_name?: string;
    company_short_name?: string | null;
    logo_url?: string | null;
    currency?: string;
    timezone?: string;
  };
  sources: Record<string, string>;
};

type FeatureFlag = {
  id: string;
  tenant_id: string;
  key: string;
  enabled: boolean;
  description: string | null;
};

export default function CommercialSettingsPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [termDraft, setTermDraft] = useState<Record<string, string>>({});
  const [numberDraft, setNumberDraft] = useState<Record<string, string>>({});
  const [apiKeyName, setApiKeyName] = useState('Partner read key');
  const [createdRawKey, setCreatedRawKey] = useState<string | null>(null);
  const [webhookName, setWebhookName] = useState('Default webhook');
  const [webhookUrl, setWebhookUrl] = useState('https://example.com/hooks/protrack');

  const apiKeysQuery = useQuery({
    queryKey: ['commercial', 'api-keys'],
    queryFn: async () =>
      (
        await apiClient.get<
          Array<{
            id: string;
            name: string;
            key_prefix: string;
            scopes: string[];
            is_active: boolean;
          }>
        >('/commercial/api-keys')
      ).data,
  });

  const webhooksQuery = useQuery({
    queryKey: ['commercial', 'webhooks'],
    queryFn: async () =>
      (
        await apiClient.get<
          Array<{
            id: string;
            name: string;
            url: string;
            secret: string;
            events: string[];
            is_active: boolean;
          }>
        >('/commercial/webhooks')
      ).data,
  });

  const deliveriesQuery = useQuery({
    queryKey: ['commercial', 'webhook-deliveries'],
    queryFn: async () =>
      (
        await apiClient.get<
          Array<{
            id: string;
            endpoint_id: string;
            event: string;
            status: string;
            attempts: number;
            max_attempts: number;
            next_attempt_at: string | null;
            last_error: string | null;
          }>
        >('/commercial/webhooks/deliveries')
      ).data,
  });

  const createKeyMutation = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post<{ raw_key: string }>('/commercial/api-keys', {
          name: apiKeyName,
          scopes: ['projects:read', 'milestones:read', 'users:read'],
        })
      ).data,
    onSuccess: (data) => {
      setCreatedRawKey(data.raw_key);
      showSuccess('API key created — copy it now; it will not be shown again');
      void queryClient.invalidateQueries({ queryKey: ['commercial', 'api-keys'] });
    },
    onError: (error) => showError(getErrorMessage(error) || 'Could not create API key'),
  });

  const revokeKeyMutation = useMutation({
    mutationFn: async (id: string) => apiClient.delete(`/commercial/api-keys/${id}`),
    onSuccess: () => {
      showSuccess('API key revoked');
      void queryClient.invalidateQueries({ queryKey: ['commercial', 'api-keys'] });
    },
    onError: (error) => showError(getErrorMessage(error) || 'Could not revoke key'),
  });

  const createWebhookMutation = useMutation({
    mutationFn: async () =>
      apiClient.post('/commercial/webhooks', {
        name: webhookName,
        url: webhookUrl,
        events: ['project.updated', 'ping'],
      }),
    onSuccess: () => {
      showSuccess('Webhook endpoint created');
      void queryClient.invalidateQueries({ queryKey: ['commercial', 'webhooks'] });
    },
    onError: (error) => showError(getErrorMessage(error) || 'Could not create webhook'),
  });

  const pingWebhookMutation = useMutation({
    mutationFn: async () => apiClient.post('/commercial/webhooks/ping', {}),
    onSuccess: () => {
      showSuccess('Webhook ping sent');
      void queryClient.invalidateQueries({ queryKey: ['commercial', 'webhook-deliveries'] });
    },
    onError: (error) => showError(getErrorMessage(error) || 'Ping failed'),
  });

  const processRetriesMutation = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post<
          Array<{ id: string; status: string }>
        >('/commercial/webhooks/process-retries', {})
      ).data,
    onSuccess: (rows) => {
      showSuccess(`Processed ${rows.length} due delivery(ies)`);
      void queryClient.invalidateQueries({ queryKey: ['commercial', 'webhook-deliveries'] });
    },
    onError: (error) => showError(getErrorMessage(error) || 'Could not process retries'),
  });

  const retryDeliveryMutation = useMutation({
    mutationFn: async (id: string) =>
      apiClient.post(`/commercial/webhooks/deliveries/${id}/retry`, {}),
    onSuccess: () => {
      showSuccess('Delivery retry attempted');
      void queryClient.invalidateQueries({ queryKey: ['commercial', 'webhook-deliveries'] });
    },
    onError: (error) => showError(getErrorMessage(error) || 'Retry failed'),
  });

  const tenantQuery = useQuery({
    queryKey: ['commercial', 'me'],
    queryFn: async () => (await apiClient.get<Tenant>('/commercial/me')).data,
  });

  const packQuery = useQuery({
    queryKey: ['commercial', 'pack'],
    queryFn: async () => (await apiClient.get<TenantPack>('/commercial/me/pack')).data,
  });

  const tenantId = tenantQuery.data?.id;
  const flagsQuery = useQuery({
    queryKey: ['commercial', 'flags', tenantId],
    queryFn: async () =>
      (await apiClient.get<FeatureFlag[]>(`/commercial/tenants/${tenantId}/flags`)).data,
    enabled: Boolean(tenantId),
  });

  useEffect(() => {
    if (!packQuery.data) return;
    setTermDraft({ ...packQuery.data.terminology });
    const numbering: Record<string, string> = {};
    Object.entries(packQuery.data.numbering_policy).forEach(([key, value]) => {
      numbering[key] = String(value);
    });
    setNumberDraft(numbering);
  }, [packQuery.data]);

  const toggleMutation = useMutation({
    mutationFn: async (payload: { key: string; enabled: boolean }) =>
      (
        await apiClient.patch<FeatureFlag>(
          `/commercial/tenants/${tenantId}/flags/${payload.key}`,
          { enabled: payload.enabled },
        )
      ).data,
    onSuccess: () => {
      showSuccess('Feature flag updated');
      void queryClient.invalidateQueries({ queryKey: ['commercial', 'flags', tenantId] });
    },
    onError: (error) => showError(getErrorMessage(error) || 'Could not update flag'),
  });

  const terminologyMutation = useMutation({
    mutationFn: async () =>
      (
        await apiClient.patch<TenantPack>('/commercial/me/terminology', {
          terminology: termDraft,
        })
      ).data,
    onSuccess: () => {
      showSuccess('Terminology saved');
      void queryClient.invalidateQueries({ queryKey: ['commercial', 'pack'] });
      void queryClient.invalidateQueries({ queryKey: ['commercial', 'me'] });
    },
    onError: (error) => showError(getErrorMessage(error) || 'Could not save terminology'),
  });

  const numberingMutation = useMutation({
    mutationFn: async () => {
      const numbering_policy: Record<string, unknown> = {};
      Object.entries(numberDraft).forEach(([key, raw]) => {
        if (raw === 'true' || raw === 'false') {
          numbering_policy[key] = raw === 'true';
        } else if (raw !== '' && !Number.isNaN(Number(raw)) && /^-?\d+(\.\d+)?$/.test(raw)) {
          numbering_policy[key] = Number(raw);
        } else {
          numbering_policy[key] = raw;
        }
      });
      return (
        await apiClient.patch<TenantPack>('/commercial/me/numbering', { numbering_policy })
      ).data;
    },
    onSuccess: () => {
      showSuccess('Numbering policy saved');
      void queryClient.invalidateQueries({ queryKey: ['commercial', 'pack'] });
      void queryClient.invalidateQueries({ queryKey: ['commercial', 'me'] });
    },
    onError: (error) => showError(getErrorMessage(error) || 'Could not save numbering'),
  });

  if (tenantQuery.isLoading || packQuery.isLoading) {
    return <LoadingState message="Loading commercial settings…" />;
  }

  const tenant = tenantQuery.data;
  const pack = packQuery.data;
  const flags = flagsQuery.data ?? [];
  const termKeys = Object.keys(pack?.terminology_catalog ?? pack?.terminology ?? {}).sort();

  return (
    <Stack spacing={2}>
      <PageHeader
        title="Commercial / tenancy"
        subtitle="Tenant pack — branding (from Theme settings), terminology, numbering, and feature flags. Prosohm edition keeps all modules ON."
      />

      <ContentCard>
        <Stack spacing={1}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Active tenant
          </Typography>
          {tenant ? (
            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
              <Chip label={tenant.name} color="primary" />
              <Chip label={`slug: ${tenant.slug}`} variant="outlined" />
              <Chip label={`edition: ${tenant.edition}`} color="success" variant="outlined" />
              <Chip
                label={tenant.is_active ? 'active' : 'inactive'}
                color={tenant.is_active ? 'success' : 'default'}
                size="small"
              />
            </Stack>
          ) : (
            <Typography color="error">Tenant not loaded</Typography>
          )}
        </Stack>
      </ContentCard>

      <ContentCard>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
          Branding pack (live)
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Sourced from Admin → Theme. Edit colours there; this view is the tenant façade for
          commercial packaging.
        </Typography>
        {pack ? (
          <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
            <Chip label={pack.company.company_name || 'Company'} color="primary" variant="outlined" />
            <Chip label={`preset: ${String(pack.branding.theme_preset ?? '—')}`} variant="outlined" />
            <Chip
              label={`primary: ${String(pack.branding.primary_color ?? '—')}`}
              variant="outlined"
            />
            <Chip label={`currency: ${pack.company.currency ?? '—'}`} variant="outlined" />
          </Stack>
        ) : null}
      </ContentCard>

      <ContentCard>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1}
          sx={{ justifyContent: 'space-between', alignItems: { sm: 'center' }, mb: 1.5 }}
        >
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Terminology dictionary
          </Typography>
          <ProsohmButton
            size="small"
            onClick={() => terminologyMutation.mutate()}
            disabled={terminologyMutation.isPending}
          >
            Save terminology
          </ProsohmButton>
        </Stack>
        <Stack spacing={1.25}>
          {termKeys.map((key) => (
            <TextField
              key={key}
              size="small"
              label={key}
              value={termDraft[key] ?? ''}
              onChange={(event) =>
                setTermDraft((prev) => ({ ...prev, [key]: event.target.value }))
              }
            />
          ))}
        </Stack>
      </ContentCard>

      <ContentCard>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1}
          sx={{ justifyContent: 'space-between', alignItems: { sm: 'center' }, mb: 1.5 }}
        >
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Numbering policy
          </Typography>
          <ProsohmButton
            size="small"
            onClick={() => numberingMutation.mutate()}
            disabled={numberingMutation.isPending}
          >
            Save numbering
          </ProsohmButton>
        </Stack>
        <Stack spacing={1.25}>
          {Object.keys(pack?.numbering_catalog ?? numberDraft)
            .sort()
            .map((key) => (
              <TextField
                key={key}
                size="small"
                label={key}
                value={numberDraft[key] ?? ''}
                onChange={(event) =>
                  setNumberDraft((prev) => ({ ...prev, [key]: event.target.value }))
                }
                helperText={
                  typeof pack?.numbering_catalog?.[key] === 'boolean'
                    ? 'Use true / false'
                    : undefined
                }
              />
            ))}
        </Stack>
      </ContentCard>

      <ContentCard>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
          Public API keys
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Partner auth for <code>/api/public/v1</code>. Requires feature.public_api.
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mb: 1.5 }}>
          <TextField
            size="small"
            label="Key name"
            value={apiKeyName}
            onChange={(e) => setApiKeyName(e.target.value)}
            fullWidth
          />
          <ProsohmButton
            size="small"
            onClick={() => createKeyMutation.mutate()}
            disabled={createKeyMutation.isPending}
          >
            Create key
          </ProsohmButton>
        </Stack>
        {createdRawKey ? (
          <Typography
            variant="body2"
            sx={{ fontFamily: 'monospace', mb: 1.5, wordBreak: 'break-all' }}
          >
            {createdRawKey}
          </Typography>
        ) : null}
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Prefix</TableCell>
              <TableCell>Active</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(apiKeysQuery.data ?? []).map((key) => (
              <TableRow key={key.id}>
                <TableCell>{key.name}</TableCell>
                <TableCell>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                    {key.key_prefix}…
                  </Typography>
                </TableCell>
                <TableCell>{key.is_active ? 'yes' : 'no'}</TableCell>
                <TableCell align="right">
                  {key.is_active ? (
                    <ProsohmButton
                      size="small"
                      buttonVariant="outlined"
                      onClick={() => revokeKeyMutation.mutate(key.id)}
                    >
                      Revoke
                    </ProsohmButton>
                  ) : null}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ContentCard>

      <ContentCard>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
          Webhooks
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Outbound signed events (HMAC). Requires feature.webhooks.
        </Typography>
        <Stack spacing={1} sx={{ mb: 1.5 }}>
          <TextField
            size="small"
            label="Name"
            value={webhookName}
            onChange={(e) => setWebhookName(e.target.value)}
          />
          <TextField
            size="small"
            label="URL"
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
          />
          <Stack direction="row" spacing={1}>
            <ProsohmButton
              size="small"
              onClick={() => createWebhookMutation.mutate()}
              disabled={createWebhookMutation.isPending}
            >
              Add endpoint
            </ProsohmButton>
            <ProsohmButton
              size="small"
              buttonVariant="outlined"
              onClick={() => pingWebhookMutation.mutate()}
              disabled={pingWebhookMutation.isPending}
            >
              Ping all
            </ProsohmButton>
            <ProsohmButton
              size="small"
              buttonVariant="outlined"
              onClick={() => processRetriesMutation.mutate()}
              disabled={processRetriesMutation.isPending}
            >
              Process retries
            </ProsohmButton>
          </Stack>
        </Stack>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>URL</TableCell>
              <TableCell>Events</TableCell>
              <TableCell>Active</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(webhooksQuery.data ?? []).map((hook) => (
              <TableRow key={hook.id}>
                <TableCell>{hook.name}</TableCell>
                <TableCell>{hook.url}</TableCell>
                <TableCell>{hook.events.join(', ')}</TableCell>
                <TableCell>{hook.is_active ? 'yes' : 'no'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mt: 2, mb: 1 }}>
          Recent deliveries
        </Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Event</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Attempts</TableCell>
              <TableCell>Next attempt</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(deliveriesQuery.data ?? []).slice(0, 15).map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.event}</TableCell>
                <TableCell>{row.status}</TableCell>
                <TableCell>
                  {row.attempts}/{row.max_attempts}
                </TableCell>
                <TableCell>
                  {row.next_attempt_at
                    ? new Date(row.next_attempt_at).toLocaleString()
                    : '—'}
                </TableCell>
                <TableCell align="right">
                  {row.status !== 'delivered' ? (
                    <ProsohmButton
                      size="small"
                      buttonVariant="outlined"
                      onClick={() => retryDeliveryMutation.mutate(row.id)}
                      disabled={retryDeliveryMutation.isPending}
                    >
                      Retry
                    </ProsohmButton>
                  ) : null}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ContentCard>

      <ContentCard>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
          Feature flags
        </Typography>
        {flagsQuery.isLoading ? (
          <LoadingState message="Loading flags…" />
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Key</TableCell>
                <TableCell>Description</TableCell>
                <TableCell align="right">Enabled</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {flags.map((flag) => (
                <TableRow key={flag.key} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {flag.key}
                    </Typography>
                  </TableCell>
                  <TableCell>{flag.description || '—'}</TableCell>
                  <TableCell align="right">
                    <Switch
                      checked={flag.enabled}
                      disabled={toggleMutation.isPending}
                      onChange={(_, checked) =>
                        toggleMutation.mutate({ key: flag.key, enabled: checked })
                      }
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ContentCard>
    </Stack>
  );
}
