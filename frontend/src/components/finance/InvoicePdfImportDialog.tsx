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

type StageHour = {
  label: string;
  hours: number;
  source_line?: string;
};

type ExtractResult = {
  text_extractable: boolean;
  ocr_used: boolean;
  warnings: string[];
  content_sha256?: string | null;
  filename?: string | null;
  document_type?: string;
  document_type_confidence?: number;
  fields: Record<string, FieldCandidate>;
  stage_hours?: StageHour[];
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
  const [dueDate, setDueDate] = useState('');
  const [taxAmount, setTaxAmount] = useState('');
  const [subtotalAmount, setSubtotalAmount] = useState('');
  const [balanceDue, setBalanceDue] = useState('');
  const [quantity, setQuantity] = useState('');
  const [notes, setNotes] = useState('');
  const [importAnyway, setImportAnyway] = useState(false);
  const [documentType, setDocumentType] = useState('invoice');
  const [hoursResolved, setHoursResolved] = useState(false);

  const reset = () => {
    setFile(null);
    setExtract(null);
    setQuoteIdEdit(quoteId || '');
    setAmount('');
    setLineDate('');
    setInvoiceNumber('');
    setDueDate('');
    setTaxAmount('');
    setSubtotalAmount('');
    setBalanceDue('');
    setQuantity('');
    setNotes('');
    setImportAnyway(false);
    setDocumentType('invoice');
    setHoursResolved(false);
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
      setDueDate(fieldValue(data.fields, 'due_date'));
      setTaxAmount(fieldValue(data.fields, 'tax_amount'));
      setSubtotalAmount(fieldValue(data.fields, 'subtotal'));
      setBalanceDue(fieldValue(data.fields, 'balance_due'));
      setQuantity(fieldValue(data.fields, 'quantity') || fieldValue(data.fields, 'raw_table_quantity'));
      setNotes(fieldValue(data.fields, 'notes'));
      setQuoteIdEdit(data.suggested_quote_id || quoteId || '');
      setDocumentType(data.document_type || 'invoice');
      setHoursResolved(false);
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
      if (dueDate) form.append('due_date', dueDate);
      if (taxAmount) form.append('tax_amount', String(taxAmount).replace(/,/g, ''));
      if (subtotalAmount) form.append('subtotal_amount', String(subtotalAmount).replace(/,/g, ''));
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

  const hourDiscrepancy = useMemo(() => {
    if (!extract) return false;
    return (extract.warnings ?? []).some((w) => w.includes('DATA REVIEW REQUIRED'));
  }, [extract]);

  const tableQty = fieldValue(extract?.fields ?? {}, 'raw_table_quantity') ||
    fieldValue(extract?.fields ?? {}, 'quantity');
  const stageSum = fieldValue(extract?.fields ?? {}, 'stage_hours_sum');
  const descTotal = fieldValue(extract?.fields ?? {}, 'raw_description_total_hours');

  const canConfirm =
    Boolean(quoteIdEdit) &&
    Boolean(amount) &&
    Boolean(lineDate) &&
    (!hourDiscrepancy || hoursResolved) &&
    !confirmMutation.isPending;

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="md">
      <DialogTitle>Invoice import review</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Review every field before saving. Balance Due never creates a payment — Paid stays $0 until
          an actual payment is recorded. Team is optional for extraction; link to an awarded quote is
          required before confirm.
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
            <Alert severity="info">
              Document detected: <strong>{(documentType || 'unknown').toUpperCase()}</strong>
              {extract.document_type_confidence != null
                ? ` · Confidence: ${Math.round(extract.document_type_confidence)}%`
                : null}
            </Alert>
            <TextField
              select
              label="Document type"
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
              helperText="Change if classification is wrong before confirming."
            >
              <MenuItem value="invoice">INVOICE</MenuItem>
              <MenuItem value="quote">QUOTE</MenuItem>
              <MenuItem value="unknown">UNKNOWN</MenuItem>
            </TextField>

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

            <Box sx={{ p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
              <Typography variant="subtitle2">Match</Typography>
              <Typography variant="body2">
                Customer Project #: {fieldValue(extract.fields, 'customer_project_number') ||
                  fieldValue(extract.fields, 'project_ref') ||
                  '—'}
              </Typography>
              <Typography variant="body2">
                Customer: {fieldValue(extract.fields, 'customer_name') || '—'}
              </Typography>
              <Typography variant="body2">
                P.O. #: {fieldValue(extract.fields, 'po_number') || '—'}
              </Typography>
            </Box>

            {hourDiscrepancy ? (
              <Alert severity="error">
                <Typography variant="subtitle2" gutterBottom>
                  Hour discrepancy — REVIEW REQUIRED
                </Typography>
                <Typography variant="body2">Invoice quantity: {tableQty || '—'}</Typography>
                <Typography variant="body2">Stage breakdown sum: {stageSum || '—'}</Typography>
                <Typography variant="body2">
                  Description total: {descTotal || '—'}
                </Typography>
                <Typography variant="body2" sx={{ mt: 1, mb: 1 }}>
                  Confirm the commercial quantity for the structured record (raw values preserved):
                </Typography>
                <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
                  {tableQty ? (
                    <Button
                      size="small"
                      variant={quantity === tableQty ? 'contained' : 'outlined'}
                      onClick={() => {
                        setQuantity(tableQty);
                        setHoursResolved(true);
                      }}
                    >
                      Use {tableQty}
                    </Button>
                  ) : null}
                  {descTotal && descTotal !== tableQty ? (
                    <Button
                      size="small"
                      variant={quantity === descTotal ? 'contained' : 'outlined'}
                      onClick={() => {
                        setQuantity(descTotal);
                        setHoursResolved(true);
                      }}
                    >
                      Use {descTotal}
                    </Button>
                  ) : null}
                  <Button size="small" variant="outlined" onClick={() => setHoursResolved(true)}>
                    Keep edited value
                  </Button>
                </Stack>
              </Alert>
            ) : null}

            {(extract.stage_hours ?? []).length > 0 ? (
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Work breakdown
                </Typography>
                {(extract.stage_hours ?? []).map((s) => (
                  <Typography key={`${s.label}-${s.hours}`} variant="body2">
                    {s.label}: {s.hours}
                  </Typography>
                ))}
              </Box>
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
              label="Due date"
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              label="Amount (grand total)"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
            />
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
              <TextField
                label="Subtotal"
                value={subtotalAmount}
                onChange={(e) => setSubtotalAmount(e.target.value)}
                fullWidth
              />
              <TextField
                label="Tax / GST"
                value={taxAmount}
                onChange={(e) => setTaxAmount(e.target.value)}
                fullWidth
              />
              <TextField
                label="Balance due (informational)"
                value={balanceDue}
                onChange={(e) => setBalanceDue(e.target.value)}
                fullWidth
                helperText="Does not create a payment"
              />
            </Stack>
            <TextField
              label="Confirmed quantity / hours"
              value={quantity}
              onChange={(e) => {
                setQuantity(e.target.value);
                if (hourDiscrepancy) setHoursResolved(true);
              }}
              helperText={
                hourDiscrepancy
                  ? `Raw qty: ${tableQty || '—'} · Stage sum: ${stageSum || '—'} · Desc TOTAL: ${descTotal || '—'}`
                  : undefined
              }
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
            {hourDiscrepancy && !hoursResolved ? (
              <Typography variant="caption" color="warning.main">
                Resolve the quantity / stage-hour discrepancy before saving.
              </Typography>
            ) : null}
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
                setHoursResolved(false);
              }}
            >
              Back
            </Button>
            <Button
              variant="contained"
              disabled={!canConfirm}
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
