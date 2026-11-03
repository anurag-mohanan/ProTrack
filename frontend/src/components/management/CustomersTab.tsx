import { Alert, Box, Button, Paper, Stack, Typography } from '@mui/material';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import { useQuery } from '@tanstack/react-query';
import { fetchCustomerProfile, fetchCustomerTable, managementQueryKeys } from '../../api/management';
import type { CockpitFilterValues, DeliveryStats, ManagementCan } from '../../types/Management';
import { formatDate } from '../../utils/format';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { customerColumns, statusLabel, valueText } from './managementFormat';
import { DataTable, ExportButton, KindChip, MetricGrid, NotesList, SectionHeader } from './ManagementParts';

function DeliveryCards({ title, stats }: { title: string; stats: DeliveryStats }) {
  return (
    <Paper variant="outlined" sx={{ p: 1.5, flex: 1, minWidth: 240 }}>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>
        {title} <KindChip kind="actual" />
      </Typography>
      <Typography variant="body2">Completed projects: {stats.completed_projects}</Typography>
      <Typography variant="body2">
        On time: {valueText(stats.on_time_rate, 'percentage')} ({stats.on_time} of {stats.delivery_evaluable} with a baseline)
      </Typography>
      <Typography variant="body2">Average delivery variance: {valueText(stats.average_variance_days, 'days')}</Typography>
      <Typography variant="body2">
        Hour variance: {valueText(stats.hour_variance_percent, 'percentage')} ({stats.comparable_projects} comparable,{' '}
        {stats.projects_over_estimate} over estimate)
      </Typography>
    </Paper>
  );
}

function CustomerProfileView({ customerId, filters, onBack }: { customerId: string; filters: CockpitFilterValues; onBack: () => void }) {
  const query = useQuery({
    queryKey: managementQueryKeys.customer(customerId, filters),
    queryFn: () => fetchCustomerProfile(customerId, filters),
  });
  if (query.isLoading) return <LoadingState message="Loading customer…" />;
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  const p = query.data;
  if (!p) return null;
  return (
    <Box>
      <Button size="small" startIcon={<ArrowBackRoundedIcon />} onClick={onBack} sx={{ mb: 1 }}>
        All customers
      </Button>
      <Typography variant="h6" sx={{ fontWeight: 700 }}>
        {p.customer.name}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {[p.customer.code, p.customer.city, p.customer.country].filter(Boolean).join(' · ') || 'No location recorded'} ·{' '}
        {p.projects.total} project(s) ·{' '}
        {p.contacts.length ? `Contacts: ${p.contacts.map((c) => c.name + (c.is_primary ? ' (primary)' : '')).join(', ')}` : 'No contacts'}
      </Typography>

      {p.finance ? (
        <>
          <SectionHeader title="Finance (INR)" />
          <MetricGrid metrics={p.finance.kpis} />
        </>
      ) : (
        <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
          Revenue and payment figures need Finance view access.
        </Alert>
      )}

      <SectionHeader title="Delivery" />
      <Stack direction="row" spacing={1.5} useFlexGap sx={{ flexWrap: 'wrap', mb: 2 }}>
        <DeliveryCards title="In the selected period" stats={p.delivery.period} />
        <DeliveryCards title="Five-year history" stats={p.delivery.history} />
      </Stack>

      <SectionHeader title="Observed signals" subtitle="Evidence from recorded history, not predictions." />
      {p.signals.length ? (
        <Box component="ul" sx={{ mt: 0, pl: 2.5 }}>
          {p.signals.map((s) => (
            <li key={s.code}>
              <Typography variant="body2">
                <strong>{s.label}</strong>: {s.evidence}
              </Typography>
            </li>
          ))}
        </Box>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          No signal meets its evidence threshold.
        </Typography>
      )}
      <NotesList title="Not assessable" notes={p.not_assessable.map((n) => n.reason)} />

      <SectionHeader title="Trend by financial year" />
      <DataTable
        rows={p.trend}
        rowKey={(r) => String(r.fy_start_year)}
        columns={[
          { label: 'Financial year', render: (r) => r.label },
          { label: 'Completed', align: 'right', render: (r) => r.completed_projects },
          { label: 'On-time', align: 'right', render: (r) => valueText(r.on_time_rate, 'percentage') },
          { label: 'Hour variance', align: 'right', render: (r) => valueText(r.hour_variance_percent, 'percentage') },
          ...(p.finance_visible
            ? [{ label: 'Invoiced', align: 'right' as const, render: (r: (typeof p.trend)[number]) => valueText(r.invoiced, 'currency') }]
            : []),
        ]}
      />

      <SectionHeader title={`Active projects (${p.projects.active.length})`} />
      <DataTable
        rows={p.projects.active}
        rowKey={(r) => r.project_id}
        columns={[
          { label: 'Project', render: (r) => r.code ?? r.tool_number ?? '—' },
          { label: 'Status', render: (r) => statusLabel(r.status) },
          { label: 'Target date', render: (r) => (r.current_target_date ? formatDate(r.current_target_date) : '—') },
          { label: 'Delivery', render: (r) => statusLabel(r.delivery_status) },
        ]}
      />

      <SectionHeader title="Forecasts" subtitle={p.forecasts.note} />
      <DataTable
        rows={p.forecasts.items}
        rowKey={(r, i) => `${r.prediction_type}-${i}`}
        empty="No current forecasts for this customer's projects."
        columns={[
          { label: 'Kind', render: () => <KindChip kind="forecast" /> },
          { label: 'Forecast', render: (r) => statusLabel(r.prediction_type) },
          { label: 'Subject', render: (r) => r.subject },
          {
            label: 'Predicted',
            render: (r) => (r.predicted_date ? formatDate(r.predicted_date) : `${r.predicted_value ?? '—'} ${r.unit ?? ''}`),
          },
          { label: 'As of', render: (r) => formatDate(r.as_of) },
        ]}
      />
      <NotesList notes={p.notes} />
    </Box>
  );
}

export function CustomersTab({
  filters,
  can,
  customerId,
  onSelect,
}: {
  filters: CockpitFilterValues;
  can: ManagementCan;
  customerId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const query = useQuery({
    queryKey: managementQueryKeys.customers(filters),
    queryFn: () => fetchCustomerTable(filters),
    enabled: !customerId,
  });
  if (customerId) return <CustomerProfileView customerId={customerId} filters={filters} onBack={() => onSelect(null)} />;
  if (query.isLoading) return <LoadingState message="Loading customers…" />;
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  const data = query.data;
  if (!data) return null;
  return (
    <Box>
      <SectionHeader
        title="Customer performance"
        subtitle="Delivery for every customer in scope; revenue columns appear with Finance access. No profitability is shown."
        action={can.export && can.finance ? <ExportButton report="customer-contribution" filters={filters} /> : null}
      />
      <DataTable
        rows={data.rows}
        rowKey={(r) => r.customer_id}
        onRowClick={(r) => onSelect(r.customer_id)}
        columns={customerColumns(data.finance_visible)}
      />
      <NotesList notes={data.notes} />
    </Box>
  );
}
