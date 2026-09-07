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
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { fetchCustomers } from '../../api/lookups';
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
};

type QuoteImportResult = {
  imported_count: number;
  items?: Array<Record<string, unknown>>;
};

type Props = {
  open: boolean;
  onClose: () => void;
  teamId: string;
  createProject?: boolean;
  onImported: (result: { imported_count: number; items?: Array<Record<string, unknown>> }) => void;
};

function fieldValue(fields: Record<string, FieldCandidate>, key: string): string {
  return fields[key]?.value ?? '';
}

export function QuotePdfImportDialog({
  open,
  onClose,
  teamId,
  createProject = true,
  onImported,
}: Props) {
  const { showSuccess, showError } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [extract, setExtract] = useState<ExtractResult | null>(null);
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

  const customersQuery = useQuery({
    queryKey: ['lookup-customers'],
    queryFn: fetchCustomers,
    enabled: open,
  });

  const reset = () => {
    setFile(null);
    setExtract(null);
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
      return (await apiClient.post<ExtractResult>('/finance/quotes/pdf/extract', form)).data;
    },
    onSuccess: (data) => {
      setExtract(data);
      setQuoteNumber(fieldValue(data.fields, 'external_quote_number'));
      setProjectNumber(fieldValue(data.fields, 'tool_number'));
      setCost(fieldValue(data.fields, 'quoted_revenue'));
      setQuotedHours(fieldValue(data.fields, 'quoted_hours'));
      setCurrencyCode(fieldValue(data.fields, 'currency_code') || 'USD');
      setQuotedDate(fieldValue(data.fields, 'quoted_date'));
      setNotes(fieldValue(data.fields, 'notes'));
      setCustomerId(data.suggested_customer_id || '');
      if (!data.text_extractable) {
        showError(data.warnings[0] || 'Unable to extract the document reliably.');
      }
    },
    onError: (error: unknown) =>
      showError(apiErrorMessage(error, 'Unable to extract the document reliably.')),
  });

  const confirmMutation = useMutation({
    mutationFn: async () => {
      if (!teamId) throw new Error('Select a team before importing.');
      if (!customerId) throw new Error('Select a customer.');
      if (!projectNumber.trim()) throw new Error('Project # is required.');
      if (!cost.trim()) throw new Error('Cost (quoted amount) is required.');
      const form = new FormData();
      form.append('team_id', teamId);
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
      showSuccess('Quote imported from PDF');
      handleClose();
      onImported(data);
    },
    onError: (error: unknown) =>
      showError(apiErrorMessage(error, 'Could not confirm quote import')),
  });

  const needsReview = useMemo(() => {
    if (!extract) return [];
    return Object.entries(extract.fields)
      .filter(([, field]) => field.needs_review)
      .map(([key]) => key);
  }, [extract]);

  const customers = useMemo(() => {
    const active = (customersQuery.data ?? []).filter((c) => c.is_active);
    const matchIds = new Set((extract?.customer_matches ?? []).map((m) => m.customer_id));
    if (matchIds.size === 0) return active;
    return [
      ...active.filter((c) => matchIds.has(c.id)),
      ...active.filter((c) => !matchIds.has(c.id)),
    ];
  }, [customersQuery.data, extract?.customer_matches]);

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="md">
      <DialogTitle>Import quote from PDF</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Optional convenience — review every field before saving. Manual quote entry remains available
          above. Scanned image PDFs need OCR (not enabled yet); use a text Prosohm QT PDF or enter
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
              disabled={!file || !teamId || extractMutation.isPending}
              onClick={() => file && extractMutation.mutate(file)}
            >
              Extract for review
            </Button>
            {!teamId ? (
              <Typography variant="caption" color="warning.main">
                Select a team in the form above before importing a quote PDF.
              </Typography>
            ) : null}
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
                Possible duplicate quote detected. Review existing records or check “Import anyway”.
              </Alert>
            ) : null}

            <TextField
              select
              label="Customer"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              required
              helperText={
                extract.fields.customer_name?.needs_review
                  ? `Extracted: ${fieldValue(extract.fields, 'customer_name') || '—'} (low confidence)`
                  : fieldValue(extract.fields, 'customer_name')
                    ? `Extracted: ${fieldValue(extract.fields, 'customer_name')}`
                    : undefined
              }
            >
              <MenuItem value="">Select customer</MenuItem>
              {customers.map((c) => (
                <MenuItem key={c.id} value={c.id}>
                  {c.name}
                </MenuItem>
              ))}
            </TextField>

            <TextField
              label="Quote #"
              value={quoteNumber}
              onChange={(e) => setQuoteNumber(e.target.value)}
              helperText={
                extract.fields.external_quote_number?.needs_review
                  ? `Low confidence (${extract.fields.external_quote_number.confidence ?? 0}%)`
                  : undefined
              }
            />
            <TextField
              label="Project #"
              value={projectNumber}
              onChange={(e) => setProjectNumber(e.target.value)}
              required
            />
            <TextField
              label="Cost (quoted amount)"
              value={cost}
              onChange={(e) => setCost(e.target.value)}
              required
            />
            <TextField
              label="Quoted hours"
              value={quotedHours}
              onChange={(e) => setQuotedHours(e.target.value)}
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

            {(extract.project_matches ?? []).length > 0 ? (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Matching projects
                </Typography>
                {(extract.project_matches ?? []).map((p) => (
                  <Typography key={p.project_id} variant="body2">
                    {p.tool_number}
                    {p.name ? ` · ${p.name}` : ''} ({Math.round(p.confidence)}%)
                  </Typography>
                ))}
              </Box>
            ) : null}

            <FormControlLabel
              control={
                <Checkbox
                  checked={createProjectLocal}
                  onChange={(e) => setCreateProjectLocal(e.target.checked)}
                />
              }
              label="Create project if missing"
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
                confirmMutation.isPending ||
                !teamId ||
                !customerId ||
                !projectNumber.trim() ||
                !cost.trim()
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
