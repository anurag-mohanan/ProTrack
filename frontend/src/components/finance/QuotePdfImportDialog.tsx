import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Accordion,
  AccordionDetails,
  AccordionSummary,
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
import { fetchCustomers, fetchTeams } from '../../api/lookups';
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
    keywords_hit?: string[];
  } | null;
  fields: Record<string, FieldCandidate>;
  stage_hours?: StageHour[];
  line_items?: Array<Record<string, unknown>>;
  structured_warnings?: Array<{
    warning_type?: string;
    message?: string;
    values?: Record<string, number | null | undefined>;
  }>;
  customer_matches: Array<{ customer_id: string; name: string; code?: string; confidence: number }>;
  project_matches: Array<{
    project_id: string;
    tool_number: string;
    name?: string | null;
    confidence: number;
  }>;
  duplicates: Array<{
    quote_id: string;
    tool_number?: string;
    external_quote_number?: string | null;
    reason: string;
  }>;
  suggested_customer_id?: string | null;
  suggested_project_id?: string | null;
};

type QuoteImportResult = {
  imported_count: number;
  items?: Array<Record<string, unknown>>;
};

type TeamOption = { id: string; name: string };

type Props = {
  open: boolean;
  onClose: () => void;
  teamId?: string;
  teams?: TeamOption[];
  createProject?: boolean;
  onImported: (result: { imported_count: number; items?: Array<Record<string, unknown>> }) => void;
  onTeamSelected?: (teamId: string) => void;
};

function fieldValue(fields: Record<string, FieldCandidate>, key: string): string {
  return fields[key]?.value ?? '';
}

export function QuotePdfImportDialog({
  open,
  onClose,
  teamId,
  teams: teamsProp,
  createProject = true,
  onImported,
  onTeamSelected,
}: Props) {
  const { showSuccess, showError } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [extract, setExtract] = useState<ExtractResult | null>(null);
  const [selectedTeamId, setSelectedTeamId] = useState(teamId || '');
  const [customerId, setCustomerId] = useState('');
  const [quoteNumber, setQuoteNumber] = useState('');
  const [projectNumber, setProjectNumber] = useState('');
  const [cost, setCost] = useState('');
  const [quotedHours, setQuotedHours] = useState('');
  const [currencyCode, setCurrencyCode] = useState('USD');
  const [quotedDate, setQuotedDate] = useState('');
  const [notes, setNotes] = useState('');
  const [importAnyway, setImportAnyway] = useState(false);
  const [createProjectLocal, setCreateProjectLocal] = useState(createProject);
  const [documentType, setDocumentType] = useState('quote');
  const [hoursResolved, setHoursResolved] = useState(false);

  const customersQuery = useQuery({
    queryKey: ['lookup-customers'],
    queryFn: fetchCustomers,
    enabled: open,
  });
  const teamsQuery = useQuery({
    queryKey: ['lookup-teams'],
    queryFn: fetchTeams,
    enabled: open && !(teamsProp && teamsProp.length > 0),
  });

  const teams = useMemo(() => {
    if (teamsProp && teamsProp.length > 0) return teamsProp;
    return (teamsQuery.data ?? []).map((t) => ({ id: t.id, name: t.name }));
  }, [teamsProp, teamsQuery.data]);

  useEffect(() => {
    if (open) setSelectedTeamId(teamId || '');
  }, [open, teamId]);

  const reset = () => {
    setFile(null);
    setExtract(null);
    setSelectedTeamId(teamId || '');
    setCustomerId('');
    setQuoteNumber('');
    setProjectNumber('');
    setCost('');
    setQuotedHours('');
    setCurrencyCode('USD');
    setQuotedDate('');
    setNotes('');
    setImportAnyway(false);
    setCreateProjectLocal(createProject);
    setDocumentType('quote');
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
      if (selectedTeamId) form.append('team_id', selectedTeamId);
      return (await apiClient.post<ExtractResult>('/finance/quotes/pdf/extract', form)).data;
    },
    onSuccess: (data) => {
      setExtract(data);
      setQuoteNumber(
        fieldValue(data.fields, 'external_quote_number') ||
          fieldValue(data.fields, 'quote_number'),
      );
      setProjectNumber(
        fieldValue(data.fields, 'tool_number') ||
          fieldValue(data.fields, 'customer_project_number'),
      );
      setCost(fieldValue(data.fields, 'quoted_revenue'));
      setQuotedHours(fieldValue(data.fields, 'quoted_hours'));
      setCurrencyCode(fieldValue(data.fields, 'currency_code') || 'USD');
      setQuotedDate(fieldValue(data.fields, 'quoted_date'));
      setNotes(fieldValue(data.fields, 'notes'));
      setCustomerId(data.suggested_customer_id || '');
      setDocumentType(data.document_type || 'quote');
      setHoursResolved(false);
      if (!data.text_extractable || !(data.source_chars && data.source_chars > 0)) {
        showError(data.warnings?.[0] || 'Unable to extract the document reliably.');
      } else if (!Object.keys(data.fields || {}).length) {
        showError(
          'Text was extracted but structured fields are empty. Check raw text below and enter values manually.',
        );
      }
    },
    onError: (error: unknown) =>
      showError(apiErrorMessage(error, 'Unable to extract the document reliably.')),
  });

  const confirmMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTeamId) throw new Error('Select a specific team before saving this quote.');
      if (!customerId) throw new Error('Select a customer.');
      if (!projectNumber.trim()) throw new Error('Project # is required.');
      if (!cost.trim()) throw new Error('Cost (quoted amount) is required.');
      const form = new FormData();
      form.append('team_id', selectedTeamId);
      form.append('customer_id', customerId);
      form.append('tool_number', projectNumber.trim());
      form.append('quoted_revenue', String(cost).replace(/,/g, ''));
      if (quoteNumber.trim()) form.append('external_quote_number', quoteNumber.trim());
      if (currencyCode.trim()) form.append('currency_code', currencyCode.trim().toUpperCase());
      if (quotedHours.trim()) form.append('quoted_hours', String(quotedHours).replace(/,/g, ''));
      if (quotedDate.trim()) form.append('quoted_date', quotedDate.trim());
      if (notes.trim()) form.append('notes', notes.trim());
      form.append('create_project', createProjectLocal ? 'true' : 'false');
      form.append('import_anyway', importAnyway ? 'true' : 'false');
      if (extract?.content_sha256) form.append('content_sha256', extract.content_sha256);
      if (file) form.append('file', file);
      return (await apiClient.post<QuoteImportResult>('/finance/quotes/pdf/confirm', form)).data;
    },
    onSuccess: (data) => {
      if (selectedTeamId) onTeamSelected?.(selectedTeamId);
      showSuccess('Quote imported from PDF');
      handleClose();
      onImported(data);
    },
    onError: (error: unknown) =>
      showError(apiErrorMessage(error, 'Could not confirm quote import')),
  });

  const hourDiscrepancy = useMemo(() => {
    if (!extract) return false;
    return (
      (extract.structured_warnings ?? []).some((w) => w.warning_type === 'HOURS_MISMATCH') ||
      (extract.warnings ?? []).some((w) => w.includes('DATA REVIEW REQUIRED'))
    );
  }, [extract]);

  const tableQty = fieldValue(extract?.fields ?? {}, 'raw_table_quantity');
  const stageSum = fieldValue(extract?.fields ?? {}, 'stage_hours_sum');
  const descTotal = fieldValue(extract?.fields ?? {}, 'raw_description_total_hours');
  const topProject = extract?.project_matches?.[0];

  const customers = useMemo(() => {
    const active = (customersQuery.data ?? []).filter((c) => c.is_active);
    const matchIds = new Set((extract?.customer_matches ?? []).map((m) => m.customer_id));
    if (matchIds.size === 0) return active;
    return [
      ...active.filter((c) => matchIds.has(c.id)),
      ...active.filter((c) => !matchIds.has(c.id)),
    ];
  }, [customersQuery.data, extract?.customer_matches]);

  const canConfirm =
    Boolean(selectedTeamId) &&
    Boolean(customerId) &&
    Boolean(projectNumber.trim()) &&
    Boolean(cost.trim()) &&
    (!hourDiscrepancy || hoursResolved) &&
    !confirmMutation.isPending;

  const confirmBlockReason = !selectedTeamId
    ? 'Select a specific team before this quote can be saved.'
    : !customerId
      ? 'Select a customer before saving.'
      : !projectNumber.trim()
        ? 'Project # is required before saving.'
        : !cost.trim()
          ? 'Quoted amount is required before saving.'
          : hourDiscrepancy && !hoursResolved
            ? 'Resolve the hour discrepancy before saving.'
            : null;

  const quality = extract?.extraction_quality;

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="md">
      <DialogTitle>Quote import review</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Extract first, then review the values ProTrack read from the PDF. Nothing is saved until you
          confirm.
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
            <ReviewSection title="DOCUMENT">
              <ReviewRow label="Document" value={extract.filename || file?.name} emphasize />
              <ReviewRow
                label="Document Type"
                value={`${(documentType || 'unknown').toUpperCase()} (${Math.round(extract.document_type_confidence ?? 0)}%)`}
              />
              <ReviewRow
                label="Extraction"
                value={`${extract.text_extraction_method || quality?.text_extraction_method || '—'} · ${extract.source_chars || quality?.character_count || 0} chars · ${quality?.line_count ?? '—'} lines`}
              />
              <ReviewRow
                label="Quote Number"
                value={fieldValue(extract.fields, 'external_quote_number') || quoteNumber}
                emphasize
              />
              <ReviewRow label="Quote Date" value={fieldValue(extract.fields, 'quoted_date')} />
              <ReviewRow label="Sales Person" value={fieldValue(extract.fields, 'sales_person')} />
            </ReviewSection>

            <TextField
              select
              size="small"
              label="Document type (override)"
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
            >
              <MenuItem value="quote">QUOTE</MenuItem>
              <MenuItem value="invoice">INVOICE</MenuItem>
              <MenuItem value="unknown">UNKNOWN</MenuItem>
            </TextField>

            {(extract.warnings ?? []).map((warning) => (
              <Alert key={warning} severity="warning">
                {warning}
              </Alert>
            ))}
            {(extract.duplicates ?? []).length > 0 ? (
              <Alert severity="error">
                Possible duplicate quote detected. Review existing records or check “Import anyway”.
              </Alert>
            ) : null}

            <ReviewSection title="PROJECT">
              <ReviewRow
                label="Extracted Customer Project #"
                value={
                  fieldValue(extract.fields, 'customer_project_number') ||
                  fieldValue(extract.fields, 'tool_number') ||
                  projectNumber
                }
                emphasize
              />
              <ReviewRow
                label="Matched ProTrack Project"
                value={
                  topProject
                    ? `${topProject.tool_number}${topProject.name ? ` — ${topProject.name}` : ''} (${Math.round(topProject.confidence)}%)`
                    : 'Not found'
                }
              />
              <ReviewRow
                label="Project Match"
                value={topProject && topProject.confidence >= 95 ? 'EXACT PROJECT NUMBER' : topProject ? 'Possible' : 'None'}
              />
            </ReviewSection>

            <ReviewSection title="CUSTOMER">
              <ReviewRow
                label="Extracted Customer"
                value={fieldValue(extract.fields, 'customer_name')}
                emphasize
              />
              <ReviewRow
                label="Attention"
                value={fieldValue(extract.fields, 'customer_contact')}
              />
              <ReviewRow
                label="ProTrack Customer"
                value={customers.find((c) => c.id === customerId)?.name || 'Select below'}
              />
            </ReviewSection>

            <ReviewSection title="COMMERCIAL">
              <ReviewRow label="Currency" value={fieldValue(extract.fields, 'currency_code') || currencyCode} />
              <ReviewRow label="Quoted Hours (table)" value={tableQty || fieldValue(extract.fields, 'quoted_hours')} />
              <ReviewRow label="Rate" value={fieldValue(extract.fields, 'rate')} />
              <ReviewRow label="Subtotal" value={fieldValue(extract.fields, 'subtotal')} />
              <ReviewRow label="Total" value={fieldValue(extract.fields, 'quoted_revenue')} emphasize />
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

            <ReviewSection title="TERMS">
              <ReviewRow label="Payment terms" value={fieldValue(extract.fields, 'payment_terms')} />
            </ReviewSection>

            {hourDiscrepancy ? (
              <Alert severity="error">
                <Typography variant="subtitle2" gutterBottom>
                  ⚠ Hour discrepancy — DATA REVIEW REQUIRED
                </Typography>
                <Typography variant="body2">Table quantity: {tableQty || '—'} Hrs</Typography>
                <Typography variant="body2">Stage breakdown: {stageSum || '—'} Hrs</Typography>
                <Typography variant="body2">Description stated total: {descTotal || '—'} Hrs</Typography>
                <Typography variant="body2" sx={{ mt: 1, mb: 1 }}>
                  Confirm commercial quoted hours (raw values stay preserved):
                </Typography>
                <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
                  {tableQty ? (
                    <Button
                      size="small"
                      variant={quotedHours === tableQty ? 'contained' : 'outlined'}
                      onClick={() => {
                        setQuotedHours(tableQty);
                        setHoursResolved(true);
                      }}
                    >
                      Use {tableQty}
                    </Button>
                  ) : null}
                  {descTotal && descTotal !== tableQty ? (
                    <Button
                      size="small"
                      variant={quotedHours === descTotal ? 'contained' : 'outlined'}
                      onClick={() => {
                        setQuotedHours(descTotal);
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
              label="Team"
              value={selectedTeamId}
              onChange={(e) => setSelectedTeamId(e.target.value)}
              required
            >
              <MenuItem value="">Select team</MenuItem>
              {teams.map((t) => (
                <MenuItem key={t.id} value={t.id}>
                  {t.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="Customer"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              required
            >
              <MenuItem value="">Select customer</MenuItem>
              {customers.map((c) => (
                <MenuItem key={c.id} value={c.id}>
                  {c.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField label="Quote #" value={quoteNumber} onChange={(e) => setQuoteNumber(e.target.value)} />
            <TextField
              label="Customer Project # (ProTrack project number)"
              value={projectNumber}
              onChange={(e) => setProjectNumber(e.target.value)}
              required
            />
            <TextField
              label="Quoted amount"
              value={cost}
              onChange={(e) => setCost(e.target.value)}
              required
            />
            <TextField
              label="Commercial quoted hours (confirmed)"
              value={quotedHours}
              onChange={(e) => {
                setQuotedHours(e.target.value);
                if (hourDiscrepancy) setHoursResolved(true);
              }}
            />
            <TextField
              label="Currency"
              value={currencyCode}
              onChange={(e) => setCurrencyCode(e.target.value.toUpperCase())}
            />
            <TextField
              label="Quoted date"
              type="date"
              value={quotedDate}
              onChange={(e) => setQuotedDate(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
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
                  checked={createProjectLocal}
                  onChange={(e) => setCreateProjectLocal(e.target.checked)}
                />
              }
              label="Create project if missing (explicit confirmation)"
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

            {confirmBlockReason ? (
              <Typography variant="caption" color="warning.main">
                {confirmBlockReason}
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
