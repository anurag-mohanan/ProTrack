import { useState, type ReactNode } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import FileDownloadRoundedIcon from '@mui/icons-material/FileDownloadRounded';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { downloadManagementReport } from '../../api/management';
import { useToast } from '../../context/ToastContext';
import type {
  CockpitFilterValues,
  FilterOptions,
  KpiDefinition,
  ManagementReport,
  Metric,
  MetricKind,
} from '../../types/Management';
import { statusLabel, valueText, type Column } from './managementFormat';

const KIND_LABEL: Record<MetricKind, string> = {
  actual: 'Actual',
  approved_plan: 'Approved plan',
  forecast: 'Forecast',
  target: 'Target',
  manual: 'Manual entry',
  baseline: 'Baseline',
};

export function KindChip({ kind }: { kind: MetricKind | string }) {
  const label = KIND_LABEL[kind as MetricKind] ?? kind;
  const color = kind === 'forecast' ? 'secondary' : kind === 'target' ? 'primary' : kind === 'approved_plan' ? 'info' : 'default';
  return <Chip size="small" variant="outlined" color={color} label={label} sx={{ height: 20, fontSize: 11 }} />;
}

export function MetricCard({ metric, definition }: { metric: Metric; definition?: KpiDefinition }) {
  const unavailable = metric.status === 'unavailable' || metric.status === 'restricted';
  return (
    <Paper variant="outlined" sx={{ p: 1.75, minWidth: 0, height: '100%' }}>
      <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="caption" color="text.secondary" sx={{ minWidth: 0 }}>
          {metric.label}
          {definition ? (
            <Tooltip title={`${definition.definition} Source: ${definition.source}`}>
              <InfoOutlinedIcon sx={{ fontSize: 14, ml: 0.5, verticalAlign: 'middle', color: 'text.disabled' }} />
            </Tooltip>
          ) : null}
        </Typography>
        <KindChip kind={metric.kind} />
      </Stack>
      <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.3, color: unavailable ? 'text.disabled' : undefined }}>
        {unavailable ? 'Not available' : valueText(metric.value, metric.unit)}
      </Typography>
      <Typography variant="caption" color="text.secondary" component="div">
        {metric.status === 'limited' ? 'Limited data. ' : ''}
        {metric.sample !== null && metric.sample !== undefined ? `Sample: ${metric.sample}. ` : ''}
        {metric.note ?? ''}
      </Typography>
    </Paper>
  );
}

export function MetricGrid({ metrics, definitions = [] }: { metrics: Metric[]; definitions?: KpiDefinition[] }) {
  const byKey = new Map(definitions.map((d) => [d.key, d]));
  return (
    <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', mb: 2 }}>
      {metrics.map((m) => (
        <MetricCard key={m.key + m.label} metric={m} definition={byKey.get(m.key)} />
      ))}
    </Box>
  );
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  empty = 'No rows for these filters.',
  onRowClick,
}: {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T, index: number) => string;
  empty?: string;
  onRowClick?: (row: T) => void;
}) {
  if (!rows.length) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {empty}
      </Typography>
    );
  }
  return (
    <TableContainer component={Paper} variant="outlined" sx={{ mb: 2 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            {columns.map((c) => (
              <TableCell key={c.label} align={c.align} sx={{ fontWeight: 700, whiteSpace: 'nowrap' }}>
                {c.label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row, index) => (
            <TableRow
              key={rowKey(row, index)}
              hover={Boolean(onRowClick)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              sx={{ cursor: onRowClick ? 'pointer' : undefined }}
            >
              {columns.map((c) => (
                <TableCell key={c.label} align={c.align}>
                  {c.render(row)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export function SectionHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ justifyContent: 'space-between', alignItems: { sm: 'center' }, mb: 1.5, mt: 1 }}>
      <Box>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          {title}
        </Typography>
        {subtitle ? (
          <Typography variant="body2" color="text.secondary">
            {subtitle}
          </Typography>
        ) : null}
      </Box>
      {action}
    </Stack>
  );
}

export function NotesList({ notes, title = 'Notes' }: { notes: string[]; title?: string }) {
  if (!notes.length) return null;
  return (
    <Box sx={{ mt: 1, mb: 2 }}>
      <Typography variant="caption" sx={{ fontWeight: 700 }}>
        {title}
      </Typography>
      <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
        {notes.map((n) => (
          <li key={n}>
            <Typography variant="caption" color="text.secondary">
              {n}
            </Typography>
          </li>
        ))}
      </Box>
    </Box>
  );
}

export function HiddenSection({ title, reason }: { title: string; reason: string }) {
  return (
    <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
      <strong>{title}:</strong> {reason}
    </Alert>
  );
}

const STATUS_COLOR: Record<string, 'default' | 'success' | 'warning' | 'error' | 'info'> = {
  on_track: 'success',
  completed: 'success',
  final: 'success',
  at_risk: 'warning',
  blocked: 'warning',
  on_hold: 'warning',
  delayed: 'error',
  overdue: 'error',
  in_progress: 'info',
  draft: 'info',
};

export function StatusChip({ status }: { status: string | null | undefined }) {
  return <Chip size="small" color={STATUS_COLOR[status ?? ''] ?? 'default'} label={statusLabel(status)} />;
}

export function ExportButton({
  report,
  filters,
  extra,
  label = 'Export Excel',
}: {
  report: ManagementReport;
  filters: CockpitFilterValues;
  extra?: { compare_by?: string; review_id?: string };
  label?: string;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      await downloadManagementReport(report, filters, extra);
    } catch (error) {
      toast.showError(error instanceof Error ? error.message : 'Export failed.');
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button size="small" variant="outlined" startIcon={<FileDownloadRoundedIcon />} onClick={() => void run()} disabled={busy}>
      {busy ? 'Exporting…' : label}
    </Button>
  );
}

export function FilterBar({
  options,
  value,
  onChange,
}: {
  options: FilterOptions;
  value: CockpitFilterValues;
  onChange: (next: CockpitFilterValues) => void;
}) {
  const set = (key: keyof CockpitFilterValues, raw: string) =>
    onChange({ ...value, [key]: raw === '' ? undefined : key === 'fy_start_year' ? Number(raw) : raw });
  const select = (key: keyof CockpitFilterValues, label: string, items: { value: string; label: string }[], width = 180) => (
    <TextField
      select
      size="small"
      label={label}
      value={value[key] ?? ''}
      onChange={(e) => set(key, e.target.value)}
      sx={{ minWidth: width }}
    >
      {key !== 'fy_start_year' ? <MenuItem value="">All</MenuItem> : null}
      {items.map((i) => (
        <MenuItem key={i.value} value={i.value}>
          {i.label}
        </MenuItem>
      ))}
    </TextField>
  );
  return (
    <Stack direction="row" spacing={1.5} useFlexGap sx={{ flexWrap: 'wrap', mb: 2 }}>
      {select(
        'fy_start_year',
        'Financial year',
        options.financial_years.map((y) => ({ value: String(y.start_year), label: y.label })),
        150,
      )}
      {select('customer_id', 'Customer', options.customers.map((c) => ({ value: c.id, label: c.name })), 200)}
      {select('classification', 'Classification', options.classifications)}
      <Tooltip title={options.project_manager_basis}>
        <span>{select('manager_id', 'Project manager', options.project_managers.map((m) => ({ value: m.id, label: m.name })))}</span>
      </Tooltip>
      {options.teams.length ? select('team_id', 'Team', options.teams.map((t) => ({ value: t.id, label: t.name }))) : null}
      {options.business_unit_supported
        ? select('business_unit', 'Business unit', options.business_units.map((u) => ({ value: u, label: u })))
        : null}
      {(['start_date', 'end_date'] as const).map((key) => (
        <TextField
          key={key}
          type="date"
          size="small"
          label={key === 'start_date' ? 'From (custom range)' : 'To (custom range)'}
          value={value[key] ?? ''}
          onChange={(e) => set(key, e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          helperText={key === 'start_date' && value.start_date ? 'Overrides the financial year' : undefined}
        />
      ))}
    </Stack>
  );
}
