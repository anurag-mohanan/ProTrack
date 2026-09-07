import { useState, type ReactNode } from 'react';
import {
  Box,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import {
  fetchAssetAssignments,
  fetchAssetIpHistory,
  fetchAssetLifecycleHistory,
  itOperationsKeys,
} from '../../api/itOperations';
import type { ITAsset } from '../../types/itOperations';
import { formatCellValue, formatDate } from '../../utils/format';
import { ProsohmButton } from '../ui/ProsohmButton';
import { LoadingState } from '../common/LoadingState';

type Props = {
  asset: ITAsset | null;
  onClose: () => void;
};

type TabKey = 'overview' | 'assignment' | 'history';

export function AssetLifecycleDrawer({ asset, onClose }: Props) {
  const [tab, setTab] = useState<TabKey>('overview');
  const open = Boolean(asset);

  const assignmentsQuery = useQuery({
    queryKey: itOperationsKeys.assetAssignments(asset?.id ?? ''),
    queryFn: () => fetchAssetAssignments(asset!.id),
    enabled: open && Boolean(asset?.id) && (tab === 'assignment' || tab === 'history'),
  });

  const ipHistoryQuery = useQuery({
    queryKey: itOperationsKeys.assetIpHistory(asset?.id ?? ''),
    queryFn: () => fetchAssetIpHistory(asset!.id),
    enabled: open && Boolean(asset?.id) && tab === 'history',
  });

  const lifecycleQuery = useQuery({
    queryKey: itOperationsKeys.assetLifecycleHistory(asset?.id ?? ''),
    queryFn: () => fetchAssetLifecycleHistory(asset!.id),
    enabled: open && Boolean(asset?.id) && tab === 'history',
  });

  const previousAssignments = (assignmentsQuery.data ?? []).filter((row) => row.returned_date);
  const openAssignments = (assignmentsQuery.data ?? []).filter((row) => !row.returned_date);

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>
        Asset lifecycle{asset?.asset_number ? ` — ${asset.asset_number}` : ''}
      </DialogTitle>
      <DialogContent dividers>
        <Tabs
          value={tab}
          onChange={(_, value: TabKey) => setTab(value)}
          sx={{ mb: 2, minHeight: 40, borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab value="overview" label="Overview" sx={{ minHeight: 40 }} />
          <Tab value="assignment" label="Assignment" sx={{ minHeight: 40 }} />
          <Tab value="history" label="History" sx={{ minHeight: 40 }} />
        </Tabs>

        {tab === 'overview' && asset ? (
          <Stack spacing={2}>
            <Section title="Identity">
              <DetailRow label="Asset #" value={asset.asset_number} />
              <DetailRow label="Type" value={asset.asset_type_name || asset.asset_type_code} />
              <DetailRow
                label="Make / Model"
                value={[asset.make, asset.model].filter(Boolean).join(' ') || null}
              />
              <DetailRow label="Serial" value={asset.serial_number} />
              <DetailRow label="Status" value={String(asset.status || '').replace(/_/g, ' ')} />
            </Section>
            <Section title="Ownership & location">
              <DetailRow label="Owner type" value={asset.purchased_by} />
              <DetailRow label="Owner customer" value={asset.owner_customer_name} />
              <DetailRow label="Location" value={asset.location} />
              <DetailRow label="Used for customer" value={asset.customer_used_for_name} />
            </Section>
            <Section title="Current user">
              <DetailRow
                label="Assigned to"
                value={asset.assigned_to_user_name || asset.current_assignee_name}
              />
              <Typography variant="caption" color="text.secondary">
                Ownership is separate from who uses the asset.
              </Typography>
            </Section>
          </Stack>
        ) : null}

        {tab === 'assignment' && asset ? (
          <Stack spacing={2}>
            {assignmentsQuery.isLoading ? (
              <LoadingState message="Loading assignment…" />
            ) : openAssignments.length > 0 ? (
              <Section title={openAssignments.length > 1 ? 'Open shared-desk occupants' : 'Current assignment'}>
                {openAssignments.map((row) => (
                  <Box key={row.id} sx={{ mb: 1 }}>
                    <DetailRow label="User" value={row.assigned_to_user_name} />
                    <DetailRow
                      label="Shift slot"
                      value={row.shift_display || row.shift_name || 'Legacy (no shift)'}
                    />
                    <DetailRow label="From" value={formatDate(row.assigned_date)} />
                    <Chip size="small" color="success" label="Current" sx={{ mt: 0.5 }} />
                  </Box>
                ))}
              </Section>
            ) : (
              <Typography color="text.secondary">
                No open assignment — asset is unassigned / open.
              </Typography>
            )}
            <Typography variant="body2" color="text.secondary">
              Shared desks: assign a second user with a different shift_id. History is never
              overwritten.
            </Typography>
          </Stack>
        ) : null}

        {tab === 'history' && asset ? (
          <Stack spacing={2.5}>
            <Section title="Assignment history">
              {assignmentsQuery.isLoading ? (
                <LoadingState message="Loading…" />
              ) : (assignmentsQuery.data ?? []).length === 0 ? (
                <Typography color="text.secondary">No assignment history.</Typography>
              ) : (
                <Stack spacing={1}>
                  {(assignmentsQuery.data ?? []).map((row) => (
                    <HistoryCard
                      key={row.id}
                      title={row.assigned_to_user_name || '—'}
                      subtitle={`${formatDate(row.assigned_date)} → ${
                        row.returned_date ? formatDate(row.returned_date) : 'Current'
                      }`}
                      current={!row.returned_date}
                      extra={row.notes}
                    />
                  ))}
                </Stack>
              )}
            </Section>

            <Section title="IP history">
              {ipHistoryQuery.isLoading ? (
                <LoadingState message="Loading…" />
              ) : (ipHistoryQuery.data ?? []).length === 0 ? (
                <Typography color="text.secondary">
                  No IP assignment history for this asset.
                </Typography>
              ) : (
                <Stack spacing={1}>
                  {(ipHistoryQuery.data ?? []).map((row) => (
                    <HistoryCard
                      key={row.id}
                      title={row.hostname || `IP record ${row.ip_address_id.slice(0, 8)}…`}
                      subtitle={`${formatDate(row.assigned_date)} → ${
                        row.released_date ? formatDate(row.released_date) : 'Current'
                      }`}
                      current={!row.released_date}
                      extra={row.notes}
                    />
                  ))}
                </Stack>
              )}
            </Section>

            <Section title="Ownership history">
              {lifecycleQuery.isLoading ? (
                <LoadingState message="Loading…" />
              ) : (lifecycleQuery.data?.ownership ?? []).length === 0 ? (
                <Typography color="text.secondary">No ownership periods recorded yet.</Typography>
              ) : (
                <Stack spacing={1}>
                  {(lifecycleQuery.data?.ownership ?? []).map((row) => (
                    <HistoryCard
                      key={String(row.id)}
                      title={`${String(row.purchased_by || '—')}${
                        row.owner_customer_id ? ` · customer ${String(row.owner_customer_id).slice(0, 8)}…` : ''
                      }`}
                      subtitle={`${formatDate(String(row.effective_from))} → ${
                        row.effective_to ? formatDate(String(row.effective_to)) : 'Current'
                      }`}
                      current={!row.effective_to}
                    />
                  ))}
                </Stack>
              )}
            </Section>

            <Section title="Location history">
              {(lifecycleQuery.data?.locations ?? []).length === 0 ? (
                <Typography color="text.secondary">No location periods recorded yet.</Typography>
              ) : (
                <Stack spacing={1}>
                  {(lifecycleQuery.data?.locations ?? []).map((row) => (
                    <HistoryCard
                      key={String(row.id)}
                      title={String(row.location || 'Not specified')}
                      subtitle={`${formatDate(String(row.effective_from))} → ${
                        row.effective_to ? formatDate(String(row.effective_to)) : 'Current'
                      }`}
                      current={!row.effective_to}
                    />
                  ))}
                </Stack>
              )}
            </Section>

            <Section title="Status / maintenance history">
              {(lifecycleQuery.data?.statuses ?? []).length === 0 ? (
                <Typography color="text.secondary">No status periods recorded yet.</Typography>
              ) : (
                <Stack spacing={1}>
                  {(lifecycleQuery.data?.statuses ?? []).map((row) => (
                    <HistoryCard
                      key={String(row.id)}
                      title={String(row.status || '—').replace(/_/g, ' ')}
                      subtitle={`${formatDate(String(row.effective_from))} → ${
                        row.effective_to ? formatDate(String(row.effective_to)) : 'Current'
                      }`}
                      current={!row.effective_to}
                      extra={row.reason ? String(row.reason) : null}
                    />
                  ))}
                </Stack>
              )}
            </Section>

            <Section title="Previous users">
              {previousAssignments.length === 0 ? (
                <Typography color="text.secondary">No previous users recorded.</Typography>
              ) : (
                <Stack spacing={0.75}>
                  {previousAssignments.map((row) => (
                    <Typography key={row.id} variant="body2" color="text.secondary">
                      {row.assigned_to_user_name || '—'}
                      {row.shift_display || row.shift_name
                        ? ` · ${row.shift_display || row.shift_name}`
                        : ''}{' '}
                      · {formatDate(row.assigned_date)} → {formatDate(row.returned_date)}
                    </Typography>
                  ))}
                </Stack>
              )}
            </Section>
          </Stack>
        ) : null}
      </DialogContent>
      <DialogActions>
        <ProsohmButton buttonVariant="outlined" onClick={onClose}>
          Close
        </ProsohmButton>
      </DialogActions>
    </Dialog>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
        {title}
      </Typography>
      <Stack spacing={0.75}>{children}</Stack>
    </Box>
  );
}

function DetailRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <Stack direction="row" spacing={1} sx={{ justifyContent: 'space-between', gap: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ minWidth: 120 }}>
        {label}
      </Typography>
      <Typography variant="body2" sx={{ textAlign: 'right', fontWeight: 500 }}>
        {formatCellValue(value)}
      </Typography>
    </Stack>
  );
}

function HistoryCard({
  title,
  subtitle,
  current,
  extra,
}: {
  title: string;
  subtitle: string;
  current?: boolean;
  extra?: string | null;
}) {
  return (
    <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, px: 1.5, py: 1.25 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
        <Typography sx={{ fontWeight: 600, flex: 1 }}>{title}</Typography>
        <Chip
          size="small"
          label={current ? 'Current' : 'Historical'}
          color={current ? 'success' : 'default'}
          variant="outlined"
        />
      </Stack>
      <Typography variant="body2" color="text.secondary">
        {subtitle}
      </Typography>
      {extra ? (
        <Typography variant="body2" color="text.secondary">
          {extra}
        </Typography>
      ) : null}
    </Box>
  );
}
