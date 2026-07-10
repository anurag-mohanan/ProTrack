import { useMemo } from 'react';
import { TableRow } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { AnalyticsBarChart, AnalyticsDonutChart, AnalyticsLineChart } from '../analytics/AnalyticsCharts';
import { DrillDownBreadcrumbs } from '../analytics/DrillDownBreadcrumbs';
import { KpiStrip } from '../analytics/KpiStrip';
import { ReportAnalyticsShell } from '../analytics/ReportAnalyticsShell';
import { ExecutionStatusChip } from '../common/StatusChip';
import { useDrillDown } from '../../hooks/useDrillDown';
import {
  ClickableTableRow,
  HealthIndicator,
  KpiMetricCard,
  OperationalDataTable,
  StickyHeaderCell,
  StickyTableCell,
} from '../ui/design-system';
import type {
  BillableUtilizationReportRow,
  BillableVsNonBillableReportRow,
  CustomerSummaryReportRow,
  ExecutionStatusSummaryRow,
  MonthlyNpTrendReportRow,
  NonProductiveHoursReportRow,
  NpHoursByDesignerReportRow,
  ProductiveHoursReportRow,
  ProjectHoursReportRow,
  ProjectPortfolioReportRow,
  ProjectStageSummaryRow,
  TopNpActivityReportRow,
} from '../../types/Reports';
import type { DesignerWorkload } from '../../types/Dashboard';
import { EXECUTION_STATUS_LABELS, PROJECT_STAGE_LABELS } from '../../types/common';
import { formatCellValue, formatNumber } from '../../utils/format';
import FolderRoundedIcon from '@mui/icons-material/FolderRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import PaidRoundedIcon from '@mui/icons-material/PaidRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';

interface ReportExportProps {
  canExport: boolean;
}

export function ProjectHoursReportView({
  rows,
  canExport,
}: { rows: ProjectHoursReportRow[] } & ReportExportProps) {
  const navigate = useNavigate();
  const drill = useDrillDown();
  const filtered = useMemo(() => {
    const customer = drill.current?.type === 'customer' ? drill.current.label : null;
    if (!customer) return rows;
    return rows.filter((r) => r.customer_name === customer);
  }, [rows, drill.current]);

  const topCustomers = useMemo(() => {
    const map = new Map<string, number>();
    rows.forEach((r) => map.set(r.customer_name, (map.get(r.customer_name) ?? 0) + r.actual_hours));
    return [...map.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([label, value], index) => ({ id: String(index), label, value }));
  }, [rows]);

  return (
    <>
      <DrillDownBreadcrumbs stack={drill.stack} onNavigate={drill.navigateTo} onReset={drill.reset} />
      <ReportAnalyticsShell
        title="Project Hours"
        subtitle="Quoted vs actual hours by project"
        canExport={canExport}
        exportFilename="project-hours"
        exportRows={filtered as unknown as Record<string, unknown>[]}
        exportColumns={[
          { key: 'tool_number', header: 'Tool Number' },
          { key: 'customer_name', header: 'Customer' },
          { key: 'quoted_hours', header: 'Quoted', format: (r) => formatNumber(r.quoted_hours as number) },
          { key: 'actual_hours', header: 'Actual', format: (r) => formatNumber(r.actual_hours as number) },
        ]}
        kpis={
          <KpiStrip columns={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard compact title="Projects" value={String(filtered.length)} icon={FolderRoundedIcon} />
            <KpiMetricCard
              compact
              title="Quoted Hours"
              value={formatNumber(filtered.reduce((s, r) => s + r.quoted_hours, 0))}
              icon={ScheduleRoundedIcon}
            />
            <KpiMetricCard
              compact
              title="Actual Hours"
              value={formatNumber(filtered.reduce((s, r) => s + r.actual_hours, 0))}
              icon={PaidRoundedIcon}
            />
            <KpiMetricCard
              compact
              title="Variance"
              value={formatNumber(filtered.reduce((s, r) => s + r.hours_variance, 0))}
              icon={GroupsRoundedIcon}
              accent="warning"
            />
          </KpiStrip>
        }
        chart={
          <AnalyticsBarChart
            horizontal
            categories={topCustomers.map((c) => c.label)}
            series={[{ label: 'Actual hours', data: topCustomers.map((c) => c.value) }]}
          />
        }
      >
        <OperationalDataTable
          maxHeight={520}
          head={
            <TableRow>
              <StickyHeaderCell pinned>Tool Number</StickyHeaderCell>
              <StickyHeaderCell>Customer</StickyHeaderCell>
              <StickyHeaderCell align="right">Quoted</StickyHeaderCell>
              <StickyHeaderCell align="right">Actual</StickyHeaderCell>
              <StickyHeaderCell align="right">Variance</StickyHeaderCell>
              <StickyHeaderCell>Stage</StickyHeaderCell>
              <StickyHeaderCell>Status</StickyHeaderCell>
              <StickyHeaderCell align="right">Support</StickyHeaderCell>
              <StickyHeaderCell align="right">Peer Review</StickyHeaderCell>
              <StickyHeaderCell align="right">EC Hours</StickyHeaderCell>
              <StickyHeaderCell>Contributors</StickyHeaderCell>
            </TableRow>
          }
        >
          {filtered.map((row) => (
            <ClickableTableRow
              key={row.project_id}
              onClick={() => {
                drill.push({ id: row.customer_name, label: row.customer_name, type: 'customer' });
                drill.push({ id: row.project_id, label: row.tool_number, type: 'project' });
                navigate(`/projects/${row.project_id}`);
              }}
            >
              <StickyTableCell pinned>{row.tool_number}</StickyTableCell>
              <StickyTableCell>{row.customer_name}</StickyTableCell>
              <StickyTableCell align="right">{formatNumber(row.quoted_hours)}</StickyTableCell>
              <StickyTableCell align="right">{formatNumber(row.actual_hours)}</StickyTableCell>
              <StickyTableCell align="right">{formatNumber(row.hours_variance)}</StickyTableCell>
              <StickyTableCell>{PROJECT_STAGE_LABELS[row.project_stage]}</StickyTableCell>
              <StickyTableCell>
                <ExecutionStatusChip status={row.execution_status} />
              </StickyTableCell>
              <StickyTableCell align="right">{formatNumber(row.support_hours ?? 0, 1)}</StickyTableCell>
              <StickyTableCell align="right">{formatNumber(row.peer_review_hours ?? 0, 1)}</StickyTableCell>
              <StickyTableCell align="right">
                {formatNumber(row.engineering_change_hours ?? 0, 1)}
              </StickyTableCell>
              <StickyTableCell>
                {(row.contributors ?? [])
                  .slice(0, 3)
                  .map(
                    (c) =>
                      `${c.user_name} (${formatNumber(c.total_hours, 1)}h${
                        c.primary_contribution_label ? ` · ${c.primary_contribution_label}` : ''
                      })`,
                  )
                  .join(', ') || '—'}
              </StickyTableCell>
            </ClickableTableRow>
          ))}
        </OperationalDataTable>
      </ReportAnalyticsShell>
    </>
  );
}

export function CustomerSummaryReportView({
  rows,
  canExport,
}: { rows: CustomerSummaryReportRow[] } & ReportExportProps) {
  const drill = useDrillDown();
  const chartData = rows.slice(0, 8).map((r) => ({
    id: r.customer_id,
    label: r.customer_name,
    value: r.total_actual_hours,
  }));

  return (
    <ReportAnalyticsShell
      title="Customer Analytics"
      subtitle="Projects, hours, and variance by customer"
      canExport={canExport}
      exportFilename="customer-summary"
      exportRows={rows as unknown as Record<string, unknown>[]}
      exportColumns={[
        { key: 'customer_name', header: 'Customer' },
        { key: 'project_count', header: 'Projects' },
        { key: 'total_actual_hours', header: 'Actual Hours', format: (r) => formatNumber(r.total_actual_hours as number) },
      ]}
      chart={<AnalyticsDonutChart data={chartData} />}
    >
      <OperationalDataTable
        maxHeight={480}
        head={
          <TableRow>
            <StickyHeaderCell pinned>Customer</StickyHeaderCell>
            <StickyHeaderCell align="right">Projects</StickyHeaderCell>
            <StickyHeaderCell align="right">Quoted</StickyHeaderCell>
            <StickyHeaderCell align="right">Actual</StickyHeaderCell>
            <StickyHeaderCell align="right">Variance</StickyHeaderCell>
          </TableRow>
        }
      >
        {rows.map((row) => (
          <ClickableTableRow
            key={row.customer_id}
            onClick={() =>
              drill.push({ id: row.customer_id, label: row.customer_name, type: 'customer' })
            }
          >
            <StickyTableCell pinned>{row.customer_name}</StickyTableCell>
            <StickyTableCell align="right">{row.project_count}</StickyTableCell>
            <StickyTableCell align="right">{formatNumber(row.total_quoted_hours)}</StickyTableCell>
            <StickyTableCell align="right">{formatNumber(row.total_actual_hours)}</StickyTableCell>
            <StickyTableCell align="right">{formatNumber(row.hours_variance)}</StickyTableCell>
          </ClickableTableRow>
        ))}
      </OperationalDataTable>
    </ReportAnalyticsShell>
  );
}

export function BillableVsNpReportView({
  data,
  canExport,
}: { data: BillableVsNonBillableReportRow } & ReportExportProps) {
  return (
    <ReportAnalyticsShell
      title="Billable vs Non-Productive"
      subtitle="Portfolio hour distribution"
      canExport={canExport}
      exportFilename="billable-vs-np"
      exportRows={[data as unknown as Record<string, unknown>]}
      exportColumns={[
        { key: 'billable_hours', header: 'Billable Hours' },
        { key: 'np_hours', header: 'NP Hours' },
        { key: 'leave_days', header: 'Leave Days' },
      ]}
      chart={
        <AnalyticsDonutChart
          data={[
            { id: 'billable', label: 'Billable', value: data.billable_hours },
            { id: 'nonbillable', label: 'Non-Billable', value: data.non_billable_hours },
            { id: 'np', label: 'NP', value: data.np_hours },
          ]}
        />
      }
      kpis={
        <KpiStrip columns={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard compact title="Billable %" value={`${formatNumber(data.billable_percent)}%`} icon={PaidRoundedIcon} accent="success" />
          <KpiMetricCard compact title="NP Hours" value={formatNumber(data.np_hours)} icon={ScheduleRoundedIcon} accent="warning" />
          <KpiMetricCard compact title="Leave Days" value={formatNumber(data.leave_days, 0)} icon={GroupsRoundedIcon} />
          <KpiMetricCard compact title="Non-Billable %" value={`${formatNumber(data.non_billable_percent)}%`} icon={FolderRoundedIcon} accent="warning" />
        </KpiStrip>
      }
    >
      <OperationalDataTable
        head={
          <TableRow>
            <StickyHeaderCell>Metric</StickyHeaderCell>
            <StickyHeaderCell align="right">Value</StickyHeaderCell>
          </TableRow>
        }
      >
        <TableRow>
          <StickyTableCell>Billable hours</StickyTableCell>
          <StickyTableCell align="right">{formatNumber(data.billable_hours)}</StickyTableCell>
        </TableRow>
        <TableRow>
          <StickyTableCell>Non-billable hours</StickyTableCell>
          <StickyTableCell align="right">{formatNumber(data.non_billable_hours)}</StickyTableCell>
        </TableRow>
        <TableRow>
          <StickyTableCell>NP hours</StickyTableCell>
          <StickyTableCell align="right">{formatNumber(data.np_hours)}</StickyTableCell>
        </TableRow>
      </OperationalDataTable>
    </ReportAnalyticsShell>
  );
}

export function NpTrendReportView({
  rows,
  canExport,
}: { rows: MonthlyNpTrendReportRow[] } & ReportExportProps) {
  return (
    <ReportAnalyticsShell
      title="NP Hours by Month"
      subtitle="Leave & non-productive monthly trend"
      canExport={canExport}
      exportFilename="np-by-month"
      exportRows={rows as unknown as Record<string, unknown>[]}
      exportColumns={[
        { key: 'month', header: 'Month' },
        { key: 'total_np_hours', header: 'NP Hours', format: (r) => formatNumber(r.total_np_hours as number) },
      ]}
      chart={
        <AnalyticsLineChart
          labels={rows.map((r) => r.month)}
          values={rows.map((r) => r.total_np_hours)}
          label="NP Hours"
        />
      }
    >
      <OperationalDataTable
        head={
          <TableRow>
            <StickyHeaderCell>Month</StickyHeaderCell>
            <StickyHeaderCell align="right">NP Hours</StickyHeaderCell>
          </TableRow>
        }
      >
        {rows.map((row) => (
          <TableRow key={row.month}>
            <StickyTableCell>{row.month}</StickyTableCell>
            <StickyTableCell align="right">{formatNumber(row.total_np_hours)}</StickyTableCell>
          </TableRow>
        ))}
      </OperationalDataTable>
    </ReportAnalyticsShell>
  );
}

export function DesignerUtilizationReportView({
  rows,
  canExport,
}: { rows: DesignerWorkload[] } & ReportExportProps) {
  const chartData = rows.slice(0, 10).map((r) => ({
    id: r.user_id,
    label: r.designer_name,
    value: r.quoted_hours_assigned > 0 ? Math.round((r.actual_hours_logged / r.quoted_hours_assigned) * 100) : 0,
  }));

  return (
    <ReportAnalyticsShell
      title="Designer Utilization"
      subtitle="Assigned vs logged hours"
      canExport={canExport}
      exportFilename="designer-utilization"
      exportRows={rows as unknown as Record<string, unknown>[]}
      exportColumns={[
        { key: 'designer_name', header: 'Designer' },
        { key: 'actual_hours_logged', header: 'Actual', format: (r) => formatNumber(r.actual_hours_logged as number) },
      ]}
      chart={
        <AnalyticsBarChart
          horizontal
          categories={chartData.map((d) => d.label)}
          series={[{ label: 'Utilization %', data: chartData.map((d) => d.value) }]}
        />
      }
    >
      <OperationalDataTable
        maxHeight={480}
        head={
          <TableRow>
            <StickyHeaderCell pinned>Designer</StickyHeaderCell>
            <StickyHeaderCell>Role</StickyHeaderCell>
            <StickyHeaderCell align="right">Active Projects</StickyHeaderCell>
            <StickyHeaderCell align="right">Hours This Week</StickyHeaderCell>
            <StickyHeaderCell align="right">Quoted</StickyHeaderCell>
            <StickyHeaderCell align="right">Actual</StickyHeaderCell>
          </TableRow>
        }
      >
        {rows.map((row) => (
          <TableRow key={row.user_id}>
            <StickyTableCell pinned>{row.designer_name}</StickyTableCell>
            <StickyTableCell>{row.role}</StickyTableCell>
            <StickyTableCell align="right">{row.active_projects}</StickyTableCell>
            <StickyTableCell align="right">{formatNumber(row.hours_this_week)}</StickyTableCell>
            <StickyTableCell align="right">{formatNumber(row.quoted_hours_assigned)}</StickyTableCell>
            <StickyTableCell align="right">{formatNumber(row.actual_hours_logged)}</StickyTableCell>
          </TableRow>
        ))}
      </OperationalDataTable>
    </ReportAnalyticsShell>
  );
}

export function BillableUtilizationReportView({
  rows,
  canExport,
}: { rows: BillableUtilizationReportRow[] } & ReportExportProps) {
  return (
    <ReportAnalyticsShell
      title="Billable Utilization"
      subtitle="Per-designer billable share"
      canExport={canExport}
      exportFilename="billable-utilization"
      exportRows={rows as unknown as Record<string, unknown>[]}
      exportColumns={[
        { key: 'designer_name', header: 'Designer' },
        { key: 'billable_percent', header: 'Billable %' },
      ]}
      chart={
        <AnalyticsBarChart
          horizontal
          categories={rows.slice(0, 10).map((r) => r.designer_name)}
          series={[
            { label: 'Billable %', data: rows.slice(0, 10).map((r) => r.billable_percent) },
          ]}
        />
      }
    >
      <OperationalDataTable
        maxHeight={480}
        head={
          <TableRow>
            <StickyHeaderCell pinned>Designer</StickyHeaderCell>
            <StickyHeaderCell align="right">Billable</StickyHeaderCell>
            <StickyHeaderCell align="right">Non-Billable</StickyHeaderCell>
            <StickyHeaderCell align="right">NP</StickyHeaderCell>
            <StickyHeaderCell align="right">Billable %</StickyHeaderCell>
          </TableRow>
        }
      >
        {rows.map((row) => (
          <TableRow key={row.user_id}>
            <StickyTableCell pinned>{row.designer_name}</StickyTableCell>
            <StickyTableCell align="right">{formatNumber(row.billable_hours)}</StickyTableCell>
            <StickyTableCell align="right">{formatNumber(row.non_billable_hours)}</StickyTableCell>
            <StickyTableCell align="right">{formatNumber(row.np_hours)}</StickyTableCell>
            <StickyTableCell align="right">{formatNumber(row.billable_percent)}%</StickyTableCell>
          </TableRow>
        ))}
      </OperationalDataTable>
    </ReportAnalyticsShell>
  );
}

export function PortfolioReportView({
  rows,
  canExport,
}: { rows: ProjectPortfolioReportRow[] } & ReportExportProps) {
  const navigate = useNavigate();
  return (
    <ReportAnalyticsShell
      title="Project Portfolio"
      subtitle="Health, stage, and delivery status"
      canExport={canExport}
      exportFilename="project-portfolio"
      exportRows={rows as unknown as Record<string, unknown>[]}
      exportColumns={[
        { key: 'tool_number', header: 'Tool' },
        { key: 'customer_name', header: 'Customer' },
        { key: 'due_date', header: 'Due Date' },
      ]}
      chart={
        <AnalyticsDonutChart
          data={[
            { id: 'green', label: 'Green', value: rows.filter((r) => r.health === 'green').length },
            { id: 'yellow', label: 'Yellow', value: rows.filter((r) => r.health === 'yellow').length },
            { id: 'red', label: 'Red', value: rows.filter((r) => r.health === 'red').length },
            { id: 'grey', label: 'Grey', value: rows.filter((r) => !r.health || r.health === 'grey').length },
          ]}
        />
      }
    >
      <OperationalDataTable
        maxHeight={520}
        head={
          <TableRow>
            <StickyHeaderCell pinned>Tool</StickyHeaderCell>
            <StickyHeaderCell>Customer</StickyHeaderCell>
            <StickyHeaderCell>Health</StickyHeaderCell>
            <StickyHeaderCell>Stage</StickyHeaderCell>
            <StickyHeaderCell>Status</StickyHeaderCell>
            <StickyHeaderCell>Due</StickyHeaderCell>
          </TableRow>
        }
      >
        {rows.map((row) => (
          <ClickableTableRow key={row.project_id} onClick={() => navigate(`/projects/${row.project_id}`)}>
            <StickyTableCell pinned>{row.tool_number}</StickyTableCell>
            <StickyTableCell>{row.customer_name}</StickyTableCell>
            <StickyTableCell>
              <HealthIndicator health={(row.health as 'green' | 'yellow' | 'red' | 'grey') ?? 'grey'} />
            </StickyTableCell>
            <StickyTableCell>{PROJECT_STAGE_LABELS[row.project_stage]}</StickyTableCell>
            <StickyTableCell>
              <ExecutionStatusChip status={row.execution_status} />
            </StickyTableCell>
            <StickyTableCell>{row.due_date}</StickyTableCell>
          </ClickableTableRow>
        ))}
      </OperationalDataTable>
    </ReportAnalyticsShell>
  );
}

export function StageSummaryReportView({
  rows,
  canExport,
}: { rows: ProjectStageSummaryRow[] } & ReportExportProps) {
  return (
    <ReportAnalyticsShell
      title="Projects by Stage"
      canExport={canExport}
      exportFilename="projects-by-stage"
      exportRows={rows as unknown as Record<string, unknown>[]}
      exportColumns={[
        { key: 'project_stage', header: 'Stage' },
        { key: 'project_count', header: 'Count' },
      ]}
      chart={
        <AnalyticsBarChart
          categories={rows.map((r) => PROJECT_STAGE_LABELS[r.project_stage])}
          series={[{ label: 'Projects', data: rows.map((r) => r.project_count) }]}
        />
      }
    >
      <OperationalDataTable
        head={
          <TableRow>
            <StickyHeaderCell>Stage</StickyHeaderCell>
            <StickyHeaderCell align="right">Projects</StickyHeaderCell>
          </TableRow>
        }
      >
        {rows.map((row) => (
          <TableRow key={row.project_stage}>
            <StickyTableCell>{PROJECT_STAGE_LABELS[row.project_stage]}</StickyTableCell>
            <StickyTableCell align="right">{row.project_count}</StickyTableCell>
          </TableRow>
        ))}
      </OperationalDataTable>
    </ReportAnalyticsShell>
  );
}

export function ExecutionSummaryReportView({
  rows,
  canExport,
}: { rows: ExecutionStatusSummaryRow[] } & ReportExportProps) {
  return (
    <ReportAnalyticsShell
      title="By Execution Status"
      canExport={canExport}
      exportFilename="execution-status"
      exportRows={rows as unknown as Record<string, unknown>[]}
      exportColumns={[
        { key: 'execution_status', header: 'Status' },
        { key: 'project_count', header: 'Count' },
      ]}
      chart={
        <AnalyticsDonutChart
          data={rows.map((r) => ({
            id: r.execution_status,
            label: EXECUTION_STATUS_LABELS[r.execution_status],
            value: r.project_count,
          }))}
        />
      }
    >
      <OperationalDataTable
        head={
          <TableRow>
            <StickyHeaderCell>Status</StickyHeaderCell>
            <StickyHeaderCell align="right">Projects</StickyHeaderCell>
          </TableRow>
        }
      >
        {rows.map((row) => (
          <TableRow key={row.execution_status}>
            <StickyTableCell>{EXECUTION_STATUS_LABELS[row.execution_status]}</StickyTableCell>
            <StickyTableCell align="right">{row.project_count}</StickyTableCell>
          </TableRow>
        ))}
      </OperationalDataTable>
    </ReportAnalyticsShell>
  );
}

export function SimpleTableReportView({
  title,
  filename,
  rows,
  columns,
  canExport,
}: {
  title: string;
  filename: string;
  rows: Record<string, unknown>[];
  columns: Array<{ key: string; header: string; align?: 'left' | 'right' }>;
  canExport: boolean;
}) {
  return (
    <ReportAnalyticsShell
      title={title}
      canExport={canExport}
      exportFilename={filename}
      exportRows={rows}
      exportColumns={columns.map((c) => ({ key: c.key, header: c.header }))}
    >
      <OperationalDataTable
        maxHeight={480}
        head={
          <TableRow>
            {columns.map((col) => (
              <StickyHeaderCell key={col.key} align={col.align}>
                {col.header}
              </StickyHeaderCell>
            ))}
          </TableRow>
        }
      >
        {rows.map((row, index) => (
          <TableRow key={index}>
            {columns.map((col) => (
              <StickyTableCell key={col.key} align={col.align}>
                {formatCellValue(row[col.key] as string | number | null)}
              </StickyTableCell>
            ))}
          </TableRow>
        ))}
      </OperationalDataTable>
    </ReportAnalyticsShell>
  );
}

export type {
  ProductiveHoursReportRow,
  NonProductiveHoursReportRow,
  NpHoursByDesignerReportRow,
  TopNpActivityReportRow,
};
