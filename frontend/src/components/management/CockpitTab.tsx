import { Box, Chip, Paper, Stack, Typography } from '@mui/material';
import { BarChart } from '@mui/x-charts/BarChart';
import type { Cockpit, CockpitFilterValues, HoursBlock } from '../../types/Management';
import { customerColumns, valueText } from './managementFormat';
import { DataTable, ExportButton, HiddenSection, KindChip, MetricGrid, NotesList, SectionHeader } from './ManagementParts';

function HoursCompare({ completed, active }: { completed: HoursBlock; active: HoursBlock }) {
  const rows = [
    { label: 'Original quoted hours', kind: 'Quoted', c: completed.quoted_hours, a: active.quoted_hours },
    { label: 'Current approved hours', kind: 'approved_plan', c: completed.approved_estimate_hours, a: active.approved_estimate_hours },
    { label: 'Actual approved hours', kind: 'actual', c: completed.actual_hours, a: active.actual_hours },
  ];
  return (
    <DataTable
      rows={rows}
      rowKey={(r) => r.label}
      columns={[
        { label: 'Hours', render: (r) => r.label },
        { label: 'Kind', render: (r) => <KindChip kind={r.kind} /> },
        {
          label: 'Completed in period',
          align: 'right',
          render: (r) => `${valueText(r.c.value, 'hours')}${r.c.sample ? ` (${r.c.sample})` : ''}`,
        },
        {
          label: 'Active today (to date)',
          align: 'right',
          render: (r) => `${valueText(r.a.value, 'hours')}${r.a.sample ? ` (${r.a.sample})` : ''}`,
        },
      ]}
    />
  );
}

export function CockpitTab({
  data,
  filters,
  onOpenCustomer,
}: {
  data: Cockpit;
  filters: CockpitFilterValues;
  onOpenCustomer: (id: string) => void;
}) {
  const { business, operations, workforce, customers, definitions, can } = data;
  const period = data.filters.period;
  return (
    <Box>
      <SectionHeader
        title="Business performance"
        subtitle={`${period.label}. Invoiced, awarded, collected and outstanding are separate Finance figures in INR.`}
        action={business.visible && can.export ? <ExportButton report="fy-performance" filters={filters} /> : null}
      />
      {business.visible ? (
        <>
          <MetricGrid metrics={business.kpis} definitions={definitions} />
          <Paper variant="outlined" sx={{ p: 1.5, mb: 2 }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              Monthly invoiced revenue and collections (actuals)
            </Typography>
            <BarChart
              height={260}
              xAxis={[{ scaleType: 'band', data: business.monthly.map((m) => m.month) }]}
              series={[
                { data: business.monthly.map((m) => m.invoiced), label: 'Invoiced' },
                { data: business.monthly.map((m) => m.collected), label: 'Collected' },
              ]}
              margin={{ left: 64, right: 16, top: 24, bottom: 40 }}
            />
          </Paper>
          <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
            <Chip size="small" label={`New customers: ${business.new_vs_repeat.new_customers} (${valueText(business.new_vs_repeat.new_revenue, 'currency')})`} />
            <Chip size="small" label={`Repeat customers: ${business.new_vs_repeat.repeat_customers} (${valueText(business.new_vs_repeat.repeat_revenue, 'currency')})`} />
          </Stack>
          <NotesList notes={[...business.notes, business.new_vs_repeat.note]} />
        </>
      ) : (
        <HiddenSection title="Business performance" reason={business.reason} />
      )}

      <SectionHeader
        title="Engineering operations"
        subtitle="Completed projects (in the period) are kept apart from active projects (today)."
        action={can.export ? <ExportButton report="delivery" filters={filters} /> : null}
      />
      <MetricGrid metrics={operations.kpis} definitions={definitions} />
      <HoursCompare completed={operations.completed.hours} active={operations.active.hours} />
      <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
        Approved hours by stage (booked in the period)
      </Typography>
      <DataTable
        rows={operations.effort_by_stage}
        rowKey={(r) => r.key}
        columns={[
          { label: 'Stage', render: (r) => r.label },
          { label: 'Hours', align: 'right', render: (r) => valueText(r.hours, 'hours') },
          { label: 'Projects', align: 'right', render: (r) => r.projects },
          { label: 'Share', align: 'right', render: (r) => valueText(r.share_percent, 'percentage') },
        ]}
      />
      <NotesList notes={[...operations.notes, ...operations.warnings.map((w) => w.message)]} />

      <SectionHeader
        title="Workforce and capacity"
        subtitle="Virtual and system accounts excluded. Capacity uses shifts, holidays and each person's working hours."
        action={workforce.visible && can.export ? <ExportButton report="utilisation" filters={filters} /> : null}
      />
      {workforce.visible ? (
        <>
          <MetricGrid metrics={[...workforce.kpis, workforce.training.completion_rate]} definitions={definitions} />
          {workforce.bottlenecks.visible ? (
            <Typography variant="body2" sx={{ mb: 1 }}>
              <KindChip kind="forecast" /> Next 4 weeks: {workforce.bottlenecks.people_short} people,{' '}
              {workforce.bottlenecks.teams_short} teams and {workforce.bottlenecks.skills_short} skills forecast short.{' '}
              {workforce.bottlenecks.note}
            </Typography>
          ) : null}
          {workforce.skills.visible ? (
            <>
              <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
                Skills: {workforce.skills.skills_with_verified_coverage} of {workforce.skills.skills_tracked} tracked skills have a
                verified holder; {workforce.skills.single_specialist_skills} depend on one verified specialist.
              </Typography>
              <DataTable
                rows={workforce.skills.distribution}
                rowKey={(r) => r.category}
                empty="No skills are tracked yet."
                columns={[
                  { label: 'Skill category', render: (r) => r.category },
                  { label: 'Skills', align: 'right', render: (r) => r.skills },
                  { label: 'Verified records', align: 'right', render: (r) => r.verified_records },
                  { label: 'Skills without a verified holder', align: 'right', render: (r) => r.skills_without_verified },
                ]}
              />
              <NotesList title="Critical skill gaps" notes={workforce.skills.critical_gaps.map((g) => g.explanation)} />
            </>
          ) : (
            <HiddenSection title="Skills" reason={workforce.skills.reason} />
          )}
          <NotesList title="Limitations" notes={workforce.limitations} />
        </>
      ) : (
        <HiddenSection title="Workforce" reason={workforce.reason} />
      )}

      <SectionHeader
        title={`Customers (top ${customers.rows.length} of ${customers.total})`}
        subtitle="Select a customer for the full profile."
      />
      <DataTable
        rows={customers.rows}
        rowKey={(r) => r.customer_id}
        onRowClick={(r) => onOpenCustomer(r.customer_id)}
        columns={customerColumns(customers.finance_visible)}
      />
      <NotesList notes={customers.notes} />
      <Typography variant="caption" color="text.secondary">
        {data.principle}
      </Typography>
    </Box>
  );
}
