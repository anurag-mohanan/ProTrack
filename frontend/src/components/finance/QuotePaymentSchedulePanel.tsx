import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchQuotePaymentSchedule,
  triggerQuotePaymentMilestone,
  type QuotePaymentScheduleSummary,
} from '../../api/paymentSchedule';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';
import { financeMoney } from './FinanceCockpitPrimitives';

type Props = {
  quoteId: string;
  currency?: string;
  onChanged?: (summary: QuotePaymentScheduleSummary) => void;
};

export function QuotePaymentSchedulePanel({ quoteId, currency = 'INR', onChanged }: Props) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [local, setLocal] = useState<QuotePaymentScheduleSummary | null>(null);

  const query = useQuery({
    queryKey: ['quote-payment-schedule', quoteId],
    queryFn: () => fetchQuotePaymentSchedule(quoteId),
  });

  useEffect(() => {
    if (query.data) setLocal(query.data);
  }, [query.data]);

  const triggerMutation = useMutation({
    mutationFn: (milestoneId: string) => triggerQuotePaymentMilestone(quoteId, milestoneId),
    onSuccess: (data) => {
      setLocal(data);
      showSuccess('Milestone marked ready to invoice');
      void queryClient.invalidateQueries({ queryKey: ['finance-quotes'] });
      onChanged?.(data);
    },
    onError: (error) => showError(apiErrorMessage(error, 'Could not trigger milestone')),
  });

  const summary = local ?? query.data;
  if (query.isLoading && !summary) {
    return <Typography variant="body2">Loading payment schedule…</Typography>;
  }
  if (!summary || !summary.milestones?.length) {
    return (
      <Alert severity="info">
        No payment schedule on this quote. Customer defaults are applied when available, or set a
        quote-specific schedule.
      </Alert>
    );
  }

  return (
    <Stack spacing={1.5}>
      <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
        {summary.payment_model ? (
          <Chip size="small" label={`Model: ${summary.payment_model}`} />
        ) : null}
        {summary.payment_terms ? (
          <Chip size="small" label={`Terms: ${summary.payment_terms}`} />
        ) : null}
        <Chip
          size="small"
          variant="outlined"
          label={`Future ${financeMoney(summary.future_milestone_amount, currency)}`}
        />
        <Chip
          size="small"
          color="info"
          variant="outlined"
          label={`Ready ${financeMoney(summary.ready_to_invoice_amount, currency)}`}
        />
        <Chip
          size="small"
          color="warning"
          variant="outlined"
          label={`Overdue ${financeMoney(summary.overdue_amount, currency)}`}
        />
      </Stack>
      {(summary.warnings ?? []).map((w) => (
        <Alert key={w} severity="warning">
          {w}
        </Alert>
      ))}
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Milestone</TableCell>
            <TableCell align="right">%</TableCell>
            <TableCell align="right">Amount</TableCell>
            <TableCell>Trigger</TableCell>
            <TableCell>Invoice</TableCell>
            <TableCell>Payment</TableCell>
            <TableCell />
          </TableRow>
        </TableHead>
        <TableBody>
          {summary.milestones.map((m) => (
            <TableRow key={m.id}>
              <TableCell>{m.name}</TableCell>
              <TableCell align="right">{m.percentage ?? '—'}</TableCell>
              <TableCell align="right">{financeMoney(m.scheduled_amount, currency)}</TableCell>
              <TableCell>
                <Typography variant="body2">{m.trigger_type}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {m.trigger_status}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography variant="body2">{m.invoice_status}</Typography>
                {m.invoice_number ? (
                  <Typography variant="caption" color="text.secondary">
                    {m.invoice_number}
                    {m.invoice_date ? ` · ${m.invoice_date}` : ''}
                  </Typography>
                ) : null}
              </TableCell>
              <TableCell>
                <Typography variant="body2">{m.payment_status}</Typography>
                {m.due_date ? (
                  <Typography variant="caption" color="text.secondary">
                    Due {m.due_date}
                  </Typography>
                ) : null}
              </TableCell>
              <TableCell>
                {m.trigger_status === 'NOT_YET_TRIGGERED' ? (
                  <Button
                    size="small"
                    onClick={() => triggerMutation.mutate(m.id)}
                    disabled={triggerMutation.isPending}
                  >
                    Mark ready
                  </Button>
                ) : null}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Stack>
  );
}
