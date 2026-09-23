import { useMemo, useRef, useState } from 'react';
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
import { useMutation } from '@tanstack/react-query';
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
      // Document analysis can include layout render + optional vision; allow IIS/ARR headroom.
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
              }}
            >
              Back
            </Button>
            <Button
              variant="contained"
              disabled={!canConfirm}
              onClick={() => confirmMutation.mutate()}
            >
              Confirm Import
            </Button>
          </>
        ) : null}
      </DialogActions>
    </Dialog>
  );
}
