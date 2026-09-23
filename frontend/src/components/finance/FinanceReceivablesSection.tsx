import {
  Chip,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { LoadingState } from '../common/LoadingState';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { FinanceSection, financeMoney } from './FinanceCockpitPrimitives';
import { teamQueryParam } from './FinanceTeamFilter';
import EventAvailableOutlinedIcon from '@mui/icons-material/EventAvailableOutlined';
import ScheduleOutlinedIcon from '@mui/icons-material/ScheduleOutlined';
import TodayOutlinedIcon from '@mui/icons-material/TodayOutlined';
import TimelapseOutlinedIcon from '@mui/icons-material/TimelapseOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import { toFiniteNumber } from '../../utils/format';

type ReceivablesAging = {
  as_of?: string;
  total_outstanding?: number | string;
  not_yet_due?: number | string;
  due_soon?: number | string;
  due_today?: number | string;
  overdue?: number | string;
  buckets?: Record<string, number | string>;
  bucket_labels?: Record<string, string>;
  rows?: Array<{
    quote_id: string;
    customer_name?: string | null;
    project_name?: string | null;
    tool_number?: string;
    invoice_number?: string | null;
    invoice_date?: string;
    due_date?: string | null;
    payment_terms?: string | null;
    outstanding?: number | string;
    days_outstanding?: number;
    days_overdue?: number | null;
    days_until_due?: number | null;
    payment_timing_status?: string;
    aging_bucket?: string;
    payment_status?: string;
  }>;
  method_notes?: Record<string, string>;
};

const OVERDUE_BUCKET_KEYS = [
  '1_30_overdue',
  '31_60_overdue',
  '61_90_overdue',
  '90_plus_overdue',
] as const;

const OVERDUE_LABELS: Record<string, string> = {
  '1_30_overdue': '1–30 overdue',
  '31_60_overdue': '31–60 overdue',
  '61_90_overdue': '61–90 overdue',
  '90_plus_overdue': '90+ overdue',
};

export function FinanceReceivablesSection({
  teamId,
  currency = 'INR',
}: {
  teamId: string;
  currency?: string;
}) {
  const q = teamQueryParam(teamId);
  const agingQuery = useQuery({
    queryKey: ['finance-receivables', teamId || 'all'],
    queryFn: async () =>
      (await apiClient.get<ReceivablesAging>(`/finance/receivables${q}`)).data,
  });

  if (agingQuery.isLoading || !agingQuery.data) {
    return <LoadingState message="Loading receivables aging…" />;
  }

  const data = agingQuery.data;
  const buckets = data.buckets || {};
  const rows = (data.rows || []).slice(0, 25);

  return (
    <FinanceSection
      title="Receivables aging"
      subtitle="Outstanding = invoiced − paid (FIFO on invoice lines). Aged by Due Date. Payment terms never create payments."
      action={
        data.as_of ? <Chip size="small" variant="outlined" label={`As of ${data.as_of}`} /> : null
      }
    >
      <Grid container spacing={1.5} sx={{ mb: 2 }}>
        <Grid size={{ xs: 12, sm: 6, md: 2.4 }}>
          <KpiMetricCard
            compact
            accent="warning"
            icon={WarningAmberOutlinedIcon}
            title="Total outstanding"
            value={financeMoney(data.total_outstanding, currency)}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
          <KpiMetricCard
            compact
            icon={EventAvailableOutlinedIcon}
            title="Not yet due"
            value={financeMoney(data.not_yet_due, currency)}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
          <KpiMetricCard
            compact
            icon={ScheduleOutlinedIcon}
            title="Due soon"
            value={financeMoney(data.due_soon, currency)}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
          <KpiMetricCard
            compact
            icon={TodayOutlinedIcon}
            title="Due today"
            value={financeMoney(data.due_today, currency)}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
          <KpiMetricCard
            compact
            accent="warning"
            icon={TimelapseOutlinedIcon}
            title="Overdue"
            value={financeMoney(data.overdue, currency)}
          />
        </Grid>
      </Grid>

      <Grid container spacing={1.5} sx={{ mb: 2 }}>
        {OVERDUE_BUCKET_KEYS.map((key) => (
          <Grid key={key} size={{ xs: 6, sm: 3 }}>
            <KpiMetricCard
              compact
              icon={TimelapseOutlinedIcon}
              title={OVERDUE_LABELS[key]}
              value={financeMoney(buckets[key], currency)}
            />
          </Grid>
        ))}
      </Grid>

      {rows.length > 0 ? (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Customer / Project</TableCell>
              <TableCell>Invoice</TableCell>
              <TableCell>Terms</TableCell>
              <TableCell>Due</TableCell>
              <TableCell align="right">Outstanding</TableCell>
              <TableCell>Timing</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={`${row.quote_id}-${row.invoice_number || row.invoice_date}`}>
                <TableCell>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {row.customer_name || '—'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {row.tool_number}
                    {row.project_name ? ` · ${row.project_name}` : ''}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="body2">{row.invoice_number || '—'}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {row.invoice_date || '—'}
                  </Typography>
                </TableCell>
                <TableCell>{row.payment_terms || '—'}</TableCell>
                <TableCell>{row.due_date || '—'}</TableCell>
                <TableCell align="right">
                  {financeMoney(row.outstanding, currency)}
                </TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    variant="outlined"
                    color={
                      row.payment_timing_status === 'OVERDUE'
                        ? 'warning'
                        : row.payment_timing_status === 'DUE_TODAY'
                          ? 'error'
                          : 'default'
                    }
                    label={
                      row.payment_timing_status === 'OVERDUE'
                        ? `Overdue ${row.days_overdue ?? 0}d`
                        : row.payment_timing_status === 'DUE_SOON'
                          ? `Due in ${row.days_until_due ?? 0}d`
                          : row.payment_timing_status?.replace(/_/g, ' ') ||
                            row.aging_bucket ||
                            '—'
                    }
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <Typography variant="body2" color="text.secondary">
          No outstanding receivables.
        </Typography>
      )}

      {data.method_notes?.aging ? (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1.5, display: 'block' }}>
          {data.method_notes.aging}
          {toFiniteNumber(buckets.aging_unavailable) > 0
            ? ` Aging unavailable: ${financeMoney(buckets.aging_unavailable, currency)}.`
            : ''}
        </Typography>
      ) : null}
    </FinanceSection>
  );
}
