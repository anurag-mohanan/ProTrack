import { useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';

type FieldCandidate = {
  value?: string | null;
  confidence?: number;
  needs_review?: boolean;
};

type ExtractResult = {
  text_extractable: boolean;
  ocr_used: boolean;
  warnings: string[];
  content_sha256?: string | null;
  filename?: string | null;
  fields: Record<string, FieldCandidate>;
  customer_matches: Array<{ customer_id: string; name: string; code?: string; confidence: number }>;
  quote_matches: Array<{
    quote_id: string;
    tool_number: string;
    external_quote_number?: string | null;
    confidence: number;
    match_reason?: string;
  }>;
  duplicates: Array<{ invoice_line_id: string; quote_id: string; reason: string; notes?: string }>;
  suggested_quote_id?: string | null;
};

type Props = {
  open: boolean;
  onClose: () => void;
  teamId?: string;
  quoteId?: string;
  onImported: (quote?: unknown) => void;
};

function fieldValue(fields: Record<string, FieldCandidate>, key: string): string {
  return fields[key]?.value ?? '';
}

export function InvoicePdfImportDialog({ open, onClose, teamId, quoteId, onImported }: Props) {
  const { showSuccess, showError } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [extract, setExtract] = useState<ExtractResult | null>(null);
  const [quoteIdEdit, setQuoteIdEdit] = useState(quoteId || '');
  const [amount, setAmount] = useState('');
  const [lineDate, setLineDate] = useState('');
  const [invoiceNumber, setInvoiceNumber] = useState('');
  const [notes, setNotes] = useState('');
  const [importAnyway, setImportAnyway] = useState(false);

  const reset = () => {
    setFile(null);
    setExtract(null);
    setQuoteIdEdit(quoteId || '');
    setAmount('');
    setLineDate('');
    setInvoiceNumber('');
    setNotes('');
    setImportAnyway(false);
    if (fileRef.current) fileRef.current.value = '';
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const extractMutation = useMutation({
    mutationFn: async (pdf: File) => {
      const form = new FormData();
      form.append('file', pdf);
      if (teamId) form.append('team_id', teamId);
      if (quoteId) form.append('quote_id', quoteId);
      return (await apiClient.post<ExtractResult>('/finance/invoices/pdf/extract', form)).data;
    },
    onSuccess: (data) => {
      setExtract(data);
      setAmount(fieldValue(data.fields, 'amount'));
      setLineDate(fieldValue(data.fields, 'invoice_date'));
      setInvoiceNumber(fieldValue(data.fields, 'invoice_number'));
      setNotes(fieldValue(data.fields, 'notes'));
      setQuoteIdEdit(data.suggested_quote_id || quoteId || '');
      if (!data.text_extractable) {
        showError(data.warnings[0] || 'Unable to extract the document reliably.');
      }
    },
    onError: (error: unknown) =>
      showError(apiErrorMessage(error, 'Unable to extract the document reliably.')),
  });

  const confirmMutation = useMutation({
    mutationFn: async () => {
      if (!quoteIdEdit) throw new Error('Select a quote / project to link this invoice.');
      if (!amount || !lineDate) throw new Error('Amount and invoice date are required.');
      const form = new FormData();
      form.append('quote_id', quoteIdEdit);
      form.append('amount', String(amount).replace(/,/g, ''));
      form.append('line_date', lineDate);
      if (invoiceNumber) form.append('invoice_number', invoiceNumber);
      if (notes) form.append('notes', notes);
      form.append('import_anyway', importAnyway ? 'true' : 'false');
      if (extract?.content_sha256) form.append('content_sha256', extract.content_sha256);
      if (file) form.append('file', file);
      return (await apiClient.post('/finance/invoices/pdf/confirm', form)).data;
    },
    onSuccess: (data) => {
      showSuccess('Invoice imported from PDF');
      handleClose();
      onImported(data);
    },
    onError: (error: unknown) =>
      showError(apiErrorMessage(error, 'Could not confirm invoice import')),
  });

  const needsReview = useMemo(() => {
    if (!extract) return [];
    return Object.entries(extract.fields)
      .filter(([, field]) => field.needs_review)
      .map(([key]) => key);
  }, [extract]);

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="md">
      <DialogTitle>Import invoice from PDF</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Optional convenience — review every field before saving. Manual invoice entry remains available
          on the quote cash ledger. Scanned image PDFs need OCR (not enabled yet); use a text PDF or enter
          manually.
        </Typography>

        {!extract ? (
          <Stack spacing={2}>
            <Button variant="outlined" component="label">
              Choose PDF
              <input
                ref={fileRef}
                hidden
                type="file"
                accept="application/pdf,.pdf"
                onChange={(e) => {
                  const next = e.target.files?.[0] ?? null;
                  setFile(next);
                }}
              />
            </Button>
            {file ? (
              <Typography variant="body2">Selected: {file.name}</Typography>
            ) : null}
            <Button
              variant="contained"
              disabled={!file || extractMutation.isPending}
              onClick={() => file && extractMutation.mutate(file)}
            >
              Extract for review
            </Button>
          </Stack>
        ) : (
          <Stack spacing={2} sx={{ mt: 1 }}>
            {(extract.warnings ?? []).map((warning) => (
              <Alert key={warning} severity="warning">
                {warning}
              </Alert>
            ))}
            {needsReview.length > 0 ? (
              <Alert severity="info">
                Needs review: {needsReview.join(', ')}. Confirm or correct before import.
              </Alert>
            ) : null}
            {(extract.duplicates ?? []).length > 0 ? (
              <Alert severity="error">
                Possible duplicate invoice detected. Review existing records or check “Import anyway”.
              </Alert>
            ) : null}

            <TextField
              select
              label="Link to quote / project"
              value={quoteIdEdit}
              onChange={(e) => setQuoteIdEdit(e.target.value)}
              required
              helperText="Required — invoices must attach to an awarded quote"
            >
              <MenuItem value="">Select quote</MenuItem>
              {(extract.quote_matches ?? []).map((match) => (
                <MenuItem key={match.quote_id} value={match.quote_id}>
                  {match.tool_number}
                  {match.external_quote_number ? ` · ${match.external_quote_number}` : ''} ·{' '}
                  {Math.round(match.confidence)}%
                </MenuItem>
              ))}
            </TextField>

            <TextField
              label="Invoice number"
              value={invoiceNumber}
              onChange={(e) => setInvoiceNumber(e.target.value)}
              helperText={
                extract.fields.invoice_number?.needs_review
                  ? `Low confidence (${extract.fields.invoice_number.confidence ?? 0}%)`
                  : undefined
              }
            />
            <TextField
              label="Invoice date (turnover month)"
              type="date"
              value={lineDate}
              onChange={(e) => setLineDate(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              required
              helperText="Invoice date drives P&L turnover — not the payment date."
            />
            <TextField
              label="Amount"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
            />
            <TextField
              label="Notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              multiline
              minRows={2}
            />

            {(extract.customer_matches ?? []).length > 0 ? (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Suggested customers (confirm via quote selection)
                </Typography>
                {(extract.customer_matches ?? []).map((c) => (
                  <Typography key={c.customer_id} variant="body2">
                    {c.name} ({Math.round(c.confidence)}%)
                  </Typography>
                ))}
              </Box>
            ) : null}

            <FormControlLabel
              control={
                <Checkbox
                  checked={importAnyway}
                  onChange={(e) => setImportAnyway(e.target.checked)}
                />
              }
              label="Import anyway despite duplicate warning"
            />
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        {extract ? (
          <>
            <Button
              onClick={() => {
                setExtract(null);
                setImportAnyway(false);
              }}
            >
              Back
            </Button>
            <Button
              variant="contained"
              disabled={
                confirmMutation.isPending || !quoteIdEdit || !amount || !lineDate
              }
              onClick={() => confirmMutation.mutate()}
            >
              Confirm & import
            </Button>
          </>
        ) : null}
      </DialogActions>
    </Dialog>
  );
}
