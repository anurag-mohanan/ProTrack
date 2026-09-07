import {
  Chip,
  Grid,
  Stack,
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
import TimelapseOutlinedIcon from '@mui/icons-material/TimelapseOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';

type ReceivablesAging = {
  as_of?: string;
  total_outstanding?: number | string;
  buckets?: Record<string, number | string>;
  bucket_labels?: Record<string, string>;
  rows?: Array<{
    quote_id: string;
    customer_name?: string | null;
    project_name?: string | null;
    tool_number?: string;
    invoice_number?: string | null;
    invoice_date?: string;
    outstanding?: number | string;
    days_outstanding?: number;
    aging_bucket?: string;
    payment_status?: string;
  }>;
  method_notes?: Record<string, string>;
};

const BUCKET_KEYS = ['0_30', '31_60', '61_90', '90_plus'] as const;

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
  const labels = data.bucket_labels || {};
  const rows = (data.rows || []).slice(0, 25);

  return (
    <FinanceSection
      title="Receivables aging"
      subtitle="Outstanding = invoiced − paid. Aging uses invoice date (cash risk), not payment date. Turnover month is unchanged."
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
            subtitle={`${data.rows?.length ?? 0} open balances`}
          />
        </Grid>
        {BUCKET_KEYS.map((key) => (
          <Grid key={key} size={{ xs: 6, sm: 3, md: 2.4 }}>
            <KpiMetricCard
              compact
              accent={key === '90_plus' ? 'error' : key === '61_90' ? 'warning' : 'info'}
              icon={TimelapseOutlinedIcon}
              title={labels[key] || key}
              value={financeMoney(buckets[key], currency)}
              subtitle="Aging bucket"
            />
          </Grid>
        ))}
      </Grid>

      {rows.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No outstanding receivables.
        </Typography>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Customer</TableCell>
              <TableCell>Quote / tool</TableCell>
              <TableCell>Invoice date</TableCell>
              <TableCell align="right">Outstanding</TableCell>
              <TableCell align="right">Days</TableCell>
              <TableCell>Bucket</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.quote_id}>
                <TableCell>{row.customer_name || '—'}</TableCell>
                <TableCell>
                  <Stack spacing={0.25}>
                    <Typography variant="body2">{row.tool_number || row.quote_id.slice(0, 8)}</Typography>
                    {row.project_name ? (
                      <Typography variant="caption" color="text.secondary">
                        {row.project_name}
                      </Typography>
                    ) : null}
                  </Stack>
                </TableCell>
                <TableCell>{row.invoice_date || '—'}</TableCell>
                <TableCell align="right">{financeMoney(row.outstanding, currency)}</TableCell>
                <TableCell align="right">{row.days_outstanding ?? '—'}</TableCell>
                <TableCell>
                  {labels[row.aging_bucket || ''] || row.aging_bucket || '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {data.method_notes?.aging ? (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
          {data.method_notes.aging}
        </Typography>
      ) : null}
    </FinanceSection>
  );
}
