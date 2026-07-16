import {
  Chip,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { toFiniteNumber } from '../../utils/format';
import { financeMoney } from './FinanceCockpitPrimitives';

export type RevenueBreakdownRow = {
  key: string;
  label: string;
  monthly_revenue_inr: number | string;
  quarterly_revenue_inr: number | string;
  quote_count?: number;
  project_count?: number;
};

export function FinanceRevenueBreakdownTable({
  rows,
  currency,
}: {
  rows: RevenueBreakdownRow[];
  currency: string;
}) {
  const total = rows.reduce((sum, row) => sum + toFiniteNumber(row.quarterly_revenue_inr), 0);

  if (!rows.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No awarded quotes with a quoted date in this month or FY quarter for this scope.
      </Typography>
    );
  }

  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Segment</TableCell>
            <TableCell align="right">Revenue / mo</TableCell>
            <TableCell align="right">Revenue / quarter</TableCell>
            <TableCell align="right">Quotes</TableCell>
            <TableCell align="right">Projects</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => {
            const quarterly = toFiniteNumber(row.quarterly_revenue_inr);
            const share = total > 0 ? (quarterly / total) * 100 : 0;
            return (
              <TableRow key={row.key} hover>
                <TableCell sx={{ minWidth: 220 }}>
                  <Stack spacing={0.5}>
                    <Typography sx={{ fontWeight: 600 }}>{row.label}</Typography>
                    <LinearProgress
                      variant="determinate"
                      value={Math.max(0, Math.min(100, share))}
                      color="success"
                      sx={{ height: 6, borderRadius: 99 }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      {share.toFixed(1)}% of quarter-to-date quote revenue
                    </Typography>
                  </Stack>
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 600 }}>
                  {financeMoney(row.monthly_revenue_inr, currency)}
                </TableCell>
                <TableCell align="right">
                  {financeMoney(row.quarterly_revenue_inr, currency)}
                </TableCell>
                <TableCell align="right">
                  <Chip size="small" label={String(row.quote_count ?? 0)} variant="outlined" />
                </TableCell>
                <TableCell align="right">
                  <Chip size="small" label={String(row.project_count ?? 0)} variant="outlined" />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
