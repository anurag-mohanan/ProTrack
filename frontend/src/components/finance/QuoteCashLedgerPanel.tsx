import { useState } from 'react';
import {
  Box,
  Button,
  IconButton,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import DeleteOutlinedIcon from '@mui/icons-material/DeleteOutlined';
import { useMutation } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';
import { toFiniteNumber } from '../../utils/format';
import { financeMoney } from './FinanceCockpitPrimitives';
import { designTokens } from '../../theme/designTokens';

export type CashLine = {
  id: string;
  amount: number | string;
  line_date: string;
  notes?: string | null;
  reference?: string | null;
};

export type QuoteCashSummary = {
  id: string;
  currency_code: string;
  quoted_revenue?: number | string | null;
  total_invoiced?: number | string | null;
  total_paid?: number | string | null;
  balance_due?: number | string | null;
  remaining_to_invoice?: number | string | null;
  remaining_contract?: number | string | null;
  invoice_lines?: CashLine[];
  payment_lines?: CashLine[];
};

type QuoteCashLedgerPanelProps = {
  quote: QuoteCashSummary;
  onChanged: (quote: QuoteCashSummary) => void;
};

export function QuoteCashLedgerPanel({ quote, onChanged }: QuoteCashLedgerPanelProps) {
  const { showSuccess, showError } = useToast();
  const currency = (quote.currency_code || 'INR').toUpperCase();
  const today = new Date().toISOString().slice(0, 10);
  const [invAmount, setInvAmount] = useState('');
  const [invDate, setInvDate] = useState(today);
  const [invNotes, setInvNotes] = useState('');
  const [payAmount, setPayAmount] = useState('');
  const [payDate, setPayDate] = useState(today);
  const [payRef, setPayRef] = useState('');

  const balanceDue = toFiniteNumber(quote.balance_due);
  const remainingToInvoice = toFiniteNumber(quote.remaining_to_invoice);

  const invoiceMutation = useMutation({
    mutationFn: async (payload?: { amount?: number }) => {
      const amount =
        payload?.amount ?? Number(String(invAmount).replace(/,/g, ''));
      if (!Number.isFinite(amount) || amount <= 0) {
        throw new Error('Enter a valid invoice amount.');
      }
      return (
        await apiClient.post<QuoteCashSummary>(`/finance/quotes/${quote.id}/invoice-lines`, {
          amount,
          line_date: invDate || today,
          notes: invNotes.trim() || null,
        })
      ).data;
    },
    onSuccess: (data) => {
      showSuccess('Invoice line added');
      setInvAmount('');
      setInvNotes('');
      onChanged(data);
    },
    onError: (error: unknown) => showError(apiErrorMessage(error, 'Could not add invoice')),
  });

  const paymentMutation = useMutation({
    mutationFn: async (payload?: { amount?: number }) => {
      const amount =
        payload?.amount ??
        Number(String(payAmount).replace(/,/g, ''));
      if (!Number.isFinite(amount) || amount <= 0) {
        throw new Error('Enter a valid payment amount.');
      }
      return (
        await apiClient.post<QuoteCashSummary>(`/finance/quotes/${quote.id}/payment-lines`, {
          amount,
          line_date: payDate || today,
          reference: payRef.trim() || null,
        })
      ).data;
    },
    onSuccess: (data) => {
      showSuccess('Payment recorded — balance updated');
      setPayAmount('');
      setPayRef('');
      onChanged(data);
    },
    onError: (error: unknown) => showError(apiErrorMessage(error, 'Could not add payment')),
  });

  const deleteInvoiceMutation = useMutation({
    mutationFn: async (lineId: string) =>
      (
        await apiClient.delete<QuoteCashSummary>(
          `/finance/quotes/${quote.id}/invoice-lines/${lineId}`,
        )
      ).data,
    onSuccess: (data) => {
      showSuccess('Invoice line removed');
      onChanged(data);
    },
    onError: (error: unknown) => showError(apiErrorMessage(error, 'Could not delete invoice')),
  });

  const deletePaymentMutation = useMutation({
    mutationFn: async (lineId: string) =>
      (
        await apiClient.delete<QuoteCashSummary>(
          `/finance/quotes/${quote.id}/payment-lines/${lineId}`,
        )
      ).data,
    onSuccess: (data) => {
      showSuccess('Payment removed');
      onChanged(data);
    },
    onError: (error: unknown) => showError(apiErrorMessage(error, 'Could not delete payment')),
  });

  const busy =
    invoiceMutation.isPending ||
    paymentMutation.isPending ||
    deleteInvoiceMutation.isPending ||
    deletePaymentMutation.isPending;

  return (
    <Box
      sx={{
        mt: 1.5,
        p: 1.5,
        borderRadius: `${designTokens.radius.md}px`,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.default',
      }}
    >
      <Typography variant="subtitle2" sx={{ fontWeight: 800, mb: 1 }}>
        Invoices & payments (running balance)
      </Typography>
      <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: 'wrap', mb: 1.5 }}>
        <Typography variant="caption">
          Quoted <strong>{financeMoney(quote.quoted_revenue, currency)}</strong>
        </Typography>
        <Typography variant="caption">
          Invoiced <strong>{financeMoney(quote.total_invoiced, currency)}</strong>
        </Typography>
        <Typography variant="caption">
          Paid <strong>{financeMoney(quote.total_paid, currency)}</strong>
        </Typography>
        <Typography variant="caption" color={balanceDue > 0 ? 'warning.main' : 'success.main'}>
          Balance due <strong>{financeMoney(quote.balance_due, currency)}</strong>
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Left to invoice {financeMoney(quote.remaining_to_invoice, currency)}
        </Typography>
      </Stack>

      <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.75 }}>
        Invoice lines
      </Typography>
      <Stack spacing={0.5} sx={{ mb: 1.5 }}>
        {(quote.invoice_lines ?? []).length === 0 ? (
          <Typography variant="caption" color="text.secondary">
            No invoices yet — add a partial or full invoice (e.g. 50% of quoted).
          </Typography>
        ) : (
          (quote.invoice_lines ?? []).map((line) => (
            <Stack
              key={line.id}
              direction="row"
              spacing={1}
              sx={{ alignItems: 'center', justifyContent: 'space-between' }}
            >
              <Typography variant="body2">
                {line.line_date} · {financeMoney(line.amount, currency)}
                {line.notes ? ` · ${line.notes}` : ''}
              </Typography>
              <IconButton
                size="small"
                aria-label="Delete invoice line"
                disabled={busy}
                onClick={() => deleteInvoiceMutation.mutate(line.id)}
              >
                <DeleteOutlinedIcon fontSize="small" />
              </IconButton>
            </Stack>
          ))
        )}
      </Stack>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mb: 2, flexWrap: 'wrap' }}>
        <TextField
          size="small"
          label="Invoice amount"
          value={invAmount}
          onChange={(e) => setInvAmount(e.target.value)}
          sx={{ minWidth: 130 }}
          helperText={
            remainingToInvoice > 0
              ? `Remaining to invoice ≈ ${financeMoney(remainingToInvoice, currency)}`
              : undefined
          }
        />
        <TextField
          size="small"
          type="date"
          label="Invoice date"
          value={invDate}
          onChange={(e) => setInvDate(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ minWidth: 150 }}
        />
        <TextField
          size="small"
          label="Note"
          value={invNotes}
          onChange={(e) => setInvNotes(e.target.value)}
          placeholder="e.g. 50% advance"
          sx={{ minWidth: 160, flex: 1 }}
        />
        <Button
          size="small"
          variant="outlined"
          disabled={busy}
          onClick={() => invoiceMutation.mutate(undefined)}
        >
          Add invoice
        </Button>
        {remainingToInvoice > 0 ? (
          <Button
            size="small"
            disabled={busy}
            onClick={() => invoiceMutation.mutate({ amount: remainingToInvoice })}
          >
            Invoice remaining
          </Button>
        ) : null}
      </Stack>

      <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.75 }}>
        Payment lines
      </Typography>
      <Stack spacing={0.5} sx={{ mb: 1.5 }}>
        {(quote.payment_lines ?? []).length === 0 ? (
          <Typography variant="caption" color="text.secondary">
            No payments yet — each payment reduces balance due.
          </Typography>
        ) : (
          (quote.payment_lines ?? []).map((line) => (
            <Stack
              key={line.id}
              direction="row"
              spacing={1}
              sx={{ alignItems: 'center', justifyContent: 'space-between' }}
            >
              <Typography variant="body2">
                {line.line_date} · {financeMoney(line.amount, currency)}
                {line.reference ? ` · ${line.reference}` : ''}
              </Typography>
              <IconButton
                size="small"
                aria-label="Delete payment line"
                disabled={busy}
                onClick={() => deletePaymentMutation.mutate(line.id)}
              >
                <DeleteOutlinedIcon fontSize="small" />
              </IconButton>
            </Stack>
          ))
        )}
      </Stack>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ flexWrap: 'wrap' }}>
        <TextField
          size="small"
          label="Payment amount"
          value={payAmount}
          onChange={(e) => setPayAmount(e.target.value)}
          sx={{ minWidth: 130 }}
          disabled={balanceDue <= 0}
        />
        <TextField
          size="small"
          type="date"
          label="Payment date"
          value={payDate}
          onChange={(e) => setPayDate(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ minWidth: 150 }}
          disabled={balanceDue <= 0}
        />
        <TextField
          size="small"
          label="Reference"
          value={payRef}
          onChange={(e) => setPayRef(e.target.value)}
          placeholder="UTR / remittance"
          sx={{ minWidth: 160, flex: 1 }}
          disabled={balanceDue <= 0}
        />
        <Button
          size="small"
          variant="outlined"
          disabled={busy || balanceDue <= 0}
          onClick={() => paymentMutation.mutate(undefined)}
        >
          Add payment
        </Button>
        {balanceDue > 0 ? (
          <Button
            size="small"
            color="success"
            variant="contained"
            disabled={busy}
            onClick={() => paymentMutation.mutate({ amount: balanceDue })}
          >
            Mark remaining paid
          </Button>
        ) : null}
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
        Follow-up reminders start 30 days after the first invoice while balance due &gt; 0, then
        weekly.
      </Typography>
    </Box>
  );
}
