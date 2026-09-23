import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
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
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';
import { ReviewRow, ReviewSection } from './PdfImportReviewBits';

type FieldCandidate = {
  value?: string | null;
  confidence?: number;
  needs_review?: boolean;
};

type StageHour = {
  label?: string;
  stage?: string;
  hours: number;
  source_line?: string;
};

type HoursBalance = {
  quoted_hours?: number;
  previously_invoiced_hours?: number;
  this_invoice_hours?: number | null;
  invoiced_hours?: number;
  remaining_hours?: number;
  remaining_hours_before_closure?: number;
  closed_balance_hours?: number;
  hours_status?: string;
  requires_balance_decision?: boolean;
  decision_required?: boolean;
  is_partial_invoice?: boolean;
  is_over_invoiced_hours?: boolean;
  over_invoiced_hours?: number;
  message?: string;
  default_decision?: string;
  remaining_value?: number | null;
};

type ExtractResult = {
  text_extractable: boolean;
  ocr_used: boolean;
  source_chars?: number;
  warnings: string[];
  content_sha256?: string | null;
  filename?: string | null;
  document_type?: string;
  document_type_confidence?: number;
  text_extraction_method?: string | null;
  raw_text?: string | null;
  extraction_quality?: {
    character_count?: number;
    line_count?: number;
    expected_keywords_found?: boolean;
    text_extraction_method?: string;
  } | null;
  fields: Record<string, FieldCandidate>;
  stage_hours?: StageHour[];
  line_items?: Array<Record<string, unknown>>;
  structured_warnings?: Array<{
    warning_type?: string;
    message?: string;
    values?: Record<string, number | null | undefined>;
  }>;
  page_preview_data_url?: string | null;
  page_count?: number | null;
  extraction_status?: string | null;
  pipeline?: string | null;
  quality_gate?: {
    status?: string;
    missing_fields?: string[];
  } | null;
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
  hours_balance?: HoursBalance | null;
  payment_terms_preview?: {
    payment_terms?: string | null;
    payment_terms_days?: number | null;
    due_date?: string | null;
    payment_terms_source?: string | null;
    warnings?: string[];
    normalized_label?: string | null;
    normalized_days?: number | null;
  } | null;
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

function formatHrs(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return '—';
  const n = Number(value);
  return Number.isInteger(n) ? `${n} hrs` : `${n} hrs`;
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
  const [balanceDecision, setBalanceDecision] = useState<'keep_balance' | 'close_remaining_balance'>(
    'keep_balance',
  );
  const [closeConfirmOpen, setCloseConfirmOpen] = useState(false);
  const [acknowledgeOverHours, setAcknowledgeOverHours] = useState(false);
  const [hoursBalance, setHoursBalance] = useState<HoursBalance | null>(null);
  const [paymentTerms, setPaymentTerms] = useState('');
  const [paymentTermsDays, setPaymentTermsDays] = useState('');
  const [paymentTermsSource, setPaymentTermsSource] = useState('DOCUMENT');
  const [termsOverridden, setTermsOverridden] = useState(false);

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
    setBalanceDecision('keep_balance');
    setCloseConfirmOpen(false);
    setAcknowledgeOverHours(false);
    setHoursBalance(null);
    setPaymentTerms('');
    setPaymentTermsDays('');
    setPaymentTermsSource('DOCUMENT');
    setTermsOverridden(false);
    if (fileRef.current) fileRef.current.value = '';
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const qtyNumber = useMemo(() => {
    const raw = String(quantity || '').replace(/,/g, '').trim();
    if (!raw) return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }, [quantity]);

  const hoursPreviewQuery = useQuery({
    queryKey: ['invoice-hours-balance', quoteIdEdit, qtyNumber],
    enabled: Boolean(extract && quoteIdEdit && qtyNumber != null && qtyNumber > 0),
    queryFn: async () => {
      const { data } = await apiClient.get<HoursBalance>(
        `/finance/quotes/${quoteIdEdit}/hours-balance`,
        { params: { this_invoice_hours: qtyNumber } },
      );
      return data;
    },
  });

  useEffect(() => {
    if (hoursPreviewQuery.data) {
      setHoursBalance(hoursPreviewQuery.data);
      if (hoursPreviewQuery.data.default_decision === 'close_remaining_balance') {
        setBalanceDecision('close_remaining_balance');
      } else {
        setBalanceDecision('keep_balance');
      }
    } else if (extract?.hours_balance && quoteIdEdit === (extract.suggested_quote_id || quoteId || '')) {
      setHoursBalance(extract.hours_balance);
    }
  }, [hoursPreviewQuery.data, extract, quoteIdEdit, quoteId]);

  const extractMutation = useMutation({
    mutationFn: async (pdf: File) => {
      const form = new FormData();
      form.append('file', pdf);
      if (teamId) form.append('team_id', teamId);
      if (quoteId) form.append('quote_id', quoteId);
      return (
        await apiClient.post<ExtractResult>('/finance/invoices/pdf/extract', form, {
          timeout: 120_000,
        })
      ).data;
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
      setQuantity(
        fieldValue(data.fields, 'quantity') || fieldValue(data.fields, 'raw_table_quantity'),
      );
      setNotes(fieldValue(data.fields, 'notes'));
      setQuoteIdEdit(data.suggested_quote_id || quoteId || '');
      setDocumentType(data.document_type || 'invoice');
      setHoursResolved(false);
      setBalanceDecision('keep_balance');
      setAcknowledgeOverHours(false);
      setHoursBalance(data.hours_balance ?? null);
      const preview = data.payment_terms_preview;
      setPaymentTerms(
        preview?.payment_terms ||
          preview?.normalized_label ||
          fieldValue(data.fields, 'payment_terms') ||
          '',
      );
      setPaymentTermsDays(
        preview?.payment_terms_days != null
          ? String(preview.payment_terms_days)
          : preview?.normalized_days != null
            ? String(preview.normalized_days)
            : '',
      );
      setPaymentTermsSource(preview?.payment_terms_source || 'DOCUMENT');
      setTermsOverridden(false);
      if (preview?.due_date && !fieldValue(data.fields, 'due_date')) {
        setDueDate(preview.due_date);
      }
      if (data.pipeline !== 'document_intelligence_v2') {
        showError(
          `Backend returned unexpected pipeline "${data.pipeline || 'none'}". Restart the API server so document_intelligence_v2 is loaded.`,
        );
      }
      if (!data.text_extractable || !(data.source_chars && data.source_chars > 0)) {
        showError(data.warnings?.[0] || 'Unable to extract the document reliably.');
      } else if (!Object.keys(data.fields || {}).length) {
        showError(
          'Text was extracted but structured fields are empty. Check raw text below and enter values manually.',
        );
      } else if (data.extraction_status === 'INCOMPLETE') {
        showError(
          `Extraction incomplete — missing: ${(data.quality_gate?.missing_fields || []).join(', ') || 'required fields'}`,
        );
      }
    },
    onError: (error: unknown) => {
      const msg = apiErrorMessage(error, 'Unable to extract the document reliably.');
      console.error('[Invoice PDF extract failed]', error);
      showError(msg);
    },
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
      if (quantity.trim()) form.append('quantity_hours', String(quantity).replace(/,/g, ''));
      if (paymentTerms.trim()) form.append('payment_terms', paymentTerms.trim());
      if (paymentTermsDays.trim() !== '') {
        form.append('payment_terms_days', String(paymentTermsDays).replace(/,/g, ''));
      }
      form.append(
        'payment_terms_source',
        termsOverridden ? 'USER_OVERRIDE' : paymentTermsSource || 'DOCUMENT',
      );
      if (notes) form.append('notes', notes);
      if (hoursBalance?.decision_required) {
        form.append('remaining_balance_action', balanceDecision);
      }
      if (hoursBalance?.is_over_invoiced_hours) {
        form.append('acknowledge_over_hours', acknowledgeOverHours ? 'true' : 'false');
      }
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

  const hourDiscrepancy = useMemo(() => {
    if (!extract) return false;
    return (
      (extract.structured_warnings ?? []).some((w) => w.warning_type === 'HOURS_MISMATCH') ||
      (extract.warnings ?? []).some((w) => w.includes('DATA REVIEW REQUIRED'))
    );
  }, [extract]);

  const tableQty =
    fieldValue(extract?.fields ?? {}, 'raw_table_quantity') ||
    fieldValue(extract?.fields ?? {}, 'quantity');
  const stageSum = fieldValue(extract?.fields ?? {}, 'stage_hours_sum');
  const descTotal = fieldValue(extract?.fields ?? {}, 'raw_description_total_hours');
  const quality = extract?.extraction_quality;

  const decisionRequired = Boolean(hoursBalance?.decision_required);
  const overHours = Boolean(hoursBalance?.is_over_invoiced_hours);

  const canConfirm =
    Boolean(quoteIdEdit) &&
    Boolean(amount) &&
    Boolean(lineDate) &&
    (!hourDiscrepancy || hoursResolved) &&
    (!overHours || acknowledgeOverHours) &&
    (!decisionRequired || balanceDecision === 'keep_balance' || balanceDecision === 'close_remaining_balance') &&
    !confirmMutation.isPending;

  const handleConfirmClick = () => {
    if (decisionRequired && balanceDecision === 'close_remaining_balance') {
      setCloseConfirmOpen(true);
      return;
    }
    confirmMutation.mutate();
  };

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="md">
      <DialogTitle>Invoice import review</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Review every field ProTrack read from the PDF. Balance Due never creates a payment — Paid
          stays $0 until an actual payment is recorded.
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
            {file ? <Typography variant="body2">Selected: {file.name}</Typography> : null}
            <Button
              variant="contained"
              disabled={!file || extractMutation.isPending}
              onClick={() => file && extractMutation.mutate(file)}
            >
              {extractMutation.isPending ? 'Extracting…' : 'Extract for review'}
            </Button>
          </Stack>
        ) : (
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Alert
              severity={
                extract.extraction_status === 'READY_FOR_REVIEW' ? 'success' : 'warning'
              }
            >
              Extraction Status:{' '}
              <strong>{extract.extraction_status || 'UNKNOWN'}</strong>
              {' · '}
              {(documentType || 'unknown').toUpperCase()} detected (
              {Math.round(extract.document_type_confidence ?? 0)}%)
              {' · '}
              {extract.text_extraction_method || 'visual'}
              {extract.pipeline ? ` · ${extract.pipeline}` : ''}
            </Alert>

            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ alignItems: 'flex-start' }}>
              {extract.page_preview_data_url ? (
                <Box sx={{ flex: '0 0 auto', width: { xs: '100%', md: 280 } }}>
                  <Typography variant="caption" color="text.secondary">
                    Source document (page 1)
                  </Typography>
                  <Box
                    component="img"
                    src={extract.page_preview_data_url}
                    alt="PDF page preview"
                    sx={{
                      mt: 0.5,
                      width: '100%',
                      border: 1,
                      borderColor: 'divider',
                      borderRadius: 1,
                    }}
                  />
                </Box>
              ) : null}
              <Stack spacing={2} sx={{ flex: 1, minWidth: 0 }}>
            <ReviewSection title="DOCUMENT">
              <ReviewRow label="Document" value={extract.filename || file?.name} emphasize />
              <ReviewRow
                label="Document Type"
                value={`${(documentType || 'unknown').toUpperCase()} (${Math.round(extract.document_type_confidence ?? 0)}%)`}
              />
              <ReviewRow
                label="Extraction"
                value={`${extract.text_extraction_method || quality?.text_extraction_method || '—'} · ${extract.source_chars || quality?.character_count || 0} chars`}
              />
              <ReviewRow
                label="Invoice Number"
                value={fieldValue(extract.fields, 'invoice_number')}
                emphasize
              />
              <ReviewRow label="Invoice Date" value={fieldValue(extract.fields, 'invoice_date')} />
              <ReviewRow label="Due Date" value={fieldValue(extract.fields, 'due_date')} />
              <ReviewRow label="Terms" value={fieldValue(extract.fields, 'payment_terms')} />
              <ReviewRow label="Sales Person" value={fieldValue(extract.fields, 'sales_person')} />
              <ReviewRow label="P.O. #" value={fieldValue(extract.fields, 'po_number')} />
            </ReviewSection>

            <TextField
              select
              size="small"
              label="Document type (override)"
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
            >
              <MenuItem value="invoice">INVOICE</MenuItem>
              <MenuItem value="quote">QUOTE</MenuItem>
              <MenuItem value="unknown">UNKNOWN</MenuItem>
            </TextField>
              </Stack>
            </Stack>

            {(extract.warnings ?? []).map((warning) => (
              <Alert key={warning} severity="warning">
                {warning}
              </Alert>
            ))}
            {(extract.duplicates ?? []).length > 0 ? (
              <Alert severity="error">
                Possible duplicate invoice detected. Review existing records or check “Import anyway”.
              </Alert>
            ) : null}

            <ReviewSection title="PROJECT">
              <ReviewRow
                label="Extracted Customer Project #"
                value={
                  fieldValue(extract.fields, 'customer_project_number') ||
                  fieldValue(extract.fields, 'project_ref')
                }
                emphasize
              />
              <ReviewRow
                label="Related Quote candidates"
                value={
                  (extract.quote_matches ?? []).length
                    ? (extract.quote_matches ?? [])
                        .slice(0, 3)
                        .map(
                          (m) =>
                            `${m.tool_number}${m.external_quote_number ? ` · ${m.external_quote_number}` : ''} (${Math.round(m.confidence)}%)`,
                        )
                        .join('; ')
                    : 'None — select quote below'
                }
              />
            </ReviewSection>

            <ReviewSection title="CUSTOMER">
              <ReviewRow
                label="Bill To"
                value={fieldValue(extract.fields, 'customer_name')}
                emphasize
              />
              <ReviewRow
                label="Billing Attention"
                value={fieldValue(extract.fields, 'billing_attention')}
              />
            </ReviewSection>

            <ReviewSection title="COMMERCIAL">
              <ReviewRow label="Currency" value={fieldValue(extract.fields, 'currency_code')} />
              <ReviewRow label="Quantity" value={tableQty} />
              <ReviewRow label="Rate" value={fieldValue(extract.fields, 'rate')} />
              <ReviewRow label="Subtotal" value={fieldValue(extract.fields, 'subtotal')} />
              <ReviewRow label="Tax / IGST" value={fieldValue(extract.fields, 'tax_amount')} />
              <ReviewRow label="Total" value={fieldValue(extract.fields, 'amount')} emphasize />
              <ReviewRow
                label="Balance Due (informational — not a payment)"
                value={fieldValue(extract.fields, 'balance_due')}
              />
              <ReviewRow label="Description" value={fieldValue(extract.fields, 'line_description')} />
            </ReviewSection>

            <ReviewSection title="WORK BREAKDOWN">
              {(extract.stage_hours ?? []).length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No stage lines detected.
                </Typography>
              ) : (
                (extract.stage_hours ?? []).map((s) => (
                  <ReviewRow
                    key={`${s.label || s.stage}-${s.hours}`}
                    label={s.label || s.stage || 'Stage'}
                    value={`${s.hours} Hrs`}
                  />
                ))
              )}
              <ReviewRow label="Stage sum" value={stageSum ? `${stageSum} Hrs` : null} />
              <ReviewRow label="Stated TOTAL in description" value={descTotal ? `${descTotal} Hrs` : null} />
            </ReviewSection>

            {hourDiscrepancy ? (
              <Alert severity="error">
                <Typography variant="subtitle2" gutterBottom>
                  ⚠ Hour discrepancy — REVIEW REQUIRED
                </Typography>
                <Typography variant="body2">Invoice quantity: {tableQty || '—'}</Typography>
                <Typography variant="body2">Stage breakdown: {stageSum || '—'}</Typography>
                <Typography variant="body2">Description total: {descTotal || '—'}</Typography>
                <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1, mt: 1 }}>
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

            <Typography variant="subtitle2">Confirm / edit before save</Typography>
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
            />
            <TextField
              label="Invoice date (turnover month)"
              type="date"
              value={lineDate}
              onChange={(e) => setLineDate(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              required
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
              />
            </Stack>
            <TextField
              label="Confirmed quantity / hours"
              value={quantity}
              onChange={(e) => {
                setQuantity(e.target.value);
                if (hourDiscrepancy) setHoursResolved(true);
              }}
            />

            {hoursBalance && (hoursBalance.quoted_hours ?? 0) > 0 ? (
              <Box
                sx={{
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: 1,
                  p: 1.5,
                  bgcolor: 'action.hover',
                }}
              >
                <Typography variant="subtitle2" sx={{ mb: 1, letterSpacing: '0.04em' }}>
                  AWARDED QUOTE CHECK
                </Typography>
                <ReviewRow label="Quoted" value={formatHrs(hoursBalance.quoted_hours)} emphasize />
                <ReviewRow
                  label="Previously Invoiced"
                  value={formatHrs(hoursBalance.previously_invoiced_hours)}
                />
                <ReviewRow
                  label="This Invoice"
                  value={formatHrs(hoursBalance.this_invoice_hours)}
                />
                <ReviewRow
                  label="Total Invoiced"
                  value={formatHrs(hoursBalance.invoiced_hours)}
                />
                <ReviewRow
                  label="Remaining"
                  value={formatHrs(hoursBalance.remaining_hours_before_closure)}
                  emphasize
                />
                {hoursBalance.hours_status === 'FULLY_INVOICED' ? (
                  <Alert severity="success" sx={{ mt: 1 }}>
                    FULLY INVOICED — commercial hours match the awarded quote.
                  </Alert>
                ) : null}
                {overHours ? (
                  <Alert severity="error" sx={{ mt: 1 }}>
                    <Typography variant="body2" gutterBottom>
                      {hoursBalance.message ||
                        `Invoice quantity exceeds quoted quantity by ${hoursBalance.over_invoiced_hours} hours.`}
                    </Typography>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={acknowledgeOverHours}
                          onChange={(e) => setAcknowledgeOverHours(e.target.checked)}
                        />
                      }
                      label="I have reviewed the over-quantity and want to proceed (quote will not change)"
                    />
                  </Alert>
                ) : null}
                {decisionRequired ? (
                  <Alert severity="warning" sx={{ mt: 1 }}>
                    <Typography variant="subtitle2" gutterBottom>
                      ⚠ Partial invoice detected
                    </Typography>
                    <Typography variant="body2" gutterBottom>
                      {hoursBalance.message ||
                        `${hoursBalance.remaining_hours_before_closure} hours remain to be invoiced. Do you want to keep this balance?`}
                    </Typography>
                    <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: 'wrap', gap: 1 }}>
                      <Button
                        size="small"
                        variant={balanceDecision === 'keep_balance' ? 'contained' : 'outlined'}
                        onClick={() => setBalanceDecision('keep_balance')}
                      >
                        Keep Balance
                      </Button>
                      <Button
                        size="small"
                        color="warning"
                        variant={
                          balanceDecision === 'close_remaining_balance' ? 'contained' : 'outlined'
                        }
                        onClick={() => setBalanceDecision('close_remaining_balance')}
                      >
                        Close Remaining Balance
                      </Button>
                    </Stack>
                  </Alert>
                ) : null}
              </Box>
            ) : null}

            <Box
              sx={{
                border: 1,
                borderColor: 'divider',
                borderRadius: 1,
                p: 1.5,
              }}
            >
              <Typography variant="subtitle2" sx={{ mb: 1, letterSpacing: '0.04em' }}>
                PAYMENT TERMS
              </Typography>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                Terms define expected timing only — they never create a payment. Source:{' '}
                {termsOverridden ? 'USER_OVERRIDE' : paymentTermsSource || '—'}
              </Typography>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                <TextField
                  label="Payment Terms"
                  value={paymentTerms}
                  onChange={(e) => {
                    setPaymentTerms(e.target.value);
                    setTermsOverridden(true);
                  }}
                  fullWidth
                  size="small"
                />
                <TextField
                  label="Lead Time (days)"
                  value={paymentTermsDays}
                  onChange={(e) => {
                    setPaymentTermsDays(e.target.value);
                    setTermsOverridden(true);
                  }}
                  fullWidth
                  size="small"
                />
              </Stack>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mt: 1.5 }}>
                <TextField
                  label="Invoice Date"
                  type="date"
                  value={lineDate}
                  onChange={(e) => setLineDate(e.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                  fullWidth
                  size="small"
                />
                <TextField
                  label="Due Date"
                  type="date"
                  value={dueDate}
                  onChange={(e) => {
                    setDueDate(e.target.value);
                    setTermsOverridden(true);
                  }}
                  slotProps={{ inputLabel: { shrink: true } }}
                  fullWidth
                  size="small"
                />
              </Stack>
              {(extract.payment_terms_preview?.warnings ?? []).map((w) => (
                <Alert key={w} severity="info" sx={{ mt: 1 }}>
                  {w}
                </Alert>
              ))}
            </Box>

            <TextField
              label="Notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              multiline
              minRows={2}
            />

            <FormControlLabel
              control={
                <Checkbox
                  checked={importAnyway}
                  onChange={(e) => setImportAnyway(e.target.checked)}
                />
              }
              label="Import anyway despite duplicate warning"
            />

            <Accordion disableGutters>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="body2">
                  Raw extracted text ({extract.source_chars || 0} chars)
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Box
                  component="pre"
                  sx={{
                    m: 0,
                    p: 1,
                    maxHeight: 240,
                    overflow: 'auto',
                    bgcolor: 'action.hover',
                    fontSize: 12,
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {extract.raw_text || '(empty)'}
                </Box>
              </AccordionDetails>
            </Accordion>

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
                setHoursBalance(null);
                setAcknowledgeOverHours(false);
                setBalanceDecision('keep_balance');
              }}
            >
              Back
            </Button>
            <Button
              variant="contained"
              disabled={!canConfirm}
              onClick={handleConfirmClick}
            >
              Confirm Import
            </Button>
          </>
        ) : null}
      </DialogActions>

      <Dialog open={closeConfirmOpen} onClose={() => setCloseConfirmOpen(false)}>
        <DialogTitle>Close remaining balance?</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            Closing the remaining {hoursBalance?.remaining_hours_before_closure ?? '—'} hours will
            mark the balance as no longer pending invoicing. The original quote will remain
            unchanged.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCloseConfirmOpen(false)}>Cancel</Button>
          <Button
            color="warning"
            variant="contained"
            onClick={() => {
              setCloseConfirmOpen(false);
              confirmMutation.mutate();
            }}
          >
            Confirm Close Balance
          </Button>
        </DialogActions>
      </Dialog>
    </Dialog>
  );
}
