import { useState } from 'react';
import { Alert, Box, MenuItem, TextField } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchEfficiency, managementQueryKeys } from '../../api/management';
import type { CockpitFilterValues, ManagementCan } from '../../types/Management';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { valueText } from './managementFormat';
import { DataTable, ExportButton, MetricGrid, NotesList, SectionHeader } from './ManagementParts';

const EFFORT_TITLES: Record<string, string> = {
  classification: 'Approved hours by classification',
  customer: 'Approved hours by customer',
  stage: 'Approved hours by stage',
  task_type: 'Approved hours by task type',
  month: 'Approved hours by month',
};

export function EfficiencyTab({ filters, can }: { filters: CockpitFilterValues; can: ManagementCan }) {
  const [compareBy, setCompareBy] = useState('month');
  const query = useQuery({
    queryKey: managementQueryKeys.efficiency(filters, compareBy),
    queryFn: () => fetchEfficiency(filters, compareBy),
  });
  if (query.isLoading) return <LoadingState message="Loading efficiency…" />;
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  const data = query.data;
  if (!data) return null;
  return (
    <Box>
      <SectionHeader
        title="Engineering efficiency"
        subtitle="Completed projects in the period, compared fairly: like-for-like samples, with the classification mix shown."
        action={
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <TextField select size="small" label="Compare by" value={compareBy} onChange={(e) => setCompareBy(e.target.value)} sx={{ minWidth: 170 }}>
              {data.dimensions.map((d) => (
                <MenuItem key={d.value} value={d.value}>
                  {d.label}
                </MenuItem>
              ))}
            </TextField>
            {can.export ? <ExportButton report="efficiency" filters={filters} extra={{ compare_by: compareBy }} /> : null}
          </Box>
        }
      />
      <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
        {data.fairness_note}
      </Alert>
      <MetricGrid metrics={data.kpis} />
      <DataTable
        rows={data.comparison}
        rowKey={(r) => r.key}
        columns={[
          { label: data.dimension_label, render: (r) => r.label },
          { label: 'Completed', align: 'right', render: (r) => r.completed_projects },
          { label: 'On-time', align: 'right', render: (r) => `${valueText(r.on_time_rate, 'percentage')} (${r.delivery_evaluable})` },
          { label: 'Avg delivery variance', align: 'right', render: (r) => valueText(r.average_variance_days, 'days') },
          { label: 'Approved h', align: 'right', render: (r) => valueText(r.approved_estimate_hours, 'hours') },
          { label: 'Actual h', align: 'right', render: (r) => valueText(r.actual_hours, 'hours') },
          { label: 'Hour variance', align: 'right', render: (r) => `${valueText(r.hour_variance_percent, 'percentage')} (${r.comparable_projects})` },
          {
            label: 'Classification mix',
            render: (r) =>
              Object.entries(r.classification_mix)
                .map(([k, v]) => `${k.replace(/_/g, ' ')} ${v}`)
                .join(', ') || '—',
          },
        ]}
      />
      {Object.entries(data.effort).map(([name, rows]) => (
        <Box key={name}>
          <SectionHeader title={EFFORT_TITLES[name] ?? name} />
          <DataTable
            rows={rows.slice(0, 15)}
            rowKey={(r) => r.key}
            columns={[
              { label: 'Group', render: (r) => r.label },
              { label: 'Hours', align: 'right', render: (r) => valueText(r.hours, 'hours') },
              { label: 'Projects', align: 'right', render: (r) => r.projects },
              { label: 'Share', align: 'right', render: (r) => valueText(r.share_percent, 'percentage') },
            ]}
          />
        </Box>
      ))}
      <NotesList notes={[...data.notes, ...data.warnings.map((w) => w.message)]} />
    </Box>
  );
}
