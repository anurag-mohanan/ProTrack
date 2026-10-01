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
  TextField,
  Typography,
} from '@mui/material';
import { fetchAssetSchedule, itAllocationKeys } from '../../api/itAllocation';
import { ScheduleTimeline } from './allocation/ScheduleTimeline';
import { useQuery } from '@tanstack/react-query';
import {
  fetchAssetAssignments,
  fetchAssetChildren,
  fetchAssetIpHistory,
  fetchAssetLifecycleHistory,
  fetchComputerInterfaces,
  fetchSoftwareInstallations,
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

type TabKey = 'overview' | 'assignment' | 'schedule' | 'history';

export function AssetLifecycleDrawer({ asset, onClose }: Props) {
  const [tab, setTab] = useState<TabKey>('overview');
  const [scheduleDate, setScheduleDate] = useState(() => new Date().toISOString().slice(0, 10));
  const open = Boolean(asset);

  const scheduleQuery = useQuery({
    queryKey: itAllocationKeys.assetSchedule(asset?.id ?? '', scheduleDate),
    queryFn: () => fetchAssetSchedule(asset!.id, scheduleDate || undefined),
    enabled: open && Boolean(asset?.id) && tab === 'schedule',
  });

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

  const childrenQuery = useQuery({
    queryKey: itOperationsKeys.assetChildren(asset?.id ?? ''),
    queryFn: () => fetchAssetChildren(asset!.id),
    enabled: open && Boolean(asset?.id) && tab === 'overview',
  });

  const softwareQuery = useQuery({
    queryKey: itOperationsKeys.softwareInstallations({
      computer_id: asset?.computer_id ?? '',
      active_only: true,
    }),
    queryFn: () =>
      fetchSoftwareInstallations({
        computer_id: asset!.computer_id!,
        active_only: true,
      }),
    enabled: open && Boolean(asset?.computer_id) && tab === 'overview',
  });

  const interfacesQuery = useQuery({
    queryKey: itOperationsKeys.computerInterfaces(asset?.computer_id ?? ''),
    queryFn: () => fetchComputerInterfaces(asset!.computer_id!),
    enabled: open && Boolean(asset?.computer_id) && tab === 'overview',
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
          <Tab value="schedule" label="Schedule" sx={{ minHeight: 40 }} />
          <Tab value="history" label="History" sx={{ minHeight: 40 }} />
        </Tabs>

        {tab === 'overview' && asset ? (
          <Stack spacing={2}>
            <Section title="Identity">
              <DetailRow label="Asset #" value={asset.asset_number} />
              {(asset.previous_asset_numbers ?? []).length > 0 ? (
                <DetailRow
                  label="Previous #s"
                  value={asset.previous_asset_numbers!.join(', ')}
                />
              ) : null}
              <DetailRow label="Type" value={asset.asset_type_name || asset.asset_type_code} />
              {asset.computer_name ? (
                <DetailRow label="Computer name" value={asset.computer_name} />
              ) : null}
              <DetailRow
                label="Make / Model"
                value={[asset.make, asset.model].filter(Boolean).join(' ') || null}
              />
              <DetailRow label="Serial" value={asset.serial_number} />
              <DetailRow label="Status" value={String(asset.status || '').replace(/_/g, ' ')} />
            </Section>
            {asset.computer_name || asset.primary_ip || asset.mac_address ? (
              <Section title="Network">
                <DetailRow label="Primary IP" value={asset.primary_ip} />
                <DetailRow label="IP type" value={asset.ip_allocation_type} />
                <DetailRow label="MAC" value={asset.mac_address} />
                <DetailRow
                  label="Network"
                  value={
                    asset.network_cidr
                      ? `${asset.network_name ? `${asset.network_name} · ` : ''}${asset.network_cidr}`
                      : null
                  }
                />
              </Section>
            ) : null}
            {asset.computer_id ? (
              <Section title="Network interfaces">
                {interfacesQuery.isLoading ? (
                  <LoadingState message="Loading interfaces…" />
                ) : (interfacesQuery.data ?? []).length === 0 ? (
                  <Typography color="text.secondary">
                    No extra NICs recorded. Add interfaces from Computers when this machine has more
                    than one adapter.
                  </Typography>
                ) : (
                  (interfacesQuery.data ?? []).map((row) => (
                    <DetailRow
                      key={row.id}
                      label={row.name}
                      value={`${row.role}${row.mac_address ? ` · ${row.mac_address}` : ''}${
                        row.is_primary ? ' · primary' : ''
                      }`}
                    />
                  ))
                )}
              </Section>
            ) : null}
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
              <DetailRow label="Team" value={asset.current_assignee_team} />
              <DetailRow label="Shift" value={asset.current_shift_display} />
              <Typography variant="caption" color="text.secondary">
                Ownership is separate from who uses the asset. Shift comes from Resource Planning.
              </Typography>
            </Section>
            {asset.computer_id ? (
              <Section title="Software">
                {softwareQuery.isLoading ? (
                  <LoadingState message="Loading software…" />
                ) : (softwareQuery.data ?? []).length === 0 ? (
                  <Typography color="text.secondary">No active installations on this computer.</Typography>
                ) : (
                  (softwareQuery.data ?? []).map((row) => (
                    <DetailRow
                      key={row.id}
                      label={row.software_name || 'Software'}
                      value={row.installed_date ? `Installed ${formatDate(row.installed_date)}` : 'Installed'}
                    />
                  ))
                )}
              </Section>
            ) : null}
            <Section title="Assigned peripherals">
              {childrenQuery.isLoading ? (
                <LoadingState message="Loading peripherals…" />
              ) : (childrenQuery.data ?? []).length === 0 ? (
                <Typography color="text.secondary">
                  No child assets linked to this computer.
                </Typography>
              ) : (
                (childrenQuery.data ?? []).map((child) => (
                  <DetailRow
                    key={child.id}
                    label={child.asset_type_name || child.asset_type_code || 'Asset'}
                    value={`${child.asset_number}${
                      [child.make, child.model].filter(Boolean).length
                        ? ` · ${[child.make, child.model].filter(Boolean).join(' ')}`
                        : ''
                    }`}
                  />
                ))
              )}
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
                      label="Assigned"
                      value={
                        row.needs_review
                          ? 'LEGACY / NEEDS REVIEW'
                          : row.window_label || row.shift_display || row.shift_name || 'All hours'
                      }
                    />
                    <DetailRow
                      label="Dates"
                      value={`${formatDate(row.assigned_date)} → ${
                        row.planned_end_date ? formatDate(row.planned_end_date) : 'open'
                      }`}
                    />
                    {row.purpose ? <DetailRow label="Purpose" value={row.purpose} /> : null}
                    {row.override_reason ? (
                      <DetailRow label="Override reason" value={row.override_reason} />
                    ) : null}
                    <Chip
                      size="small"
                      color={row.needs_review ? 'warning' : 'success'}
                      label={row.needs_review ? 'Needs review' : 'Current'}
                      sx={{ mt: 0.5 }}
                    />
                  </Box>
                ))}
              </Section>
            ) : (
              <Typography color="text.secondary">
                No open assignment — asset is unassigned / open.
              </Typography>
            )}
            <Typography variant="body2" color="text.secondary">
              Shareable resources can hold several users as long as their shift or time windows do not
              overlap. See the Schedule tab for free gaps. History is never overwritten.
            </Typography>
          </Stack>
        ) : null}

        {tab === 'schedule' && asset ? (
          <Stack spacing={2}>
            <TextField
              type="date"
              size="small"
              label="Date"
              value={scheduleDate}
              onChange={(e) => setScheduleDate(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              sx={{ maxWidth: 200 }}
            />
            {scheduleQuery.isLoading ? (
              <LoadingState message="Loading schedule…" />
            ) : scheduleQuery.isError ? (
              <Typography color="error">Could not load the schedule for this asset.</Typography>
            ) : scheduleQuery.data ? (
              <>
                <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
                  <Chip
                    size="small"
                    label={scheduleQuery.data.policy.shareable ? 'Shareable across shifts' : 'Exclusive (one user)'}
                    color={scheduleQuery.data.policy.shareable ? 'info' : 'default'}
                  />
                  {scheduleQuery.data.policy.requires_shift ? (
                    <Chip size="small" variant="outlined" label="Shift required" />
                  ) : null}
                  <Chip
                    size="small"
                    color={scheduleQuery.data.lifecycle_ok ? 'success' : 'error'}
                    label={`Lifecycle: ${scheduleQuery.data.lifecycle_status.replace(/_/g, ' ')}`}
                  />
                </Stack>
                {!scheduleQuery.data.lifecycle_ok && scheduleQuery.data.lifecycle_reason ? (
                  <Typography variant="body2" color="error">
                    {scheduleQuery.data.lifecycle_reason}
                  </Typography>
                ) : null}
                <Section title="Occupancy (24 h)">
                  <ScheduleTimeline blocks={scheduleQuery.data.blocks} />
                </Section>
                <Section title="Assignments & reservations on this date">
                  {scheduleQuery.data.assignments.length === 0 ? (
                    <Typography color="text.secondary">Free for the whole day.</Typography>
                  ) : (
                    scheduleQuery.data.assignments.map((row) => (
                      <DetailRow
                        key={row.id}
                        label={row.user_name || (row.kind === 'reservation' ? 'Reserved' : 'Assigned')}
                        value={`${row.kind === 'reservation' ? 'Reservation · ' : ''}${row.window}${
                          row.legacy ? ' · LEGACY / NEEDS REVIEW' : ''
                        } · ${row.dates}`}
                      />
                    ))
                  )}
                </Section>
              </>
            ) : null}
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
                      title={row.address || row.hostname || `IP ${row.ip_address_id.slice(0, 8)}…`}
                      subtitle={`${formatDate(row.assigned_date)} → ${
                        row.released_date ? formatDate(row.released_date) : 'Current'
                      }`}
                      current={!row.released_date}
                      extra={[row.network_cidr, row.hostname, row.notes].filter(Boolean).join(' · ') || null}
                    />
                  ))}
                </Stack>
              )}
            </Section>

            <Section title="Computer name history">
              {(lifecycleQuery.data?.computer_names ?? []).length === 0 ? (
                <Typography color="text.secondary">No computer-name periods recorded yet.</Typography>
              ) : (
                <Stack spacing={1}>
                  {(lifecycleQuery.data?.computer_names ?? []).map((row) => (
                    <HistoryCard
                      key={String(row.id)}
                      title={String(row.computer_name || '—')}
                      subtitle={`${formatDate(String(row.effective_from))} → ${
                        row.effective_to ? formatDate(String(row.effective_to)) : 'Current'
                      }`}
                      current={!row.effective_to}
                      extra={row.reason ? String(row.reason).replace(/_/g, ' ') : null}
                    />
                  ))}
                </Stack>
              )}
            </Section>

            <Section title="Asset number history">
              {(lifecycleQuery.data?.asset_numbers ?? []).length === 0 ? (
                <Typography color="text.secondary">No asset-number periods recorded yet.</Typography>
              ) : (
                <Stack spacing={1}>
                  {(lifecycleQuery.data?.asset_numbers ?? []).map((row) => (
                    <HistoryCard
                      key={String(row.id)}
                      title={String(row.asset_number || '—')}
                      subtitle={`${formatDate(String(row.effective_from))} → ${
                        row.effective_to ? formatDate(String(row.effective_to)) : 'Current'
                      }`}
                      current={!row.effective_to}
                      extra={row.reason ? String(row.reason).replace(/_/g, ' ') : null}
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
